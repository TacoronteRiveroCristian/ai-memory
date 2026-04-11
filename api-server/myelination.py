"""Layer 1 — Myelination and Permeability.

Manages myelin_score on cross-project relations and project permeability.
"""

import logging
from typing import Optional

import asyncpg

logger = logging.getLogger("ai-memory-brain")

# Myelination deltas
MYELIN_DELTA_DIRECT_ACCESS = 0.05
MYELIN_DELTA_CO_ACTIVATION = 0.02
MYELIN_DELTA_CONSOLIDATION_VALIDATION = 0.08
MYELIN_DELTA_UTILITY_BONUS = 0.03
MYELIN_DELTA_DECAY_PER_CYCLE = -0.01
MYELIN_DELTA_COACTIVATION = 0.03
MYELIN_DELTA_REM_PRUNE = -0.05
PERMEABILITY_INCREMENT = 0.01
PERMEABILITY_MANUAL_BRIDGE = 0.3
PERMEABILITY_THRESHOLD = 0.15
PERMEABILITY_DECAY_PER_CYCLE = -0.005
PERMEABILITY_CO_ACTIVATION = 0.005


def compute_myelin_decay_rate(base_decay: float, reinforcement_count: int) -> float:
    """Adaptive decay — frequently reinforced paths resist forgetting."""
    return base_decay / (1.0 + 0.3 * reinforcement_count)


def compute_max_myelin(reinforcement_count: int) -> float:
    """Adaptive ceiling — grows with reinforcement, capped at 1.0."""
    return min(1.0, 0.5 + 0.05 * reinforcement_count)


async def record_myelination_event(
    conn: asyncpg.Connection,
    relation_id: Optional[str],
    permeability_id: Optional[int],
    event_type: str,
    delta: float,
    new_score: float,
) -> None:
    """Record a myelination event in the audit log."""
    await conn.execute(
        """
        INSERT INTO myelination_events (relation_id, permeability_id, event_type, delta, new_score)
        VALUES ($1, $2, $3, $4, $5)
        """,
        relation_id,
        permeability_id,
        event_type,
        delta,
        new_score,
    )


async def update_myelin_score(
    conn: asyncpg.Connection,
    relation_id: str,
    delta: float,
    event_type: str,
) -> float:
    """Update myelin_score on a relation with adaptive ceiling and record the event."""
    import uuid as _uuid

    rid = _uuid.UUID(relation_id) if isinstance(relation_id, str) else relation_id

    # Fetch reinforcement_count for adaptive ceiling
    rc_row = await conn.fetchrow(
        "SELECT reinforcement_count FROM memory_relations WHERE id = $1",
        rid,
    )
    reinforcement_count = int(rc_row["reinforcement_count"]) if rc_row else 0
    max_myelin = compute_max_myelin(reinforcement_count)

    row = await conn.fetchrow(
        """
        UPDATE memory_relations
        SET myelin_score = GREATEST(0.0, LEAST($3, myelin_score + $2)),
            myelin_last_updated = NOW()
        WHERE id = $1
        RETURNING myelin_score
        """,
        rid,
        delta,
        max_myelin,
    )
    new_score = float(row["myelin_score"]) if row else 0.0
    if new_score <= 0.0 and delta < 0:
        await conn.execute(
            "UPDATE memory_relations SET active = FALSE WHERE id = $1",
            rid,
        )
    await record_myelination_event(conn, relation_id, None, event_type, delta, new_score)
    return new_score


async def ensure_permeability(
    conn: asyncpg.Connection,
    project_name: str,
    related_project_name: str,
    organic: bool = True,
    reason: str = "",
) -> int:
    """Get or create a permeability record. Returns permeability_id."""
    row = await conn.fetchrow(
        """
        INSERT INTO project_permeability (project_id, related_project_id, organic_origin, formation_reason)
        VALUES (
            (SELECT id FROM projects WHERE name = $1 LIMIT 1),
            (SELECT id FROM projects WHERE name = $2 LIMIT 1),
            $3, $4
        )
        ON CONFLICT (project_id, related_project_id) DO UPDATE
            SET last_activity = NOW()
        RETURNING id
        """,
        project_name,
        related_project_name,
        organic,
        reason,
    )
    return row["id"]


