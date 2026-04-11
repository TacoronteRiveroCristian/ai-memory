"""Integration tests for heartbeat monitor endpoints."""


def test_trigger_deep_sleep_queues_run(brain_client):
    """POST /api/test/trigger-deep-sleep should queue a deep sleep run."""
    result = brain_client.post("/api/test/trigger-deep-sleep", {})
    assert result["queued"] is True
    assert "run_id" in result

    # Check status
    run_id = result["run_id"]
    status = brain_client.get(f"/api/test/deep-sleep-status/{run_id}")
    assert status["run_id"] == run_id
    assert status["status"] in ("pending", "running", "completed")


def test_trigger_deep_sleep_deduplicates(brain_client):
    """Triggering while one is pending should return existing run."""
    first = brain_client.post("/api/test/trigger-deep-sleep", {})
    second = brain_client.post("/api/test/trigger-deep-sleep", {})
    # If the first is still pending, second should return same run_id
    if first["queued"]:
        assert second["run_id"] == first["run_id"]
        assert second["queued"] is False


def test_heartbeat_status_returns_empty_initially(brain_client):
    """GET /api/heartbeat/status should work even with no cycles."""
    status = brain_client.get("/api/heartbeat/status")
    assert "cycles_completed" in status
    assert "checks_summary" in status
    assert status["cycles_completed"] >= 0


def test_heartbeat_report_stores_cycle(brain_client):
    """POST /api/heartbeat/report should persist a cycle."""
    import uuid
    cycle_id = f"hb-test-{uuid.uuid4().hex[:8]}"
    brain_client.post("/api/heartbeat/report", {
        "cycle_id": cycle_id,
        "mode": "accelerated",
        "phase": "completed",
        "injected_memories": 8,
        "checks": [
            {"name": "relationships_formed", "passed": True, "detail": "3/3 linked"},
            {"name": "contradiction_detected", "passed": False, "detail": "score=0"},
        ],
        "passed": 1,
        "failed": 1,
    })

    status = brain_client.get("/api/heartbeat/status")
    latest = status.get("latest_cycle")
    assert latest is not None
    # The cycle we just reported should be findable
    found = any(
        c["cycle_id"] == cycle_id
        for c in [latest] + status.get("history", [])
    )
    assert found, f"Cycle {cycle_id} not found in status response"
