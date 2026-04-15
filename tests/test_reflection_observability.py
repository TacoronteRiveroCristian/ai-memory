"""Tests for reflection observability endpoints (runs, promotions, contradictions)."""

import time

import pytest


def test_list_reflection_runs_smoke(brain_client):
    payload = brain_client.list_reflection_runs(limit=5)
    assert "runs" in payload
    assert "count" in payload
    assert payload["count"] == len(payload["runs"])
    assert payload["filter"]["limit"] == 5


def test_list_reflection_runs_returns_manual_run(brain_client):
    queued = brain_client.run_reflection()
    assert "run_id" in queued
    # The run exists in reflection_runs even if the worker hasn't picked it up yet.
    payload = brain_client.list_reflection_runs(limit=10)
    run_ids = [r["id"] for r in payload["runs"]]
    assert queued["run_id"] in run_ids


def test_list_reflection_runs_unknown_project_is_empty(brain_client):
    payload = brain_client.list_reflection_runs(project="does-not-exist-zzz")
    assert payload["runs"] == []
    assert payload["count"] == 0


def test_list_reflection_runs_limit_is_clamped(brain_client):
    payload = brain_client.list_reflection_runs(limit=999)
    assert payload["filter"]["limit"] == 100


def test_list_contradictions_smoke(brain_client):
    payload = brain_client.list_contradictions(limit=10)
    assert "contradictions" in payload
    assert payload["count"] == len(payload["contradictions"])


def test_list_contradictions_rejects_bad_status(brain_client):
    import httpx
    try:
        brain_client.list_contradictions(status="nope")
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 400
    else:
        raise AssertionError("expected 400 for invalid status")


def test_list_contradictions_surfaces_suspected_pair(brain_client, unique_project_name):
    if brain_client.health().get("test_mode"):
        pytest.skip("Requires real embeddings — contradiction detection uses semantic signals that hash-mode embeddings can't produce.")
    project = unique_project_name("contra-obs")
    mem_a = brain_client.create_memory(
        content="Siempre usar Redis para cache de embeddings en producción",
        project=project, memory_type="decision",
        tags="redis,cache,embeddings", importance=0.85, agent_id="pytest",
    )["memory_id"]
    time.sleep(0.5)
    mem_b = brain_client.create_memory(
        content="Nunca usar Redis para cache; preferir Memcached por consumo de memoria",
        project=project, memory_type="decision",
        tags="redis,cache,memcached", importance=0.85, agent_id="pytest",
    )["memory_id"]
    time.sleep(1.0)

    payload = brain_client.list_contradictions(project=project, limit=50)
    # We accept that the pair may land as a direct `contradicts` relation instead
    # of a queue entry. The test passes if EITHER the queue has the pair OR the
    # relation exists on one of the memories.
    queue_pair_ids = {
        (c["memory_a"]["id"], c["memory_b"]["id"])
        for c in payload["contradictions"]
    }
    in_queue = (mem_a, mem_b) in queue_pair_ids or (mem_b, mem_a) in queue_pair_ids
    if not in_queue:
        rels = brain_client.relations(mem_a).get("relations", []) + \
               brain_client.relations(mem_b).get("relations", [])
        assert any(r.get("relation_type") == "contradicts" for r in rels), \
            f"neither queue entry nor contradicts relation found for {mem_a}/{mem_b}"


def test_list_contradictions_unknown_project_is_empty(brain_client):
    payload = brain_client.list_contradictions(project="does-not-exist-zzz")
    assert payload["contradictions"] == []


def test_brain_activity_shape(brain_client):
    payload = brain_client.brain_activity(hours=24)
    assert payload["window_hours"] == 24
    assert set(["reflection_runs", "contradictions_new", "contradictions_resolved", "stats"]).issubset(payload)
    stats = payload["stats"]
    for key in ("runs", "promotions", "new_contradictions", "resolved_contradictions"):
        assert key in stats
        assert isinstance(stats[key], int)


def test_brain_activity_hours_clamped(brain_client):
    payload = brain_client.brain_activity(hours=9999)
    assert payload["window_hours"] == 168


def test_brain_activity_unknown_project_is_empty(brain_client):
    payload = brain_client.brain_activity(hours=24, project="does-not-exist-zzz")
    assert payload["reflection_runs"] == []
    assert payload["contradictions_new"] == []
    assert payload["contradictions_resolved"] == []
    assert payload["stats"]["runs"] == 0
