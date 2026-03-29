import asyncio
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import httpx
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ai-memory-brain")

QDRANT_HOST = os.environ["QDRANT_HOST"]
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"]
POSTGRES_URL = os.environ["POSTGRES_URL"]
REDIS_URL = os.environ["REDIS_URL"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
MEM0_URL = os.environ.get("MEM0_URL", "")
API_KEY = os.environ["API_KEY"]
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-reasoner")
WORKER_HEARTBEAT_KEY = os.environ.get("WORKER_HEARTBEAT_KEY", "reflection_worker:heartbeat")
WORKER_HEARTBEAT_MAX_AGE = int(os.environ.get("WORKER_HEARTBEAT_MAX_AGE_SECONDS", "120"))
COLLECTION_NAME = "memories"
VECTOR_DIM = 1536

qdrant: Optional[AsyncQdrantClient] = None
pg_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None
openai_client: Optional[AsyncOpenAI] = None
http_client: Optional[httpx.AsyncClient] = None

app = FastAPI(title="AI Memory Brain", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
mcp = FastMCP("AIMemoryBrain", streamable_http_path="/")


class MemoryCreateRequest(BaseModel):
    content: str
    project: str
    memory_type: str = "general"
    tags: str = ""
    importance: float = 0.7
    agent_id: str = "api"
    skip_similar: bool = False
    dedupe_threshold: float = Field(default=0.92, ge=0.5, le=0.999)


class SearchMemoryRequest(BaseModel):
    query: str
    project: Optional[str] = None
    memory_type: Optional[str] = None
    limit: int = Field(default=8, ge=1, le=25)


class TaskStateRequest(BaseModel):
    task_title: str
    project: str
    new_state: str
    details: str = ""
    agent_id: str = "api"


class DecisionRequest(BaseModel):
    title: str
    decision: str
    project: str
    rationale: str = ""
    alternatives: str = ""
    tags: str = ""
    agent_id: str = "api"


class ErrorRequest(BaseModel):
    error_description: str
    solution: str
    project: str
    error_signature: str = ""
    tags: str = ""


class SessionDecisionItem(BaseModel):
    title: str
    decision: str
    rationale: str = ""


class SessionErrorItem(BaseModel):
    error_signature: str = ""
    description: str
    solution: str


class SessionFollowUpItem(BaseModel):
    title: str
    state: str = "pending"
    details: str = ""


class SessionSummaryRequest(BaseModel):
    project: str
    agent_id: str
    session_id: str
    goal: str
    outcome: str
    summary: str
    changes: list[str] = Field(default_factory=list)
    decisions: list[SessionDecisionItem] = Field(default_factory=list)
    errors: list[SessionErrorItem] = Field(default_factory=list)
    follow_ups: list[SessionFollowUpItem] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def has_real_secret(value: Optional[str]) -> bool:
    return bool(value and "change-me" not in value)


def normalize_tags(tags: str | list[str]) -> list[str]:
    if isinstance(tags, list):
        return [str(tag).strip() for tag in tags if str(tag).strip()]
    return [tag.strip() for tag in tags.split(",") if tag.strip()]


def tags_to_string(tags: str | list[str]) -> str:
    return ",".join(normalize_tags(tags))


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_session_summary_document(payload: SessionSummaryRequest) -> str:
    lines = [
        f"Project: {payload.project}",
        f"Agent ID: {payload.agent_id}",
        f"Session ID: {payload.session_id}",
        f"Goal: {payload.goal}",
        f"Outcome: {payload.outcome}",
        "Summary:",
        payload.summary,
    ]

    if payload.changes:
        lines.append("Changes:")
        lines.extend([f"- {item}" for item in payload.changes])

    if payload.decisions:
        lines.append("Decisions:")
        lines.extend([f"- {item.title}: {item.decision} | rationale={item.rationale}" for item in payload.decisions])

    if payload.errors:
        lines.append("Errors:")
        lines.extend(
            [f"- {item.error_signature or item.description[:80]}: {item.description} | solution={item.solution}" for item in payload.errors]
        )

    if payload.follow_ups:
        lines.append("Follow-ups:")
        lines.extend([f"- [{item.state}] {item.title}: {item.details}" for item in payload.follow_ups])

    if payload.tags:
        lines.append(f"Tags: {', '.join(payload.tags)}")

    return "\n".join(lines)


def serialize_row(row: Optional[asyncpg.Record]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    result: dict[str, Any] = {}
    for key, value in dict(row).items():
        if isinstance(value, datetime):
            result[key] = value.astimezone(timezone.utc).isoformat()
        elif isinstance(value, uuid.UUID):
            result[key] = str(value)
        else:
            result[key] = value
    return result


async def ensure_project(project_name: str) -> Optional[uuid.UUID]:
    if not pg_pool:
        return None
    async with pg_pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO projects (name) VALUES ($1)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            project_name,
        )


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


async def get_embedding(text: str) -> list[float]:
    cache_key = "embed:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    if redis_client:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    response = await openai_client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    embedding = response.data[0].embedding

    if redis_client:
        await redis_client.setex(cache_key, 3600, json.dumps(embedding))
    return embedding


async def find_similar_memory(
    content: str,
    project: str,
    memory_type: Optional[str] = None,
    threshold: float = 0.92,
) -> Optional[dict[str, Any]]:
    embedding = await get_embedding(content)
    conditions = [FieldCondition(key="project_id", match=MatchValue(value=project))]
    if memory_type:
        conditions.append(FieldCondition(key="memory_type", match=MatchValue(value=memory_type)))
    response = await qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding,
        query_filter=Filter(must=conditions),
        limit=1,
        with_payload=True,
        score_threshold=threshold,
    )
    results = response.points
    if not results:
        return None
    top = results[0]
    return {"id": str(top.id), "score": float(top.score), "payload": top.payload}


async def mem0_health() -> bool:
    if not http_client or not MEM0_URL:
        return False
    try:
        response = await http_client.get(f"{MEM0_URL}/health", timeout=5.0)
        return response.status_code < 400
    except Exception:
        return False


async def mem0_search_context(query: str, project: str, agent_id: Optional[str] = None, limit: int = 5) -> list[str]:
    if not http_client or not MEM0_URL:
        return []
    payload: dict[str, Any] = {
        "query": query,
        "user_id": project,
        "limit": limit,
    }
    if agent_id:
        payload["agent_id"] = agent_id
    try:
        response = await http_client.post(f"{MEM0_URL}/search", json=payload, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("mem0 search fallo para context: %s", exc)
        return []

    raw_results = data.get("results", data if isinstance(data, list) else [])
    lines: list[str] = []
    for item in raw_results[:limit]:
        if not isinstance(item, dict):
            lines.append(f"- {item}")
            continue
        memory_text = item.get("memory") or item.get("content") or item.get("text")
        if not memory_text and isinstance(item.get("payload"), dict):
            memory_text = item["payload"].get("content")
        if not memory_text:
            memory_text = canonical_json(item)
        score = item.get("score")
        prefix = f"- score={score:.3f} " if isinstance(score, (int, float)) else "- "
        lines.append(prefix + str(memory_text)[:280])
    return lines


async def ingest_session_into_mem0(payload: SessionSummaryRequest) -> tuple[bool, Optional[str]]:
    if not http_client or not MEM0_URL:
        return False, "mem0_unavailable"

    body = {
        "messages": [{"role": "user", "content": build_session_summary_document(payload)}],
        "user_id": payload.project,
        "agent_id": payload.agent_id,
        "run_id": payload.session_id,
        "metadata": {
            "project": payload.project,
            "session_id": payload.session_id,
            "goal": payload.goal,
            "outcome": payload.outcome,
            "tags": payload.tags,
            "record_type": "session_summary",
        },
    }
    try:
        response = await http_client.post(f"{MEM0_URL}/memories", json=body, timeout=25.0)
        response.raise_for_status()
        return True, None
    except Exception as exc:
        logger.warning("Mem0 no pudo ingerir session summary %s: %s", payload.session_id, exc)
        return False, str(exc)


async def persist_session_summary(payload: SessionSummaryRequest) -> dict[str, Any]:
    if not pg_pool:
        return {"error": "postgres_unavailable"}

    project_id = await ensure_project(payload.project)
    payload_dict = payload.model_dump()
    checksum = digest_text(canonical_json(payload_dict))

    async with pg_pool.acquire() as conn:
        inserted = await conn.fetchrow(
            """
            INSERT INTO session_summaries (project_id, agent_id, session_id, payload_json, checksum, status)
            VALUES ($1, $2, $3, $4::jsonb, $5, 'pending')
            ON CONFLICT (checksum) DO NOTHING
            RETURNING id
            """,
            project_id,
            payload.agent_id,
            payload.session_id,
            json.dumps(payload_dict, ensure_ascii=False),
            checksum,
        )

    if not inserted:
        return {"duplicate": True, "checksum": checksum}

    working_memory_ingested, mem0_error = await ingest_session_into_mem0(payload)

    async with pg_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE session_summaries
            SET last_error = $2
            WHERE checksum = $1
            """,
            checksum,
            mem0_error,
        )

    return {
        "checksum": checksum,
        "working_memory_ingested": working_memory_ingested,
        "mem0_error": mem0_error,
    }


async def get_worker_heartbeat_state() -> tuple[bool, Optional[str]]:
    if not redis_client:
        return False, None
    raw = await redis_client.get(WORKER_HEARTBEAT_KEY)
    if not raw:
        return False, None
    heartbeat_value = raw
    if raw.startswith("{"):
        try:
            heartbeat_value = json.loads(raw).get("timestamp")
        except json.JSONDecodeError:
            heartbeat_value = raw
    try:
        heartbeat_dt = datetime.fromisoformat(heartbeat_value)
    except Exception:
        return False, heartbeat_value
    age = (datetime.now(timezone.utc) - heartbeat_dt.astimezone(timezone.utc)).total_seconds()
    return age <= WORKER_HEARTBEAT_MAX_AGE, heartbeat_dt.astimezone(timezone.utc).isoformat()


async def get_reflection_status_payload() -> dict[str, Any]:
    if not pg_pool:
        return {"pending_sessions": 0, "processing_sessions": 0, "worker_healthy": False}
    worker_healthy, worker_last_heartbeat = await get_worker_heartbeat_state()
    async with pg_pool.acquire() as conn:
        pending_sessions = await conn.fetchval("SELECT COUNT(*) FROM session_summaries WHERE status = 'pending'")
        processing_sessions = await conn.fetchval("SELECT COUNT(*) FROM session_summaries WHERE status = 'processing'")
        last_run = await conn.fetchrow(
            """
            SELECT id, mode, status, model, input_count, promoted_count, error, started_at, finished_at
            FROM reflection_runs
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        last_successful_run = await conn.fetchrow(
            """
            SELECT id, mode, status, model, input_count, promoted_count, error, started_at, finished_at
            FROM reflection_runs
            WHERE status = 'completed' AND (error IS NULL OR error = '')
            ORDER BY finished_at DESC NULLS LAST
            LIMIT 1
            """
        )
    return {
        "pending_sessions": pending_sessions,
        "processing_sessions": processing_sessions,
        "worker_healthy": worker_healthy,
        "worker_last_heartbeat": worker_last_heartbeat,
        "last_run": serialize_row(last_run),
        "last_successful_run": serialize_row(last_successful_run),
    }


async def queue_manual_reflection() -> dict[str, Any]:
    if not pg_pool:
        return {"error": "postgres_unavailable"}
    async with pg_pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id, status
            FROM reflection_runs
            WHERE mode = 'manual' AND status IN ('queued', 'running')
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        if existing:
            return {"run_id": str(existing["id"]), "queued": False, "status": existing["status"]}
        run_id = await conn.fetchval(
            """
            INSERT INTO reflection_runs (mode, status, model)
            VALUES ('manual', 'queued', $1)
            RETURNING id
            """,
            DEEPSEEK_MODEL,
        )
    return {"run_id": str(run_id), "queued": True, "status": "queued"}


@app.middleware("http")
async def enforce_api_key(request: Request, call_next):
    path = request.url.path
    if path in {"/health", "/ready"}:
        return await call_next(request)
    if path == "/stats" or path.startswith("/api/") or path.startswith("/mcp"):
        if request.headers.get("X-API-Key") != API_KEY:
            return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
    return await call_next(request)


async def init_qdrant():
    global qdrant
    qdrant = AsyncQdrantClient(
        url=f"http://{QDRANT_HOST}:{QDRANT_PORT}",
        api_key=QDRANT_API_KEY,
        prefer_grpc=False,
        https=False,
        check_compatibility=False,
    )
    collections = await qdrant.get_collections()
    names = [collection.name for collection in collections.collections]
    if COLLECTION_NAME not in names:
        await qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_DIM,
                distance=Distance.COSINE,
                on_disk=True,
            ),
        )
        for field in ["project_id", "agent_id", "memory_type"]:
            await qdrant.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        logger.info("Coleccion '%s' creada en Qdrant", COLLECTION_NAME)


