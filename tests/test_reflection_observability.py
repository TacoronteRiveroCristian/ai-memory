"""Tests for reflection observability endpoints (runs, promotions, contradictions)."""

import time


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
