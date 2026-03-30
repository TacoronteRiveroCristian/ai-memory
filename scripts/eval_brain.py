#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
LATENCY_ENDPOINTS = ("structured_search", "project_context", "plasticity_session", "graph_subgraph")
DETERMINISTIC_P95_THRESHOLDS_MS = {
    "structured_search": 250.0,
    "project_context": 2500.0,
    "plasticity_session": 1500.0,
    "graph_subgraph": 900.0,
}


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def compute_query_metrics(result_ids: list[str], expected_ids: list[str], forbidden_ids: list[str]) -> dict[str, Any]:
    first_rank = next((index + 1 for index, memory_id in enumerate(result_ids) if memory_id in expected_ids), None)
    hits = [memory_id for memory_id in result_ids if memory_id in expected_ids]
    forbidden_hits = [memory_id for memory_id in result_ids if memory_id in forbidden_ids]
    return {
        "hit_at_1": bool(result_ids and result_ids[0] in expected_ids),
        "hit_at_3": any(memory_id in expected_ids for memory_id in result_ids[:3]),
        "recall_at_k": round(len(hits) / max(1, len(expected_ids)), 4),
        "mrr": round(1.0 / first_rank, 4) if first_rank else 0.0,
        "first_relevant_rank": first_rank,
        "forbidden_hit_count": len(forbidden_hits),
        "forbidden_hits": forbidden_hits,
    }


def empty_latency_buckets() -> dict[str, list[float]]:
    return {endpoint: [] for endpoint in LATENCY_ENDPOINTS}


def record_latency(buckets: dict[str, list[float]], endpoint: str, latency_ms: float):
    buckets.setdefault(endpoint, []).append(round(float(latency_ms), 3))


def merge_latency_buckets(*items: dict[str, list[float]]) -> dict[str, list[float]]:
    merged = empty_latency_buckets()
    for item in items:
        for endpoint, values in item.items():
            merged.setdefault(endpoint, []).extend(values)
    return merged


def summarize_latency(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "p50_ms": round(statistics.median(values), 3) if values else 0.0,
        "p95_ms": round(percentile(values, 0.95), 3),
    }


def resolve_p95_threshold(mode: str, explicit_value: Optional[float], endpoint: str) -> Optional[float]:
    if explicit_value is not None:
        return explicit_value
    if mode == "deterministic":
        return DETERMINISTIC_P95_THRESHOLDS_MS[endpoint]
    return None


class EvalClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    def close(self):
        self.client.close()

    def get(self, path: str, **kwargs):
        response = self.client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any]):
        response = self.client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    def health(self):
        return self.get("/health")

    def create_memory(self, payload: dict[str, Any]):
        return self.post("/api/memories", payload)

    def structured_search(self, payload: dict[str, Any]):
        start = time.perf_counter()
        response = self.post("/api/search/structured", payload)
        latency_ms = (time.perf_counter() - start) * 1000.0
        response["latency_ms"] = round(latency_ms, 3)
        return response

    def bridge_projects(self, payload: dict[str, Any]):
        return self.post("/api/project-bridges", payload)

    def list_bridges(self, project: str):
        return self.get("/api/project-bridges", params={"project": project})

    def project_context(self, project_name: str, include_related: bool = True):
        start = time.perf_counter()
        response = self.get(
            "/api/project-context",
            params={"project_name": project_name, "include_related": str(include_related).lower()},
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        response["latency_ms"] = round(latency_ms, 3)
        return response

    def relations(self, memory_id: str):
        return self.get("/api/relations", params={"memory_id": memory_id})

    def link_memories(self, payload: dict[str, Any]):
        return self.post("/api/relations", payload)

    def apply_session_plasticity(self, payload: dict[str, Any]):
        start = time.perf_counter()
        response = self.post("/api/plasticity/session", payload)
        latency_ms = (time.perf_counter() - start) * 1000.0
        response["latency_ms"] = round(latency_ms, 3)
        return response

    def graph_subgraph(self, payload: dict[str, Any]):
        start = time.perf_counter()
        response = self.post("/api/graph/subgraph", payload)
        latency_ms = (time.perf_counter() - start) * 1000.0
        response["latency_ms"] = round(latency_ms, 3)
        return response

    def set_test_clock(self, when: Optional[str]):
        return self.post("/api/test/clock", {"now": when})


def resolve_project_name(base_name: str, run_id: str) -> str:
    return f"{base_name}-{run_id}"


def find_relation(relations: list[dict[str, Any]], other_memory_id: str) -> Optional[dict[str, Any]]:
    for relation in relations:
        if relation.get("other_memory_id") == other_memory_id:
            return relation
    return None


def seed_memories(client: EvalClient, memories: list[dict[str, Any]], run_id: str) -> tuple[dict[str, str], dict[str, str]]:
    aliases: dict[str, str] = {}
    project_map: dict[str, str] = {}
    for item in memories:
        project_base = item["project"] if "project" in item else item.get("project_base", "")
        actual_project = resolve_project_name(project_base, run_id)
        project_map[project_base] = actual_project
        created = client.create_memory(
            {
                "content": item["content"],
                "project": actual_project,
                "memory_type": item.get("memory_type", "general"),
                "tags": item.get("tags", ""),
                "importance": item.get("importance", 0.8),
                "agent_id": "eval-runner",
            }
        )
        aliases[item["alias"]] = created["memory_id"]
    return aliases, project_map


def merge_project_maps(*maps: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for mapping in maps:
        merged.update(mapping)
    return merged


def evaluate_retrieval_family(
    client: EvalClient, dataset: list[dict[str, Any]], run_id: str
) -> tuple[list[dict[str, Any]], dict[str, list[float]], bool]:
    scenario_results: list[dict[str, Any]] = []
    latencies = empty_latency_buckets()
    all_passed = True

    for scenario in dataset:
        project_base = scenario["project"]
        seed_payload = []
        for item in scenario["seed_memories"]:
            seeded = dict(item)
            seeded["project"] = project_base
            seed_payload.append(seeded)
        alias_map, project_map = seed_memories(client, seed_payload, run_id)
        query_results: list[dict[str, Any]] = []
        scenario_passed = True

        for query in scenario["queries"]:
            payload = {
                "query": query["query"],
                "project": project_map[query["project"]],
                "scope": query.get("scope", "project"),
                "tags": query.get("tags", []),
                "limit": query.get("limit", 5),
                "register_access": False,
            }
            response = client.structured_search(payload)
            record_latency(latencies, "structured_search", response["latency_ms"])
            result_ids = [item["memory_id"] for item in response["results"]]
            metrics = compute_query_metrics(
                result_ids=result_ids,
                expected_ids=[alias_map[alias] for alias in query.get("expected_hits", [])],
                forbidden_ids=[alias_map[alias] for alias in query.get("forbidden_hits", [])],
            )
            relation_ok = True
            relation_types = []
            expected_relation_types = query.get("expected_relation_types", [])
            if expected_relation_types and len(query.get("expected_hits", [])) >= 2:
                left_alias, right_alias = query["expected_hits"][:2]
                relations = client.relations(alias_map[left_alias])["relations"]
                relation = find_relation(relations, alias_map[right_alias])
                relation_types = [relation["relation_type"]] if relation else []
                relation_ok = bool(relation and relation["relation_type"] in expected_relation_types)
            query_passed = metrics["hit_at_3"] and metrics["forbidden_hit_count"] == 0 and relation_ok
            scenario_passed = scenario_passed and query_passed
            query_results.append(
                {
                    "query": query["query"],
                    "response_ids": result_ids,
                    "latency_ms": response["latency_ms"],
                    "metrics": metrics,
                    "relation_types": relation_types,
                    "passed": query_passed,
                }
            )

        scenario_results.append({"name": scenario["name"], "passed": scenario_passed, "queries": query_results})
        all_passed = all_passed and scenario_passed

    return scenario_results, latencies, all_passed


def evaluate_bridge_family(
    client: EvalClient, dataset: list[dict[str, Any]], run_id: str
) -> tuple[list[dict[str, Any]], dict[str, list[float]], bool]:
    scenario_results: list[dict[str, Any]] = []
    latencies = empty_latency_buckets()
    all_passed = True

    for scenario in dataset:
        pre_aliases, pre_projects = seed_memories(client, scenario["pre_bridge_memories"], run_id)
        query_config = scenario["query"]

        blocked = client.structured_search(
            {
                "query": query_config["query"],
                "project": resolve_project_name(query_config["project"], run_id),
                "scope": query_config["scope"],
                "limit": query_config["limit"],
                "register_access": False,
            }
        )
        record_latency(latencies, "structured_search", blocked["latency_ms"])
        blocked_projects = [item["project"] for item in blocked["results"]]
        forbidden_before = {pre_aliases[alias] for alias in query_config.get("forbidden_hits_before_bridge", []) if alias in pre_aliases}
        blocked_metrics = compute_query_metrics(
            result_ids=[item["memory_id"] for item in blocked["results"]],
            expected_ids=[],
            forbidden_ids=list(forbidden_before),
        )

        bridge_payload = dict(scenario["bridge"])
        bridge_payload["project"] = resolve_project_name(bridge_payload["project"], run_id)
        bridge_payload["related_project"] = resolve_project_name(bridge_payload["related_project"], run_id)
        client.bridge_projects(bridge_payload)

        post_aliases, post_projects = seed_memories(client, scenario["post_bridge_memories"], run_id)
        aliases = {**pre_aliases, **post_aliases}
        projects = merge_project_maps(pre_projects, post_projects)

        allowed = client.structured_search(
            {
                "query": query_config["query"],
                "project": resolve_project_name(query_config["project"], run_id),
                "scope": query_config["scope"],
                "limit": query_config["limit"],
                "register_access": False,
            }
        )
        record_latency(latencies, "structured_search", allowed["latency_ms"])
        allowed_metrics = compute_query_metrics(
            result_ids=[item["memory_id"] for item in allowed["results"]],
            expected_ids=[aliases[alias] for alias in query_config.get("expected_hits", [])],
            forbidden_ids=[],
        )
        context = client.project_context(resolve_project_name(scenario["project_a"], run_id), include_related=True)
        record_latency(latencies, "project_context", context["latency_ms"])
        context_ok = "RELATED IDEAS" in context["result"] and resolve_project_name(scenario["project_b"], run_id) in context["result"]

        scenario_passed = blocked_metrics["forbidden_hit_count"] == 0 and allowed_metrics["hit_at_3"] and context_ok
        scenario_results.append(
            {
                "name": scenario["name"],
                "passed": scenario_passed,
                "blocked_projects": blocked_projects,
                "blocked_search_latency_ms": blocked["latency_ms"],
                "blocked_metrics": blocked_metrics,
                "allowed_search_latency_ms": allowed["latency_ms"],
                "allowed_metrics": allowed_metrics,
                "project_context_latency_ms": context["latency_ms"],
                "context_has_related": context_ok,
                "bridges": client.list_bridges(resolve_project_name(scenario["project_a"], run_id))["bridges"],
                "projects": projects,
            }
        )
        all_passed = all_passed and scenario_passed

    return scenario_results, latencies, all_passed


def evaluate_plasticity_family(
    client: EvalClient, dataset: list[dict[str, Any]], run_id: str, mode: str
) -> tuple[list[dict[str, Any]], dict[str, list[float]], bool]:
    scenario_results: list[dict[str, Any]] = []
    latencies = empty_latency_buckets()
    all_passed = True

    for scenario in dataset:
        project = resolve_project_name(scenario["project"], run_id)
        if mode == "deterministic":
            client.set_test_clock(scenario["clock_start"])
        aliases, _ = seed_memories(
            client,
            [{**item, "project": scenario["project"]} for item in scenario["seed_memories"]],
            run_id,
        )
        manual_payload = dict(scenario["manual_relation"])
        manual_payload["source_memory_id"] = aliases[manual_payload.pop("source")]
        manual_payload["target_memory_id"] = aliases[manual_payload.pop("target")]
        client.link_memories(manual_payload)

        query_payload = dict(scenario["reinforcement_query"])
        query_payload["project"] = project
        query_payload["register_access"] = False
        baseline = client.structured_search(query_payload)
        record_latency(latencies, "structured_search", baseline["latency_ms"])
        baseline_ids = [item["memory_id"] for item in baseline["results"]]
        baseline_rank = next((index + 1 for index, memory_id in enumerate(baseline_ids) if memory_id == aliases["auto_b"]), None)
        initial_relation = find_relation(client.relations(aliases["auto_a"])["relations"], aliases["auto_b"])
        initial_weight = float(initial_relation["weight"]) if initial_relation else 0.0

        for _ in range(int(scenario.get("reinforcement_runs", 1))):
            reinforced = client.structured_search({**query_payload, "register_access": True})
            record_latency(latencies, "structured_search", reinforced["latency_ms"])

        reinforced_relation = find_relation(client.relations(aliases["auto_a"])["relations"], aliases["auto_b"])
        reinforced_weight = float(reinforced_relation["weight"]) if reinforced_relation else 0.0
        reinforced_rank_payload = client.structured_search(query_payload)
        record_latency(latencies, "structured_search", reinforced_rank_payload["latency_ms"])
        reinforced_rank_ids = [item["memory_id"] for item in reinforced_rank_payload["results"]]
        reinforced_rank = next(
            (index + 1 for index, memory_id in enumerate(reinforced_rank_ids) if memory_id == aliases["auto_b"]),
            None,
        )

        decayed_weight = reinforced_weight
        decayed_rank = reinforced_rank
        decayed_count = 0
        if mode == "deterministic":
            client.set_test_clock(scenario["decay_clock"])
            plasticity_payload = {
                "project": project,
                "agent_id": "eval-runner",
                "session_id": f"plasticity-{run_id}",
                "goal": scenario["plasticity_session"]["goal"],
                "outcome": scenario["plasticity_session"]["outcome"],
                "summary": scenario["plasticity_session"]["summary"],
                "changes": [],
                "decisions": [],
                "errors": [],
                "follow_ups": [],
                "tags": scenario["plasticity_session"].get("tags", []),
            }
            plasticity = client.apply_session_plasticity(plasticity_payload)
            record_latency(latencies, "plasticity_session", plasticity["latency_ms"])
            decayed_count = int(plasticity.get("decayed_relations", 0))
            decayed_relation = find_relation(client.relations(aliases["auto_a"])["relations"], aliases["auto_b"])
            decayed_weight = float(decayed_relation["weight"]) if decayed_relation else 0.0
            decayed_rank_payload = client.structured_search(query_payload)
            record_latency(latencies, "structured_search", decayed_rank_payload["latency_ms"])
            decayed_rank_ids = [item["memory_id"] for item in decayed_rank_payload["results"]]
            decayed_rank = next(
                (index + 1 for index, memory_id in enumerate(decayed_rank_ids) if memory_id == aliases["auto_b"]),
                None,
            )

        manual_relation = find_relation(client.relations(aliases["manual_a"])["relations"], aliases["manual_b"])
        scenario_passed = (
            reinforced_weight >= initial_weight
            and (mode != "deterministic" or decayed_weight < reinforced_weight)
            and manual_relation is not None
            and manual_relation.get("origin") == "manual"
            and bool(manual_relation.get("active"))
        )
        scenario_results.append(
            {
                "name": scenario["name"],
                "passed": scenario_passed,
                "initial_relation_weight": initial_weight,
                "reinforced_relation_weight": reinforced_weight,
                "decayed_relation_weight": decayed_weight,
                "baseline_search_latency_ms": baseline["latency_ms"],
                "initial_rank": baseline_rank,
                "reinforced_rank_search_latency_ms": reinforced_rank_payload["latency_ms"],
                "reinforced_rank": reinforced_rank,
                "plasticity_session_latency_ms": plasticity["latency_ms"] if mode == "deterministic" else 0.0,
                "decayed_rank_search_latency_ms": decayed_rank_payload["latency_ms"] if mode == "deterministic" else 0.0,
                "decayed_rank": decayed_rank,
                "rank_delta_after_reinforcement": (baseline_rank or 999) - (reinforced_rank or 999),
                "rank_delta_after_decay": (reinforced_rank or 999) - (decayed_rank or 999),
                "decayed_relations": decayed_count,
                "manual_relation": manual_relation,
            }
        )
        all_passed = all_passed and scenario_passed

    return scenario_results, latencies, all_passed


def evaluate_graph_family(
    client: EvalClient, dataset: list[dict[str, Any]], run_id: str
) -> tuple[list[dict[str, Any]], dict[str, list[float]], bool]:
    scenario_results: list[dict[str, Any]] = []
    latencies = empty_latency_buckets()
    all_passed = True

    for scenario in dataset:
        project = resolve_project_name(scenario["project"], run_id)
        alias_map, _ = seed_memories(
            client,
            [{**item, "project": scenario["project"]} for item in scenario["seed_memories"]],
            run_id,
        )

        request = dict(scenario["request"])
        request["project"] = project
        if "center_alias" in request:
            request["center_memory_id"] = alias_map[request.pop("center_alias")]
        response = client.graph_subgraph(request)
        record_latency(latencies, "graph_subgraph", response["latency_ms"])

        node_ids = {item["memory_id"] for item in response["nodes"]}
        edge_ok = all(
            edge["source_memory_id"] in node_ids and edge["target_memory_id"] in node_ids
            for edge in response["edges"]
        )
        expected_hits = {alias_map[alias] for alias in scenario.get("expected_hits", [])}
        scenario_passed = (
            response["summary"]["node_count"] <= int(request["node_limit"])
            and response["summary"]["edge_count"] <= int(request["edge_limit"])
            and expected_hits.issubset(node_ids)
            and edge_ok
        )
        scenario_results.append(
            {
                "name": scenario["name"],
                "passed": scenario_passed,
                "latency_ms": response["latency_ms"],
                "summary": response["summary"],
                "node_ids": sorted(node_ids),
            }
        )
        all_passed = all_passed and scenario_passed

    return scenario_results, latencies, all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalua el cerebro de memoria con datasets semilla.")
    parser.add_argument("--mode", choices=["deterministic", "live"], default="deterministic")
    parser.add_argument("--dataset", default=str(ROOT / "evals" / "brain_dataset.json"))
    parser.add_argument("--output", default="")
    parser.add_argument("--run-id", default=f"eval-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--structured-search-p95-threshold-ms", type=float, default=None)
    parser.add_argument("--project-context-p95-threshold-ms", type=float, default=None)
    parser.add_argument("--plasticity-session-p95-threshold-ms", type=float, default=None)
    parser.add_argument("--graph-subgraph-p95-threshold-ms", type=float, default=None)
    args = parser.parse_args()

    base_url = os.getenv("AI_MEMORY_BASE_URL", "http://127.0.0.1:8050")
    api_key = os.getenv("MEMORY_API_KEY", "")
    if not api_key:
        print("MEMORY_API_KEY no configurada.", file=sys.stderr)
        return 2

    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    client = EvalClient(base_url, api_key)
    try:
        health = client.health()
        if args.mode == "deterministic" and not health.get("test_mode"):
            print("El modo deterministic requiere AI_MEMORY_TEST_MODE=true en el API server.", file=sys.stderr)
            return 2

        retrieval_results, retrieval_latencies, retrieval_passed = evaluate_retrieval_family(
            client, dataset.get("retrieval", []), args.run_id
        )
        bridge_results, bridge_latencies, bridge_passed = evaluate_bridge_family(
            client, dataset.get("bridges", []), args.run_id
        )
        plasticity_results, plasticity_latencies, plasticity_passed = evaluate_plasticity_family(
            client, dataset.get("plasticity", []), args.run_id, args.mode
        )
        graph_results, graph_latencies, graph_passed = evaluate_graph_family(
            client, dataset.get("graph", []), args.run_id
        )

        all_latencies = merge_latency_buckets(retrieval_latencies, bridge_latencies, plasticity_latencies, graph_latencies)
        latency_summary = {endpoint: summarize_latency(all_latencies.get(endpoint, [])) for endpoint in LATENCY_ENDPOINTS}
        thresholds = {
            "structured_search": resolve_p95_threshold(args.mode, args.structured_search_p95_threshold_ms, "structured_search"),
            "project_context": resolve_p95_threshold(args.mode, args.project_context_p95_threshold_ms, "project_context"),
            "plasticity_session": resolve_p95_threshold(
                args.mode, args.plasticity_session_p95_threshold_ms, "plasticity_session"
            ),
            "graph_subgraph": resolve_p95_threshold(args.mode, args.graph_subgraph_p95_threshold_ms, "graph_subgraph"),
        }
        thresholds_passed = {
            endpoint: (
                True
                if thresholds[endpoint] is None
                else latency_summary[endpoint]["p95_ms"] <= float(thresholds[endpoint])
            )
            for endpoint in LATENCY_ENDPOINTS
        }
        aggregate = {
            "search_latency_p50_ms": latency_summary["structured_search"]["p50_ms"],
            "search_latency_p95_ms": latency_summary["structured_search"]["p95_ms"],
            "project_context_latency_p50_ms": latency_summary["project_context"]["p50_ms"],
            "project_context_latency_p95_ms": latency_summary["project_context"]["p95_ms"],
            "plasticity_session_latency_p50_ms": latency_summary["plasticity_session"]["p50_ms"],
            "plasticity_session_latency_p95_ms": latency_summary["plasticity_session"]["p95_ms"],
            "graph_subgraph_latency_p50_ms": latency_summary["graph_subgraph"]["p50_ms"],
            "graph_subgraph_latency_p95_ms": latency_summary["graph_subgraph"]["p95_ms"],
            "latency_ms": latency_summary,
            "thresholds_ms": thresholds,
            "thresholds_passed": thresholds_passed,
            "family_passed": {
                "retrieval": retrieval_passed,
                "bridges": bridge_passed,
                "plasticity": plasticity_passed,
                "graph": graph_passed,
            },
        }
        result = {
            "mode": args.mode,
            "run_id": args.run_id,
            "base_url": base_url,
            "health": health,
            "aggregate": aggregate,
            "retrieval": retrieval_results,
            "bridges": bridge_results,
            "plasticity": plasticity_results,
            "graph": graph_results,
        }

        output_path = Path(args.output) if args.output else ROOT / "evals" / "results" / f"brain-eval-{args.run_id}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        print(json.dumps({"output": str(output_path), "aggregate": aggregate}, ensure_ascii=False, indent=2))
        threshold_gate = all(thresholds_passed.values())
        return 0 if retrieval_passed and bridge_passed and plasticity_passed and graph_passed and threshold_gate else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
