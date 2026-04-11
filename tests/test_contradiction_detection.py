"""Tests for proactive contradiction detection during auto-linking."""

import json
import time


def test_contradiction_detected_automatically(brain_client, unique_project_name):
    """Storing contradictory memories should produce a contradicts relation or
    evidence with a positive contradiction_score."""
    project = unique_project_name("contra")

    mem_a = brain_client.create_memory(
        content="Usar Redis para cache de embeddings es la mejor práctica en producción",
        project=project,
        memory_type="decision",
        tags="redis,cache,embeddings",
        importance=0.85,
        agent_id="pytest",
    )["memory_id"]

    # Small pause so auto-link can run against first memory
    time.sleep(0.5)

    mem_b = brain_client.create_memory(
        content="No usar Redis para cache, usar Memcached porque Redis consume demasiada memoria",
        project=project,
        memory_type="decision",
        tags="redis,cache,memcached",
        importance=0.85,
        agent_id="pytest",
    )["memory_id"]

    time.sleep(0.5)

    # Check relations for either memory
    rels_a = brain_client.relations(mem_a).get("relations", [])
    rels_b = brain_client.relations(mem_b).get("relations", [])
    all_rels = rels_a + rels_b

    # Accept if any relation is type contradicts OR has positive contradiction_score in evidence.
    # In test mode (hash-based embeddings), only negation patterns fire so the score is lower
    # than the full contradicts threshold, but should still be > 0.
    has_contradiction_signal = False
    for rel in all_rels:
        if rel.get("relation_type") == "contradicts":
            has_contradiction_signal = True
            break
        raw_evidence = rel.get("evidence_json") or rel.get("evidence") or {}
        evidence = json.loads(raw_evidence) if isinstance(raw_evidence, str) else raw_evidence
        if isinstance(evidence, dict):
            cscore = evidence.get("contradiction_score", 0)
            if cscore and float(cscore) > 0:
                has_contradiction_signal = True
                break

    assert has_contradiction_signal, (
        f"Expected contradiction signal between memories, got relations: {all_rels}"
    )


def test_no_false_contradiction(brain_client, unique_project_name):
    """Two agreeing memories about the same topic should NOT produce a
    contradicts relation."""
    project = unique_project_name("nocontra")

    mem_a = brain_client.create_memory(
        content="Redis es excelente para cache de embeddings por su velocidad",
        project=project,
        memory_type="observation",
        tags="redis,cache",
        importance=0.85,
        agent_id="pytest",
    )["memory_id"]

    time.sleep(0.5)

    mem_b = brain_client.create_memory(
        content="Redis mejora significativamente la latencia del cache de embeddings",
        project=project,
        memory_type="observation",
        tags="redis,cache",
        importance=0.85,
        agent_id="pytest",
    )["memory_id"]

    time.sleep(0.5)

    rels_a = brain_client.relations(mem_a).get("relations", [])
    rels_b = brain_client.relations(mem_b).get("relations", [])
    all_rels = rels_a + rels_b

    contradicts_rels = [r for r in all_rels if r.get("relation_type") == "contradicts"]
    assert len(contradicts_rels) == 0, (
        f"Did not expect contradicts relations between agreeing memories, got: {contradicts_rels}"
    )
