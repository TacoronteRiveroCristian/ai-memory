import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import asyncpg
import httpx
import redis.asyncio as aioredis
from openai import AsyncOpenAI

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("reflection-worker")

POSTGRES_URL = os.environ["POSTGRES_URL"]
REDIS_URL = os.environ["REDIS_URL"]
API_SERVER_URL = os.environ["API_SERVER_URL"]
API_KEY = os.environ["API_KEY"]
MEM0_URL = os.environ["MEM0_URL"]
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-reasoner")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
REFLECTION_INTERVAL = int(os.environ.get("REFLECTION_INTERVAL_SECONDS", "21600"))
REFLECTION_POLL_INTERVAL = int(os.environ.get("REFLECTION_POLL_INTERVAL_SECONDS", "30"))
WORKER_HEARTBEAT_KEY = os.environ.get("WORKER_HEARTBEAT_KEY", "reflection_worker:heartbeat")
WORKER_HEARTBEAT_TTL = int(os.environ.get("WORKER_HEARTBEAT_TTL_SECONDS", "120"))
HEARTBEAT_FILE = Path("/tmp/reflection-worker-heartbeat")
ADVISORY_LOCK_KEY = 829311
VALID_TASK_STATES = {"pending", "active", "blocked", "done", "cancelled"}

pg_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None
http_client: Optional[httpx.AsyncClient] = None
deepseek_client: Optional[AsyncOpenAI] = None


def now_utc() -> datetime:
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
    response = await http_client.request(method, f"{API_SERVER_URL}{path}", json=payload, headers=headers, timeout=30.0)
    response.raise_for_status()
    return response.json()


async def mem0_search(payload: dict[str, Any]) -> list[str]:
    body = {
        "query": f"recent work context for goal {payload['goal']} and outcome {payload['outcome']}. Summary: {payload['summary']}",
        "user_id": payload["project"],
        "agent_id": payload["agent_id"],
        "limit": 6,
    }
    try:
        response = await http_client.post(f"{MEM0_URL}/search", json=body, timeout=15.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("No fue posible consultar Mem0 para la sesion %s: %s", payload["session_id"], exc)
        return []

    raw_results = data.get("results", data if isinstance(data, list) else [])
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
    return results


async def deepseek_reflection(payload: dict[str, Any], working_memory: list[str]) -> dict[str, Any]:
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
    return await promote_findings(conn, run_id, payload, findings)


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


async def run_loop():
    while True:
        try:
            await update_heartbeat()
            await handle_manual_runs()
            await handle_scheduled_run()
        except Exception:
            logger.exception("Bucle principal del reflection worker fallo")
        await asyncio.sleep(REFLECTION_POLL_INTERVAL)


async def startup():
    global pg_pool, redis_client, http_client, deepseek_client

    async def init_postgres():
        return await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=4, command_timeout=30)

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
