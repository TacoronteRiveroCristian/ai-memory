import asyncio
import hashlib
import json
import logging
import math
import os
import re
import uuid
from contextlib import asynccontextmanager
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
from mcp.server.transport_security import TransportSecuritySettings
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
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
WORKER_HEARTBEAT_KEY = os.environ.get("WORKER_HEARTBEAT_KEY", "reflection_worker:heartbeat")
WORKER_HEARTBEAT_MAX_AGE = int(os.environ.get("WORKER_HEARTBEAT_MAX_AGE_SECONDS", "120"))
MEM0_INGEST_TIMEOUT_SECONDS = float(os.environ.get("MEM0_INGEST_TIMEOUT_SECONDS", "90"))
COLLECTION_NAME = "memories"
VECTOR_DIM = 1536
VALID_SEARCH_SCOPES = {"project", "bridged", "global"}
VALID_RELATION_TYPES = {"same_concept", "extends", "supports", "applies_to", "derived_from", "contradicts"}
RELATION_ACTIVE_THRESHOLD = 0.18
TAG_NORMALIZE_RE = re.compile(r"[^a-z0-9/_-]+")
AUTO_LINK_CANDIDATE_LIMIT = 6
AUTO_LINK_SCORE_THRESHOLD = 0.78

qdrant: Optional[AsyncQdrantClient] = None
pg_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None
openai_client: Optional[AsyncOpenAI] = None
deepseek_client: Optional[AsyncOpenAI] = None
http_client: Optional[httpx.AsyncClient] = None