async def ready_status() -> dict:
    worker_healthy, worker_last_heartbeat = await get_worker_heartbeat_state()
    status = {
        "postgres": False,
        "redis": False,
        "qdrant": False,
        "mem0": False,
        "reflection_worker": worker_healthy,
        "worker_last_heartbeat": worker_last_heartbeat,
        "openai_configured": has_real_secret(OPENAI_API_KEY),
        "deepseek_configured": has_real_secret(DEEPSEEK_API_KEY),
    }

    if pg_pool:
        try:
            async with pg_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            status["postgres"] = True
        except Exception:
            pass

    if redis_client:
        try:
            status["redis"] = (await redis_client.ping()) is True
        except Exception:
            pass

    if qdrant:
        try:
            await qdrant.get_collection(COLLECTION_NAME)
            status["qdrant"] = True
        except Exception:
            pass

    status["mem0"] = await mem0_health()
    status["ready"] = all(
        [
            status["postgres"],
            status["redis"],
            status["qdrant"],
            status["mem0"],
            status["reflection_worker"],
            status["openai_configured"],
            status["deepseek_configured"],
        ]
    )
    return status


@mcp.tool()
async def store_memory(
    content: str,
    project: str,
    memory_type: str = "general",
    tags: str = "",
    importance: float = 0.7,
    agent_id: str = "unknown",
    skip_similar: bool = False,
    dedupe_threshold: float = 0.92,
) -> str:
    try:
        await ensure_project(project)
        tags_list = normalize_tags(tags)

        if skip_similar:
            similar = await find_similar_memory(content, project, memory_type, dedupe_threshold)
            if similar:
                return (
                    f"SKIP similar_memory existing={similar['id']} "
                    f"score={similar['score']:.3f} project={project} type={memory_type}"
                )

        embedding = await get_embedding(content)
        memory_id = str(uuid.uuid4())
        payload = {
            "content": content,
            "project_id": project,
            "agent_id": agent_id,
            "memory_type": memory_type,
            "tags": tags_list,
            "importance": importance,
            "created_at": now_iso(),
            "access_count": 0,
        }
        await qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(id=memory_id, vector=embedding, payload=payload)],
        )
        if pg_pool:
            async with pg_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO memory_log
                    (id, project_id, agent_id, action_type, summary, details, importance, tags)
                    VALUES (
                        $1,
                        (SELECT id FROM projects WHERE name = $2 LIMIT 1),
                        $3, $4, $5, $6::jsonb, $7, $8
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    uuid.UUID(memory_id),
                    project,
                    agent_id,
                    memory_type,
                    content[:500],
                    json.dumps({"content": content}),
                    importance,
                    tags_list,
                )
        return f"OK memory_id={memory_id} project={project} type={memory_type}"
    except Exception as exc:
        logger.exception("store_memory fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def search_memory(
    query: str,
    project: Optional[str] = None,
    memory_type: Optional[str] = None,
    limit: int = 8,
) -> str:
    try:
        embedding = await get_embedding(query)
        conditions = []
        if project:
            conditions.append(FieldCondition(key="project_id", match=MatchValue(value=project)))
        if memory_type:
            conditions.append(FieldCondition(key="memory_type", match=MatchValue(value=memory_type)))
        search_filter = Filter(must=conditions) if conditions else None
        response = await qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=embedding,
            query_filter=search_filter,
            limit=limit,
            with_payload=True,
            score_threshold=0.35,
        )
        results = response.points
        if not results:
            return f"No encontre memorias relevantes para '{query}'"
        lines = [f"{len(results)} memorias relevantes para '{query}':"]
        for index, result in enumerate(results, 1):
            payload = result.payload
            lines.append(
                f"[{index}] score={result.score:.3f} "
                f"type={payload.get('memory_type', '?')} "
                f"project={payload.get('project_id', '?')} "
                f"content={payload.get('content', '')[:260]}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.exception("search_memory fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def get_project_context(project_name: str, agent_id: Optional[str] = None) -> str:
    try:
        output = [f"PROJECT {project_name}"]
        if agent_id:
            output.append(f"AGENT {agent_id}")
        if pg_pool:
            async with pg_pool.acquire() as conn:
                tasks = await conn.fetch(
                    """
                    SELECT t.title, t.state, t.priority, t.agent_id
                    FROM tasks t
                    JOIN projects p ON p.id = t.project_id
                    WHERE p.name = $1 AND t.state NOT IN ('done', 'cancelled')
                    ORDER BY t.priority DESC, t.created_at DESC
                    LIMIT 10
                    """,
                    project_name,
                )
                if tasks:
                    output.append("ACTIVE TASKS")
                    output.extend(
                        [
                            f"- [{task['state']}] {task['title']} (p={task['priority']}, agent={task['agent_id']})"
                            for task in tasks
                        ]
                    )

                decisions = await conn.fetch(
                    """
                    SELECT d.title, d.decision, d.rationale
                    FROM decisions d
                    JOIN projects p ON p.id = d.project_id
                    WHERE p.name = $1
                    ORDER BY d.created_at DESC
                    LIMIT 5
                    """,
                    project_name,
                )
                if decisions:
                    output.append("DECISIONS")
                    output.extend(
                        [f"- {row['title']}: {row['decision']} | rationale={row['rationale'] or ''}" for row in decisions]
                    )

        working_memory = await mem0_search_context(
            query=f"recent work, active context, open loops, errors and decisions for project {project_name}",
            project=project_name,
            agent_id=agent_id,
            limit=5,
        )
        if working_memory:
            output.append("WORKING MEMORY")
            output.extend(working_memory)

        semantic = await search_memory(f"context architecture overview {project_name}", project=project_name, limit=5)
        output.append("MEMORY SEARCH")
        output.append(semantic)
        return "\n".join(output)
    except Exception as exc:
        logger.exception("get_project_context fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def update_task_state(
    task_title: str,
    project: str,
    new_state: str,
    details: str = "",
    agent_id: str = "unknown",
) -> str:
    valid_states = {"pending", "active", "blocked", "done", "cancelled"}
    if new_state not in valid_states:
        return "ERROR invalid_state"
    try:
        if not pg_pool:
            return "ERROR postgres_unavailable"
        project_id = await ensure_project(project)
        async with pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tasks (project_id, title, state, description, agent_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (project_id, title) DO UPDATE
                SET state = EXCLUDED.state,
                    description = CASE
                        WHEN EXCLUDED.description <> '' THEN EXCLUDED.description
                        ELSE tasks.description
                    END,
                    agent_id = EXCLUDED.agent_id,
                    updated_at = NOW(),
                    completed_at = CASE WHEN EXCLUDED.state = 'done' THEN NOW() ELSE NULL END
                """,
                project_id,
                task_title,
                new_state,
                details,
                agent_id,
            )
        return f"OK task='{task_title}' state={new_state} project={project}"
    except Exception as exc:
        logger.exception("update_task_state fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def list_active_tasks(project: Optional[str] = None) -> str:
    try:
        if not pg_pool:
            return "ERROR postgres_unavailable"
        async with pg_pool.acquire() as conn:
            if project:
                rows = await conn.fetch(
                    """
                    SELECT t.title, t.state, t.priority, t.agent_id, p.name AS project
                    FROM tasks t
                    JOIN projects p ON p.id = t.project_id
                    WHERE p.name = $1 AND t.state NOT IN ('done', 'cancelled')
                    ORDER BY t.priority DESC, t.created_at ASC
                    """,
                    project,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT t.title, t.state, t.priority, t.agent_id, p.name AS project
                    FROM tasks t
                    JOIN projects p ON p.id = t.project_id
                    WHERE t.state NOT IN ('done', 'cancelled')
                    ORDER BY p.name, t.priority DESC, t.created_at ASC
                    LIMIT 50
                    """
                )
        if not rows:
            return "No active tasks"
        return "\n".join(
            [
                f"[{row['project']}] [{row['state']}] {row['title']} (p={row['priority']}, agent={row['agent_id']})"
                for row in rows
            ]
        )
    except Exception as exc:
        logger.exception("list_active_tasks fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def store_decision(
    title: str,
    decision: str,
    project: str,
    rationale: str = "",
    alternatives: str = "",
    tags: str = "",
    agent_id: str = "unknown",
) -> str:
    try:
        if not pg_pool:
            return "ERROR postgres_unavailable"
        project_id = await ensure_project(project)
        tags_list = normalize_tags(tags)
        async with pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO decisions
                (project_id, title, decision, rationale, alternatives, agent_id, tags)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                project_id,
                title,
                decision,
                rationale,
                alternatives,
                agent_id,
                tags_list,
            )
        await store_memory(
            content=f"DECISION: {title}\n{decision}\nRationale: {rationale}",
            project=project,
            memory_type="decision",
            tags=tags,
            importance=0.9,
            agent_id=agent_id,
            skip_similar=True,
        )
        return f"OK decision='{title}' project={project}"
    except Exception as exc:
        logger.exception("store_decision fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def store_error(
    error_description: str,
    solution: str,
    project: str,
    error_signature: str = "",
    tags: str = "",
) -> str:
    try:
        if not pg_pool:
            return "ERROR postgres_unavailable"
        project_id = await ensure_project(project)
        signature = error_signature or error_description[:100]
        tags_list = normalize_tags(tags)
        async with pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO known_errors
                (project_id, error_signature, description, solution, tags)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (project_id, error_signature) DO UPDATE
                SET description = EXCLUDED.description,
                    solution = EXCLUDED.solution,
                    tags = EXCLUDED.tags,
                    occurrence_count = known_errors.occurrence_count + 1,
                    last_seen = NOW()
                """,
                project_id,
                signature,
                error_description,
                solution,
                tags_list,
            )
        await store_memory(
            content=f"KNOWN ERROR: {error_description}\nSOLUTION: {solution}",
            project=project,
            memory_type="error",
            tags=tags,
            importance=0.95,
            agent_id="error-recorder",
            skip_similar=True,
        )
        return f"OK error_signature='{signature}' project={project}"
    except Exception as exc:
        logger.exception("store_error fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def record_session_summary(
    project: str,
    agent_id: str,
    session_id: str,
    goal: str,
    outcome: str,
    summary: str,
    changes: Optional[list[str]] = None,
    decisions: Optional[list[dict[str, str]]] = None,
    errors: Optional[list[dict[str, str]]] = None,
    follow_ups: Optional[list[dict[str, str]]] = None,
    tags: Optional[list[str]] = None,
) -> str:
    try:
        payload = SessionSummaryRequest(
            project=project,
            agent_id=agent_id,
            session_id=session_id,
            goal=goal,
            outcome=outcome,
            summary=summary,
            changes=changes or [],
            decisions=[SessionDecisionItem(**item) for item in (decisions or [])],
            errors=[SessionErrorItem(**item) for item in (errors or [])],
            follow_ups=[SessionFollowUpItem(**item) for item in (follow_ups or [])],
            tags=tags or [],
        )
        result = await persist_session_summary(payload)
        if result.get("error"):
            return f"ERROR {result['error']}"
        if result.get("duplicate"):
            return f"ERROR duplicate_session checksum={result['checksum']}"
        return (
            f"OK session_id={session_id} checksum={result['checksum']} "
            f"working_memory_ingested={str(result['working_memory_ingested']).lower()}"
        )
    except Exception as exc:
        logger.exception("record_session_summary fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def run_memory_reflection() -> str:
    try:
        result = await queue_manual_reflection()
        if result.get("error"):
            return f"ERROR {result['error']}"
        return f"OK run_id={result['run_id']} status={result['status']} queued={str(result['queued']).lower()}"
    except Exception as exc:
        logger.exception("run_memory_reflection fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def get_reflection_status() -> str:
    try:
        status = await get_reflection_status_payload()
        return json.dumps(status, ensure_ascii=False)
    except Exception as exc:
        logger.exception("get_reflection_status fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def delete_memory(memory_id: str) -> str:
    try:
        await qdrant.delete(collection_name=COLLECTION_NAME, points_selector=[memory_id])
        return f"OK deleted={memory_id}"
    except Exception as exc:
        logger.exception("delete_memory fallo")
        return f"ERROR {exc}"


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": now_iso()}


@app.get("/ready")
async def ready():
    status = await ready_status()
    code = 200 if status["ready"] else 503
    return JSONResponse(status_code=code, content=status)


@app.get("/stats")
async def stats():
    info = await qdrant.get_collection(COLLECTION_NAME)
    payload = info.model_dump()
    return {
        "points_count": payload.get("points_count", 0),
        "indexed_vectors_count": payload.get("indexed_vectors_count", 0),
        "segments_count": payload.get("segments_count", 0),
        "collection": COLLECTION_NAME,
    }


@app.post("/api/memories")
async def create_memory(payload: MemoryCreateRequest):
    result = await store_memory(**payload.model_dump())
    if result.startswith("ERROR"):
        raise HTTPException(status_code=500, detail=result)
    return {"result": result}


@app.post("/api/search")
async def api_search_memory(payload: SearchMemoryRequest):
    result = await search_memory(**payload.model_dump())
    if result.startswith("ERROR"):
        raise HTTPException(status_code=500, detail=result)
    return {"result": result}


@app.get("/api/project-context")
async def api_project_context(project_name: str, agent_id: Optional[str] = None):
    result = await get_project_context(project_name, agent_id)
    if result.startswith("ERROR"):
        raise HTTPException(status_code=500, detail=result)
    return {"result": result}


@app.post("/api/tasks/state")
async def api_task_state(payload: TaskStateRequest):
    result = await update_task_state(**payload.model_dump())
    if result.startswith("ERROR"):
        raise HTTPException(status_code=400, detail=result)
    return {"result": result}


@app.get("/api/tasks")
async def api_list_tasks(project: Optional[str] = None):
    result = await list_active_tasks(project)
    if result.startswith("ERROR"):
        raise HTTPException(status_code=500, detail=result)
    return {"result": result}


@app.post("/api/decisions")
async def api_store_decision(payload: DecisionRequest):
    result = await store_decision(**payload.model_dump())
    if result.startswith("ERROR"):
        raise HTTPException(status_code=500, detail=result)
    return {"result": result}


@app.post("/api/errors")
async def api_store_error(payload: ErrorRequest):
    result = await store_error(**payload.model_dump())
    if result.startswith("ERROR"):
        raise HTTPException(status_code=500, detail=result)
    return {"result": result}


@app.post("/api/sessions")
async def api_record_session(payload: SessionSummaryRequest):
    result = await persist_session_summary(payload)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    if result.get("duplicate"):
        raise HTTPException(status_code=409, detail={"message": "duplicate_session", "checksum": result["checksum"]})
    return {
        "result": "OK",
        "session_id": payload.session_id,
        "checksum": result["checksum"],
        "working_memory_ingested": result["working_memory_ingested"],
        "mem0_error": result["mem0_error"],
    }


@app.post("/api/reflections/run")
async def api_run_reflection():
    result = await queue_manual_reflection()
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/api/reflections/status")
async def api_reflection_status():
    return await get_reflection_status_payload()


@app.on_event("startup")
async def startup():
    global pg_pool, redis_client, openai_client, http_client
    logger.info("Iniciando AI Memory Brain")
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    http_client = httpx.AsyncClient(timeout=10.0)

    async def init_postgres():
        return await asyncpg.create_pool(
            POSTGRES_URL,
            min_size=1,
            max_size=8,
            command_timeout=30,
        )

    async def init_redis():
        client = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        await client.ping()
        return client

    pg_pool = await retry_async("postgres", init_postgres)
    logger.info("PostgreSQL conectado")
    redis_client = await retry_async("redis", init_redis)
    logger.info("Redis conectado")
    await retry_async("qdrant", init_qdrant)
    logger.info("Qdrant conectado")

    if MEM0_URL:
        try:
            await retry_async("mem0", lambda: http_client.get(f"{MEM0_URL}/health"), attempts=8, delay=2.0)
            logger.info("Mem0 disponible")
        except Exception as exc:
            logger.warning("Mem0 no listo aun: %s", exc)


@app.on_event("shutdown")
async def shutdown():
    if pg_pool:
        await pg_pool.close()
    if redis_client:
        await redis_client.close()
    if qdrant:
        await qdrant.close()
    if http_client:
        await http_client.aclose()


mcp_app = mcp.streamable_http_app()
app.mount("/mcp", mcp_app)


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8050, log_level="info", workers=1)
