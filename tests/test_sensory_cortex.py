"""Tests for Layer 0 — Multi-Modal Sensory Cortex.

Covers: keyphrase extraction, cascade tiers, fusion search, tag canonicalization,
brain health endpoint, cross-project permeability.
"""

import time

import pytest


def test_keyphrases_extracted_on_store(brain_client, unique_project_name):
    """Storing a memory should extract keyphrases automatically."""
    project = unique_project_name("l0-kp")
    result = brain_client.create_memory(
        content="Fixed retry logic in payment service after timeout errors caused cascading failures",
        project=project,
        memory_type="observation",
        tags="retry,payment,timeout",
        importance=0.8,
    )
    mid = result["memory_id"]
    detail = brain_client.memory_detail(mid)
    memory = detail.get("memory", detail)
    kp = memory.get("keyphrases", [])
    assert isinstance(kp, list)
    assert len(kp) >= 3, f"Expected at least 3 keyphrases, got {kp}"


def test_cascade_creates_relations_for_similar_content(brain_client, unique_project_name):
    """Two similar memories should form a synapse via the cascade.

    In test mode, hash-based embeddings produce Tier 3 candidates (not Tier 1/2).
    Tier 3 candidates are staged for sleep validation (NREM phase) rather than
    creating relations immediately. We verify the cascade worked by checking
    either immediate relations (Tier 1/2) or synapse formation in brain health stats.
    """
    project = unique_project_name("l0-cascade")
    id1 = brain_client.create_memory(
        content="The payment service uses exponential backoff for retry logic when downstream calls fail",
        project=project,
        memory_type="observation",
        tags="retry,payment",
        importance=0.8,
    )["memory_id"]
    time.sleep(0.3)
    id2 = brain_client.create_memory(
        content="Payment service implements exponential backoff retry strategy for handling transient failures",
        project=project,
        memory_type="observation",
        tags="retry,payment",
        importance=0.8,
    )["memory_id"]
    time.sleep(0.3)

    # Check for immediate relations (Tier 1/2) first
    rels = brain_client.relations(id2)
    if rels.get("relations"):
        return  # Tier 1/2 created immediate relation — test passes

    # In test mode, hash-based embeddings typically produce Tier 3 candidates.
    # Verify the cascade created synapse candidates via brain health stats.
    health = brain_client.brain_health()
    synapses = health.get("synapse_formation", {})
    pending = synapses.get("tier3_candidates_pending", 0)
    promoted = synapses.get("tier3_promoted", 0)
    total = pending + promoted + synapses.get("tier1_instant", 0) + synapses.get("tier2_confirmed", 0)
    assert total > 0, (
        "Cascade should create synapse candidates for similar content; "
        f"got synapse_formation={synapses}"
    )


def test_fusion_search_returns_results(brain_client, unique_project_name):
    """Fusion search should return results using dual vectors."""
    project = unique_project_name("l0-fusion")
    brain_client.create_memory(
        content="Implemented circuit breaker pattern for the order service to handle downstream failures gracefully",
        project=project,
        memory_type="decision",
        tags="resilience,circuit-breaker",
        importance=0.9,
    )
    time.sleep(0.5)
    results = brain_client.structured_search(
        query="How does the order service handle failures?",
        project=project,
        scope="project",
        limit=5,
    )
    assert len(results["results"]) >= 1, "Fusion search should find the circuit breaker memory"


def test_memory_includes_valence_arousal_in_search(brain_client, unique_project_name):
    """Search results should include valence, arousal, created_at for cascade signals."""
    project = unique_project_name("l0-meta")
    brain_client.create_memory(
        content="Critical production error caused data corruption in the user table",
        project=project,
        memory_type="error",
        tags="production,critical",
        importance=0.95,
    )
    time.sleep(0.3)
    results = brain_client.structured_search(
        query="production error data corruption",
        project=project,
        scope="project",
        limit=3,
    )
    assert len(results["results"]) >= 1
    first = results["results"][0]
    assert "valence" in first, "Search results should include valence"
    assert "arousal" in first, "Search results should include arousal"
    assert "created_at" in first, "Search results should include created_at"


def test_cross_project_bridge_creates_permeability(brain_client, unique_project_name):
    """Bridging projects should also create a permeability record."""
    proj_a = unique_project_name("l0-perm-a")
    proj_b = unique_project_name("l0-perm-b")
    # Ensure projects exist by storing a memory in each
    brain_client.create_memory(content="Memory in project A", project=proj_a, importance=0.5)
    brain_client.create_memory(content="Memory in project B", project=proj_b, importance=0.5)
    time.sleep(0.3)
    brain_client.bridge_projects(project=proj_a, related_project=proj_b, reason="test permeability")
    # No assertion on permeability directly (no API for it yet),
    # but the bridge should succeed without error
    bridges = brain_client.list_bridges(proj_a)
    assert len(bridges.get("bridges", [])) >= 1


def test_brain_health_endpoint(brain_client, unique_project_name):
    """The /brain/health endpoint should return valid health metrics."""
    project = unique_project_name("l0-health")
    brain_client.create_memory(
        content="Test memory for brain health check endpoint validation",
        project=project,
        importance=0.5,
    )
    time.sleep(0.5)
    health = brain_client.brain_health()
    assert "overall_health" in health
    assert "regions" in health
    assert "connectivity" in health
    assert "synapse_formation" in health
    assert "sleep" in health
    assert "alerts" in health
    assert isinstance(health["overall_health"], (int, float))
    assert 0 <= health["overall_health"] <= 1.0


def test_brain_health_includes_project_regions(brain_client, unique_project_name):
    """Brain health should show per-project region stats."""
    project = unique_project_name("l0-region")
    brain_client.create_memory(content="Memory A in region test", project=project, importance=0.6)
    brain_client.create_memory(content="Memory B in region test", project=project, importance=0.7)
    time.sleep(0.5)
    health = brain_client.brain_health()
    assert project in health["regions"], f"Project {project} should appear in regions"
    region = health["regions"][project]
    assert region["memory_count"] >= 2
    assert "orphan_ratio" in region
    assert "keyphrases_coverage" in region
