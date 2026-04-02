"""Layer 5 — Brain Health Observability.

Computes biological health metrics for the /brain/health endpoint.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger("ai-memory-brain")


async def compute_brain_health(conn: asyncpg.Connection) -> dict[str, Any]:
    """Compute full brain health report."""
    now = datetime.now(timezone.utc)

    # Per-project region stats
    regions: dict[str, Any] = {}
    project_rows = await conn.fetch(
        """
        SELECT p.name, COUNT(m.id) AS memory_count,
               AVG(m.activation_score) AS avg_activation,
               SUM(CASE WHEN m.abstraction_level > 0 THEN 1 ELSE 0 END) AS schemas_count
        FROM projects p
        LEFT JOIN memory_log m ON m.project_id = p.id
        GROUP BY p.name
        HAVING COUNT(m.id) > 0
        """
    )
    total_orphan_ratio = 0.0
    total_keyphrases_coverage = 0.0
    project_count = len(project_rows)

    for row in project_rows:
        pname = str(row["name"])
        mem_count = int(row["memory_count"])

        orphan_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM memory_log m
            WHERE m.project_id = (SELECT id FROM projects WHERE name = $1)
              AND NOT EXISTS (
                SELECT 1 FROM memory_relations mr
                WHERE (mr.source_memory_id = m.id OR mr.target_memory_id = m.id) AND mr.active = TRUE
              )
            """,
            pname,
        )
        orphan_ratio = round(int(orphan_count) / max(mem_count, 1), 3)
        total_orphan_ratio += orphan_ratio

        active_synapses = await conn.fetchval(
            """
            SELECT COUNT(*) FROM memory_relations mr
            JOIN memory_log ms ON ms.id = mr.source_memory_id
            WHERE ms.project_id = (SELECT id FROM projects WHERE name = $1) AND mr.active = TRUE
            """,
            pname,
        )

        kp_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM memory_log m
            WHERE m.project_id = (SELECT id FROM projects WHERE name = $1)
              AND m.keyphrases IS NOT NULL AND array_length(m.keyphrases, 1) > 0
            """,
            pname,
        )
        kp_coverage = round(int(kp_count or 0) / max(mem_count, 1), 3)
        total_keyphrases_coverage += kp_coverage

        last_nrem = await conn.fetchval(
            """
            SELECT MAX(completed_at) FROM sleep_cycles
            WHERE cycle_type = 'nrem' AND $1 = ANY(projects_processed)
            """,
            pname,
        )

        regions[pname] = {
            "memory_count": mem_count,
            "active_synapses": int(active_synapses or 0),
            "avg_activation": round(float(row["avg_activation"] or 0), 3),
            "schemas_count": int(row["schemas_count"] or 0),
            "orphan_memories": int(orphan_count),
            "orphan_ratio": orphan_ratio,
            "keyphrases_coverage": kp_coverage,
            "last_nrem": last_nrem.isoformat() if last_nrem else None,
        }

    # Connectivity (cross-project permeability)
    connectivity: dict[str, Any] = {}
    perm_rows = await conn.fetch(
        """
        SELECT p1.name AS proj1, p2.name AS proj2,
               pp.permeability_score, pp.organic_origin, pp.formation_reason
        FROM project_permeability pp
        JOIN projects p1 ON p1.id = pp.project_id
        JOIN projects p2 ON p2.id = pp.related_project_id
        WHERE pp.permeability_score > 0
        """
    )
    for prow in perm_rows:
        key = f"{prow['proj1']}<->{prow['proj2']}"
        myelin_stats = await conn.fetchrow(
            """
            SELECT COUNT(*) as cnt, COALESCE(AVG(mr.myelin_score), 0) as avg_myelin
            FROM memory_relations mr
            JOIN memory_log ms ON ms.id = mr.source_memory_id
            JOIN memory_log mt ON mt.id = mr.target_memory_id
            JOIN projects ps ON ps.id = ms.project_id
            JOIN projects pt ON pt.id = mt.project_id
            WHERE mr.active = TRUE AND mr.myelin_score > 0
              AND ((ps.name = $1 AND pt.name = $2) OR (ps.name = $2 AND pt.name = $1))
            """,
            prow["proj1"],
            prow["proj2"],
        )
        connectivity[key] = {
            "permeability_score": round(float(prow["permeability_score"]), 3),
            "myelinated_relations": int(myelin_stats["cnt"]) if myelin_stats else 0,
            "avg_myelin_score": round(float(myelin_stats["avg_myelin"]), 3) if myelin_stats else 0.0,
            "organic_origin": bool(prow["organic_origin"]),
            "formation_reason": prow["formation_reason"] or "",
        }

    # Synapse formation stats
    tier_stats = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'pending') AS pending,
            COUNT(*) FILTER (WHERE status = 'promoted') AS promoted,
            COUNT(*) FILTER (WHERE status = 'rejected') AS rejected
        FROM synapse_candidates
        """
    )

    tier12 = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE evidence_json->>'tier' = '1') AS tier1,
            COUNT(*) FILTER (WHERE evidence_json->>'tier' = '2') AS tier2
        FROM memory_relations
        WHERE evidence_json ? 'tier'
        """
    )

    synapse_formation = {
        "tier1_instant": int(tier12["tier1"] or 0) if tier12 else 0,
        "tier2_confirmed": int(tier12["tier2"] or 0) if tier12 else 0,
        "tier3_candidates_pending": int(tier_stats["pending"] or 0) if tier_stats else 0,
        "tier3_promoted": int(tier_stats["promoted"] or 0) if tier_stats else 0,
        "tier3_rejected": int(tier_stats["rejected"] or 0) if tier_stats else 0,
    }

    # Sleep stats
    last_nrem_global = await conn.fetchval(
        "SELECT MAX(completed_at) FROM sleep_cycles WHERE cycle_type = 'nrem'"
    )
    last_rem_global = await conn.fetchval(
        "SELECT MAX(completed_at) FROM sleep_cycles WHERE cycle_type = 'rem'"
    )

    cross_activity = await conn.fetchval(
        """
        SELECT COUNT(*) FROM myelination_events
        WHERE created_at > COALESCE(
            (SELECT MAX(completed_at) FROM sleep_cycles WHERE cycle_type = 'rem'),
            NOW() - INTERVAL '7 days'
        )
        """
    )

    sleep_info = {
        "last_nrem": last_nrem_global.isoformat() if last_nrem_global else None,
        "last_rem": last_rem_global.isoformat() if last_rem_global else None,
        "cross_activity_score": int(cross_activity or 0),
        "rem_threshold": 15,
    }

    # Alerts
    alerts: list[dict[str, str]] = []
    for pname, region in regions.items():
        if region["orphan_ratio"] > 0.30:
            alerts.append({
                "type": "fragmentation",
                "severity": "warning",
                "message": f"{pname} has {region['orphan_memories']} orphan memories ({region['orphan_ratio']:.0%}), consider seeding relations",
            })
        if region["keyphrases_coverage"] < 0.80:
            alerts.append({
                "type": "migration_incomplete",
                "severity": "info",
                "message": f"{pname} keyphrases coverage at {region['keyphrases_coverage']:.0%} (<80%)",
            })

    if sleep_info["cross_activity_score"] > 10:
        alerts.append({
            "type": "sleep_needed",
            "severity": "info",
            "message": f"cross_activity_score approaching REM threshold ({sleep_info['cross_activity_score']}/15)",
        })

    # Overall health
    avg_orphan = total_orphan_ratio / max(project_count, 1)
    avg_kp = total_keyphrases_coverage / max(project_count, 1)
    avg_myelin = 0.0
    if connectivity:
        avg_myelin = sum(c["avg_myelin_score"] for c in connectivity.values()) / len(connectivity)

    sleep_health = 0.5
    if last_nrem_global:
        hours_since = (now - last_nrem_global).total_seconds() / 3600
        sleep_health = max(0, 1.0 - hours_since / 48)

    overall = round(
        (1 - avg_orphan) * 0.20
        + avg_myelin * 0.15
        + 0.5 * 0.15  # fragmentation placeholder
        + sleep_health * 0.15
        + 0.5 * 0.15  # schema coverage placeholder
        + avg_kp * 0.10
        + 0.5 * 0.10,  # signal balance placeholder
        3,
    )

    return {
        "overall_health": overall,
        "timestamp": now.isoformat(),
        "regions": regions,
        "connectivity": connectivity,
        "synapse_formation": synapse_formation,
        "sleep": sleep_info,
        "alerts": alerts,
    }
