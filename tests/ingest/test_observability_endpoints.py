"""Integration tests for the persistent observability endpoints.

Run with (same contract as the rest of tests/ingest/):
    make stack-test-up
    CLASSIFIER_PROVIDER=fake \
    INGEST_DISABLED_PROJECTS=ingest-disabled-test \
    AI_MEMORY_BASE_URL=http://127.0.0.1:8050 \
    .venv/bin/python -m pytest tests/ingest/test_observability_endpoints.py -q

These tests exercise the DB layer of ingest_persistence by driving the full
HTTP pipeline and then querying the new read endpoints. They assume the fake
classifier is active (deterministic outputs) and that INGEST_AUDIT_ENABLED
defaults to true.
"""
from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

BASE_URL = os.getenv("AI_MEMORY_BASE_URL", "http://127.0.0.1:8050")
API_KEY = os.getenv("MEMORY_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=30) as c:
        yield c


def _edit_turn(project: str, **overrides):
    base = {
        "project": project,
        "session_id": uuid.uuid4().hex,
        "turn_id": uuid.uuid4().hex,
        "timestamp": "2026-04-14T00:00:00Z",
        "user_message": "Please fix the authentication bug in the login flow",
        "assistant_message": "Fixed the bug by validating the JWT signature before use",
        "tool_calls": [
            {"name": "Edit", "target": "auth.py", "summary": "validate token signature"}
        ],
    }
    base.update(overrides)
    return base


def _post_with_cooldown(client, payload):
    # The in-process rate limiter enforces INGEST_RATE_LIMIT_SECONDS per session.
    r = client.post("/ingest_turn", json=payload)
    time.sleep(2.1)
    return r


def test_global_stats_returns_project_rollup(client):
    project = "obs-rollup-" + uuid.uuid4().hex[:6]
    for _ in range(3):
        _post_with_cooldown(client, _edit_turn(project, session_id=uuid.uuid4().hex))

    r = client.get("/ingest/stats")  # no project param → global view
    assert r.status_code == 200, r.text
    body = r.json()
    assert "projects" in body
    assert "totals" in body
    assert body["window_days"] >= 1
    assert project in body["projects"], f"project missing from global view: {body['projects']}"
    p = body["projects"][project]
    assert p["turns"] >= 3
    assert p["classified"] >= 1
    assert p["last_turn_at"] is not None
    # Totals must be at least as big as this project's contribution.
    assert body["totals"]["turns"] >= p["turns"]


def test_global_stats_tracks_filter_reasons_per_project(client):
    # Mix of one trivial (filtered by pre-filter) and one project_disabled.
    project = "obs-reasons-" + uuid.uuid4().hex[:6]
    trivial = _edit_turn(project, user_message="ok")  # too short → trivial_user_message
    _post_with_cooldown(client, trivial)
    disabled = _edit_turn("ingest-disabled-test")
    _post_with_cooldown(client, disabled)

    r = client.get("/ingest/stats")
    assert r.status_code == 200
    body = r.json()
    projects = body["projects"]
    assert project in projects
    reasons = projects[project]["filtered_by_reason"]
    assert reasons.get("trivial_user_message", 0) >= 1

    assert "ingest-disabled-test" in projects
    reasons_disabled = projects["ingest-disabled-test"]["filtered_by_reason"]
    assert reasons_disabled.get("project_disabled", 0) >= 1


def test_audit_endpoint_records_turn_outcomes(client):
    project = "obs-audit-" + uuid.uuid4().hex[:6]
    # One that goes through the classifier (write-tool + long enough user msg).
    _post_with_cooldown(client, _edit_turn(project, session_id=uuid.uuid4().hex))
    # One that is filtered as trivial.
    _post_with_cooldown(client, _edit_turn(project, user_message="ok", session_id=uuid.uuid4().hex))

    r = client.get(f"/ingest/audit?project={project}&limit=20")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] >= 2
    outcomes = {row["outcome"] for row in body["rows"]}
    assert "filtered" in outcomes
    assert ("accepted_actions" in outcomes) or ("accepted_empty" in outcomes)

    # Each row should have the minimum expected shape.
    sample = body["rows"][0]
    for key in (
        "id", "ts", "project", "session_id", "turn_id", "turn_hash",
        "user_len", "assistant_len", "tools_count", "outcome",
        "action_types",
    ):
        assert key in sample, f"audit row missing key: {key}"
    assert sample["project"] == project


def test_audit_endpoint_filters_by_outcome(client):
    project = "obs-audit-f-" + uuid.uuid4().hex[:6]
    _post_with_cooldown(client, _edit_turn(project, user_message="ok", session_id=uuid.uuid4().hex))

    r = client.get(f"/ingest/audit?project={project}&outcome=filtered&limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    for row in body["rows"]:
        assert row["outcome"] == "filtered"
        assert row["filter_reason"] is not None


def test_project_stats_backward_compatible(client):
    # /ingest/stats?project=X must keep its previous shape for consumers that
    # already depend on it.
    project = "obs-compat-" + uuid.uuid4().hex[:6]
    _post_with_cooldown(client, _edit_turn(project))

    r = client.get(f"/ingest/stats?project={project}")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "project", "turns_ingested", "filtered", "classified",
        "actions_stored", "deduped", "avg_classifier_ms", "errors",
        "links_created",
    ):
        assert key in body, f"legacy stats missing key: {key}"
    assert body["project"] == project
    assert body["turns_ingested"] >= 1
