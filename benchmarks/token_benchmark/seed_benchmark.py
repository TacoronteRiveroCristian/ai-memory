#!/usr/bin/env python3
"""Seed the benchmark dataset (15 projects, ~375 memories) into the AI Memory stack."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent

# Reuse DemoBrainClient and seeding logic from the main scripts
SCRIPTS_DIR = PROJECT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from seed_demo_brain import DemoBrainClient, seed_demo_brain, _filter_catalog  # noqa: E402

# Import benchmark catalog instead of demo catalog
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from catalog import build_benchmark_catalog  # noqa: E402

load_dotenv(PROJECT_DIR / ".env")


def seed_benchmark_brain(
    client: DemoBrainClient,
    *,
    namespace: str = "",
    deterministic: bool = False,
    with_plasticity: bool = False,
    with_reflection: bool = False,
    project_slugs: list[str] | None = None,
) -> dict[str, Any]:
    """Seed the benchmark catalog using the same logic as seed_demo_brain."""
    from copy import deepcopy
    from typing import Any

    catalog = build_benchmark_catalog(namespace)

    # Apply project filter if specified
    if project_slugs:
        catalog = _filter_catalog(catalog, project_slugs)

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

    for project in catalog["projects"]:
        project_name = project["project"]
        project_names_by_slug[project["slug"]] = project_name
        created_memory_ids[project_name] = {}

        print(f"  Seeding {project_name} ({len(project['memories'])} memories)...")
        for memory in project["memories"]:
            response = client.create_memory(
                content=memory["content"],
                project=project_name,
                memory_type=memory["memory_type"],
                tags=",".join(memory["tags"]),
                importance=memory["importance"],
                agent_id="bench-seed",
                skip_similar=True,
                dedupe_threshold=0.97,
            )
            memory_id = response.get("memory_id")
            if not memory_id:
                from seed_demo_brain import parse_result_fields
                fields = parse_result_fields(str(response.get("result", "")))
                memory_id = fields.get("existing") or fields.get("memory_id")
            if memory_id:
                created_memory_ids[project_name][memory["key"]] = memory_id

        # Store decision
        decision_payload = {
            **project["decision"],
            "project": project_name,
            "tags": ",".join(project["decision"]["tags"]),
        }
        decision_results[project_name] = client.store_decision(**decision_payload)

        # Store error
        error_payload = {
            **project["error"],
            "project": project_name,
            "tags": ",".join(project["error"]["tags"]),
        }
        error_results[project_name] = client.store_error(**error_payload)

        # Record session
        session_payload = {
            **project["session"],
            "project": project_name,
        }
        sessions_by_project[project_name] = session_payload
        session_response = client.record_session(**session_payload)
        session_results[project_name] = session_response

    # Create bridges
    bridge_results = []
    for bridge in catalog["bridges"]:
        bridge_results.append(client.bridge_projects(**bridge))
    print(f"  Created {len(bridge_results)} bridges.")

    # Create manual relations (tolerate 400 for duplicates)
    relation_results = []
    relation_errors = 0
    for relation in catalog["manual_relations"]:
        source_id = created_memory_ids.get(relation["source_project"], {}).get(relation["source_key"])
        target_id = created_memory_ids.get(relation["target_project"], {}).get(relation["target_key"])
        if source_id and target_id:
            try:
                relation_results.append(
                    client.link_memories(
                        source_memory_id=source_id,
                        target_memory_id=target_id,
                        relation_type=relation["relation_type"],
                        reason=relation["reason"],
                        weight=relation["weight"],
                    )
                )
            except Exception:
                relation_errors += 1
    print(f"  Created {len(relation_results)} manual relations ({relation_errors} skipped/duplicate).")

    return {
        "namespace": catalog["namespace"],
        "project_names": [p["project"] for p in catalog["projects"]],
        "project_names_by_slug": project_names_by_slug,
        "created_memory_ids": created_memory_ids,
        "bridge_results": bridge_results,
        "relation_results": relation_results,
        "decision_results": decision_results,
        "error_results": error_results,
        "session_results": session_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed benchmark dataset (15 projects, ~375 memories).")
    parser.add_argument("--base-url", default=os.getenv("AI_MEMORY_BASE_URL", "http://127.0.0.1:8050"))
    parser.add_argument("--api-key", default=os.getenv("MEMORY_API_KEY", ""))
    parser.add_argument("--namespace", default="")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--with-plasticity", action="store_true")
    parser.add_argument("--with-reflection", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    if not args.api_key:
        print("Missing MEMORY_API_KEY or --api-key.", file=sys.stderr)
        return 1

    client = DemoBrainClient(args.base_url, args.api_key, timeout_seconds=args.timeout_seconds)
    try:
        ready = client.ready()
        if not ready.get("ready"):
            print(f"Stack not ready at {args.base_url}: {ready}", file=sys.stderr)
            return 1

        print("Seeding benchmark dataset...")
        result = seed_benchmark_brain(
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

    print("\nBenchmark dataset seeded successfully.")
    print(f"  Projects: {len(result['project_names'])}")
    total_memories = sum(len(mids) for mids in result["created_memory_ids"].values())
    print(f"  Memories: {total_memories}")
    print(f"  Bridges: {len(result['bridge_results'])}")
    print(f"  Relations: {len(result['relation_results'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
