import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import asyncpg
import httpx
import redis.asyncio as aioredis
from openai import AsyncOpenAI

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("reflection-worker")

def env_text(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


POSTGRES_URL = os.environ["POSTGRES_URL"].strip()
REDIS_URL = os.environ["REDIS_URL"].strip()
API_SERVER_URL = os.environ["API_SERVER_URL"].strip()
API_KEY = os.environ["API_KEY"].strip()
MEM0_URL = os.environ["MEM0_URL"].strip()
DEEPSEEK_API_KEY = env_text("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = env_text("DEEPSEEK_MODEL", "deepseek-reasoner")
DEEPSEEK_BASE_URL = env_text("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
REFLECTION_INTERVAL = int(os.environ.get("REFLECTION_INTERVAL_SECONDS", "21600"))
REFLECTION_POLL_INTERVAL = int(os.environ.get("REFLECTION_POLL_INTERVAL_SECONDS", "30"))
DEEP_SLEEP_INTERVAL = int(os.environ.get("DEEP_SLEEP_INTERVAL_SECONDS", "86400"))
WORKER_HEARTBEAT_KEY = env_text("WORKER_HEARTBEAT_KEY", "reflection_worker:heartbeat")
WORKER_HEARTBEAT_TTL = int(os.environ.get("WORKER_HEARTBEAT_TTL_SECONDS", "120"))
API_CALL_TIMEOUT = float(os.environ.get("API_CALL_TIMEOUT_SECONDS", "30.0"))
WORKER_PG_POOL_MAX_SIZE = int(os.environ.get("WORKER_PG_POOL_MAX_SIZE", "4"))
AI_MEMORY_TEST_MODE = os.environ.get("AI_MEMORY_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
AI_MEMORY_TEST_NOW = os.environ.get("AI_MEMORY_TEST_NOW", "").strip()
HEARTBEAT_FILE = Path("/tmp/reflection-worker-heartbeat")
ADVISORY_LOCK_KEY = 829311
VALID_TASK_STATES = {"pending", "active", "blocked", "done", "cancelled"}

# Negation patterns for suspected contradiction re-evaluation (NREM phase)
NEGATION_PATTERNS: list[tuple[str, str]] = [
    (r"\bno\s+usar\b", r"\busar\b"),
    (r"\bevitar\b", r"\bpreferir\b"),
    (r"\bdeprecated?\b", r"\brecomend(?:ado|ed)\b"),
    (r"\bremove[dr]?\b", r"\badd(?:ed)?\b"),
    (r"\bdisable[dr]?\b", r"\benable[dr]?\b"),
    (r"\bnot?\s+recommend", r"\brecommend"),
    (r"\banti[_-]?pattern\b", r"\bbest[_-]?practice\b"),
]

pg_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None
http_client: Optional[httpx.AsyncClient] = None
deepseek_client: Optional[AsyncOpenAI] = None
TEST_NOW_OVERRIDE: Optional[datetime] = None


def now_utc() -> datetime:
    if TEST_NOW_OVERRIDE is not None:
        return TEST_NOW_OVERRIDE
    if AI_MEMORY_TEST_MODE and AI_MEMORY_TEST_NOW:
        parsed = datetime.fromisoformat(AI_MEMORY_TEST_NOW)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def has_real_secret(value: Optional[str]) -> bool:
    return bool(value and "change-me" not in value)


def item_hash(project: str, item_type: str, payload: Any) -> str:
    return hashlib.sha256(canonical_json({"project": project, "item_type": item_type, "payload": payload}).encode("utf-8")).hexdigest()


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        stripped = "".join(part for part in parts if not part.strip().lower().startswith("json")).strip()
    return stripped


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = strip_code_fences(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("DeepSeek no devolvio un JSON valido")
    return json.loads(cleaned[start : end + 1])


def normalize_tags(tags: Any) -> list[str]:
    if isinstance(tags, list):
        return [str(tag).strip() for tag in tags if str(tag).strip()]
    if isinstance(tags, str):
        return [tag.strip() for tag in tags.split(",") if tag.strip()]
    return []


def deterministic_reflection(payload: dict[str, Any], working_memory: list[str]) -> dict[str, Any]:
    project_summary = payload.get("summary", "").strip() or payload.get("outcome", "").strip()
    base_tags = normalize_tags(payload.get("tags", []))
    agent_id = str(payload.get("agent_id", "reflection-test")).strip() or "reflection-test"

    durable_memories = []
    if project_summary:
        durable_memories.append(
            {
                "content": f"PROJECT SUMMARY: {project_summary}",
                "memory_type": "context",
                "importance": 0.8,
                "tags": sorted(set(base_tags + ["reflection", "summary"])),
                "agent_id": agent_id,
            }
        )
    for change in payload.get("changes", [])[:3]:
        if str(change).strip():
            durable_memories.append(
                {
                    "content": f"CHANGE MEMORY: {str(change).strip()}",
                    "memory_type": "general",
                    "importance": 0.72,
                    "tags": sorted(set(base_tags + ["reflection", "change"])),
                    "agent_id": agent_id,
                }
            )
    if working_memory:
        durable_memories.append(
            {
                "content": f"WORKING MEMORY LINK: {working_memory[0]}",
                "memory_type": "context",
                "importance": 0.68,
                "tags": sorted(set(base_tags + ["reflection", "working-memory"])),
                "agent_id": agent_id,
            }
        )

    decisions = []
    for item in payload.get("decisions", [])[:5]:
        title = str(item.get("title", "")).strip()
        decision = str(item.get("decision", "")).strip()
        if title and decision:
            decisions.append(
                {
                    "title": title,
                    "decision": decision,
                    "rationale": str(item.get("rationale", "")).strip(),
                    "tags": base_tags,
                    "agent_id": agent_id,
                }
            )

    errors = []
    for item in payload.get("errors", [])[:5]:
        description = str(item.get("description", "")).strip()
        solution = str(item.get("solution", "")).strip()
        if description and solution:
            errors.append(
                {
                    "error_signature": str(item.get("error_signature", "")).strip() or description[:100],
                    "description": description,
                    "solution": solution,
                    "tags": base_tags,
                }
            )

    tasks = []
    for item in payload.get("follow_ups", [])[:5]:
        title = str(item.get("title", "")).strip()
        if title:
            tasks.append(
                {
                    "title": title,
                    "state": str(item.get("state", "pending")).strip().lower() or "pending",
                    "details": str(item.get("details", "")).strip(),
                    "agent_id": agent_id,
                }
            )

    return {
        "project_summary": project_summary,
        "durable_memories": durable_memories[:5],
        "decisions": decisions,
        "errors": errors,
        "tasks": tasks,
    }


async def retry_async(label: str, callback, attempts: int = 20, delay: float = 2.0):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return await callback()
        except Exception as exc:
            last_error = exc
            logger.warning("%s intento %s/%s fallido: %s", label, attempt, attempts, exc)
            await asyncio.sleep(delay)
    raise RuntimeError(f"No fue posible inicializar {label}: {last_error}") from last_error


async def update_heartbeat():
    heartbeat_payload = json.dumps({"timestamp": now_iso()}, ensure_ascii=False)
    HEARTBEAT_FILE.write_text(heartbeat_payload, encoding="utf-8")
    if redis_client:
        await redis_client.setex(WORKER_HEARTBEAT_KEY, WORKER_HEARTBEAT_TTL, heartbeat_payload)


async def api_call(method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    headers = {"X-API-Key": API_KEY}
    response = await http_client.request(method, f"{API_SERVER_URL}{path}", json=payload, headers=headers, timeout=API_CALL_TIMEOUT)
    response.raise_for_status()
    return response.json()


async def mem0_search(payload: dict[str, Any]) -> list[str]:
    body = {
        "query": f"recent work context for goal {payload['goal']} and outcome {payload['outcome']}. Summary: {payload['summary']}",
        "user_id": payload["project"],
        "agent_id": payload["agent_id"],
        "limit": 6,
        "enable_graph": True,
    }
    try:
        response = await http_client.post(f"{MEM0_URL}/search", json=body, timeout=15.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("No fue posible consultar Mem0 para la sesion %s: %s", payload["session_id"], exc)
        return []

    raw_results = data.get("results", data if isinstance(data, list) else [])
    relations = data.get("relations", []) if isinstance(data, dict) else []
    results: list[str] = []
    for item in raw_results[:6]:
        if isinstance(item, dict):
            memory_text = item.get("memory") or item.get("content") or item.get("text")
            if not memory_text and isinstance(item.get("payload"), dict):
                memory_text = item["payload"].get("content")
            if memory_text:
                results.append(str(memory_text)[:320])
        elif item:
            results.append(str(item)[:320])
    for relation in relations[:2]:
        if relation:
            results.append(f"relation {json.dumps(relation, ensure_ascii=False)[:280]}")
    return results


async def deepseek_reflection(payload: dict[str, Any], working_memory: list[str]) -> dict[str, Any]:
    if AI_MEMORY_TEST_MODE:
        return deterministic_reflection(payload, working_memory)
    if not has_real_secret(DEEPSEEK_API_KEY):
        raise RuntimeError("deepseek_not_configured")

    system_prompt = (
        "Eres un motor de consolidacion de memoria para agentes de software. "
        "Convierte un resumen estructurado de sesion en memoria duradera util para futuras sesiones. "
        "Devuelve solo JSON valido, sin markdown ni explicaciones. "
        "No incluyas cadena de razonamiento ni reasoning_content. "
        "Usa este esquema exacto: "
        "{"
        "\"project_summary\": string, "
        "\"durable_memories\": [{\"content\": string, \"memory_type\": string, \"importance\": number, \"tags\": [string], \"agent_id\": string}], "
        "\"decisions\": [{\"title\": string, \"decision\": string, \"rationale\": string, \"tags\": [string], \"agent_id\": string}], "
        "\"errors\": [{\"error_signature\": string, \"description\": string, \"solution\": string, \"tags\": [string]}], "
        "\"tasks\": [{\"title\": string, \"state\": string, \"details\": string, \"agent_id\": string}]"
        "}. "
        "Solo incluye elementos que merezcan persistencia. Limita durable_memories a 5 items."
    )
    user_prompt = canonical_json(
        {
            "session_summary": payload,
            "recent_working_memory": working_memory,
            "valid_task_states": sorted(VALID_TASK_STATES),
        }
    )
    response = await deepseek_client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    return extract_json_object(content)


async def promotion_exists(conn: asyncpg.Connection, project: str, item_type: str, digest: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT 1
            FROM reflection_promotions rp
            JOIN projects p ON p.id = rp.project_id
            WHERE p.name = $1 AND rp.item_type = $2 AND rp.item_hash = $3
            LIMIT 1
            """,
            project,
            item_type,
            digest,
        )
    )


async def record_promotion(conn: asyncpg.Connection, run_id, project: str, item_type: str, digest: str, target_ref: str):
    await conn.execute(
        """
        INSERT INTO reflection_promotions (run_id, project_id, item_type, item_hash, target_ref)
        VALUES (
            $1,
            (SELECT id FROM projects WHERE name = $2 LIMIT 1),
            $3,
            $4,
            $5
        )
        ON CONFLICT (project_id, item_type, item_hash) DO NOTHING
        """,
        run_id,
        project,
        item_type,
        digest,
        target_ref[:255],
    )


async def promote_findings(conn: asyncpg.Connection, run_id, payload: dict[str, Any], findings: dict[str, Any]) -> int:
    promoted = 0
    project = payload["project"]
    default_agent = payload["agent_id"]

    project_summary = findings.get("project_summary")
    if project_summary:
        summary_item = {
            "content": f"PROJECT SUMMARY: {project_summary}",
            "memory_type": "context",
            "importance": 0.75,
            "tags": ["reflection", "project-summary"],
            "agent_id": default_agent,
        }
        findings.setdefault("durable_memories", []).insert(0, summary_item)

    for item in findings.get("durable_memories", []):
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        normalized = {
            "content": content,
            "memory_type": str(item.get("memory_type", "general")).strip() or "general",
            "importance": float(item.get("importance", 0.7)),
            "tags": normalize_tags(item.get("tags", [])),
            "agent_id": str(item.get("agent_id", default_agent)).strip() or default_agent,
        }
        digest = item_hash(project, "durable_memory", normalized)
        if await promotion_exists(conn, project, "durable_memory", digest):
            continue
        response = await api_call(
            "POST",
            "/api/memories",
            {
                "content": normalized["content"],
                "project": project,
                "memory_type": normalized["memory_type"],
                "importance": normalized["importance"],
                "tags": ",".join(normalized["tags"]),
                "agent_id": normalized["agent_id"],
                "skip_similar": True,
                "dedupe_threshold": 0.92,
            },
        )
        await record_promotion(conn, run_id, project, "durable_memory", digest, response.get("result", "stored"))
        promoted += 1

    for item in findings.get("decisions", []):
        title = str(item.get("title", "")).strip()
        decision = str(item.get("decision", "")).strip()
        if not title or not decision:
            continue
        normalized = {
            "title": title,
            "decision": decision,
            "rationale": str(item.get("rationale", "")).strip(),
            "tags": normalize_tags(item.get("tags", [])),
            "agent_id": str(item.get("agent_id", default_agent)).strip() or default_agent,
        }
        digest = item_hash(project, "decision", normalized)
        if await promotion_exists(conn, project, "decision", digest):
            continue
        response = await api_call(
            "POST",
            "/api/decisions",
            {
                "title": normalized["title"],
                "decision": normalized["decision"],
                "project": project,
                "rationale": normalized["rationale"],
                "alternatives": "",
                "tags": ",".join(normalized["tags"]),
                "agent_id": normalized["agent_id"],
            },
        )
        await record_promotion(conn, run_id, project, "decision", digest, response.get("result", "stored"))
        promoted += 1

    for item in findings.get("errors", []):
        description = str(item.get("description", "")).strip()
        solution = str(item.get("solution", "")).strip()
        if not description or not solution:
            continue
        normalized = {
            "error_signature": str(item.get("error_signature", "")).strip() or description[:100],
            "description": description,
            "solution": solution,
            "tags": normalize_tags(item.get("tags", [])),
        }
        digest = item_hash(project, "error", normalized)
        if await promotion_exists(conn, project, "error", digest):
            continue
        response = await api_call(
            "POST",
            "/api/errors",
            {
                "error_signature": normalized["error_signature"],
                "error_description": normalized["description"],
                "solution": normalized["solution"],
                "project": project,
                "tags": ",".join(normalized["tags"]),
            },
        )
        await record_promotion(conn, run_id, project, "error", digest, response.get("result", "stored"))
        promoted += 1

    for item in findings.get("tasks", []):
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        state = str(item.get("state", "pending")).strip().lower()
        if state not in VALID_TASK_STATES:
            state = "pending"
        normalized = {
            "title": title,
            "state": state,
            "details": str(item.get("details", "")).strip(),
            "agent_id": str(item.get("agent_id", default_agent)).strip() or default_agent,
        }
        digest = item_hash(project, "task", normalized)
        if await promotion_exists(conn, project, "task", digest):
            continue
        response = await api_call(
            "POST",
            "/api/tasks/state",
            {
                "task_title": normalized["title"],
                "project": project,
                "new_state": normalized["state"],
                "details": normalized["details"],
                "agent_id": normalized["agent_id"],
            },
        )
        await record_promotion(conn, run_id, project, "task", digest, response.get("result", "stored"))
        promoted += 1

    return promoted


async def process_session(conn: asyncpg.Connection, run_id, row: asyncpg.Record) -> int:
    payload = row["payload_json"]
    if not isinstance(payload, dict):
        payload = json.loads(payload)
    working_memory = await mem0_search(payload)
    findings = await deepseek_reflection(payload, working_memory)
    promoted = await promote_findings(conn, run_id, payload, findings)
    try:
        await api_call("POST", "/api/plasticity/session", payload)
    except Exception:
        logger.exception("Fase de plasticidad fallo para session %s", payload.get("session_id"))
    return promoted


async def claim_pending_sessions(conn: asyncpg.Connection, limit: int = 20) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        WITH claimed AS (
            SELECT id
            FROM session_summaries
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        UPDATE session_summaries s
        SET status = 'processing'
        FROM claimed
        WHERE s.id = claimed.id
        RETURNING s.id, s.payload_json, s.session_id
        """,
        limit,
    )


async def recover_interrupted_state(conn: asyncpg.Connection):
    reset_sessions = await conn.execute(
        """
        UPDATE session_summaries
        SET status = 'pending',
            last_error = CASE
                WHEN COALESCE(last_error, '') = '' THEN 'requeued_after_worker_interruption'
                ELSE LEFT(last_error || ' | requeued_after_worker_interruption', 2000)
            END
        WHERE status = 'processing' AND reviewed_at IS NULL
        """
    )
    failed_runs = await conn.execute(
        """
        UPDATE reflection_runs
        SET status = 'failed',
            finished_at = NOW(),
            error = CASE
                WHEN COALESCE(error, '') = '' THEN 'worker_interruption_detected'
                ELSE LEFT(error || ' | worker_interruption_detected', 2000)
            END
        WHERE status = 'running' AND finished_at IS NULL
        """
    )
    logger.info("Recuperacion de estado interrumpido: %s, %s", reset_sessions, failed_runs)


async def execute_run(conn: asyncpg.Connection, run_id):
    await conn.execute(
        """
        UPDATE reflection_runs
        SET status = 'running', started_at = NOW(), error = NULL, input_count = 0, promoted_count = 0
        WHERE id = $1
        """,
        run_id,
    )
    total_inputs = 0
    total_promoted = 0
    failures = 0

    try:
        while True:
            await update_heartbeat()
            claimed = await claim_pending_sessions(conn)
            if not claimed:
                break
            batch_failures = 0
            total_inputs += len(claimed)
            for row in claimed:
                try:
                    await update_heartbeat()
                    total_promoted += await process_session(conn, run_id, row)
                    await conn.execute(
                        """
                        UPDATE session_summaries
                        SET status = 'reviewed', reviewed_at = NOW(), last_error = NULL
                        WHERE id = $1
                        """,
                        row["id"],
                    )
                except Exception as exc:
                    failures += 1
                    logger.exception("Fallo procesando session %s", row["session_id"])
                    await conn.execute(
                        """
                        UPDATE session_summaries
                        SET status = 'pending', last_error = $2
                        WHERE id = $1
                        """,
                        row["id"],
                        str(exc)[:2000],
                    )
                    batch_failures += 1
            if batch_failures:
                break
        error = f"session_failures={failures}" if failures else None
        await conn.execute(
            """
            UPDATE reflection_runs
            SET status = 'completed',
                finished_at = NOW(),
                input_count = $2,
                promoted_count = $3,
                error = $4
            WHERE id = $1
            """,
            run_id,
            total_inputs,
            total_promoted,
            error,
        )
    except Exception as exc:
        logger.exception("Reflection run %s fallo", run_id)
        await conn.execute(
            """
            UPDATE reflection_runs
            SET status = 'failed',
                finished_at = NOW(),
                input_count = $2,
                promoted_count = $3,
                error = $4
            WHERE id = $1
            """,
            run_id,
            total_inputs,
            total_promoted,
            str(exc)[:2000],
        )


async def handle_manual_runs():
    async with pg_pool.acquire() as conn:
        locked = await conn.fetchval("SELECT pg_try_advisory_lock($1)", ADVISORY_LOCK_KEY)
        if not locked:
            return
        try:
            await recover_interrupted_state(conn)
            while True:
                run_row = await conn.fetchrow(
                    """
                    SELECT id
                    FROM reflection_runs
                    WHERE mode = 'manual' AND status = 'queued'
                    ORDER BY started_at ASC
                    LIMIT 1
                    """
                )
                if not run_row:
                    break
                await execute_run(conn, run_row["id"])
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_KEY)


async def handle_scheduled_run():
    async with pg_pool.acquire() as conn:
        locked = await conn.fetchval("SELECT pg_try_advisory_lock($1)", ADVISORY_LOCK_KEY)
        if not locked:
            return
        try:
            await recover_interrupted_state(conn)
            last_run_at = await conn.fetchval(
                """
                SELECT COALESCE(finished_at, started_at)
                FROM reflection_runs
                WHERE mode = 'scheduled'
                ORDER BY COALESCE(finished_at, started_at) DESC
                LIMIT 1
                """
            )
            if last_run_at and now_utc() - last_run_at.astimezone(timezone.utc) < timedelta(seconds=REFLECTION_INTERVAL):
                return

            run_id = await conn.fetchval(
                """
                INSERT INTO reflection_runs (mode, status, model)
                VALUES ('scheduled', 'queued', $1)
                RETURNING id
                """,
                DEEPSEEK_MODEL,
            )
            await execute_run(conn, run_id)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_KEY)


async def deepseek_schema_prompt(project: str, memories: list[dict]) -> Optional[str]:
    """[6] Extrae el principio general subyacente de un cluster de memorias relacionadas."""
    if AI_MEMORY_TEST_MODE:
        topics = list({m.get("memory_type", "general") for m in memories})
        return f"SCHEMA: Principio general derivado de {len(memories)} memorias del proyecto {project} sobre {', '.join(topics[:3])}"
    if not has_real_secret(DEEPSEEK_API_KEY):
        return None
    snippets = [f"- [{m.get('memory_type', '?')}] {str(m.get('content', m.get('summary', '')))[:300]}" for m in memories[:8]]
    prompt = (
        f"Dado el siguiente conjunto de {len(memories)} memorias del proyecto '{project}', "
        "extrae en UNA SOLA FRASE el principio general, patrón o regla subyacente que las conecta. "
        "Sé preciso y concreto. Devuelve solo la frase, sin comillas ni explicaciones.\n\n"
        + "\n".join(snippets)
    )
    try:
        response = await deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            temperature=0.1,
            messages=[
                {"role": "system", "content": "Eres un motor de abstracción cognitiva para agentes de software."},
                {"role": "user", "content": prompt},
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        return content[:500] if content else None
    except Exception as exc:
        logger.warning("Schema LLM fallo: %s", exc)
        return None


async def deepseek_contradiction_prompt(
    memory_a: dict, memory_b: dict
) -> Optional[dict]:
    """[7] Resuelve una contradicción entre dos memorias."""
    if AI_MEMORY_TEST_MODE:
        # Heurístico determinista: gana la más reciente
        return {"resolution_type": "b_wins", "condition_text": "deterministic_test_resolution"}
    if not has_real_secret(DEEPSEEK_API_KEY):
        return None
    prompt = canonical_json({
        "memory_a": {
            "content": str(memory_a.get("content", memory_a.get("summary", "")))[:400],
            "memory_type": memory_a.get("action_type", "general"),
            "stability_score": memory_a.get("stability_score", 0.5),
            "access_count": memory_a.get("access_count", 0),
        },
        "memory_b": {
            "content": str(memory_b.get("content", memory_b.get("summary", "")))[:400],
            "memory_type": memory_b.get("action_type", "general"),
            "stability_score": memory_b.get("stability_score", 0.5),
            "access_count": memory_b.get("access_count", 0),
        },
    })
    system = (
        "Eres un motor de coherencia epistémica. Dos memorias se contradicen. "
        "Devuelve solo JSON: {\"resolution_type\": \"a_wins\"|\"b_wins\"|\"synthesis\"|\"conditional\", "
        "\"condition_text\": string_or_null}. "
        "a_wins/b_wins si una es claramente obsoleta o incorrecta. "
        "conditional si ambas son válidas bajo condiciones distintas. "
        "synthesis si se pueden integrar en un principio superior."
    )
    try:
        response = await deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return extract_json_object(response.choices[0].message.content or "")
    except Exception as exc:
        logger.warning("Contradiction LLM fallo: %s", exc)
        return None


async def run_schema_extraction(conn: asyncpg.Connection, run_id) -> int:
    """[6] Fase de extracción de esquemas: agrupa memorias conectadas y abstrae principios."""
    created = 0
    # Fetch hot memories grouped by project
    project_rows = await conn.fetch(
        """
        SELECT DISTINCT p.name AS project
        FROM memory_log ml
        JOIN projects p ON p.id = ml.project_id
        WHERE ml.activation_score > 0.3
          AND ml.action_type <> 'schema'
        """
    )
    for proj_row in project_rows:
        project = proj_row["project"]
        # Fetch clusters: memorias del proyecto con relaciones same_concept/extends
        cluster_rows = await conn.fetch(
            """
            SELECT DISTINCT
                LEAST(mr.source_memory_id::text, mr.target_memory_id::text) AS pair_a,
                GREATEST(mr.source_memory_id::text, mr.target_memory_id::text) AS pair_b,
                src.action_type AS src_type,
                COALESCE(src.tags, '{}') AS src_tags
            FROM memory_relations mr
            JOIN memory_log src ON src.id = mr.source_memory_id
            JOIN memory_log dst ON dst.id = mr.target_memory_id
            JOIN projects sp ON sp.id = src.project_id
            WHERE mr.active = TRUE
              AND mr.relation_type IN ('same_concept', 'extends', 'supports')
              AND sp.name = $1
              AND src.activation_score > 0.25
              AND src.action_type <> 'schema'
            LIMIT 60
            """,
            project,
        )
        if len(cluster_rows) < 3:
            continue
        # Group memory IDs from cluster pairs
        memory_id_set: set[str] = set()
        for row in cluster_rows:
            memory_id_set.add(str(row["pair_a"]))
            memory_id_set.add(str(row["pair_b"]))
        if len(memory_id_set) < 3:
            continue
        memory_ids = list(memory_id_set)[:12]
        # Check if a schema already exists for this cluster
        tag_sample = list(cluster_rows[0]["src_tags"])[:3] if cluster_rows[0]["src_tags"] else []
        existing_schema = await conn.fetchval(
            """
            SELECT COUNT(*) FROM memory_log ml
            JOIN projects p ON p.id = ml.project_id
            WHERE p.name = $1 AND ml.action_type = 'schema'
              AND ml.tags && $2::text[]
            """,
            project,
            tag_sample or ["schema"],
        )
        if existing_schema and not AI_MEMORY_TEST_MODE:
            continue
        memories_data = await conn.fetch(
            """
            SELECT id, summary, action_type, tags, activation_score, stability_score
            FROM memory_log WHERE id = ANY($1::uuid[])
            """,
            [uuid.UUID(mid) for mid in memory_ids],
        )
        mem_dicts = [dict(row) for row in memories_data]
        schema_text = await deepseek_schema_prompt(project, mem_dicts)
        if not schema_text:
            continue
        # Promote schema via API
        schema_tags = normalize_tags(tag_sample + ["schema", "abstraction"])
        try:
            response = await api_call(
                "POST",
                "/api/memories",
                {
                    "content": schema_text,
                    "project": project,
                    "memory_type": "schema",
                    "importance": 0.85,
                    "tags": ",".join(schema_tags),
                    "agent_id": "deep-sleep-worker",
                    "skip_similar": True,
                    "dedupe_threshold": 0.88,
                },
            )
            result_str = response.get("result", "")
            if result_str.startswith("OK"):
                schema_id = result_str.split("memory_id=")[1].split()[0] if "memory_id=" in result_str else None
                if schema_id:
                    # Register schema_sources links
                    for mid in memory_ids:
                        try:
                            await conn.execute(
                                """
                                INSERT INTO schema_sources (schema_memory_id, source_memory_id)
                                VALUES ($1::uuid, $2::uuid)
                                ON CONFLICT DO NOTHING
                                """,
                                uuid.UUID(schema_id),
                                uuid.UUID(mid),
                            )
                        except Exception:
                            pass
                created += 1
                logger.info("[6] Schema creado para proyecto %s: %s", project, schema_text[:120])
        except Exception as exc:
            logger.warning("[6] Error promoviendo schema para %s: %s", project, exc)
    return created


async def resolve_contradictions(conn: asyncpg.Connection) -> int:
    """[7] Resuelve pares de memorias contradictorias de la cola."""
    resolved = 0
    pending = await conn.fetch(
        """
        SELECT cq.id, cq.memory_a_id, cq.memory_b_id
        FROM contradiction_queue cq
        WHERE cq.resolution_status = 'pending'
        ORDER BY cq.created_at ASC
        LIMIT 10
        """
    )
    if not pending:
        return 0
    for row in pending:
        cq_id = row["id"]
        mem_a_id = str(row["memory_a_id"])
        mem_b_id = str(row["memory_b_id"])
        try:
            mem_a = await conn.fetchrow(
                "SELECT id, summary, action_type, stability_score, access_count FROM memory_log WHERE id = $1::uuid",
                uuid.UUID(mem_a_id),
            )
            mem_b = await conn.fetchrow(
                "SELECT id, summary, action_type, stability_score, access_count FROM memory_log WHERE id = $1::uuid",
                uuid.UUID(mem_b_id),
            )
            if not mem_a or not mem_b:
                await conn.execute(
                    "UPDATE contradiction_queue SET resolution_status='resolved', resolution_type='missing_memory', resolved_at=NOW() WHERE id=$1",
                    cq_id,
                )
                continue
            resolution = await deepseek_contradiction_prompt(dict(mem_a), dict(mem_b))
            if not resolution:
                continue
            res_type = resolution.get("resolution_type", "conditional")
            condition_text = resolution.get("condition_text") or ""
            # Apply resolution
            if res_type == "a_wins":
                await conn.execute(
                    "UPDATE memory_log SET stability_score = GREATEST(0.05, stability_score * 0.15) WHERE id = $1::uuid",
                    uuid.UUID(mem_b_id),
                )
            elif res_type == "b_wins":
                await conn.execute(
                    "UPDATE memory_log SET stability_score = GREATEST(0.05, stability_score * 0.15) WHERE id = $1::uuid",
                    uuid.UUID(mem_a_id),
                )
            elif res_type == "synthesis":
                synth_content = f"SYNTHESIS: {str(mem_a['summary'])[:200]} / {str(mem_b['summary'])[:200]}"
                project_name = await conn.fetchval(
                    "SELECT p.name FROM memory_log ml JOIN projects p ON p.id = ml.project_id WHERE ml.id = $1::uuid",
                    uuid.UUID(mem_a_id),
                )
                if project_name:
                    try:
                        resp = await api_call("POST", "/api/memories", {
                            "content": synth_content,
                            "project": project_name,
                            "memory_type": "schema",
                            "importance": 0.85,
                            "tags": "synthesis,contradiction-resolution",
                            "agent_id": "deep-sleep-worker",
                        })
                        synth_id = ""
                        if resp.get("result", "").startswith("OK") and "memory_id=" in resp.get("result", ""):
                            synth_id = resp["result"].split("memory_id=")[1].split()[0]
                        if synth_id:
                            # Create derived_from relations to both originals
                            for orig_id in (mem_a_id, mem_b_id):
                                try:
                                    await api_call("POST", "/api/relations", {
                                        "source_memory_id": synth_id,
                                        "target_memory_id": orig_id,
                                        "relation_type": "derived_from",
                                        "weight": 0.9,
                                    })
                                except Exception:
                                    logger.debug("Failed to create derived_from relation for synthesis %s -> %s", synth_id[:8], orig_id[:8])
                            # Record in schema_sources
                            for orig_id in (mem_a_id, mem_b_id):
                                try:
                                    await conn.execute(
                                        """
                                        INSERT INTO schema_sources (schema_memory_id, source_memory_id)
                                        VALUES ($1::uuid, $2::uuid)
                                        ON CONFLICT (schema_memory_id, source_memory_id) DO NOTHING
                                        """,
                                        uuid.UUID(synth_id),
                                        uuid.UUID(orig_id),
                                    )
                                except Exception:
                                    pass
                            await conn.execute(
                                "UPDATE contradiction_queue SET resolution_memory_id = $2::uuid WHERE id = $1",
                                cq_id,
                                uuid.UUID(synth_id),
                            )
                        # Proportional degradation of both originals
                        for orig_id in (mem_a_id, mem_b_id):
                            await conn.execute(
                                "UPDATE memory_log SET stability_score = GREATEST(0.05, stability_score * 0.5) WHERE id = $1::uuid",
                                uuid.UUID(orig_id),
                            )
                    except Exception as exc:
                        logger.debug("Error creando síntesis: %s", exc)
            elif res_type == "conditional":
                cond_content = f"CONDITIONAL: {condition_text or ''} — {str(mem_a['summary'])[:150]} / {str(mem_b['summary'])[:150]}"
                project_name = await conn.fetchval(
                    "SELECT p.name FROM memory_log ml JOIN projects p ON p.id = ml.project_id WHERE ml.id = $1::uuid",
                    uuid.UUID(mem_a_id),
                )
                if project_name:
                    try:
                        resp = await api_call("POST", "/api/memories", {
                            "content": cond_content,
                            "project": project_name,
                            "memory_type": "schema",
                            "importance": 0.8,
                            "tags": "conditional,contradiction-resolution",
                            "agent_id": "deep-sleep-worker",
                        })
                        cond_id = ""
                        if resp.get("result", "").startswith("OK") and "memory_id=" in resp.get("result", ""):
                            cond_id = resp["result"].split("memory_id=")[1].split()[0]
                        if cond_id:
                            # Create applies_to relations to both originals
                            for orig_id in (mem_a_id, mem_b_id):
                                try:
                                    await api_call("POST", "/api/relations", {
                                        "source_memory_id": cond_id,
                                        "target_memory_id": orig_id,
                                        "relation_type": "applies_to",
                                        "weight": 0.8,
                                    })
                                except Exception:
                                    logger.debug("Failed to create applies_to relation for conditional %s -> %s", cond_id[:8], orig_id[:8])
                            # No degradation — both originals are correct in context
                    except Exception as exc:
                        logger.debug("Error creando conditional resolution: %s", exc)
            await conn.execute(
                """
                UPDATE contradiction_queue
                SET resolution_status = 'resolved',
                    resolution_type = $2,
                    condition_text = $3,
                    resolved_at = NOW()
                WHERE id = $1
                """,
                cq_id,
                res_type,
                condition_text or None,
            )
            resolved += 1
            logger.info("[7] Contradiccion resuelta (%s): %s vs %s", res_type, mem_a_id[:8], mem_b_id[:8])
        except Exception as exc:
            logger.warning("[7] Error resolviendo contradiccion %s: %s", cq_id, exc)
    return resolved


async def prune_cold_memories(conn: asyncpg.Connection) -> int:
    """[8][L3] Poda memorias frías: improved criteria — access_count=0, stability<0.2, age>21d, no pin, low arousal."""
    result = await conn.execute(
        """
        UPDATE memory_log ml
        SET stability_score = GREATEST(0.05, ml.stability_score * 0.3)
        WHERE ml.access_count = 0
          AND ml.stability_score < 0.2
          AND ml.manual_pin = FALSE
          AND COALESCE(ml.arousal, 0.5) <= 0.6
          AND ml.action_type <> 'schema'
          AND ml.created_at < NOW() - INTERVAL '21 days'
        """
    )
    return int(result.split()[-1]) if result else 0


async def reinforce_hot_clusters(conn: asyncpg.Connection) -> int:
    """[8] Refuerza relaciones entre memorias calientes del mismo proyecto."""
    result = await conn.execute(
        """
        UPDATE memory_relations mr
        SET weight = LEAST(1.0, mr.weight + 0.02),
            reinforcement_count = mr.reinforcement_count + 1,
            last_activated_at = NOW(),
            active = TRUE,
            updated_at = NOW()
        FROM memory_log src, memory_log dst
        WHERE mr.source_memory_id = src.id
          AND mr.target_memory_id = dst.id
          AND src.activation_score > 0.4
          AND dst.activation_score > 0.4
          AND src.project_id = dst.project_id
          AND mr.active = TRUE
          AND mr.origin <> 'manual'
        """
    )
    return int(result.split()[-1]) if result else 0


async def validate_synapse_candidates(conn, project_name: str) -> dict[str, int]:
    """[L2] NREM phase: validate Tier 3 synapse candidates."""
    stats = {"promoted": 0, "rejected": 0}
    rows = await conn.fetch(
        """
        SELECT sc.*, ms.stability_score AS src_stability, mt.stability_score AS tgt_stability
        FROM synapse_candidates sc
        JOIN memory_log ms ON ms.id = sc.source_memory_id
        JOIN memory_log mt ON mt.id = sc.target_memory_id
        JOIN projects p ON p.id = ms.project_id
        WHERE sc.status = 'pending' AND p.name = $1
        ORDER BY sc.combined_score DESC
        LIMIT 50
        """,
        project_name,
    )
    for row in rows:
        src_stable = float(row["src_stability"] or 0) > 0.1
        tgt_stable = float(row["tgt_stability"] or 0) > 0.1
        existing = await conn.fetchval(
            """
            SELECT 1 FROM memory_relations
            WHERE ((source_memory_id = $1 AND target_memory_id = $2)
                OR (source_memory_id = $2 AND target_memory_id = $1))
              AND active = TRUE
            """,
            row["source_memory_id"],
            row["target_memory_id"],
        )
        if not src_stable or not tgt_stable or existing:
            await conn.execute(
                "UPDATE synapse_candidates SET status = 'rejected', reviewed_at = NOW() WHERE id = $1",
                row["id"],
            )
            stats["rejected"] += 1
        else:
            await conn.execute(
                """
                INSERT INTO memory_relations (source_memory_id, target_memory_id, relation_type, weight, origin, evidence_json)
                VALUES ($1, $2, $3, $4, 'sleep_validation',
                        jsonb_build_object('tier', 3, 'combined_score', $5::float))
                ON CONFLICT (source_memory_id, target_memory_id, relation_type) DO NOTHING
                """,
                row["source_memory_id"],
                row["target_memory_id"],
                row["suggested_type"] or "supports",
                float(row["combined_score"]) * 0.85,
                float(row["combined_score"]),
            )
            await conn.execute(
                "UPDATE synapse_candidates SET status = 'promoted', reviewed_at = NOW() WHERE id = $1",
                row["id"],
            )
            stats["promoted"] += 1
    return stats


async def apply_adaptive_myelin_decay(conn) -> int:
    """[L3] REM phase: adaptive myelin decay — frequently used paths resist forgetting.

    decay_rate = 0.01 / (1 + 0.3 * reinforcement_count)
    """
    rows = await conn.fetch("""
        SELECT id, myelin_score, reinforcement_count
        FROM memory_relations
        WHERE myelin_score > 0
          AND last_activated_at < NOW() - INTERVAL '48 hours'
    """)
    decayed = 0
    base_decay = 0.01
    for row in rows:
        reinforcement = int(row["reinforcement_count"] or 0)
        effective_decay = base_decay / (1.0 + 0.3 * reinforcement)
        new_score = max(0.0, float(row["myelin_score"]) - effective_decay)
        await conn.execute(
            "UPDATE memory_relations SET myelin_score = $2, myelin_last_updated = NOW() WHERE id = $1",
            row["id"], new_score,
        )
        if new_score <= 0.0:
            await conn.execute(
                "UPDATE memory_relations SET active = FALSE WHERE id = $1",
                row["id"],
            )
        decayed += 1
    return decayed


async def apply_permeability_decay(conn) -> int:
    """[L2] REM phase: decay unused project permeability."""
    result = await conn.execute(
        """
        UPDATE project_permeability
        SET permeability_score = GREATEST(0.0, permeability_score - 0.005)
        WHERE last_activity < NOW() - INTERVAL '48 hours'
        """
    )
    return int(result.split()[-1]) if result else 0


async def record_sleep_cycle(conn, cycle_type: str, trigger_reason: str, projects: list[str], stats: dict) -> int:
    """Record a sleep cycle start."""
    row = await conn.fetchrow(
        """
        INSERT INTO sleep_cycles (cycle_type, trigger_reason, projects_processed, stats)
        VALUES ($1, $2, $3, $4::jsonb)
        RETURNING id
        """,
        cycle_type,
        trigger_reason,
        projects,
        json.dumps(stats),
    )
    return row["id"]


async def complete_sleep_cycle(conn, cycle_id: int, stats: dict):
    """Mark a sleep cycle as complete."""
    await conn.execute(
        """
        UPDATE sleep_cycles SET completed_at = NOW(), stats = $2::jsonb WHERE id = $1
        """,
        cycle_id,
        json.dumps(stats),
    )


async def validate_suspected_contradictions(conn: asyncpg.Connection) -> dict[str, int]:
    """[L3] NREM: re-evaluate suspected contradictions using valence opposition + negation patterns.

    Promotes to 'pending' if rescore > 0.5, dismisses if < 0.3, else keeps as 'suspected'.
    """
    stats = {"promoted": 0, "dismissed": 0}
    rows = await conn.fetch(
        """
        SELECT cq.id, cq.memory_a_id, cq.memory_b_id,
               ma.summary AS summary_a, ma.valence AS valence_a,
               mb.summary AS summary_b, mb.valence AS valence_b
        FROM contradiction_queue cq
        JOIN memory_log ma ON ma.id = cq.memory_a_id
        JOIN memory_log mb ON mb.id = cq.memory_b_id
        WHERE cq.resolution_status = 'suspected'
        ORDER BY cq.created_at ASC
        LIMIT 50
        """
    )
    for row in rows:
        score = 0.0
        valence_a = float(row["valence_a"] or 0)
        valence_b = float(row["valence_b"] or 0)
        # Valence opposition
        if valence_a * valence_b < 0:
            score += 0.35
        # Negation pattern matching
        lower_a = str(row["summary_a"] or "").lower()
        lower_b = str(row["summary_b"] or "").lower()
        pattern_score = 0.0
        for pat_a, pat_b in NEGATION_PATTERNS:
            if (re.search(pat_a, lower_a) and re.search(pat_b, lower_b)) or \
               (re.search(pat_b, lower_a) and re.search(pat_a, lower_b)):
                pattern_score += 0.15
        score += min(pattern_score, 0.35)
        # Content length divergence as weak signal
        len_a, len_b = len(lower_a), len(lower_b)
        if len_a > 0 and len_b > 0 and max(len_a, len_b) / min(len_a, len_b) > 3:
            score += 0.10
        score = min(score, 1.0)

        if score > 0.5:
            await conn.execute(
                "UPDATE contradiction_queue SET resolution_status = 'pending' WHERE id = $1",
                row["id"],
            )
            stats["promoted"] += 1
        elif score < 0.3:
            await conn.execute(
                "UPDATE contradiction_queue SET resolution_status = 'dismissed', resolved_at = NOW() WHERE id = $1",
                row["id"],
            )
            stats["dismissed"] += 1
        # else: keep as 'suspected'
    return stats


async def cleanup_orphan_relations(conn: asyncpg.Connection) -> int:
    """[L3] REM: deactivate relations where both endpoints have very low stability."""
    result = await conn.execute(
        """
        UPDATE memory_relations mr
        SET active = FALSE
        FROM memory_log src, memory_log dst
        WHERE mr.source_memory_id = src.id
          AND mr.target_memory_id = dst.id
          AND src.stability_score < 0.1
          AND dst.stability_score < 0.1
          AND mr.active = TRUE
          AND mr.origin <> 'manual'
        """
    )
    return int(result.split()[-1]) if result else 0


async def expire_stale_candidates(conn: asyncpg.Connection) -> int:
    """[L3] REM: expire Tier 3 synapse candidates older than 72 hours."""
    result = await conn.execute(
        """
        UPDATE synapse_candidates
        SET status = 'expired', reviewed_at = NOW()
        WHERE status = 'pending'
          AND created_at < NOW() - INTERVAL '72 hours'
        """
    )
    return int(result.split()[-1]) if result else 0


async def run_nrem_phase(conn: asyncpg.Connection, run_id, project_names: list[str]) -> dict:
    """[L3] NREM phase — Strengthen & Abstract.

    1. Schema extraction
    2. Suspected contradiction validation
    3. Synapse candidate validation
    4. Cluster reinforcement
    5. Contradiction resolution
    """
    nrem_stats = {
        "schemas_created": 0,
        "suspected_promoted": 0,
        "suspected_dismissed": 0,
        "candidates_promoted": 0,
        "candidates_rejected": 0,
        "clusters_reinforced": 0,
        "contradictions_resolved": 0,
    }
    # 1. Schema extraction
    await update_heartbeat()
    nrem_stats["schemas_created"] = await run_schema_extraction(conn, run_id)

    # 2. Suspected contradiction validation
    await update_heartbeat()
    suspected = await validate_suspected_contradictions(conn)
    nrem_stats["suspected_promoted"] = suspected["promoted"]
    nrem_stats["suspected_dismissed"] = suspected["dismissed"]

    # 3. Synapse candidate validation per project
    await update_heartbeat()
    for pname in project_names:
        try:
            cstats = await validate_synapse_candidates(conn, pname)
            nrem_stats["candidates_promoted"] += cstats["promoted"]
            nrem_stats["candidates_rejected"] += cstats["rejected"]
        except Exception as exc:
            logger.warning("[L3] NREM candidate validation failed for %s: %s", pname, exc)

    # 4. Cluster reinforcement
    await update_heartbeat()
    nrem_stats["clusters_reinforced"] = await reinforce_hot_clusters(conn)

    # 5. Contradiction resolution
    await update_heartbeat()
    nrem_stats["contradictions_resolved"] = await resolve_contradictions(conn)

    return nrem_stats


async def run_rem_phase(conn: asyncpg.Connection, project_names: list[str]) -> dict:
    """[L3] REM phase — Prune & Clean.

    1. Cold memory pruning (improved criteria)
    2. Orphan relation cleanup
    3. Adaptive myelin decay
    4. Permeability decay
    5. Tier 3 candidate expiry
    """
    rem_stats = {
        "memories_pruned": 0,
        "relations_orphaned": 0,
        "myelin_decayed": 0,
        "permeability_decayed": 0,
        "candidates_expired": 0,
    }
    # 1. Cold memory pruning
    await update_heartbeat()
    rem_stats["memories_pruned"] = await prune_cold_memories(conn)

    # 2. Orphan relation cleanup
    await update_heartbeat()
    rem_stats["relations_orphaned"] = await cleanup_orphan_relations(conn)

    # 3. Adaptive myelin decay
    await update_heartbeat()
    rem_stats["myelin_decayed"] = await apply_adaptive_myelin_decay(conn)

    # 4. Permeability decay
    await update_heartbeat()
    rem_stats["permeability_decayed"] = await apply_permeability_decay(conn)

    # 5. Tier 3 candidate expiry
    await update_heartbeat()
    rem_stats["candidates_expired"] = await expire_stale_candidates(conn)

    return rem_stats


async def handle_deep_sleep():
    """[8][L3] Deep Sleep Phase: structured NREM (strengthen/abstract) then REM (prune/clean)."""
    if not pg_pool:
        return
    async with pg_pool.acquire() as conn:
        locked = await conn.fetchval("SELECT pg_try_advisory_lock($1)", ADVISORY_LOCK_KEY + 1)
        if not locked:
            return
        try:
            # Check if deep sleep interval has elapsed
            last_run = await conn.fetchval(
                "SELECT COALESCE(finished_at, started_at) FROM deep_sleep_runs ORDER BY started_at DESC LIMIT 1"
            )
            if last_run and now_utc() - last_run.astimezone(timezone.utc) < timedelta(seconds=DEEP_SLEEP_INTERVAL):
                return
            run_id = await conn.fetchval(
                "INSERT INTO deep_sleep_runs (status) VALUES ('running') RETURNING id"
            )
            logger.info("[L3] Deep Sleep iniciado (run_id=%s)", run_id)
            error_text = None

            # Get all projects with activity
            project_names = [
                str(r["name"]) for r in await conn.fetch(
                    "SELECT DISTINCT p.name FROM projects p JOIN memory_log m ON m.project_id = p.id"
                )
            ]

            nrem_stats = {}
            rem_stats = {}
            try:
                # NREM phase — strengthen & abstract
                nrem_stats = await run_nrem_phase(conn, run_id, project_names)
                logger.info(
                    "[L3] NREM complete: schemas=%d suspected_promoted=%d suspected_dismissed=%d "
                    "candidates_promoted=%d candidates_rejected=%d reinforced=%d contradictions=%d",
                    nrem_stats.get("schemas_created", 0),
                    nrem_stats.get("suspected_promoted", 0),
                    nrem_stats.get("suspected_dismissed", 0),
                    nrem_stats.get("candidates_promoted", 0),
                    nrem_stats.get("candidates_rejected", 0),
                    nrem_stats.get("clusters_reinforced", 0),
                    nrem_stats.get("contradictions_resolved", 0),
                )

                # REM phase — prune & clean
                rem_stats = await run_rem_phase(conn, project_names)
                logger.info(
                    "[L3] REM complete: pruned=%d orphaned=%d myelin_decayed=%d "
                    "permeability_decayed=%d candidates_expired=%d",
                    rem_stats.get("memories_pruned", 0),
                    rem_stats.get("relations_orphaned", 0),
                    rem_stats.get("myelin_decayed", 0),
                    rem_stats.get("permeability_decayed", 0),
                    rem_stats.get("candidates_expired", 0),
                )
            except Exception as exc:
                logger.exception("[L3] Deep Sleep failed partially")
                error_text = str(exc)[:2000]

            # Record two sleep cycles: NREM and REM
            try:
                nrem_cycle_id = await record_sleep_cycle(conn, "nrem", "deep_sleep_interval", project_names, {})
                await complete_sleep_cycle(conn, nrem_cycle_id, nrem_stats)
            except Exception:
                logger.debug("Failed to record NREM sleep cycle")
            try:
                rem_cycle_id = await record_sleep_cycle(conn, "rem", "deep_sleep_interval", project_names, {})
                await complete_sleep_cycle(conn, rem_cycle_id, rem_stats)
            except Exception:
                logger.debug("Failed to record REM sleep cycle")

            # Compute combined stats for deep_sleep_runs
            memories_scanned_val = await conn.fetchval("SELECT COUNT(*) FROM memory_log") or 0
            combined = {**nrem_stats, **rem_stats}
            await conn.execute(
                """
                UPDATE deep_sleep_runs
                SET status = $2,
                    memories_scanned = $3,
                    schemas_created = $4,
                    contradictions_resolved = $5,
                    memories_pruned = $6,
                    relations_reinforced = $7,
                    error = $8,
                    finished_at = NOW()
                WHERE id = $1
                """,
                run_id,
                "failed" if error_text else "completed",
                memories_scanned_val,
                combined.get("schemas_created", 0),
                combined.get("contradictions_resolved", 0),
                combined.get("memories_pruned", 0),
                combined.get("clusters_reinforced", 0),
                error_text,
            )
            logger.info("[L3] Deep Sleep completed (run_id=%s)", run_id)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_KEY + 1)


async def run_loop():
    while True:
        try:
            await update_heartbeat()
            await handle_manual_runs()
            await handle_scheduled_run()
            await handle_deep_sleep()
        except Exception:
            logger.exception("Bucle principal del reflection worker fallo")
        await asyncio.sleep(REFLECTION_POLL_INTERVAL)


async def startup():
    global pg_pool, redis_client, http_client, deepseek_client
    global TEST_NOW_OVERRIDE

    async def init_postgres():
        return await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=WORKER_PG_POOL_MAX_SIZE, command_timeout=30)

    async def init_redis():
        client = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        await client.ping()
        return client

    async def init_api():
        client = httpx.AsyncClient(timeout=20.0)
        response = await client.get(f"{API_SERVER_URL}/health")
        response.raise_for_status()
        return client

    pg_pool = await retry_async("postgres", init_postgres)
    redis_client = await retry_async("redis", init_redis)
    http_client = await retry_async("api-server", init_api)
    if AI_MEMORY_TEST_MODE and AI_MEMORY_TEST_NOW:
        TEST_NOW_OVERRIDE = now_utc()
    deepseek_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY or "change-me", base_url=DEEPSEEK_BASE_URL)
    await update_heartbeat()
    logger.info("Reflection worker listo")


async def shutdown():
    if pg_pool:
        await pg_pool.close()
    if redis_client:
        await redis_client.close()
    if http_client:
        await http_client.aclose()


async def main():
    await startup()
    try:
        await run_loop()
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
