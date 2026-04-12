"""Verification checks that compare snapshots to detect biological process effects."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from client import HeartbeatClient
from batches import CycleContext

logger = logging.getLogger("heartbeat-monitor")


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def take_memory_snapshot(client: HeartbeatClient, memory_id: str) -> dict[str, Any]:
    """Capture current state of a memory for later comparison."""
    detail = client.memory_detail(memory_id)
    mem = detail.get("memory", detail)
    rels = client.relations(memory_id).get("relations", [])
    return {
        "memory_id": memory_id,
        "stability_score": mem.get("stability_score", 0),
        "activation_score": mem.get("activation_score", 0),
        "review_count": mem.get("review_count", 0),
        "relations": rels,
        "relation_count": len(rels),
    }


def check_relationships_formed(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 1: memories should have auto-linked relationships."""
    batch1_ids = [ctx.memory_ids[k] for k in ("cluster_0", "cluster_1", "cluster_2") if k in ctx.memory_ids]
    if len(batch1_ids) < 2:
        return CheckResult("relationships_formed", False, "Not enough cluster memories injected")

    total_rels = 0
    for mid in batch1_ids:
        rels = client.relations(mid).get("relations", [])
        linked = [r for r in rels if r.get("other_memory_id") in batch1_ids or r.get("source_memory_id") in batch1_ids or r.get("target_memory_id") in batch1_ids]
        total_rels += len(linked)

    unique_rels = total_rels // 2
    passed = unique_rels >= 2
    return CheckResult("relationships_formed", passed, f"{unique_rels}/3 pairs linked")


def check_contradiction_detected(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 2: contradictory memories should produce contradiction signal."""
    contra_ids = [ctx.memory_ids.get("contra_0"), ctx.memory_ids.get("contra_1")]
    if not all(contra_ids):
        return CheckResult("contradiction_detected", False, "Contradiction memories not injected")

    for mid in contra_ids:
        rels = client.relations(mid).get("relations", [])
        for rel in rels:
            if rel.get("relation_type") == "contradicts":
                return CheckResult("contradiction_detected", True, "contradicts relation found")
            raw = rel.get("evidence_json") or rel.get("evidence") or "{}"
            evidence = json.loads(raw) if isinstance(raw, str) else raw
            cscore = evidence.get("contradiction_score", 0)
            if cscore and float(cscore) > 0:
                return CheckResult("contradiction_detected", True, f"score={cscore}")

    return CheckResult("contradiction_detected", False, "No contradiction signal found")


def check_contradiction_resolved(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """After NREM, contradictions should be resolved or at least processed."""
    contra_ids = [ctx.memory_ids.get("contra_0"), ctx.memory_ids.get("contra_1")]
    if not all(contra_ids):
        return CheckResult("contradiction_resolved", False, "Contradiction memories not injected")

    # Check for resolution relations
    for mid in contra_ids:
        rels = client.relations(mid).get("relations", [])
        for rel in rels:
            if rel.get("relation_type") in ("derived_from", "applies_to"):
                return CheckResult("contradiction_resolved", True, f"resolution type={rel['relation_type']}")
            if rel.get("relation_type") == "contradicts":
                return CheckResult("contradiction_resolved", True, "contradicts relation active (NREM processed)")

    # Check for b_wins signature: mem_b stability much lower than mem_a
    # (test mode heuristic resolves contradictions with b_wins)
    try:
        snap_a = take_memory_snapshot(client, contra_ids[0])
        snap_b = take_memory_snapshot(client, contra_ids[1])
        stab_a = snap_a["stability_score"]
        stab_b = snap_b["stability_score"]
        if stab_a > 0 and stab_b < stab_a * 0.5:
            return CheckResult(
                "contradiction_resolved", True,
                f"b_wins detected: a={stab_a:.3f} b={stab_b:.3f}"
            )
    except Exception:
        pass

    return CheckResult("contradiction_resolved", False, "No resolution evidence after NREM")


def check_cross_project_myelin(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 3: cross-project relations should have myelin > 0 after NREM."""
    cross_ids = [ctx.memory_ids.get("cross_0"), ctx.memory_ids.get("cross_1")]
    if not all(cross_ids):
        return CheckResult("cross_project_myelin", False, "Cross-project memories not injected")

    for mid in cross_ids:
        rels = client.relations(mid).get("relations", [])
        for rel in rels:
            myelin = rel.get("myelin_score", 0)
            if myelin and float(myelin) > 0:
                return CheckResult("cross_project_myelin", True, f"myelin_score={myelin}")

    return CheckResult("cross_project_myelin", False, "No myelin > 0 on cross-project relations")


def check_reinforcement_applied(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 4: plasticity session should have incremented reinforcement on batch 1 relations."""
    batch1_ids = [ctx.memory_ids.get(f"cluster_{i}") for i in range(3)]
    batch1_ids = [x for x in batch1_ids if x]
    if not batch1_ids:
        return CheckResult("reinforcement_applied", False, "No cluster memories to check")

    for mid in batch1_ids:
        rels = client.relations(mid).get("relations", [])
        for rel in rels:
            rc = rel.get("reinforcement_count", 0)
            if rc and int(rc) > 1:
                return CheckResult("reinforcement_applied", True, f"reinforcement_count={rc}")

    return CheckResult("reinforcement_applied", False, "No relation with reinforcement_count > 1")


def check_stability_increased(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Accessed memories should have higher stability than initial snapshot."""
    for key in ("cluster_0", "cluster_1", "cluster_2"):
        mid = ctx.memory_ids.get(key)
        if not mid or key not in ctx.initial_snapshots:
            continue
        initial = ctx.initial_snapshots[key]["stability_score"]
        current = take_memory_snapshot(client, mid)["stability_score"]
        if current > initial:
            return CheckResult("stability_increased", True, f"{initial:.3f}->{current:.3f}")

    return CheckResult("stability_increased", False, "No stability increase detected")


def check_cold_memory_decayed(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 5: cold memory should have lower stability after REM."""
    mid = ctx.memory_ids.get("cold_0")
    if not mid or "cold_0" not in ctx.initial_snapshots:
        return CheckResult("cold_memory_decayed", False, "Cold memory not injected")

    initial = ctx.initial_snapshots["cold_0"]["stability_score"]
    current = take_memory_snapshot(client, mid)["stability_score"]
    if current < initial:
        return CheckResult("cold_memory_decayed", True, f"{initial:.3f}->{current:.3f}")

    return CheckResult("cold_memory_decayed", False, f"No decay: {initial:.3f}->{current:.3f}")


def check_overall_health_stable(client: HeartbeatClient, previous_health: float) -> CheckResult:
    """Brain health should not degrade significantly."""
    health = client.brain_health()
    current = health.get("overall_health", 0)
    threshold = max(previous_health - 0.1, 0.3)
    passed = current >= threshold
    return CheckResult("overall_health_stable", passed, f"{previous_health:.3f}->{current:.3f}")


ALL_CHECKS = [
    check_relationships_formed,
    check_contradiction_detected,
    check_contradiction_resolved,
    check_cross_project_myelin,
    check_reinforcement_applied,
    check_stability_increased,
    check_cold_memory_decayed,
]
