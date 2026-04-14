"""Passive turn ingestion endpoint."""
from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, Request

from auto_linker import auto_link
from classifier import get_classifier
from ingest_dedupe import action_fingerprint, lookback_limit
from ingest_filter import should_classify
from ingest_models import (
    ActionOutcome,
    IngestResponse,
    TurnPayload,
)
from ingest_persistence import (
    TurnEvent,
    compute_turn_hash,
    fetch_audit,
    fetch_global_stats,
    persist_turn_event,
)
from ingest_rate_limit import RateLimiter
from ingest_sanitize import sanitize_turn

logger = logging.getLogger(__name__)

_MEMORY_ID_RE = re.compile(r"memory_id=([0-9a-f-]{36})")
_STORED_PREFIXES = ("KNOWN ERROR: ", "DECISION: ")
_STORED_SEPARATORS = ("\nSOLUTION: ", "\nRationale: ")


def _canonicalize_stored(summary: str) -> dict[str, str]:
    """Reverse the format applied by store_error/store_decision so the
    fingerprint of a freshly-stored memory matches the originating action."""
    text = summary or ""
    for prefix in _STORED_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    for sep in _STORED_SEPARATORS:
        text = text.replace(sep, "\n")
    title, _, rest = text.partition("\n")
    return {"title": title.strip(), "content": rest.strip()}
_rate_limiter = RateLimiter()

_stats: dict[str, dict[str, int]] = defaultdict(lambda: {
    "turns": 0,
    "filtered": 0,
    "classified": 0,
    "stored": 0,
    "deduped": 0,
    "errors": 0,
    "links": 0,
    "classifier_ms_total": 0,
    "classifier_ms_count": 0,
})

_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = get_classifier()
    return _classifier


def _project_disabled(project: str) -> bool:
    raw = os.getenv("INGEST_DISABLED_PROJECTS", "")
    banned = [p.strip() for p in raw.split(",") if p.strip()]
    return project in banned


def _global_enabled() -> bool:
    return os.getenv("INGEST_ENABLED", "true").lower() == "true"


