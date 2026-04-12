"""Heartbeat Monitor — living proof that biological memory processes work.

Continuously injects trap memories, triggers deep sleep, and verifies
that every biological process produces measurable effects.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path

from client import HeartbeatClient
from batches import (
    BATCH_1_CLUSTER,
    BATCH_2_CONTRADICTION,
    BATCH_3_CROSS_PROJECT,
    BATCH_5_COLD,
    BRIDGE_REASON,
    CycleContext,
)
from checks import (
    ALL_CHECKS,
    CheckResult,
    check_overall_health_stable,
    take_memory_snapshot,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("heartbeat-monitor")

BASE_URL = os.environ.get("AI_MEMORY_BASE_URL", "http://api-server:8050")
API_KEY = os.environ.get("MEMORY_API_KEY", "")
MODE = os.environ.get("HEARTBEAT_MODE", "accelerated")
INJECT_INTERVAL = int(os.environ.get("HEARTBEAT_INJECT_INTERVAL", "30"))
SLEEP_INTERVAL = int(os.environ.get("HEARTBEAT_SLEEP_INTERVAL", "300"))
VERIFY_INTERVAL = int(os.environ.get("HEARTBEAT_VERIFY_INTERVAL", "120"))
HEARTBEAT_FILE = Path("/tmp/heartbeat-alive")


def touch_heartbeat():
    HEARTBEAT_FILE.write_text(str(time.time()))


def wait_for_api(client: HeartbeatClient, max_wait: int = 120) -> bool:
    """Wait until the API server is reachable."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            client.get("/health")
            return True
        except Exception:
            logger.info("Waiting for API server at %s ...", BASE_URL)
            time.sleep(5)
    return False


def cleanup_previous(client: HeartbeatClient, prefix: str):
    """Delete any leftover heartbeat projects."""
    try:
        health = client.brain_health()
        regions = health.get("regions", {})
        for project_name in regions:
            if project_name.startswith(prefix):
                try:
                    client.delete_project(project_name)
                    logger.info("Cleaned up old project: %s", project_name)
                except Exception:
                    pass
    except Exception:
        logger.debug("Cleanup scan failed (non-critical)")


def inject_batch(client: HeartbeatClient, ctx: CycleContext, batch, project: str, id_prefix: str):
    """Inject a batch of trap memories and record their IDs."""
    for i, mem in enumerate(batch.memories):
        result = client.create_memory(
            content=mem.content,
            project=project,
            memory_type=mem.memory_type,
            tags=mem.tags,
            importance=mem.importance,
            agent_id="heartbeat-monitor",
        )
        key = f"{id_prefix}_{i}"
        ctx.memory_ids[key] = result["memory_id"]
        logger.info("  Injected %s: %s", key, result["memory_id"][:8])


def _search_to_activate(client: HeartbeatClient, project: str, query: str):
    """Fire a search to set last_accessed_at and boost stability on matching memories."""
    try:
        client.structured_search(query=query, project=project, limit=5)
        logger.info("  Search activation: '%s' in %s", query[:40], project)
    except Exception as exc:
        logger.debug("  Search activation failed: %s", exc)


def _trigger_ebbinghaus_decay(client: HeartbeatClient, ctx: CycleContext):
    """Trigger Ebbinghaus decay via plasticity session (uses api-server's now_utc)."""
    session_id = f"hb-decay-{uuid.uuid4().hex[:8]}"
    try:
        client.record_session(
            project=ctx.project_a,
            agent_id="heartbeat-decay",
            session_id=session_id,
            summary="Decay trigger",
            goal="Trigger Ebbinghaus decay",
            outcome="Completed",
            changes=[],
            decisions=[],
            errors=[],
            follow_ups=[],
        )
        client.apply_session_plasticity(
            project=ctx.project_a,
            agent_id="heartbeat-decay",
            session_id=session_id,
            summary="Decay trigger",
            goal="Trigger Ebbinghaus decay",
            outcome="Completed",
            changes=[],
            decisions=[],
            errors=[],
            follow_ups=[],
        )
        logger.info("  Ebbinghaus decay triggered via plasticity session")
    except Exception as exc:
        logger.debug("  Ebbinghaus decay trigger failed: %s", exc)


def _is_test_mode(client: HeartbeatClient) -> bool:
    """Check if the API server is running in test mode."""
    try:
        health = client.get("/health")
        return health.get("test_mode", False)
    except Exception:
        return False


