#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import httpx
from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from demo_brain_catalog import build_demo_catalog


load_dotenv(PROJECT_DIR / ".env")


def parse_result_fields(result: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in str(result).split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key.strip()] = value.strip().strip("'\"")
    return fields


class DemoBrainClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout_seconds,
        )

    def close(self):
        self._client.close()

    def get(self, path: str, **kwargs):
        response = self._client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any], *, expected_statuses: Iterable[int] | None = None):
        response = self._client.post(path, json=payload)
        allowed = set(expected_statuses or {200})
        if response.status_code not in allowed:
            response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def health(self):
        return self.get("/health")

    def ready(self):
        return self.get("/ready")

    def create_memory(self, **payload):
        return self.post("/api/memories", payload)

    def memory_detail(self, memory_id: str):
        return self.get(f"/api/memories/{memory_id}")

    def graph_metrics(self, project: str | None = None):
        params = {"project": project} if project else {}
        return self.get("/api/graph/metrics", params=params)

    def graph_facets(self, project: str | None = None):
        params = {"project": project} if project else {}
        return self.get("/api/graph/facets", params=params)

    def structured_search(self, **payload):
        return self.post("/api/search/structured", payload)

    def link_memories(self, **payload):
        return self.post("/api/relations", payload)

    def relations(self, memory_id: str):
        return self.get("/api/relations", params={"memory_id": memory_id})

    def bridge_projects(self, **payload):
        return self.post("/api/project-bridges", payload)

    def list_bridges(self, project: str):
        return self.get("/api/project-bridges", params={"project": project})

    def store_decision(self, **payload):
        return self.post("/api/decisions", payload)

    def store_error(self, **payload):
        return self.post("/api/errors", payload)

    def record_session(self, **payload):
        return self.post("/api/sessions", payload, expected_statuses={200, 409})

    def apply_session_plasticity(self, **payload):
        return self.post("/api/plasticity/session", payload)

    def run_reflection(self):
        return self.post("/api/reflections/run", {})

    def reflection_status(self):
        return self.get("/api/reflections/status")

    def set_test_clock(self, when: str | None):
        return self.post("/api/test/clock", {"now": when}, expected_statuses={200, 404})


def _memory_id_from_response(response: dict[str, Any]) -> str:
    response_id = response.get("memory_id")
    if isinstance(response_id, str) and response_id:
        return response_id
    fields = parse_result_fields(str(response.get("result", "")))
    existing = fields.get("existing")
    if existing:
        return existing
    memory_id = fields.get("memory_id")
    if memory_id:
        return memory_id
    raise RuntimeError(f"No pude extraer memory_id de la respuesta: {response}")


def _csv_tags(tags: list[str]) -> str:
    return ",".join(tags)


def _filter_catalog(catalog: dict[str, Any], project_slugs: list[str] | None) -> dict[str, Any]:
    if not project_slugs:
        return catalog
    wanted = set(project_slugs)
    projects = [project for project in catalog["projects"] if project["slug"] in wanted]
    bridges = [
        bridge
        for bridge in catalog["bridges"]
        if any(
            project["project"] == bridge["project"] or project["project"] == bridge["related_project"]
            for project in projects
        )
        and bridge["project"] in {project["project"] for project in projects}
        and bridge["related_project"] in {project["project"] for project in projects}
    ]
    manual_relations = [
        relation
        for relation in catalog["manual_relations"]
        if relation["source_project"] in {project["project"] for project in projects}
        and relation["target_project"] in {project["project"] for project in projects}
    ]
    return {
        **catalog,
        "projects": projects,
        "bridges": bridges,
        "manual_relations": manual_relations,
    }