async def _fetch_recent_memories(project: str, limit: int, pg_pool) -> list[dict[str, Any]]:
    if not pg_pool:
        return []
    try:
        async with pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT m.id::text AS id, COALESCE(m.summary, '') AS content
                FROM memory_log m
                JOIN projects p ON m.project_id = p.id
                WHERE p.name = $1
                ORDER BY m.created_at DESC
                LIMIT $2
                """,
                project,
                limit,
            )
            return [_canonicalize_stored(r["content"]) for r in rows]
    except Exception as e:
        logger.warning("recent-memories fetch failed: %s", e)
        return []


def _extract_memory_id(store_result: str | None) -> str | None:
    if not store_result:
        return None
    m = _MEMORY_ID_RE.search(store_result)
    return m.group(1) if m else None


async def _execute_action(
    action,
    project: str,
    *,
    store_decision,
    store_error,
    store_memory,
    link_memories,
    qdrant,
    get_embedding,
) -> ActionOutcome:
    try:
        if action.type == "store_decision":
            result = await store_decision(
                title=action.title,
                decision=action.content,
                project=project,
                rationale="",
                alternatives="",
                tags=action.tags,
                agent_id="passive-ingest",
            )
        elif action.type == "store_error":
            result = await store_error(
                error_description=action.title,
                solution=action.content,
                project=project,
                error_signature="",
                tags=action.tags,
            )
        elif action.type in ("store_observation", "store_architecture"):
            memory_type = "observation" if action.type == "store_observation" else "architecture"
            result = await store_memory(
                content=f"{action.title}\n{action.content}",
                project=project,
                memory_type=memory_type,
                tags=action.tags,
                importance=action.importance,
                agent_id="passive-ingest",
                skip_similar=True,
            )
        else:
            return ActionOutcome(type=action.type, skipped=True, skip_reason="unknown_type")

        if isinstance(result, str) and result.startswith("ERROR"):
            return ActionOutcome(type=action.type, error=result)

        memory_id = _extract_memory_id(result if isinstance(result, str) else None)
        links_created = 0
        if memory_id:
            try:
                vec = await get_embedding(f"{action.title}\n{action.content}")
                links_created = await auto_link(
                    new_memory_id=memory_id,
                    new_memory_vector=vec,
                    project=project,
                    qdrant_client=qdrant,
                    link_memories_fn=link_memories,
                )
            except Exception as e:
                logger.warning("auto_link failed for %s: %s", memory_id, e)
        return ActionOutcome(type=action.type, memory_id=memory_id, links_created=links_created)
    except Exception as e:
        logger.exception("execute_action failed")
        return ActionOutcome(type=action.type, error=str(e))


def _build_event(payload: TurnPayload) -> TurnEvent:
    return TurnEvent(
        project=payload.project,
        session_id=payload.session_id or "",
        turn_id=payload.turn_id or "",
        user_len=len(payload.user_message or ""),
        assistant_len=len(payload.assistant_message or ""),
        tools_count=len(payload.tool_calls or []),
        turn_hash=compute_turn_hash(payload.user_message or "", payload.assistant_message or ""),
    )


def init_ingest_routes(app) -> None:
    # Lazy import of the server module to avoid circular-import at module load.
    import server  # api-server/server.py

    async def _persist(event: TurnEvent) -> None:
        await persist_turn_event(getattr(server, "pg_pool", None), event)

    @app.post("/ingest_turn", response_model=IngestResponse)
    async def ingest_turn(request: Request) -> IngestResponse:
        started = time.perf_counter()

        if not _global_enabled():
            return IngestResponse(
                status="ok",
                filtered=True,
                reason="global_disabled",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

        body = await request.json()
        try:
            payload = TurnPayload(**body)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))

        _stats[payload.project]["turns"] += 1
        event = _build_event(payload)

        if _project_disabled(payload.project):
            _stats[payload.project]["filtered"] += 1
            event.mark_filtered("project_disabled")
            await _persist(event)
            return IngestResponse(
                status="ok",
                filtered=True,
                reason="project_disabled",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

        if not _rate_limiter.allow(payload.session_id):
            _stats[payload.project]["filtered"] += 1
            event.mark_filtered("rate_limited")
            await _persist(event)
            return IngestResponse(
                status="ok",
                filtered=True,
                reason="rate_limited",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

        sanitized = sanitize_turn(payload.model_dump())
        ok, reason = should_classify(sanitized)
        if not ok:
            _stats[payload.project]["filtered"] += 1
            event.mark_filtered(reason)
            await _persist(event)
            return IngestResponse(
                status="ok",
                filtered=True,
                reason=reason,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

        clf = _get_classifier()
        clf_t0 = time.perf_counter()
        try:
            result = clf.classify(sanitized)
        except Exception as e:
            logger.exception("classifier failed")
            _stats[payload.project]["errors"] += 1
            event.mark_error(str(e)[:500])
            await _persist(event)
            return IngestResponse(
                status="error",
                stage="classifier",
                detail=str(e),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        clf_ms = int((time.perf_counter() - clf_t0) * 1000)
        _stats[payload.project]["classifier_ms_total"] += clf_ms
        _stats[payload.project]["classifier_ms_count"] += 1
        _stats[payload.project]["classified"] += 1
        event.mark_classified(clf_ms, [a.type for a in result.actions])

        recent = await _fetch_recent_memories(
            payload.project, lookback_limit(), getattr(server, "pg_pool", None)
        )
        outcomes: list[ActionOutcome] = []
        for action in result.actions:
            fp = action_fingerprint({"title": action.title, "content": action.content})
            if any(action_fingerprint(m) == fp for m in recent):
                _stats[payload.project]["deduped"] += 1
                event.deduped += 1
                outcomes.append(
                    ActionOutcome(type=action.type, skipped=True, skip_reason="duplicate")
                )
                continue
            outcome = await _execute_action(
                action,
                payload.project,
                store_decision=server.store_decision,
                store_error=server.store_error,
                store_memory=server.store_memory,
                link_memories=server.link_memories,
                qdrant=server.qdrant,
                get_embedding=server.get_embedding,
            )
            if outcome.memory_id and not outcome.error:
                _stats[payload.project]["stored"] += 1
                _stats[payload.project]["links"] += outcome.links_created
                event.stored += 1
                event.links += outcome.links_created
            elif outcome.error:
                _stats[payload.project]["errors"] += 1
                event.errors += 1
            outcomes.append(outcome)

        stored = sum(1 for o in outcomes if o.memory_id and not o.error)
        dedup_count = sum(1 for o in outcomes if o.skipped and o.skip_reason == "duplicate")
        logger.info(
            "ingest_turn project=%s turn=%s classifier_ms=%d emitted=%d stored=%d deduped=%d",
            payload.project, payload.turn_id, clf_ms, len(result.actions), stored, dedup_count,
        )
        await _persist(event)
        return IngestResponse(
            status="ok",
            filtered=False,
            actions_taken=stored,
            actions=outcomes,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    @app.get("/ingest/stats")
    async def ingest_stats(project: str | None = None, days: int = 7) -> dict[str, Any]:
        """Ingest observability.

        - `project=X` → backward-compatible project view from in-memory counters.
        - (no project) → global rollup from `ingest_daily_stats` over the last
          `days` days: per-project breakdown + totals + filter reasons.
        """
        if project:
            s = _stats.get(project, {})
            if not s:
                return {"project": project, "turns_ingested": 0}
            count = s["classifier_ms_count"]
            avg = (s["classifier_ms_total"] // count) if count else 0
            return {
                "project": project,
                "turns_ingested": s["turns"],
                "filtered": s["filtered"],
                "classified": s["classified"],
                "actions_stored": s["stored"],
                "deduped": s["deduped"],
                "avg_classifier_ms": avg,
                "errors": s["errors"],
                "links_created": s["links"],
            }
        pg_pool = getattr(server, "pg_pool", None)
        return await fetch_global_stats(pg_pool, days=max(1, min(days, 90)))

    @app.get("/ingest/audit")
    async def ingest_audit(
        project: str | None = None,
        outcome: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return the most recent classifier decisions for manual inspection.

        Filter by `project` and/or `outcome` (one of: filtered, accepted_empty,
        accepted_actions, error). This is the answer to "what is the classifier
        rejecting, and why?".
        """
        pg_pool = getattr(server, "pg_pool", None)
        rows = await fetch_audit(
            pg_pool,
            project=project,
            outcome=outcome,
            limit=max(1, min(limit, 500)),
        )
        return {"count": len(rows), "rows": rows}