def phase_inject(client: HeartbeatClient, ctx: CycleContext):
    """Phase 1: Inject all trap batches."""
    logger.info("=== PHASE 1: INJECT (cycle %s) ===", ctx.cycle_id)

    cleanup_previous(client, "heartbeat-")
    ctx.set_projects("mon")

    logger.info("Batch 1: Cluster base (%s)", ctx.project_a)
    inject_batch(client, ctx, BATCH_1_CLUSTER, ctx.project_a, "cluster")
    time.sleep(1)

    logger.info("Batch 2: Contradiction")
    inject_batch(client, ctx, BATCH_2_CONTRADICTION, ctx.project_a, "contra")
    time.sleep(1)

    logger.info("Batch 3: Cross-project (%s)", ctx.project_b)
    inject_batch(client, ctx, BATCH_3_CROSS_PROJECT, ctx.project_b, "cross")

    try:
        client.bridge_projects(
            project=ctx.project_a,
            related_project=ctx.project_b,
            reason=BRIDGE_REASON,
        )
        logger.info("  Bridge created: %s <-> %s", ctx.project_a, ctx.project_b)
    except Exception as exc:
        logger.warning("  Bridge creation failed: %s", exc)

    time.sleep(1)

    logger.info("Batch 4: Reinforcement (plasticity session)")
    session_id = f"hb-session-{uuid.uuid4().hex[:8]}"
    try:
        client.record_session(
            project=ctx.project_a,
            agent_id="heartbeat-monitor",
            session_id=session_id,
            summary="Revisión de la arquitectura de monitorización de inversores Modbus",
            goal="Verificar configuración de polling y registros Huawei",
            outcome="Confirmada lectura cada 10s en registro 32080",
            changes=[],
            decisions=[],
            errors=[],
            follow_ups=[],
        )
        client.apply_session_plasticity(
            project=ctx.project_a,
            agent_id="heartbeat-monitor",
            session_id=session_id,
            summary="Revisión de la arquitectura de monitorización de inversores Modbus",
            goal="Verificar configuración de polling y registros Huawei",
            outcome="Confirmada lectura cada 10s en registro 32080",
            changes=[],
            decisions=[],
            errors=[],
            follow_ups=[],
        )
        logger.info("  Plasticity session applied")
    except Exception as exc:
        logger.warning("  Plasticity session failed: %s", exc)

    logger.info("Batch 5: Cold memory (will not be accessed)")
    inject_batch(client, ctx, BATCH_5_COLD, ctx.project_a, "cold")

    # Take initial snapshots BEFORE search activation
    # (so stability_increased can detect the boost from search)
    logger.info("Taking initial snapshots...")
    for key, mid in ctx.memory_ids.items():
        try:
            ctx.initial_snapshots[key] = take_memory_snapshot(client, mid)
        except Exception:
            logger.debug("  Snapshot failed for %s", key)

    # Search cluster and cross-project memories to set last_accessed_at
    # and boost stability (needed for myelin strengthening and stability check)
    _search_to_activate(client, ctx.project_a, "inversores Modbus monitorización")
    _search_to_activate(client, ctx.project_b, "mantenimiento predictivo Modbus")

    total = len(ctx.memory_ids)
    logger.info("Phase 1 complete: %d memories injected", total)
    touch_heartbeat()
    return total


def phase_sleep(client: HeartbeatClient, ctx: CycleContext):
    """Phase 2: Trigger deep sleep and wait for completion."""
    logger.info("=== PHASE 2: DEEP SLEEP (cycle %s) ===", ctx.cycle_id)

    try:
        result = client.trigger_deep_sleep()
        run_id = result["run_id"]
        logger.info("Deep sleep triggered: run_id=%s (queued=%s)", run_id, result.get("queued"))
    except Exception as exc:
        logger.error("Failed to trigger deep sleep: %s", exc)
        return

    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            status = client.deep_sleep_status(run_id)
            s = status["status"]
            if s == "completed":
                logger.info("Deep sleep completed: %s", status.get("stats", {}))
                touch_heartbeat()
                return
            if s == "failed":
                logger.error("Deep sleep failed: %s", status.get("stats", {}))
                touch_heartbeat()
                return
            logger.info("Deep sleep status: %s (waiting...)", s)
        except Exception as exc:
            logger.debug("Status poll error: %s", exc)
        time.sleep(10)

    logger.warning("Deep sleep did not complete within 5 minutes")
    touch_heartbeat()


