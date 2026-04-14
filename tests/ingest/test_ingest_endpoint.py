"""Integration tests for /ingest_turn against a live api-server.

Run with:
    make stack-test-up
    CLASSIFIER_PROVIDER=fake \
    INGEST_DISABLED_PROJECTS=ingest-disabled-test \
    AI_MEMORY_BASE_URL=http://127.0.0.1:8050 \
    .venv/bin/python -m pytest tests/ingest/test_ingest_endpoint.py -q
"""
import os
import time
import uuid

import httpx
import pytest

BASE_URL = os.getenv("AI_MEMORY_BASE_URL", "http://127.0.0.1:8050")
API_KEY = os.getenv("MEMORY_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def _turn(**overrides):
    base = {
        "project": "ingest-test-" + uuid.uuid4().hex[:8],
        "session_id": uuid.uuid4().hex,
        "turn_id": uuid.uuid4().hex,
        "timestamp": "2026-04-13T00:00:00Z",
        "user_message": "Please fix the authentication bug in the login flow",
        "assistant_message": "Fixed the bug by validating the JWT signature before use",
        "tool_calls": [
            {"name": "Edit", "target": "auth.py", "summary": "validate token signature"}
        ],
    }
    base.update(overrides)
    return base


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=30) as c:
        yield c


def test_full_turn_stores_error_action(client):
    r = client.post("/ingest_turn", json=_turn())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["filtered"] is False
    assert body["actions_taken"] >= 1
    assert any(a["type"] == "store_error" for a in body["actions"])


def test_trivial_turn_is_prefiltered_fast(client):
    turn = _turn(user_message="ok", tool_calls=[{"name": "Edit", "summary": "x"}])
    t0 = time.perf_counter()
    r = client.post("/ingest_turn", json=turn)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    body = r.json()
    assert body["filtered"] is True
    assert body["reason"] == "trivial_user_message"
    assert elapsed_ms < 500  # HTTP round-trip, generous


def test_secret_in_turn_is_redacted_before_storage(client):
    secret = "sk-abc123def456ghi789jkl012mno345"
    turn = _turn(
        user_message=f"Please decide if we use {secret} here (we should not)",
        assistant_message=f"Decision: never store the {secret} key in code",
    )
    r = client.post("/ingest_turn", json=turn)
    assert r.status_code == 200
    search = client.post(
        "/api/search",
        json={"query": secret, "project": turn["project"], "limit": 20},
    )
    if search.status_code == 200:
        for hit in search.json().get("results", []):
            assert secret not in hit.get("content", "")


def test_duplicate_turn_deduped_on_second_call(client):
    project = "ingest-dup-" + uuid.uuid4().hex[:6]
    turn = _turn(project=project)
    r1 = client.post("/ingest_turn", json=turn)
    assert r1.status_code == 200
    time.sleep(2.1)  # clear rate limit
    turn2 = dict(turn)
    turn2["session_id"] = uuid.uuid4().hex
    turn2["turn_id"] = uuid.uuid4().hex
    r2 = client.post("/ingest_turn", json=turn2)
    body = r2.json()
    deduped = [a for a in body.get("actions", []) if a.get("skip_reason") == "duplicate"]
    assert len(deduped) >= 1


def test_project_opt_out(client):
    turn = _turn(project="ingest-disabled-test")
    r = client.post("/ingest_turn", json=turn)
    body = r.json()
    assert body["filtered"] is True
    assert body["reason"] == "project_disabled"


def test_rate_limit_same_session(client):
    sid = uuid.uuid4().hex
    t1 = _turn(session_id=sid)
    t2 = _turn(session_id=sid)
    r1 = client.post("/ingest_turn", json=t1)
    r2 = client.post("/ingest_turn", json=t2)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json().get("reason") == "rate_limited"


def test_ingest_stats_endpoint(client):
    project = "ingest-stats-" + uuid.uuid4().hex[:6]
    for _ in range(3):
        client.post("/ingest_turn", json=_turn(project=project))
        time.sleep(2.1)
    r = client.get(f"/ingest/stats?project={project}")
    assert r.status_code == 200
    body = r.json()
    assert body["turns_ingested"] == 3
