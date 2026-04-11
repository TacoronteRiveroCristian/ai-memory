"""Tests for activation consolidation (Redis -> DB) during plasticity sessions."""

import time


def test_plasticity_session_includes_consolidation_key(brain_client, unique_project_name):
    """After creating memories and triggering a plasticity session, the response
    should contain the consolidated_activations key."""
    project = unique_project_name("consolid")

    # Seed a few memories so the plasticity session has something to work with
    brain_client.create_memory(
        content="FastAPI server handles all memory CRUD operations",
        project=project,
        memory_type="observation",
        tags=["fastapi", "server"],
        importance=0.85,
        agent_id="pytest",
    )
    brain_client.create_memory(
        content="Qdrant provides vector similarity search for embeddings",
        project=project,
        memory_type="observation",
        tags=["qdrant", "search"],
        importance=0.85,
        agent_id="pytest",
    )
    brain_client.create_memory(
        content="Redis caches embeddings to reduce OpenAI API calls",
        project=project,
        memory_type="decision",
        tags=["redis", "cache"],
        importance=0.85,
        agent_id="pytest",
    )

    time.sleep(0.5)

    session_id = f"session-{project}"

    # Record the session first
    brain_client.record_session(
        project=project,
        agent_id="pytest",
        session_id=session_id,
        goal="Understand how embeddings are cached",
        outcome="Confirmed Redis is used for embedding cache",
        summary="Reviewed the memory architecture and caching layer",
        changes=["Updated cache TTL configuration"],
        decisions=[],
        errors=[],
        follow_ups=[],
        tags=["redis", "cache", "architecture"],
    )

    result = brain_client.apply_session_plasticity(
        project=project,
        agent_id="pytest",
        session_id=session_id,
        summary="Reviewed the memory architecture and caching layer",
        goal="Understand how embeddings are cached",
        outcome="Confirmed Redis is used for embedding cache",
        changes=["Updated cache TTL configuration"],
        decisions=[],
        errors=[],
        follow_ups=[],
        tags=["redis", "cache", "architecture"],
    )

    assert "consolidated_activations" in result, (
        f"Expected 'consolidated_activations' key in plasticity response, got keys: {list(result.keys())}"
    )
    assert isinstance(result["consolidated_activations"], int)
