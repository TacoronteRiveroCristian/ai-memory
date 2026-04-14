"""Pure-Python unit tests for ingest_persistence helpers.

These tests do not hit Postgres — they cover the parts of the module that
are deterministic and do not need a live DB (turn hashing, audit-enabled
flag, TurnEvent state transitions, fetch_global_stats/fetch_audit no-op
when pg_pool is None).

DB-backed behavior is exercised by the integration tests in
test_observability_endpoints.py against a running stack.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from ingest_persistence import (
    OUTCOME_ACCEPTED_ACTIONS,
    OUTCOME_ACCEPTED_EMPTY,
    OUTCOME_ERROR,
    OUTCOME_FILTERED,
    TurnEvent,
    audit_enabled,
    compute_turn_hash,
    fetch_audit,
    fetch_global_stats,
    persist_turn_event,
)


def _event(**overrides):
    base = dict(
        project="proj-unit",
        session_id="sess",
        turn_id="turn",
        user_len=30,
        assistant_len=40,
        tools_count=1,
        turn_hash="abc123",
    )
    base.update(overrides)
    return TurnEvent(**base)


def test_compute_turn_hash_is_stable_and_short():
    h1 = compute_turn_hash("hola", "mundo")
    h2 = compute_turn_hash("hola", "mundo")
    assert h1 == h2
    assert len(h1) == 16
    assert h1 != compute_turn_hash("hola", "mundoz")


def test_compute_turn_hash_handles_empty():
    assert compute_turn_hash("", "") == compute_turn_hash("", "")
    assert compute_turn_hash(None, None) == compute_turn_hash("", "")  # type: ignore[arg-type]


def test_compute_turn_hash_truncates_at_4000_chars():
    prefix = "x" * 3990
    a = compute_turn_hash(prefix + "A" * 100, "")
    b = compute_turn_hash(prefix + "A" * 200, "")
    # Both collapse at the 4000-char window → equal hash.
    assert a == b


def test_audit_enabled_default_true(monkeypatch):
    monkeypatch.delenv("INGEST_AUDIT_ENABLED", raising=False)
    assert audit_enabled() is True


def test_audit_enabled_respects_false(monkeypatch):
    monkeypatch.setenv("INGEST_AUDIT_ENABLED", "false")
    assert audit_enabled() is False
    monkeypatch.setenv("INGEST_AUDIT_ENABLED", "FALSE")
    assert audit_enabled() is False


def test_turn_event_mark_filtered_sets_outcome_and_reason():
    e = _event()
    e.mark_filtered("rate_limited")
    assert e.outcome == OUTCOME_FILTERED
    assert e.filter_reason == "rate_limited"


def test_turn_event_mark_classified_empty_vs_actions():
    e = _event()
    e.mark_classified(120, [])
    assert e.outcome == OUTCOME_ACCEPTED_EMPTY
    assert e.classifier_ms == 120
    assert e.action_types == []

    e2 = _event()
    e2.mark_classified(80, ["store_decision", "store_error"])
    assert e2.outcome == OUTCOME_ACCEPTED_ACTIONS
    assert e2.action_types == ["store_decision", "store_error"]


def test_turn_event_mark_error_increments_errors():
    e = _event()
    e.mark_error("classifier timeout")
    assert e.outcome == OUTCOME_ERROR
    assert e.error_detail == "classifier timeout"
    assert e.errors == 1


def test_persist_turn_event_noop_when_pg_pool_none():
    # Must not raise, must not touch anything.
    asyncio.run(persist_turn_event(None, _event()))


def test_fetch_global_stats_noop_when_pg_pool_none():
    result = asyncio.run(fetch_global_stats(None))
    assert result["projects"] == {}
    assert result["totals"]["turns"] == 0
    assert result["window_days"] == 7


def test_fetch_audit_noop_when_pg_pool_none():
    assert asyncio.run(fetch_audit(None)) == []
    assert asyncio.run(fetch_audit(None, project="x", outcome="error", limit=10)) == []
