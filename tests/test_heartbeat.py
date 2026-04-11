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


def test_heartbeat_inject_creates_memories_and_relations(brain_client, unique_project_name):
    """Simulate batch 1 injection and verify relationships form."""
    project = unique_project_name("hb-e2e")

    import time

    mem_a = brain_client.create_memory(
        content="La monitorización de inversores fotovoltaicos requiere lectura de registros Modbus TCP cada 10 segundos",
        project=project,
        memory_type="architecture",
        tags="inversores,modbus,monitorizacion",
        importance=0.85,
        agent_id="heartbeat-test",
    )["memory_id"]

    mem_b = brain_client.create_memory(
        content="Decidimos usar polling síncrono para la lectura de inversores porque el firmware no soporta push",
        project=project,
        memory_type="decision",
        tags="inversores,polling,firmware",
        importance=0.8,
        agent_id="heartbeat-test",
    )["memory_id"]

    time.sleep(1)

    mem_c = brain_client.create_memory(
        content="Los inversores Huawei SUN2000 reportan potencia activa en el registro 32080",
        project=project,
        memory_type="observation",
        tags="inversores,huawei,registros",
        importance=0.75,
        agent_id="heartbeat-test",
    )["memory_id"]

    time.sleep(1)

    # At least some relations should have formed
    all_rels = []
    for mid in [mem_a, mem_b, mem_c]:
        rels = brain_client.relations(mid).get("relations", [])
        all_rels.extend(rels)

    assert len(all_rels) > 0, "Expected at least one relation to form between cluster memories"


def test_heartbeat_deep_sleep_trigger_and_complete(brain_client):
    """Trigger deep sleep and verify it completes."""
    import time

    result = brain_client.post("/api/test/trigger-deep-sleep", {})
    assert "run_id" in result
    run_id = result["run_id"]

    # Poll until done (max 120s)
    for _ in range(24):
        time.sleep(5)
        status = brain_client.get(f"/api/test/deep-sleep-status/{run_id}")
        if status["status"] in ("completed", "failed"):
            assert status["status"] == "completed", f"Deep sleep failed: {status.get('stats')}"
            return

    assert False, "Deep sleep did not complete within 120 seconds"
