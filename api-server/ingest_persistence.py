"""Persistent observability for the passive-ingest pipeline.

Two tables, both idempotent via run_schema_migrations:

    ingest_daily_stats(day, project, ...)  -- one row per (day, project),
        incrementally upserted. Counts turns, filtered-by-reason, classified,
        stored, deduped, errors, links, classifier-ms aggregates.

    classifier_audit(id, ts, project, ...)  -- one row per classified turn,
        toggleable via INGEST_AUDIT_ENABLED. Persists the outcome so we can
        later answer "what did the classifier reject, and why?".

The module is intentionally dependency-light: callers pass in a pg_pool and
a small event description. Failures here never break the ingest path — we
log and swallow.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


OUTCOME_FILTERED = "filtered"
OUTCOME_ACCEPTED_EMPTY = "accepted_empty"
OUTCOME_ACCEPTED_ACTIONS = "accepted_actions"
OUTCOME_ERROR = "error"


def audit_enabled() -> bool:
    return os.getenv("INGEST_AUDIT_ENABLED", "true").lower() == "true"


def compute_turn_hash(user_message: str, assistant_message: str) -> str:
    """Stable short hash over the turn payload (for de-dup / audit correlation)."""
    material = f"{user_message or ''}||{assistant_message or ''}"[:4000]
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


@dataclass
class TurnEvent:
    """Accumulator describing what happened during one ingest_turn call.

    The handler mutates this as it progresses and passes the final event to
    `persist_turn_event` exactly once, right before returning the HTTP response.
    """

    project: str
    session_id: str
    turn_id: str
    user_len: int
    assistant_len: int
    tools_count: int
    turn_hash: str

    outcome: str = OUTCOME_FILTERED  # reset by the handler as it progresses
    filter_reason: str | None = None
    classifier_ms: int | None = None
    action_types: list[str] = field(default_factory=list)
    stored: int = 0
    deduped: int = 0
    errors: int = 0
    links: int = 0
    error_detail: str | None = None

    def mark_filtered(self, reason: str) -> None:
        self.outcome = OUTCOME_FILTERED
        self.filter_reason = reason

    def mark_error(self, detail: str) -> None:
        self.outcome = OUTCOME_ERROR
        self.error_detail = detail
        self.errors += 1

    def mark_classified(self, ms: int, action_types: list[str]) -> None:
        self.classifier_ms = ms
        self.action_types = list(action_types)
        self.outcome = OUTCOME_ACCEPTED_ACTIONS if action_types else OUTCOME_ACCEPTED_EMPTY


async def persist_turn_event(pg_pool, event: TurnEvent) -> None:
    """Write one TurnEvent to both `ingest_daily_stats` and `classifier_audit`.

    Failures are logged and swallowed — the ingest response must not fail
    because observability plumbing had a bad day.
    """
    if pg_pool is None:
        return
    try:
        async with pg_pool.acquire() as conn:
            async with conn.transaction():
                await _upsert_daily_stats(conn, event)
                if audit_enabled():
                    await _insert_audit_row(conn, event)
    except Exception as e:  # noqa: BLE001
        logger.warning("persist_turn_event failed (project=%s): %s", event.project, e)


async def _upsert_daily_stats(conn, event: TurnEvent) -> None:
    filtered_delta = 1 if event.outcome == OUTCOME_FILTERED else 0
    classified_delta = 1 if event.outcome in (OUTCOME_ACCEPTED_EMPTY, OUTCOME_ACCEPTED_ACTIONS) else 0
    clf_ms_total = int(event.classifier_ms or 0)
    clf_ms_count = 1 if event.classifier_ms is not None else 0
    reason_patch = (
        json.dumps({event.filter_reason: 1})
        if filtered_delta and event.filter_reason
        else "{}"
    )

    await conn.execute(
        """
        INSERT INTO ingest_daily_stats (
            day, project, turns, filtered, filtered_by_reason,
            classified, stored, deduped, errors, links,
            classifier_ms_total, classifier_ms_count, last_turn_at
        ) VALUES (
            CURRENT_DATE, $1, 1, $2, $3::jsonb,
            $4, $5, $6, $7, $8,
            $9, $10, NOW()
        )
        ON CONFLICT (day, project) DO UPDATE SET
            turns = ingest_daily_stats.turns + 1,
            filtered = ingest_daily_stats.filtered + EXCLUDED.filtered,
            filtered_by_reason = CASE
                WHEN EXCLUDED.filtered = 0 THEN ingest_daily_stats.filtered_by_reason
                ELSE jsonb_set(
                    ingest_daily_stats.filtered_by_reason,
                    ARRAY[COALESCE($11::text, '__unknown__')],
                    to_jsonb(
                        COALESCE(
                            (ingest_daily_stats.filtered_by_reason
                                ->> COALESCE($11::text, '__unknown__'))::int,
                            0
                        ) + 1
                    ),
                    true
                )
            END,
            classified = ingest_daily_stats.classified + EXCLUDED.classified,
            stored = ingest_daily_stats.stored + EXCLUDED.stored,
            deduped = ingest_daily_stats.deduped + EXCLUDED.deduped,
            errors = ingest_daily_stats.errors + EXCLUDED.errors,
            links = ingest_daily_stats.links + EXCLUDED.links,
            classifier_ms_total = ingest_daily_stats.classifier_ms_total + EXCLUDED.classifier_ms_total,
            classifier_ms_count = ingest_daily_stats.classifier_ms_count + EXCLUDED.classifier_ms_count,
            last_turn_at = NOW()
        """,
        event.project,
        filtered_delta,
        reason_patch,
        classified_delta,
        event.stored,
        event.deduped,
        event.errors,
        event.links,
        clf_ms_total,
        clf_ms_count,
        event.filter_reason,
    )


async def _insert_audit_row(conn, event: TurnEvent) -> None:
    await conn.execute(
        """
        INSERT INTO classifier_audit (
            project, session_id, turn_id, turn_hash,
            user_len, assistant_len, tools_count,
            outcome, filter_reason, action_types,
            classifier_ms, error_detail
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """,
        event.project,
        event.session_id,
        event.turn_id,
        event.turn_hash,
        event.user_len,
        event.assistant_len,
        event.tools_count,
        event.outcome,
        event.filter_reason,
        event.action_types,
        event.classifier_ms,
        event.error_detail,
    )


async def fetch_global_stats(pg_pool, *, days: int = 7) -> dict[str, Any]:
    """Per-project rollup over the last N days + grand totals.

    Shape:
        {
          "window_days": 7,
          "generated_at": "...",
          "projects": {
             "<name>": { turns, filtered, filtered_by_reason, classified,
                         stored, deduped, errors, links, avg_classifier_ms,
                         last_turn_at }
          },
          "totals": { turns, filtered, classified, stored, deduped, errors, links }
        }
    """
    if pg_pool is None:
        return {"window_days": days, "projects": {}, "totals": _empty_totals()}
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT project,
                   SUM(turns) AS turns,
                   SUM(filtered) AS filtered,
                   SUM(classified) AS classified,
                   SUM(stored) AS stored,
                   SUM(deduped) AS deduped,
                   SUM(errors) AS errors,
                   SUM(links) AS links,
                   SUM(classifier_ms_total) AS clf_ms_total,
                   SUM(classifier_ms_count) AS clf_ms_count,
                   MAX(last_turn_at) AS last_turn_at
            FROM ingest_daily_stats
            WHERE day >= CURRENT_DATE - ($1::int - 1)
            GROUP BY project
            ORDER BY MAX(last_turn_at) DESC NULLS LAST
            """,
            days,
        )
        reason_rows = await conn.fetch(
            """
            SELECT project, filtered_by_reason
            FROM ingest_daily_stats
            WHERE day >= CURRENT_DATE - ($1::int - 1)
            """,
            days,
        )

    reasons_by_project: dict[str, dict[str, int]] = {}
    for r in reason_rows:
        fbr = r["filtered_by_reason"] or {}
        if isinstance(fbr, str):
            try:
                fbr = json.loads(fbr)
            except json.JSONDecodeError:
                fbr = {}
        bucket = reasons_by_project.setdefault(r["project"], {})
        for k, v in fbr.items():
            bucket[k] = bucket.get(k, 0) + int(v)

    projects: dict[str, Any] = {}
    totals = _empty_totals()
    for row in rows:
        p = row["project"]
        count = int(row["clf_ms_count"] or 0)
        avg = int((row["clf_ms_total"] or 0) // count) if count else 0
        projects[p] = {
            "turns": int(row["turns"] or 0),
            "filtered": int(row["filtered"] or 0),
            "filtered_by_reason": reasons_by_project.get(p, {}),
            "classified": int(row["classified"] or 0),
            "stored": int(row["stored"] or 0),
            "deduped": int(row["deduped"] or 0),
            "errors": int(row["errors"] or 0),
            "links": int(row["links"] or 0),
            "avg_classifier_ms": avg,
            "last_turn_at": row["last_turn_at"].isoformat() if row["last_turn_at"] else None,
        }
        for k in totals:
            totals[k] += projects[p][k]
    return {"window_days": days, "projects": projects, "totals": totals}


def _empty_totals() -> dict[str, int]:
    return {
        "turns": 0,
        "filtered": 0,
        "classified": 0,
        "stored": 0,
        "deduped": 0,
        "errors": 0,
        "links": 0,
    }


async def fetch_audit(
    pg_pool,
    *,
    project: str | None = None,
    outcome: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if pg_pool is None:
        return []
    where = []
    args: list[Any] = []
    if project:
        args.append(project)
        where.append(f"project = ${len(args)}")
    if outcome:
        args.append(outcome)
        where.append(f"outcome = ${len(args)}")
    args.append(limit)
    limit_idx = len(args)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT id, ts, project, session_id, turn_id, turn_hash,
               user_len, assistant_len, tools_count, outcome,
               filter_reason, action_types, classifier_ms, error_detail
        FROM classifier_audit
        {where_sql}
        ORDER BY ts DESC
        LIMIT ${limit_idx}
    """
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
    return [
        {
            "id": int(r["id"]),
            "ts": r["ts"].isoformat() if r["ts"] else None,
            "project": r["project"],
            "session_id": r["session_id"],
            "turn_id": r["turn_id"],
            "turn_hash": r["turn_hash"],
            "user_len": int(r["user_len"]),
            "assistant_len": int(r["assistant_len"]),
            "tools_count": int(r["tools_count"]),
            "outcome": r["outcome"],
            "filter_reason": r["filter_reason"],
            "action_types": list(r["action_types"] or []),
            "classifier_ms": int(r["classifier_ms"]) if r["classifier_ms"] is not None else None,
            "error_detail": r["error_detail"],
        }
        for r in rows
    ]
