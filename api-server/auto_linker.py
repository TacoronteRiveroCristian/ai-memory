"""Semantic top-k auto-linker. Runs after every successful store_*."""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _topk() -> int:
    return int(os.getenv("INGEST_AUTOLINK_TOPK", "3"))


def _threshold() -> float:
    return float(os.getenv("INGEST_AUTOLINK_THRESHOLD", "0.75"))


def _relation() -> str:
    return os.getenv("INGEST_AUTOLINK_RELATION", "related")


async def auto_link(
    *,
    new_memory_id: str,
    new_memory_vector: list[float],
    project: str,
    qdrant_client: Any,
    link_memories_fn,
) -> int:
    """Search top-k nearest memories and create links. Returns count of links created."""
    try:
        result = await qdrant_client.query_points(
            collection_name=project,
            query=new_memory_vector,
            limit=_topk() + 1,
            score_threshold=_threshold(),
            with_payload=False,
        )
        points = getattr(result, "points", None) or result
    except Exception as e:
        logger.warning("auto_linker qdrant query failed: %s", e)
        return 0

    created = 0
    relation = _relation()
    for p in points:
        pid = getattr(p, "id", None)
        if pid is None and isinstance(p, dict):
            pid = p.get("id")
        if not pid or str(pid) == str(new_memory_id):
            continue
        score = getattr(p, "score", None)
        if score is None and isinstance(p, dict):
            score = p.get("score")
        try:
            reason = (
                f"auto-linked by passive ingest, similarity={score:.3f}"
                if isinstance(score, (int, float))
                else "auto-linked by passive ingest"
            )
            await link_memories_fn(
                source_memory_id=str(new_memory_id),
                target_memory_id=str(pid),
                relation_type=relation,
                reason=reason,
            )
            created += 1
            if created >= _topk():
                break
        except Exception as e:
            logger.warning("auto_linker link_memories failed for %s -> %s: %s",
                           new_memory_id, pid, e)
    return created