def seed_demo_brain(
    client: Any,
    *,
    namespace: str = "",
    deterministic: bool = False,
    with_plasticity: bool = False,
    with_reflection: bool = False,
    project_slugs: list[str] | None = None,
    create_bridges: bool = True,
    create_manual_relations: bool = True,
) -> dict[str, Any]:
    catalog = _filter_catalog(build_demo_catalog(namespace), project_slugs)
    if deterministic:
        try:
            client.set_test_clock(catalog["test_now"])
        except Exception:
            pass

    created_memory_ids: dict[str, dict[str, str]] = {}
    sessions_by_project: dict[str, dict[str, Any]] = {}
    project_names_by_slug: dict[str, str] = {}
    decision_results: dict[str, Any] = {}
    error_results: dict[str, Any] = {}
    session_results: dict[str, Any] = {}
    plasticity_results: dict[str, Any] = {}
    reflection_result: dict[str, Any] | None = None

    for project in catalog["projects"]:
        project_name = project["project"]
        project_names_by_slug[project["slug"]] = project_name
        created_memory_ids[project_name] = {}

        for memory in project["memories"]:
            response = client.create_memory(
                content=memory["content"],
                project=project_name,
                memory_type=memory["memory_type"],
                tags=_csv_tags(memory["tags"]),
                importance=memory["importance"],
                agent_id="demo-seed",
                skip_similar=True,
                dedupe_threshold=0.97,
            )
            created_memory_ids[project_name][memory["key"]] = _memory_id_from_response(response)

        decision_payload = {
            **project["decision"],
            "project": project_name,
            "tags": _csv_tags(project["decision"]["tags"]),
        }
        error_payload = {
            **project["error"],
            "project": project_name,
            "tags": _csv_tags(project["error"]["tags"]),
        }
        session_payload = {
            **project["session"],
            "project": project_name,
        }
        sessions_by_project[project_name] = session_payload
        decision_results[project_name] = client.store_decision(**decision_payload)
        error_results[project_name] = client.store_error(**error_payload)

        session_response = client.record_session(**session_payload)
        if session_response.get("detail", {}).get("message") == "duplicate_session":
            session_results[project_name] = {
                "result": "DUPLICATE",
                "session_id": session_payload["session_id"],
                "checksum": session_response["detail"]["checksum"],
                "working_memory_ingested": False,
            }
        else:
            session_results[project_name] = session_response

    bridge_results: list[dict[str, Any]] = []
    if create_bridges:
        for bridge in catalog["bridges"]:
            bridge_results.append(client.bridge_projects(**bridge))

    relation_results: list[dict[str, Any]] = []
    if create_manual_relations:
        for relation in catalog["manual_relations"]:
            source_memory_id = created_memory_ids[relation["source_project"]][relation["source_key"]]
            target_memory_id = created_memory_ids[relation["target_project"]][relation["target_key"]]
            relation_results.append(
                client.link_memories(
                    source_memory_id=source_memory_id,
                    target_memory_id=target_memory_id,
                    relation_type=relation["relation_type"],
                    reason=relation["reason"],
                    weight=relation["weight"],
                )
            )

    if with_plasticity:
        for project_name, session_payload in sessions_by_project.items():
            plasticity_results[project_name] = client.apply_session_plasticity(**session_payload)

    if with_reflection:
        reflection_result = client.run_reflection()
        run_id = reflection_result.get("run_id")
        if run_id:
            deadline = time.time() + 120.0
            while time.time() < deadline:
                status = client.reflection_status()
                last_run = status.get("last_run") or {}
                if last_run.get("id") == run_id and last_run.get("status") in {"completed", "failed"}:
                    reflection_result["status_detail"] = status
                    break
                time.sleep(5)

    anchor_memory_ids = {
        project_name: memory_ids["shared-methodology"]
        for project_name, memory_ids in created_memory_ids.items()
    }

    return {
        "namespace": catalog["namespace"],
        "project_names": [project["project"] for project in catalog["projects"]],
        "project_names_by_slug": project_names_by_slug,
        "shared_method_query": catalog["shared_method_query"],
        "anchor_memory_ids": anchor_memory_ids,
        "created_memory_ids": created_memory_ids,
        "bridge_results": bridge_results,
        "relation_results": relation_results,
        "decision_results": decision_results,
        "error_results": error_results,
        "session_results": session_results,
        "session_payloads": sessions_by_project,
        "plasticity_results": plasticity_results,
        "reflection_result": reflection_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Puebla un cerebro demo multi-proyecto.")
    parser.add_argument("--base-url", default=os.getenv("AI_MEMORY_BASE_URL", "http://127.0.0.1:8050"))
    parser.add_argument("--api-key", default=os.getenv("MEMORY_API_KEY", ""))
    parser.add_argument("--namespace", default="")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--with-plasticity", action="store_true")
    parser.add_argument("--with-reflection", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    if not args.api_key:
        print("Falta MEMORY_API_KEY o --api-key.", file=sys.stderr)
        return 1

    client = DemoBrainClient(args.base_url, args.api_key, timeout_seconds=args.timeout_seconds)
    try:
        ready = client.ready()
        if not ready.get("ready"):
            print(f"Stack no lista en {args.base_url}: {ready}", file=sys.stderr)
            return 1
        result = seed_demo_brain(
            client,
            namespace=args.namespace,
            deterministic=args.deterministic,
            with_plasticity=args.with_plasticity,
            with_reflection=args.with_reflection,
        )
    finally:
        client.close()

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("Demo brain sembrado correctamente.")
    print(f"namespace={result['namespace'] or 'persistente'}")
    for project_name in result["project_names"]:
        anchor = result["anchor_memory_ids"][project_name]
        print(f"- {project_name} anchor={anchor}")
    print(f"bridges={len(result['bridge_results'])} manual_relations={len(result['relation_results'])}")
    if result["plasticity_results"]:
        print("plasticity=aplicada")
    if result["reflection_result"]:
        print(f"reflection={result['reflection_result']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
