"""Integration tests for deep sleep evolution (NREM/REM phases, adaptive myelin, improved synthesis)."""

from __future__ import annotations

import uuid
from typing import Any


def minimal_session_payload(project: str) -> dict[str, Any]:
    return {
        "project": project,
        "agent_id": "pytest",
        "session_id": f"session-dse-{uuid.uuid4().hex[:8]}",
        "goal": "Deep sleep evolution validation",
        "outcome": "Plasticity tick completed",
        "summary": "Validate plasticity response fields after deep sleep evolution refactor.",
        "changes": [],
        "decisions": [],
        "errors": [],
        "follow_ups": [],
        "tags": ["tests", "deep-sleep-evolution"],
    }


def test_plasticity_session_returns_all_fields(brain_client, unique_project_name):
    """Plasticity response should contain all expected fields."""
    project = unique_project_name("dse-plasticity")

    # Create memories so plasticity has something to work with
    brain_client.create_memory(
        content="Adaptive myelin decay uses reinforcement count to slow forgetting of well-used pathways.",
        project=project,
        memory_type="observation",
        tags="myelin,adaptive-decay",
        importance=0.8,
        agent_id="pytest",
    )
    brain_client.create_memory(
        content="NREM phase strengthens schemas and validates suspected contradictions before pruning.",
        project=project,
        memory_type="observation",
        tags="nrem,sleep-phase",
        importance=0.75,
        agent_id="pytest",
    )

    # Record a session so plasticity has context
    brain_client.record_session(
        project=project,
        agent_id="pytest",
        session_id=f"session-dse-fields-{uuid.uuid4().hex[:8]}",
        summary="Testing adaptive myelin and NREM phase validation.",
        goal="Verify plasticity response completeness",
        outcome="All fields present",
        changes=["Added adaptive myelin decay"],
        decisions=[],
        errors=[],
        follow_ups=[],
    )

    # Apply plasticity
    plasticity = brain_client.apply_session_plasticity(**minimal_session_payload(project))

    expected_keys = {
        "activated_memories",
        "reinforced_pairs",
        "expanded_links",
        "decayed_relations",
        "decayed_stability",
        "consolidated_activations",
    }
    missing = expected_keys - set(plasticity.keys())
    assert not missing, f"Missing keys in plasticity response: {missing}"


def test_brain_health_endpoint(brain_client):
    """Brain health endpoint returns status."""
    health = brain_client.brain_health()
    assert "overall_health" in health