app = FastAPI(title="AI Memory Brain", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
mcp = FastMCP(
    "AIMemoryBrain",
    streamable_http_path="/",
    # This instance is accessed from other machines on the LAN during testing,
    # so localhost-only host validation would reject legitimate requests.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
mcp_app = mcp.streamable_http_app()


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
    scope: str = "project"
    tags: list[str] = Field(default_factory=list)


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


class LinkMemoriesRequest(BaseModel):
    source_memory_id: str
    target_memory_id: str
    relation_type: str
    reason: str
    weight: float = Field(default=0.75, ge=0.05, le=1.0)


class BridgeProjectsRequest(BaseModel):
    project: str
    related_project: str
    reason: str
    active: bool = True
    created_by: str = "api"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def has_real_secret(value: Optional[str]) -> bool:
    return bool(value and "change-me" not in value)


def canonicalize_tag(tag: str) -> str:
    normalized = TAG_NORMALIZE_RE.sub("-", str(tag).strip().lower())
    normalized = normalized.strip("-/")
    normalized = re.sub(r"-{2,}", "-", normalized)
    normalized = re.sub(r"/{2,}", "/", normalized)
    return normalized


def normalize_tags(tags: str | list[str]) -> list[str]:
    raw_tags = tags if isinstance(tags, list) else tags.split(",")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_tags:
        tag = canonicalize_tag(str(raw))
        if not tag or tag in seen:
            continue
        normalized.append(tag)
        seen.add(tag)
    return normalized


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


def build_session_summary_facts(payload: SessionSummaryRequest) -> list[str]:
    facts = [
        f"Summary: {payload.summary}",
        f"Goal is {payload.goal}",
        f"Outcome is {payload.outcome}",
    ]

    facts.extend([f"Change: {item}" for item in payload.changes[:8]])
    facts.extend(
        [
            (
                f"Decision: {item.title}. {item.decision}. Rationale: {item.rationale}"
                if item.rationale
                else f"Decision: {item.title}. {item.decision}."
            )
            for item in payload.decisions[:8]
        ]
    )
    facts.extend(
        [
            (
                f"Error: {item.description}. Solution: {item.solution}. Signature: {item.error_signature}"
                if item.error_signature
                else f"Error: {item.description}. Solution: {item.solution}."
            )
            for item in payload.errors[:8]
        ]
    )
    facts.extend(
        [
            (
                f"Follow-up [{item.state}]: {item.title}. {item.details}"
                if item.details
                else f"Follow-up [{item.state}]: {item.title}"
            )
            for item in payload.follow_ups[:8]
        ]
    )
    if payload.tags:
        facts.append(f"Tags: {', '.join(payload.tags)}")
    return [fact.strip() for fact in facts if fact.strip()]


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


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def parse_result_fields(result: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in result.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key.strip()] = value.strip().strip("'\"")
    return fields


def validate_search_scope(scope: str) -> str:
    normalized = str(scope or "project").strip().lower()
    if normalized not in VALID_SEARCH_SCOPES:
        raise ValueError(f"invalid_scope:{scope}")
    return normalized


def validate_relation_type(relation_type: str) -> str:
    normalized = str(relation_type or "").strip().lower()
    if normalized not in VALID_RELATION_TYPES:
        raise ValueError(f"invalid_relation_type:{relation_type}")
    return normalized


def canonical_memory_pair(source_memory_id: str, target_memory_id: str) -> tuple[str, str]:
    source_id = str(source_memory_id).strip()
    target_id = str(target_memory_id).strip()
    return (source_id, target_id) if source_id <= target_id else (target_id, source_id)


def compute_recency_frequency(access_count: int, last_accessed_at: Optional[datetime]) -> float:
    frequency = clamp01(math.log1p(max(access_count, 0)) / math.log(10))
    if not last_accessed_at:
        return round(0.6 * frequency, 4)
    age_days = max(
        0.0,
        (datetime.now(timezone.utc) - last_accessed_at.astimezone(timezone.utc)).total_seconds() / 86400.0,
    )
    recency = clamp01(1.0 - min(age_days, 30.0) / 30.0)
    return round(clamp01(0.6 * frequency + 0.4 * recency), 4)


def compute_tag_overlap(query_tags: list[str], memory_tags: list[str]) -> float:
    if not query_tags:
        return 0.0
    query_set = set(normalize_tags(query_tags))
    memory_set = set(normalize_tags(memory_tags))
    if not query_set or not memory_set:
        return 0.0
    overlap = len(query_set & memory_set)
    return round(clamp01(overlap / max(1, len(query_set))), 4)


def extract_memory_text(item: Any) -> str:
    if isinstance(item, dict):
        memory_text = item.get("memory") or item.get("content") or item.get("text")
        if not memory_text and isinstance(item.get("payload"), dict):
            memory_text = item["payload"].get("content")
        if memory_text:
            return str(memory_text)
        return canonical_json(item)
    return str(item)


async def get_project_id(project_name: str) -> Optional[uuid.UUID]:
    if not pg_pool:
        return None
    async with pg_pool.acquire() as conn:
        return await conn.fetchval("SELECT id FROM projects WHERE name = $1 LIMIT 1", project_name)


async def get_project_bridge_names(project_name: str) -> list[str]:
    if not pg_pool or not project_name:
        return []
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT p.name
            FROM project_bridges pb
            JOIN projects left_p ON left_p.id = pb.project_id
            JOIN projects right_p ON right_p.id = pb.related_project_id
            JOIN projects p
                ON p.id = CASE
                    WHEN left_p.name = $1 THEN pb.related_project_id
                    ELSE pb.project_id
                END
            WHERE pb.active = TRUE AND ($1 IN (left_p.name, right_p.name))
            ORDER BY p.name
            """,
            project_name,
        )
    return [str(row["name"]) for row in rows]


async def resolve_scope_projects(project_name: Optional[str], scope: str) -> list[str]:
    normalized_scope = validate_search_scope(scope)
    if not project_name:
        return []
    if normalized_scope == "project":
        return [project_name]
    if normalized_scope == "global":
        return []
    related = await get_project_bridge_names(project_name)
    return [project_name, *[name for name in related if name != project_name]]


async def run_schema_migrations():
    if not pg_pool:
        return
    statements = [
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0",
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ",
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS activation_score FLOAT DEFAULT 0",
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS stability_score FLOAT DEFAULT 0.5",
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS manual_pin BOOLEAN DEFAULT FALSE",
        """
        CREATE TABLE IF NOT EXISTS memory_relations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            source_memory_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
            target_memory_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
            relation_type VARCHAR(50) NOT NULL,
            weight FLOAT DEFAULT 0.5,
            origin VARCHAR(50) NOT NULL DEFAULT 'vector_inference',
            evidence_json JSONB DEFAULT '{}',
            reinforcement_count INTEGER DEFAULT 1,
            last_activated_at TIMESTAMPTZ,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT memory_relations_no_self CHECK (source_memory_id <> target_memory_id),
            CONSTRAINT memory_relations_unique UNIQUE (source_memory_id, target_memory_id, relation_type)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS project_bridges (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
            related_project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
            reason TEXT NOT NULL DEFAULT '',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by VARCHAR(100) NOT NULL DEFAULT 'api',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT project_bridges_no_self CHECK (project_id <> related_project_id),
            CONSTRAINT project_bridges_unique UNIQUE (project_id, related_project_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_memory_log_accessed ON memory_log(last_accessed_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_memory_relations_source ON memory_relations(source_memory_id, weight DESC)",
        "CREATE INDEX IF NOT EXISTS idx_memory_relations_target ON memory_relations(target_memory_id, weight DESC)",
        "CREATE INDEX IF NOT EXISTS idx_memory_relations_active ON memory_relations(active, updated_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_project_bridges_project ON project_bridges(project_id, active)",
        "CREATE INDEX IF NOT EXISTS idx_project_bridges_related ON project_bridges(related_project_id, active)",
        "DROP TRIGGER IF EXISTS update_memory_relations_updated_at ON memory_relations",
        """
        CREATE TRIGGER update_memory_relations_updated_at BEFORE UPDATE ON memory_relations
            FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        """,
        "DROP TRIGGER IF EXISTS update_project_bridges_updated_at ON project_bridges",
        """
        CREATE TRIGGER update_project_bridges_updated_at BEFORE UPDATE ON project_bridges
            FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        """,
    ]
    async with pg_pool.acquire() as conn:
        for statement in statements:
            await conn.execute(statement)


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


async def fetch_memory_records(memory_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not pg_pool or not memory_ids:
        return {}
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ml.id,
                p.name AS project_name,
                ml.agent_id,
                ml.action_type,
                ml.summary,
                ml.details,
                ml.importance,
                ml.tags,
                ml.access_count,
                ml.last_accessed_at,
                ml.activation_score,
                ml.stability_score,
                ml.manual_pin
            FROM memory_log ml
            LEFT JOIN projects p ON p.id = ml.project_id
            WHERE ml.id = ANY($1::uuid[])
            """,
            [uuid.UUID(memory_id) for memory_id in memory_ids],
        )
    records: dict[str, dict[str, Any]] = {}
    for row in rows:
        details = row["details"] if isinstance(row["details"], dict) else {}
        records[str(row["id"])] = {
            "id": str(row["id"]),
            "project": row["project_name"],
            "agent_id": row["agent_id"],
            "memory_type": row["action_type"],
            "summary": row["summary"],
            "content": details.get("content") or row["summary"],
            "importance": float(row["importance"] or 0.5),
            "tags": normalize_tags(row["tags"] or []),
            "access_count": int(row["access_count"] or 0),
            "last_accessed_at": row["last_accessed_at"],
            "activation_score": float(row["activation_score"] or 0.0),
            "stability_score": float(row["stability_score"] or 0.5),
            "manual_pin": bool(row["manual_pin"]),
        }
    return records


async def fetch_incident_relation_weights(memory_ids: list[str]) -> dict[str, float]:
    if not pg_pool or not memory_ids:
        return {}
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT source_memory_id, target_memory_id, weight
            FROM memory_relations
            WHERE active = TRUE
              AND (source_memory_id = ANY($1::uuid[]) OR target_memory_id = ANY($1::uuid[]))
            """,
            [uuid.UUID(memory_id) for memory_id in memory_ids],
        )
    weights: dict[str, float] = {memory_id: 0.0 for memory_id in memory_ids}
    for row in rows:
        source_id = str(row["source_memory_id"])
        target_id = str(row["target_memory_id"])
        weight = float(row["weight"] or 0.0)
        if source_id in weights:
            weights[source_id] = max(weights[source_id], weight)
        if target_id in weights:
            weights[target_id] = max(weights[target_id], weight)
    return weights


async def upsert_memory_relation(
    source_memory_id: str,
    target_memory_id: str,
    relation_type: str,
    weight: float,
    origin: str,
    evidence: Optional[dict[str, Any]] = None,
    mark_activated: bool = True,
) -> dict[str, Any]:
    if not pg_pool:
        raise RuntimeError("postgres_unavailable")
    relation_type = validate_relation_type(relation_type)
    source_id, target_id = canonical_memory_pair(source_memory_id, target_memory_id)
    active = origin == "manual" or weight >= RELATION_ACTIVE_THRESHOLD
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO memory_relations
            (source_memory_id, target_memory_id, relation_type, weight, origin, evidence_json, reinforcement_count, last_activated_at, active)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, 1, CASE WHEN $7 THEN NOW() ELSE NULL END, $8)
            ON CONFLICT (source_memory_id, target_memory_id, relation_type) DO UPDATE
            SET weight = CASE
                    WHEN memory_relations.origin = 'manual' THEN GREATEST(memory_relations.weight, EXCLUDED.weight)
                    ELSE LEAST(1.0, GREATEST(memory_relations.weight, EXCLUDED.weight))
                END,
                origin = CASE
                    WHEN memory_relations.origin = 'manual' THEN memory_relations.origin
                    ELSE EXCLUDED.origin
                END,
                evidence_json = COALESCE(memory_relations.evidence_json, '{}'::jsonb) || EXCLUDED.evidence_json,
                reinforcement_count = memory_relations.reinforcement_count + 1,
                last_activated_at = CASE
                    WHEN $7 THEN NOW()
                    ELSE memory_relations.last_activated_at
                END,
                active = CASE
                    WHEN memory_relations.origin = 'manual' THEN TRUE
                    ELSE (LEAST(1.0, GREATEST(memory_relations.weight, EXCLUDED.weight)) >= $9)
                END,
                updated_at = NOW()
            RETURNING id, source_memory_id, target_memory_id, relation_type, weight, origin, reinforcement_count, active
            """,
            uuid.UUID(source_id),
            uuid.UUID(target_id),
            relation_type,
            clamp01(weight),
            origin,
            json.dumps(evidence or {}, ensure_ascii=False),
            mark_activated,
            active,
            RELATION_ACTIVE_THRESHOLD,
        )
        if origin == "manual":
            await conn.execute(
                """
                UPDATE memory_log
                SET manual_pin = TRUE,
                    stability_score = 1.0
                WHERE id = ANY($1::uuid[])
                """,
                [uuid.UUID(source_id), uuid.UUID(target_id)],
            )
    return serialize_row(row) or {}


async def decay_project_relations(project_name: str, stale_days: int = 21) -> int:
    if not pg_pool or not project_name:
        return 0
    async with pg_pool.acquire() as conn:
        result = await conn.execute(
            """
            WITH project_memories AS (
                SELECT ml.id
                FROM memory_log ml
                JOIN projects p ON p.id = ml.project_id
                WHERE p.name = $1
            )
            UPDATE memory_relations mr
            SET weight = GREATEST(0.0, mr.weight - 0.03),
                active = CASE
                    WHEN mr.origin = 'manual' THEN TRUE
                    ELSE (GREATEST(0.0, mr.weight - 0.03) >= $2)
                END,
                updated_at = NOW()
            WHERE mr.origin <> 'manual'
              AND (
                  mr.source_memory_id IN (SELECT id FROM project_memories)
                  OR mr.target_memory_id IN (SELECT id FROM project_memories)
              )
              AND COALESCE(mr.last_activated_at, mr.created_at) < NOW() - (($3::text || ' days')::interval)
            """,
            project_name,
            RELATION_ACTIVE_THRESHOLD,
            stale_days,
        )
    return int(result.split()[-1])


async def register_memory_access(results: list[dict[str, Any]]):
    if not pg_pool or not results:
        return
    top_ids = [uuid.UUID(item["id"]) for item in results[:4]]
    async with pg_pool.acquire() as conn:
        for item in results:
            await conn.execute(
                """
                UPDATE memory_log
                SET access_count = access_count + 1,
                    last_accessed_at = NOW(),
                    activation_score = GREATEST(COALESCE(activation_score, 0), $2),
                    stability_score = CASE
                        WHEN manual_pin THEN 1.0
                        ELSE LEAST(1.0, GREATEST(COALESCE(stability_score, 0.3), $3))
                    END
                WHERE id = $1
                """,
                uuid.UUID(item["id"]),
                float(item["hybrid_score"]),
                clamp01(max(float(item["hybrid_score"]), float(item.get("stability_score", 0.5)))),
            )
        if len(top_ids) >= 2:
            await conn.execute(
                """
                UPDATE memory_relations
                SET reinforcement_count = reinforcement_count + 1,
                    last_activated_at = NOW(),
                    weight = CASE
                        WHEN origin = 'manual' THEN weight
                        ELSE LEAST(1.0, weight + 0.02)
                    END,
                    active = TRUE,
                    updated_at = NOW()
                WHERE source_memory_id = ANY($1::uuid[])
                  AND target_memory_id = ANY($1::uuid[])
                """,
                top_ids,
            )


async def structured_search_memories(
    query: str,
    project: Optional[str] = None,
    memory_type: Optional[str] = None,
    limit: int = 8,
    scope: str = "project",
    tags: str | list[str] = "",
    score_threshold: float = 0.35,
    exclude_memory_ids: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    normalized_scope = validate_search_scope(scope)
    normalized_tags = normalize_tags(tags)
    allowed_projects = set(await resolve_scope_projects(project, normalized_scope))
    exclude_ids = {str(memory_id) for memory_id in (exclude_memory_ids or [])}
    query_embedding = await get_embedding(query)
    conditions = []
    if project and normalized_scope == "project":
        conditions.append(FieldCondition(key="project_id", match=MatchValue(value=project)))
    if memory_type:
        conditions.append(FieldCondition(key="memory_type", match=MatchValue(value=memory_type)))
    query_filter = Filter(must=conditions) if conditions else None
    raw_limit = max(limit * 6, 24)
    response = await qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        query_filter=query_filter,
        limit=raw_limit,
        with_payload=True,
        score_threshold=score_threshold,
    )
    points = response.points
    metadata = await fetch_memory_records([str(point.id) for point in points])
    relation_weights = await fetch_incident_relation_weights([str(point.id) for point in points])

    results: list[dict[str, Any]] = []
    for point in points:
        memory_id = str(point.id)
        if memory_id in exclude_ids:
            continue
        payload = point.payload or {}
        meta = metadata.get(memory_id, {})
        project_name = str(payload.get("project_id") or meta.get("project") or "")
        if allowed_projects and project_name not in allowed_projects:
            continue
        memory_tags = normalize_tags(payload.get("tags", []) or meta.get("tags", []))
        if normalized_tags and not (set(normalized_tags) & set(memory_tags)):
            continue
        access_count = int(meta.get("access_count", 0))
        last_accessed_at = meta.get("last_accessed_at")
        recency_frequency = compute_recency_frequency(access_count, last_accessed_at)
        relation_weight = clamp01(float(relation_weights.get(memory_id, 0.0)))
        tag_overlap = compute_tag_overlap(normalized_tags, memory_tags)
        semantic_relevance = clamp01(float(point.score))
        hybrid_score = round(
            clamp01(
                0.5 * semantic_relevance
                + 0.2 * relation_weight
                + 0.2 * recency_frequency
                + 0.1 * tag_overlap
            ),
            4,
        )
        details = meta.get("content") or payload.get("content") or ""
        results.append(
            {
                "id": memory_id,
                "project": project_name,
                "memory_type": str(payload.get("memory_type") or meta.get("memory_type") or "?"),
                "content": str(payload.get("content") or details),
                "tags": memory_tags,
                "semantic_score": round(float(point.score), 4),
                "hybrid_score": hybrid_score,
                "relation_weight": relation_weight,
                "recency_frequency": recency_frequency,
                "tag_overlap": tag_overlap,
                "importance": float(payload.get("importance") or meta.get("importance") or 0.5),
                "stability_score": float(meta.get("stability_score", 0.5) or 0.5),
                "manual_pin": bool(meta.get("manual_pin", False)),
            }
        )
    results.sort(key=lambda item: (item["hybrid_score"], item["semantic_score"], item["importance"]), reverse=True)
    return results[:limit]


async def classify_relation_with_llm(
    source: dict[str, Any],
    candidate: dict[str, Any],
    semantic_score: float,
    shared_tags: list[str],
) -> Optional[dict[str, Any]]:
    if not deepseek_client or not has_real_secret(DEEPSEEK_API_KEY):
        return None
    prompt = canonical_json(
        {
            "source": {
                "project": source.get("project"),
                "memory_type": source.get("memory_type"),
                "tags": source.get("tags", []),
                "content": source.get("content", "")[:600],
            },
            "candidate": {
                "project": candidate.get("project"),
                "memory_type": candidate.get("memory_type"),
                "tags": candidate.get("tags", []),
                "content": candidate.get("content", "")[:600],
            },
            "semantic_score": round(float(semantic_score), 4),
            "shared_tags": shared_tags,
            "valid_relation_types": sorted(VALID_RELATION_TYPES),
        }
    )
    response = await deepseek_client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Clasifica la relacion entre dos memorias de software. "
                    "Devuelve solo JSON valido con {\"relation_type\": string|null, \"weight\": number, \"reason\": string}. "
                    "Si no hay relacion util, usa relation_type=null."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    parsed = json.loads(content[start : end + 1])
    relation_type = parsed.get("relation_type")
    if relation_type is None:
        return None
    try:
        normalized_relation = validate_relation_type(str(relation_type))
    except ValueError:
        return None
    return {
        "relation_type": normalized_relation,
        "weight": clamp01(float(parsed.get("weight", semantic_score))),
        "reason": str(parsed.get("reason", "")).strip(),
    }


def classify_relation_heuristic(
    source: dict[str, Any],
    candidate: dict[str, Any],
    semantic_score: float,
    shared_tags: list[str],
) -> Optional[dict[str, Any]]:
    source_text = str(source.get("content", "")).lower()
    candidate_text = str(candidate.get("content", "")).lower()
    same_type = source.get("memory_type") == candidate.get("memory_type")
    if semantic_score >= 0.95 and (same_type or shared_tags):
        return {"relation_type": "same_concept", "weight": clamp01(semantic_score), "reason": "high_semantic_overlap"}
    if semantic_score >= 0.9 and shared_tags:
        return {"relation_type": "extends", "weight": clamp01(semantic_score - 0.05), "reason": "shared_tags"}
    if any(token in source_text for token in ["builds on", "extends", "expands"]) or any(
        token in candidate_text for token in ["builds on", "extends", "expands"]
    ):
        return {"relation_type": "extends", "weight": clamp01(max(0.7, semantic_score)), "reason": "extension_language"}
    if same_type and shared_tags and semantic_score >= 0.84:
        return {"relation_type": "supports", "weight": clamp01(semantic_score - 0.04), "reason": "same_type_shared_tags"}
    if shared_tags and semantic_score >= 0.82:
        return {"relation_type": "applies_to", "weight": clamp01(semantic_score - 0.08), "reason": "tag_supported_similarity"}
    if semantic_score >= 0.88 and source.get("project") != candidate.get("project"):
        return {"relation_type": "derived_from", "weight": clamp01(semantic_score - 0.06), "reason": "cross_project_reuse"}
    return None


async def auto_link_memory(
    memory_id: str,
    content: str,
    project: str,
    memory_type: str,
    tags: str | list[str],
    origin: str = "vector_inference",
) -> list[dict[str, Any]]:
    if not pg_pool:
        return []
    normalized_tags = normalize_tags(tags)
    allowed_projects = set(await resolve_scope_projects(project, "bridged"))
    source_memory = {
        "id": memory_id,
        "project": project,
        "memory_type": memory_type,
        "content": content,
        "tags": normalized_tags,
    }
    candidates = await structured_search_memories(
        query=content,
        project=project,
        memory_type=None,
        limit=AUTO_LINK_CANDIDATE_LIMIT,
        scope="bridged",
        tags="",
        score_threshold=AUTO_LINK_SCORE_THRESHOLD,
        exclude_memory_ids=[memory_id],
    )
    created: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            if candidate["project"] not in allowed_projects:
                continue
            candidate_tags = normalize_tags(candidate.get("tags", []))
            shared_tags = sorted(set(normalized_tags) & set(candidate_tags))
            if candidate["semantic_score"] < 0.88 and not shared_tags:
                continue
            relation = classify_relation_heuristic(source_memory, candidate, candidate["semantic_score"], shared_tags)
            if relation is None and candidate["semantic_score"] >= 0.86:
                relation = await classify_relation_with_llm(source_memory, candidate, candidate["semantic_score"], shared_tags)
            if relation is None:
                continue
            created.append(
                await upsert_memory_relation(
                    source_memory_id=memory_id,
                    target_memory_id=candidate["id"],
                    relation_type=relation["relation_type"],
                    weight=float(relation["weight"]),
                    origin=origin,
                    evidence={
                        "reason": relation.get("reason", ""),
                        "semantic_score": candidate["semantic_score"],
                        "shared_tags": shared_tags,
                        "source_project": project,
                        "target_project": candidate["project"],
                    },
                )
            )
        except Exception as exc:
            logger.warning("No fue posible enlazar %s con %s: %s", memory_id, candidate.get("id"), exc)
    return created


async def bridge_projects_internal(
    project: str,
    related_project: str,
    reason: str,
    active: bool = True,
    created_by: str = "api",
) -> dict[str, Any]:
    if not pg_pool:
        raise RuntimeError("postgres_unavailable")
    left_name, right_name = sorted([project.strip(), related_project.strip()], key=str.lower)
    if not left_name or not right_name or left_name == right_name:
        raise ValueError("invalid_project_bridge")
    left_id = await ensure_project(left_name)
    right_id = await ensure_project(right_name)
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO project_bridges (project_id, related_project_id, reason, active, created_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (project_id, related_project_id) DO UPDATE
            SET reason = EXCLUDED.reason,
                active = EXCLUDED.active,
                created_by = EXCLUDED.created_by,
                updated_at = NOW()
            RETURNING id, active, reason, created_at, updated_at
            """,
            left_id,
            right_id,
            reason.strip(),
            active,
            created_by,
        )
    payload = serialize_row(row) or {}
    payload.update({"project": left_name, "related_project": right_name})
    return payload


async def get_related_ideas(project_name: str, limit: int = 5) -> list[str]:
    if not pg_pool or not project_name:
        return []
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                mr.relation_type,
                mr.weight,
                src.summary AS source_summary,
                dst.summary AS target_summary,
                src_p.name AS source_project,
                dst_p.name AS target_project
            FROM memory_relations mr
            JOIN memory_log src ON src.id = mr.source_memory_id
            JOIN memory_log dst ON dst.id = mr.target_memory_id
            LEFT JOIN projects src_p ON src_p.id = src.project_id
            LEFT JOIN projects dst_p ON dst_p.id = dst.project_id
            WHERE mr.active = TRUE
              AND (
                    (src_p.name = $1 AND dst_p.name <> $1)
                 OR (dst_p.name = $1 AND src_p.name <> $1)
              )
              AND EXISTS (
                    SELECT 1
                    FROM project_bridges pb
                    WHERE pb.active = TRUE
                      AND (
                            (pb.project_id = src.project_id AND pb.related_project_id = dst.project_id)
                         OR (pb.project_id = dst.project_id AND pb.related_project_id = src.project_id)
                      )
              )
            ORDER BY mr.weight DESC, mr.reinforcement_count DESC, mr.updated_at DESC
            LIMIT $2
            """,
            project_name,
            limit,
        )
    lines: list[str] = []
    for row in rows:
        other_project = row["target_project"] if row["source_project"] == project_name else row["source_project"]
        summary = row["target_summary"] if row["source_project"] == project_name else row["source_summary"]
        lines.append(
            f"- [{other_project}] relation={row['relation_type']} weight={float(row['weight']):.3f} idea={str(summary)[:220]}"
        )
    return lines


async def apply_session_plasticity(payload: SessionSummaryRequest) -> dict[str, Any]:
    queries = [payload.summary, payload.goal, payload.outcome]
    queries.extend(payload.changes[:4])
    queries.extend([f"{item.title} {item.decision}" for item in payload.decisions[:4]])
    queries.extend([f"{item.error_signature} {item.description}" for item in payload.errors[:2]])

    activated: dict[str, dict[str, Any]] = {}
    for query in [item for item in queries if item]:
        matches = await structured_search_memories(
            query=query,
            project=payload.project,
            scope="bridged",
            limit=4,
            tags=payload.tags,
            score_threshold=0.45,
        )
        for match in matches:
            current = activated.get(match["id"])
            if current is None or match["hybrid_score"] > current["hybrid_score"]:
                activated[match["id"]] = match

    selected = sorted(activated.values(), key=lambda item: item["hybrid_score"], reverse=True)[:3]
    if selected:
        await register_memory_access(selected)
        for match in selected:
            await auto_link_memory(
                memory_id=match["id"],
                content=match["content"],
                project=match["project"],
                memory_type=match["memory_type"],
                tags=match.get("tags", []),
                origin="reflection",
            )
    decayed = await decay_project_relations(payload.project)
    return {"activated_memories": len(selected), "decayed_relations": decayed}

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
        "enable_graph": True,
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
    relations = data.get("relations", []) if isinstance(data, dict) else []
    lines: list[str] = []
    for item in raw_results[:limit]:
        if not isinstance(item, dict):
            lines.append(f"- {item}")
            continue
        score = item.get("score")
        prefix = f"- score={score:.3f} " if isinstance(score, (int, float)) else "- "
        lines.append(prefix + extract_memory_text(item)[:280])
    for relation in relations[: max(0, min(3, limit - len(lines)))]:
        if isinstance(relation, dict):
            lines.append(f"- relation {canonical_json(relation)[:260]}")
    return lines


async def ingest_session_into_mem0(payload: SessionSummaryRequest) -> tuple[bool, Optional[str]]:
    if not http_client or not MEM0_URL:
        return False, "mem0_unavailable"

    metadata = {
        "project": payload.project,
        "session_id": payload.session_id,
        "goal": payload.goal,
        "outcome": payload.outcome,
        "tags": payload.tags,
        "record_type": "session_summary",
    }

    async def post_messages(messages: list[str]) -> dict[str, Any]:
        body = {
            "messages": [{"role": "user", "content": message} for message in messages],
            "user_id": payload.project,
            "agent_id": payload.agent_id,
            "run_id": payload.session_id,
            "metadata": metadata,
            "enable_graph": True,
        }
        response = await http_client.post(
            f"{MEM0_URL}/memories",
            json=body,
            timeout=MEM0_INGEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"results": data}

    def result_count(data: dict[str, Any]) -> int:
        raw_results = data.get("results", [])
        return len(raw_results) if isinstance(raw_results, list) else int(bool(raw_results))

    try:
        summary_result = await post_messages([build_session_summary_document(payload)])
        summary_added = result_count(summary_result)
        if summary_added > 0:
            return True, None

        fallback_added = 0
        for fact in build_session_summary_facts(payload):
            fallback_added += result_count(await post_messages([fact]))
            if fallback_added >= 4:
                break

        if fallback_added > 0:
            logger.info(
                "Mem0 ingesta de sesion %s recuperada con fallback atomico (%s memorias).",
                payload.session_id,
                fallback_added,
            )
            return True, None

        logger.warning("Mem0 devolvio results vacio para session summary %s", payload.session_id)
        return False, "mem0_empty_results"
    except Exception as exc:
        error_detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        logger.warning("Mem0 no pudo ingerir session summary %s: %s", payload.session_id, error_detail)
        return False, error_detail


async def persist_session_summary(payload: SessionSummaryRequest) -> dict[str, Any]:
    if not pg_pool:
        return {"error": "postgres_unavailable"}

    payload = payload.model_copy(update={"tags": normalize_tags(payload.tags)})
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
        logger.info("Coleccion '%s' creada en Qdrant", COLLECTION_NAME)
    for field in ["project_id", "agent_id", "memory_type", "tags"]:
        try:
            await qdrant.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            logger.debug("No fue posible crear/verificar indice payload %s: %s", field, exc)


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
    """Guarda una memoria explícita y reusable en la memoria semántica del proyecto.

    Cuándo usar:
    - Cuando un agente descubre un hecho, convención, hallazgo o resultado que
      debe sobrevivir a la sesión actual.
    - Para conocimiento durable; no para logs efímeros o pensamiento intermedio.

    Cómo usar:
    - `content` debe ser autocontenido y entendible fuera del contexto inmediato.
    - `project` debe ser el nombre estable del proyecto al que pertenece.
    - `memory_type` permite clasificar (`general`, `decision`, `error`, etc.).
    - `tags` acepta una cadena CSV para mejorar filtrado y trazabilidad.
    - `skip_similar=True` evita duplicados semánticos antes de escribir.

    Devuelve:
    - `OK ...` si la memoria se guardó.
    - `SKIP ...` si se omitió por alta similitud con otra memoria existente.
    - `ERROR ...` si ocurrió un fallo.
    """
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
                    (
                        id, project_id, agent_id, action_type, summary, details, importance, tags,
                        access_count, activation_score, stability_score, manual_pin
                    )
                    VALUES (
                        $1,
                        (SELECT id FROM projects WHERE name = $2 LIMIT 1),
                        $3, $4, $5, $6::jsonb, $7, $8, 0, 0, $9, FALSE
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    uuid.UUID(memory_id),
                    project,
                    agent_id,
                    memory_type,
                    content[:500],
                    json.dumps({"content": content, "tags": tags_list}, ensure_ascii=False),
                    importance,
                    tags_list,
                    clamp01(max(importance, 0.35)),
                )
        try:
            await auto_link_memory(
                memory_id=memory_id,
                content=content,
                project=project,
                memory_type=memory_type,
                tags=tags_list,
                origin="vector_inference",
            )
        except Exception:
            logger.exception("Auto-link de memoria %s fallo", memory_id)
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
    scope: str = "project",
    tags: str = "",
) -> str:
    """Busca memorias por similitud semántica y devuelve un resumen legible.

    Cuándo usar:
    - Al arrancar una tarea o retomar contexto.
    - Antes de tomar una decisión para revisar si ya existe conocimiento previo.
    - Cuando se necesita recuperar errores, decisiones o notas relevantes.

    Cómo usar:
    - `query` debe escribirse en lenguaje natural con el contexto que buscas.
    - Usa `project` para limitar la búsqueda a un proyecto concreto.
    - Usa `memory_type` si solo quieres una categoría concreta.
    - Ajusta `limit` para controlar el número máximo de resultados.

    Devuelve:
    - Una lista textual de memorias relevantes con score y extracto.
    - Un mensaje informando que no hubo coincidencias.
    - `ERROR ...` si la búsqueda falla.
    """
    try:
        results = await structured_search_memories(
            query=query,
            project=project,
            memory_type=memory_type,
            limit=limit,
            scope=scope,
            tags=tags,
            score_threshold=0.35,
        )
        if not results:
            return f"No encontre memorias relevantes para '{query}'"
        await register_memory_access(results)
        lines = [f"{len(results)} memorias relevantes para '{query}':"]
        for index, result in enumerate(results, 1):
            lines.append(
                f"[{index}] score={result['semantic_score']:.3f} "
                f"hybrid={result['hybrid_score']:.3f} "
                f"type={result['memory_type']} "
                f"project={result['project']} "
                f"content={result['content'][:260]}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.exception("search_memory fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def get_project_context(project_name: str, agent_id: Optional[str] = None, include_related: bool = True) -> str:
    """Construye una vista rápida del estado operativo y memorias de un proyecto.

    Cuándo usar:
    - Al inicio de una sesión de trabajo.
    - Cuando un agente cambia de tarea o necesita rehidratar contexto.
    - Antes de planificar trabajo nuevo o revisar lo pendiente.

    Cómo usar:
    - Pasa `project_name` con el nombre canónico del proyecto.
    - `agent_id` es opcional y ayuda a recuperar working memory más específica.
    - El resultado combina tareas activas, decisiones recientes, working memory
      y una búsqueda semántica contextual.

    Devuelve:
    - Un bloque de texto estructurado con contexto operativo del proyecto.
    - `ERROR ...` si no pudo construirse el contexto.
    """
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

        semantic = await search_memory(
            f"context architecture overview {project_name}",
            project=project_name,
            limit=5,
            scope="project",
        )
        output.append("MEMORY SEARCH")
        output.append(semantic)
        if include_related:
            related_ideas = await get_related_ideas(project_name, limit=5)
            if related_ideas:
                output.append("RELATED IDEAS")
                output.extend(related_ideas)
        return "\n".join(output)
    except Exception as exc:
        logger.exception("get_project_context fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def link_memories(
    source_memory_id: str,
    target_memory_id: str,
    relation_type: str,
    reason: str,
    weight: float = 0.75,
) -> str:
    """Crea o refuerza un enlace explícito entre dos memorias existentes."""
    try:
        relation = await upsert_memory_relation(
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relation_type=relation_type,
            weight=weight,
            origin="manual",
            evidence={"reason": reason.strip()},
        )
        return (
            f"OK relation_id={relation.get('id')} "
            f"type={relation.get('relation_type')} "
            f"weight={float(relation.get('weight', 0.0)):.3f}"
        )
    except Exception as exc:
        logger.exception("link_memories fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def bridge_projects(project: str, related_project: str, reason: str, active: bool = True) -> str:
    """Activa o actualiza un puente explícito entre dos proyectos."""
    try:
        bridge = await bridge_projects_internal(project, related_project, reason, active=active)
        return (
            f"OK bridge_id={bridge.get('id')} "
            f"project={bridge.get('project')} "
            f"related_project={bridge.get('related_project')} "
            f"active={str(bool(bridge.get('active'))).lower()}"
        )
    except Exception as exc:
        logger.exception("bridge_projects fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def update_task_state(
    task_title: str,
    project: str,
    new_state: str,
    details: str = "",
    agent_id: str = "unknown",
) -> str:
    """Crea o actualiza el estado de una tarea compartida del proyecto.

    Cuándo usar:
    - Cuando una tarea pasa a `active`, `blocked`, `done` o `cancelled`.
    - Para dejar trazabilidad compartida entre agentes sobre trabajo en curso.

    Cómo usar:
    - `task_title` debe ser estable para que el upsert actualice la misma tarea.
    - `new_state` solo admite `pending`, `active`, `blocked`, `done` o
      `cancelled`.
    - `details` permite guardar contexto adicional útil.
    - `agent_id` identifica quién actualizó la tarea.

    Devuelve:
    - `OK ...` si la tarea quedó registrada.
    - `ERROR invalid_state` si el estado no es válido.
    - `ERROR ...` ante fallos de persistencia.
    """
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
    """Lista las tareas activas o no cerradas, globales o de un proyecto.

    Cuándo usar:
    - Antes de planificar el siguiente paso.
    - Para coordinar varios agentes trabajando sobre el mismo proyecto.
    - Para revisar qué quedó pendiente o bloqueado.

    Cómo usar:
    - Omite `project` para ver un resumen global.
    - Indica `project` para limitar el listado a un proyecto concreto.

    Devuelve:
    - Una lista textual de tareas con proyecto, estado, prioridad y agente.
    - `No active tasks` si no hay tareas abiertas.
    - `ERROR ...` si la consulta falla.
    """
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
    """Registra una decisión importante y la promueve también a memoria semántica.

    Cuándo usar:
    - Cuando se elige una arquitectura, convención, política o criterio estable.
    - Cuando una decisión debe poder recuperarse más adelante con su contexto.

    Cómo usar:
    - `title` debe nombrar la decisión de forma corta y estable.
    - `decision` debe dejar claro qué se decidió.
    - `rationale` y `alternatives` ayudan a entender por qué se tomó.
    - `tags` y `agent_id` mejoran trazabilidad y recuperación posterior.

    Devuelve:
    - `OK ...` si la decisión quedó registrada.
    - `ERROR ...` si falló la persistencia o la memoria derivada.
    """
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
    """Guarda un error conocido con su solución y aumenta su contador de ocurrencias.

    Cuándo usar:
    - Cuando ya entendiste el problema y tienes una solución o workaround útil.
    - Para errores recurrentes que conviene reconocer rápidamente en el futuro.

    Cómo usar:
    - `error_description` debe describir el síntoma o contexto del fallo.
    - `solution` debe explicar la corrección o mitigación aplicada.
    - `error_signature` conviene usarlo como identificador estable del problema;
      si se omite, se deriva del inicio de la descripción.
    - `tags` ayuda a clasificar por stack, módulo o tipo de incidente.

    Devuelve:
    - `OK ...` si el error quedó registrado o actualizado.
    - `ERROR ...` si hubo un problema de persistencia.
    """
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
    """Cierra una sesión de trabajo con un resumen estructurado y reusable.

    Cuándo usar:
    - Al terminar un bloque significativo de trabajo.
    - Cuando quieres dejar continuidad real para otro agente o para una sesión
      futura.

    Cómo usar:
    - `session_id` debe ser único por sesión para evitar duplicados.
    - `goal`, `outcome` y `summary` deben capturar intención, resultado y
      contexto final.
    - `changes`, `decisions`, `errors` y `follow_ups` permiten registrar
      artefactos importantes en formato estructurado.
    - `tags` sirve para agrupar la sesión por tema o área.

    Devuelve:
    - `OK ...` con checksum y estado de ingesta de working memory.
    - `ERROR duplicate_session ...` si se intenta guardar dos veces la misma
      sesión.
    - `ERROR ...` ante cualquier otro fallo.
    """
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
    """Encola una reflexión manual para consolidar memoria desde sesiones previas.

    Cuándo usar:
    - Después de varias sesiones importantes.
    - Cuando quieres forzar consolidación sin esperar al ciclo automático.
    - Tras cambios relevantes que deberían promocionarse a memoria más estable.

    Cómo usar:
    - Llama la tool una sola vez por necesidad real de consolidación.
    - Consulta luego `get_reflection_status` para seguir el estado del worker.

    Devuelve:
    - `OK ...` con `run_id` y estado de la ejecución encolada.
    - `ERROR ...` si no pudo encolarse.
    """
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
    """Consulta el estado del worker de reflexión y de la última ejecución conocida.

    Cuándo usar:
    - Después de lanzar `run_memory_reflection`.
    - Para monitorear si el worker está vivo y si la cola avanza correctamente.

    Cómo usar:
    - Invócala tal cual, sin parámetros.
    - Interpreta la respuesta como JSON serializado.

    Devuelve:
    - Un JSON en texto con heartbeat del worker, última ejecución y readiness.
    - `ERROR ...` si no puede obtenerse el estado.
    """
    try:
        status = await get_reflection_status_payload()
        return json.dumps(status, ensure_ascii=False)
    except Exception as exc:
        logger.exception("get_reflection_status fallo")
        return f"ERROR {exc}"


@mcp.tool()
async def delete_memory(memory_id: str) -> str:
    """Elimina una memoria explícita por su identificador.

    Cuándo usar:
    - Para limpiar duplicados, recuerdos inválidos o datos cargados por error.
    - Solo cuando estás seguro de que la memoria no debe seguir disponible.

    Cómo usar:
    - Pasa `memory_id` exacto de la memoria a eliminar.
    - Úsala con cuidado: es una operación destructiva.

    Devuelve:
    - `OK ...` si la memoria fue eliminada.
    - `ERROR ...` si la operación falla.
    """
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
    fields = parse_result_fields(result)
    return {"result": result, "memory_id": fields.get("memory_id")}


@app.post("/api/search")
async def api_search_memory(payload: SearchMemoryRequest):
    result = await search_memory(**payload.model_dump())
    if result.startswith("ERROR"):
        raise HTTPException(status_code=500, detail=result)
    return {"result": result}


@app.get("/api/project-context")
async def api_project_context(project_name: str, agent_id: Optional[str] = None, include_related: bool = True):
    result = await get_project_context(project_name, agent_id, include_related=include_related)
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


@app.post("/api/relations")
async def api_link_memories(payload: LinkMemoriesRequest):
    result = await link_memories(**payload.model_dump())
    if result.startswith("ERROR"):
        raise HTTPException(status_code=400, detail=result)
    return {"result": result}


@app.post("/api/project-bridges")
async def api_bridge_projects(payload: BridgeProjectsRequest):
    try:
        bridge = await bridge_projects_internal(**payload.model_dump())
        return {"result": "OK", "bridge": bridge}
    except Exception as exc:
        logger.exception("api_bridge_projects fallo")
        raise HTTPException(status_code=400, detail=str(exc))


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


@app.post("/api/plasticity/session")
async def api_apply_session_plasticity(payload: SessionSummaryRequest):
    try:
        return await apply_session_plasticity(payload)
    except Exception as exc:
        logger.exception("api_apply_session_plasticity fallo")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/reflections/run")
async def api_run_reflection():
    result = await queue_manual_reflection()
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/api/reflections/status")
async def api_reflection_status():
    return await get_reflection_status_payload()


async def initialize_app_state():
    global pg_pool, redis_client, openai_client, deepseek_client, http_client
    logger.info("Iniciando AI Memory Brain")
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    deepseek_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY or "change-me", base_url=DEEPSEEK_BASE_URL)
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
    await run_schema_migrations()
    logger.info("Migraciones de esquema aplicadas")
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


async def shutdown_app_state():
    if pg_pool:
        await pg_pool.close()
    if redis_client:
        await redis_client.close()
    if qdrant:
        await qdrant.close()
    if http_client:
        await http_client.aclose()


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    await initialize_app_state()
    try:
        # Mounted sub-app lifespans are not entered automatically by FastAPI,
        # so we must run FastMCP's session manager from the parent app.
        async with mcp.session_manager.run():
            yield
    finally:
        await shutdown_app_state()


app.router.lifespan_context = app_lifespan
app.mount("/mcp", mcp_app)


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8050, log_level="info", workers=1)
