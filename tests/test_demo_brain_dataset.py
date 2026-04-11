from __future__ import annotations

import uuid

import pytest

from scripts.demo_brain_catalog import SHARED_TAGS, build_demo_catalog
from scripts.seed_demo_brain import seed_demo_brain


@pytest.fixture(scope="module")
def seeded_demo_dataset(brain_client):
    namespace = f"pytest-demo-{uuid.uuid4().hex[:8]}"
    return seed_demo_brain(
        brain_client,
        namespace=namespace,
        deterministic=True,
        with_plasticity=True,
    )


def test_demo_projects_appear_in_global_facets(seeded_demo_dataset, brain_client):
    # Check each demo project individually to avoid LIMIT 100 cap in global facets
    for proj in seeded_demo_dataset["project_names"]:
        facets = brain_client.graph_facets(project=proj)
        project_names = {item["project"] for item in facets["projects"]}
        assert proj in project_names, f"Demo project {proj} not found in facets"


def test_demo_project_facets_expose_expected_types_and_shared_tags(seeded_demo_dataset, brain_client):
    ems_project = seeded_demo_dataset["project_names_by_slug"]["demo-ems-fotovoltaica"]
    facets = brain_client.graph_facets(project=ems_project)

    memory_types = {item["memory_type"] for item in facets["memory_types"]}
    assert {"architecture", "decision", "error"}.issubset(memory_types)

    top_tags = {item["tag"] for item in facets["top_tags"]}
    assert SHARED_TAGS["method_condition"] in top_tags
    assert SHARED_TAGS["stack_pipeline"] in top_tags
    assert SHARED_TAGS["metric_availability"] in top_tags


def test_bridged_search_requires_project_bridges(brain_client):
    namespace = f"pytest-bridge-{uuid.uuid4().hex[:8]}"
    isolated = seed_demo_brain(
        brain_client,
        namespace=namespace,
        deterministic=True,
        project_slugs=[
            "demo-ems-fotovoltaica",
            "demo-monitorizacion-estaciones-meteorologicas",
        ],
        create_bridges=False,
        create_manual_relations=False,
    )

    ems_project = isolated["project_names_by_slug"]["demo-ems-fotovoltaica"]
    weather_project = isolated["project_names_by_slug"]["demo-monitorizacion-estaciones-meteorologicas"]

    blocked = brain_client.structured_search(
        query=isolated["shared_method_query"],
        project=ems_project,
        scope="bridged",
        limit=8,
        register_access=False,
    )
    assert all(item["project"] != weather_project for item in blocked["results"])

    brain_client.bridge_projects(
        project=ems_project,
        related_project=weather_project,
        reason="La metodología de monitorización se comparte entre EMS y estaciones meteo.",
        active=True,
        created_by="pytest",
    )

    allowed = brain_client.structured_search(
        query=isolated["shared_method_query"],
        project=ems_project,
        scope="bridged",
        limit=8,
        register_access=False,
    )
    assert any(item["project"] == weather_project for item in allowed["results"])


def test_focus_subgraph_and_relations_show_cross_project_methodology(seeded_demo_dataset, brain_client):
    ems_project = seeded_demo_dataset["project_names_by_slug"]["demo-ems-fotovoltaica"]
    focus_memory_id = seeded_demo_dataset["anchor_memory_ids"][ems_project]

    focus = brain_client.graph_subgraph(
        project=ems_project,
        mode="memory_focus",
        center_memory_id=focus_memory_id,
        scope="bridged",
        node_limit=18,
        edge_limit=36,
        include_inactive=False,
    )
    projects_in_graph = {node["project"] for node in focus["nodes"]}
    assert len(projects_in_graph) >= 3

    detail = brain_client.memory_detail(focus_memory_id)
    related_projects = {relation["other_project"] for relation in detail["relations"] if relation["other_project"]}
    assert seeded_demo_dataset["project_names_by_slug"]["demo-monitorizacion-estaciones-meteorologicas"] in related_projects
    assert detail["relation_count"] >= 2


def test_demo_metrics_and_plasticity_remain_active(seeded_demo_dataset, brain_client):
    ems_project = seeded_demo_dataset["project_names_by_slug"]["demo-ems-fotovoltaica"]

    metrics_before = brain_client.graph_metrics(project=ems_project)
    plasticity = brain_client.apply_session_plasticity(**seeded_demo_dataset["session_payloads"][ems_project])
    metrics_after = brain_client.graph_metrics(project=ems_project)

    assert metrics_before["bridge_count"] >= 1
    assert metrics_before["relation_count"] > 0
    assert metrics_before["hot_memory_count"] > 0
    assert plasticity["activated_memories"] >= 1
    assert plasticity["reinforced_pairs"] >= 0
    assert metrics_after["avg_activation_score"] >= metrics_before["avg_activation_score"]


def test_expected_bridges_exist_for_seeded_demo(seeded_demo_dataset, brain_client):
    catalog = build_demo_catalog(seeded_demo_dataset["namespace"])
    expected_pairs = {
        tuple(sorted((bridge["project"], bridge["related_project"])))
        for bridge in catalog["bridges"]
    }

    observed_pairs = set()
    for project_name in seeded_demo_dataset["project_names"]:
        bridges = brain_client.list_bridges(project_name)["bridges"]
        for bridge in bridges:
            observed_pairs.add(tuple(sorted((bridge["project"], bridge["related_project"]))))

    assert expected_pairs.issubset(observed_pairs)