def phase_verify(client: HeartbeatClient, ctx: CycleContext, previous_health: float) -> list[CheckResult]:
    """Phase 3: Run all verification checks."""
    logger.info("=== PHASE 3: VERIFY (cycle %s) ===", ctx.cycle_id)

    results: list[CheckResult] = []

    for check_fn in ALL_CHECKS:
        try:
            result = check_fn(client, ctx)
        except Exception as exc:
            result = CheckResult(check_fn.__name__.replace("check_", ""), False, f"Error: {exc}")
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        logger.info("  [%s] %s: %s", status, result.name, result.detail)

    try:
        health_result = check_overall_health_stable(client, previous_health)
    except Exception as exc:
        health_result = CheckResult("overall_health_stable", False, f"Error: {exc}")
    results.append(health_result)
    status = "PASS" if health_result.passed else "FAIL"
    logger.info("  [%s] %s: %s", status, health_result.name, health_result.detail)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    logger.info("Phase 3 complete: %d passed, %d failed", passed, failed)

    try:
        client.report_cycle({
            "cycle_id": ctx.cycle_id,
            "mode": MODE,
            "phase": "completed",
            "injected_memories": len(ctx.memory_ids),
            "checks": [r.to_dict() for r in results],
            "passed": passed,
            "failed": failed,
        })
        logger.info("Cycle report stored")
    except Exception as exc:
        logger.warning("Failed to store cycle report: %s", exc)

    touch_heartbeat()
    return results


def run_cycle(client: HeartbeatClient, previous_health: float) -> tuple[list[CheckResult], float]:
    """Execute one full heartbeat cycle: inject -> sleep -> verify."""
    ctx = CycleContext()
    test_mode = _is_test_mode(client)
    logger.info("Starting heartbeat cycle %s (mode=%s, test_mode=%s)", ctx.cycle_id, MODE, test_mode)

    phase_inject(client, ctx)

    logger.info("Waiting %ds before triggering deep sleep...", SLEEP_INTERVAL)
    remaining = SLEEP_INTERVAL
    while remaining > 0:
        wait = min(remaining, 30)
        time.sleep(wait)
        remaining -= wait
        touch_heartbeat()

    phase_sleep(client, ctx)

    # In test mode: take post-sleep snapshots (before clock advance) for stability check,
    # then advance clock and trigger Ebbinghaus decay for cold memory check
    if test_mode:
        # Snapshot after deep sleep but before decay — captures stability boost from search
        logger.info("Taking post-sleep snapshots for stability comparison...")
        for key in ("cluster_0", "cluster_1", "cluster_2"):
            mid = ctx.memory_ids.get(key)
            if mid:
                try:
                    ctx.post_sleep_snapshots[key] = take_memory_snapshot(client, mid)
                except Exception:
                    pass

        try:
            from datetime import datetime, timedelta, timezone
            future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            client.set_test_clock(future)
            logger.info("Test clock advanced 30 days for Ebbinghaus decay")
            _trigger_ebbinghaus_decay(client, ctx)
        except Exception as exc:
            logger.warning("Failed test clock advance/decay: %s", exc)

    logger.info("Waiting %ds before verification...", VERIFY_INTERVAL)
    remaining = VERIFY_INTERVAL
    while remaining > 0:
        wait = min(remaining, 30)
        time.sleep(wait)
        remaining -= wait
        touch_heartbeat()

    results = phase_verify(client, ctx, previous_health)

    # Reset test clock after verification
    if test_mode:
        try:
            client.set_test_clock(None)
            logger.info("Test clock reset")
        except Exception as exc:
            logger.warning("Failed to reset test clock: %s", exc)

    try:
        current_health = client.brain_health().get("overall_health", 0.5)
    except Exception:
        current_health = previous_health

    return results, current_health


def main():
    logger.info("Heartbeat Monitor starting (mode=%s)", MODE)
    logger.info("  Inject interval: %ds", INJECT_INTERVAL)
    logger.info("  Sleep interval: %ds", SLEEP_INTERVAL)
    logger.info("  Verify interval: %ds", VERIFY_INTERVAL)

    client = HeartbeatClient(BASE_URL, API_KEY)
    touch_heartbeat()

    if not wait_for_api(client):
        logger.error("API server not reachable at %s — exiting", BASE_URL)
        return

    logger.info("API server reachable. Starting heartbeat cycles.")
    previous_health = 0.5
    cycle_count = 0

    try:
        while True:
            cycle_count += 1
            logger.info("===== CYCLE %d =====", cycle_count)
            try:
                results, previous_health = run_cycle(client, previous_health)
                passed = sum(1 for r in results if r.passed)
                failed = len(results) - passed
                logger.info("===== CYCLE %d COMPLETE: %d passed, %d failed =====", cycle_count, passed, failed)
            except Exception:
                logger.exception("Cycle %d failed", cycle_count)

            logger.info("Next cycle in %ds...", INJECT_INTERVAL)
            remaining = INJECT_INTERVAL
            while remaining > 0:
                wait = min(remaining, 30)
                time.sleep(wait)
                remaining -= wait
                touch_heartbeat()
    finally:
        client.close()


if __name__ == "__main__":
    main()