async def increment_permeability(
    conn: asyncpg.Connection,
    project_name: str,
    related_project_name: str,
    delta: float = PERMEABILITY_INCREMENT,
    event_type: str = "synapse_reinforcement",
) -> float:
    """Increment permeability between two projects."""
    perm_id = await ensure_permeability(
        conn, project_name, related_project_name, organic=True
    )
    row = await conn.fetchrow(
        """
        UPDATE project_permeability
        SET permeability_score = LEAST(1.0, permeability_score + $2),
            last_activity = NOW()
        WHERE id = $1
        RETURNING permeability_score
        """,
        perm_id,
        delta,
    )
    new_score = float(row["permeability_score"]) if row else 0.0
    await record_myelination_event(conn, None, perm_id, event_type, delta, new_score)
    return new_score


async def get_permeability_score(
    conn: asyncpg.Connection,
    project_name: str,
    related_project_name: str,
) -> float:
    """Get permeability score between two projects."""
    row = await conn.fetchrow(
        """
        SELECT permeability_score FROM project_permeability
        WHERE project_id = (SELECT id FROM projects WHERE name = $1 LIMIT 1)
          AND related_project_id = (SELECT id FROM projects WHERE name = $2 LIMIT 1)
        """,
        project_name,
        related_project_name,
    )
    return float(row["permeability_score"]) if row else 0.0


async def get_permeable_projects(
    conn: asyncpg.Connection,
    project_name: str,
    threshold: float = PERMEABILITY_THRESHOLD,
) -> list[str]:
    """Get project names with permeability >= threshold (replaces project_bridges query)."""
    rows = await conn.fetch(
        """
        SELECT p.name
        FROM project_permeability pp
        JOIN projects p ON p.id = pp.related_project_id
        WHERE pp.project_id = (SELECT id FROM projects WHERE name = $1 LIMIT 1)
          AND pp.permeability_score >= $2
        UNION
        SELECT p.name
        FROM project_permeability pp
        JOIN projects p ON p.id = pp.project_id
        WHERE pp.related_project_id = (SELECT id FROM projects WHERE name = $1 LIMIT 1)
          AND pp.permeability_score >= $2
        """,
        project_name,
        threshold,
    )
    return [str(row["name"]) for row in rows]


async def strengthen_coactivated_myelin(conn: asyncpg.Connection) -> int:
    """Strengthen myelin on cross-project relations where both endpoints were recently co-accessed.

    Finds relations where both source and target memories were accessed within 1 hour of each other,
    increments myelin_score by MYELIN_DELTA_COACTIVATION respecting the adaptive ceiling,
    and logs a coactivation event.
    """
    rows = await conn.fetch(
        """
        SELECT mr.id, mr.myelin_score, mr.reinforcement_count,
               src.project_id AS src_project, dst.project_id AS dst_project
        FROM memory_relations mr
        JOIN memory_log src ON src.id = mr.source_memory_id
        JOIN memory_log dst ON dst.id = mr.target_memory_id
        WHERE src.project_id <> dst.project_id
          AND mr.active = TRUE
          AND src.last_accessed_at IS NOT NULL
          AND dst.last_accessed_at IS NOT NULL
          AND ABS(EXTRACT(EPOCH FROM (src.last_accessed_at - dst.last_accessed_at))) < 3600
          AND GREATEST(src.last_accessed_at, dst.last_accessed_at) > NOW() - INTERVAL '24 hours'
        """
    )
    strengthened = 0
    for row in rows:
        reinforcement_count = int(row["reinforcement_count"] or 0)
        max_my = compute_max_myelin(reinforcement_count)
        current = float(row["myelin_score"] or 0)
        new_score = min(max_my, current + MYELIN_DELTA_COACTIVATION)
        if new_score != current:
            await conn.execute(
                """
                UPDATE memory_relations
                SET myelin_score = $2, myelin_last_updated = NOW()
                WHERE id = $1
                """,
                row["id"],
                new_score,
            )
            await record_myelination_event(
                conn,
                str(row["id"]),
                None,
                "coactivation",
                MYELIN_DELTA_COACTIVATION,
                new_score,
            )
            strengthened += 1
    return strengthened
