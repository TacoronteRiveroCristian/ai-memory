import asyncio
import hashlib
import json
import logging
import math
import os
import re
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import httpx
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    HasIdCondition,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Prefetch,
    VectorParams,
)
from sensory_cortex import (
    extract_keyphrases,
    canonicalize_tags as sc_canonicalize_tags,
    classify_synapse_cascade,
    compute_combined_score,
    emotional_proximity as sc_emotional_proximity,
    importance_attraction as sc_importance_attraction,
    temporal_proximity as sc_temporal_proximity,
    type_compatibility as sc_type_compatibility,
)
from myelination import (
    get_permeable_projects,
    increment_permeability,
    update_myelin_score,
    ensure_permeability,
    MYELIN_DELTA_DIRECT_ACCESS,
    MYELIN_DELTA_CO_ACTIVATION,
    PERMEABILITY_CO_ACTIVATION,
    PERMEABILITY_THRESHOLD,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ai-memory-brain")

def env_text(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


QDRANT_HOST = os.environ["QDRANT_HOST"].strip()
QDRANT_PORT = int(env_text("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"].strip()
POSTGRES_URL = os.environ["POSTGRES_URL"].strip()
REDIS_URL = os.environ["REDIS_URL"].strip()
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"].strip()
EMBEDDING_MODEL = env_text("EMBEDDING_MODEL", "text-embedding-3-small")
MEM0_URL = env_text("MEM0_URL", "")
API_KEY = os.environ["API_KEY"].strip()
DEEPSEEK_API_KEY = env_text("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = env_text("DEEPSEEK_MODEL", "deepseek-reasoner")
DEEPSEEK_BASE_URL = env_text("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
WORKER_HEARTBEAT_KEY = env_text("WORKER_HEARTBEAT_KEY", "reflection_worker:heartbeat")
WORKER_HEARTBEAT_MAX_AGE = int(os.environ.get("WORKER_HEARTBEAT_MAX_AGE_SECONDS", "120"))
MEM0_INGEST_TIMEOUT_SECONDS = float(os.environ.get("MEM0_INGEST_TIMEOUT_SECONDS", "90"))
PROJECT_CONTEXT_WORKING_MEMORY_TIMEOUT_SECONDS = float(
    os.environ.get("PROJECT_CONTEXT_WORKING_MEMORY_TIMEOUT_SECONDS", "2.0")
)
PROJECT_CONTEXT_WORKING_MEMORY_LIMIT = max(1, int(os.environ.get("PROJECT_CONTEXT_WORKING_MEMORY_LIMIT", "3")))
PROJECT_CONTEXT_WORKING_MEMORY_USE_GRAPH = os.environ.get(
    "PROJECT_CONTEXT_WORKING_MEMORY_USE_GRAPH", "false"
).strip().lower() in {"1", "true", "yes", "on"}
COLLECTION_NAME = "memories"
VECTOR_DIM = 1536
VALID_SEARCH_SCOPES = {"project", "bridged", "global"}
VALID_RELATION_TYPES = {"same_concept", "extends", "supports", "applies_to", "derived_from", "contradicts"}
VALID_GRAPH_MODES = {"project_hot", "search", "memory_focus"}
RELATION_ACTIVE_THRESHOLD = 0.18
TAG_NORMALIZE_RE = re.compile(r"[^a-z0-9/_-]+")
TOKEN_RE = re.compile(r"[a-z0-9_/-]+")
AUTO_LINK_CANDIDATE_LIMIT = 6
AUTO_LINK_SCORE_THRESHOLD = 0.78
ACTIVATION_PROPAGATION_TTL = 900          # 15 min en Redis
ACTIVATION_PROPAGATION_DECAY = 0.4        # factor de decaimiento por salto
NOVELTY_MERGE_THRESHOLD = 0.15            # novelty below this triggers merge instead of new memory
CONFIDENCE_THRESHOLD = 1.5               # max/mean ratio below this flags low confidence
DEEP_SLEEP_INTERVAL = int(os.environ.get("DEEP_SLEEP_INTERVAL_SECONDS", "86400"))  # 24h
PG_POOL_MAX_SIZE = int(os.environ.get("PG_POOL_MAX_SIZE", "8"))
PG_POOL_MIN_SIZE = int(os.environ.get("PG_POOL_MIN_SIZE", "1"))
# [2] Valencia: keywords para inferencia heurística de carga emocional
_NEGATIVE_KEYWORDS = frozenset({
    "error", "fallo", "fail", "bug", "problema", "issue", "crash", "broken",
    "exception", "traceback", "critical", "fatal", "bloqueo", "timeout",
    "corrupt", "corrupted", "perdida", "data loss",
})
_POSITIVE_KEYWORDS = frozenset({
    "solucion", "solution", "exito", "success", "completado", "fixed",
    "implementado", "funcionando", "resuelto", "optimizado", "mejorado",
    "deployed", "lanzado", "done", "achieved",
})
_HIGH_AROUSAL_KEYWORDS = frozenset({
    "critical", "fatal", "emergency", "urgente", "bloqueante", "showstopper",
    "crash", "corruption", "breakthrough", "hito", "milestone", "discovery",
    "revelation",
})
AI_MEMORY_TEST_MODE = os.environ.get("AI_MEMORY_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
AI_MEMORY_TEST_NOW = os.environ.get("AI_MEMORY_TEST_NOW", "").strip()
SESSION_MEM0_TIMEOUT_SECONDS = min(MEM0_INGEST_TIMEOUT_SECONDS, 5.0) if AI_MEMORY_TEST_MODE else MEM0_INGEST_TIMEOUT_SECONDS
EMBEDDING_CACHE_NAMESPACE = "embed:test:v2" if AI_MEMORY_TEST_MODE else f"embed:live:{EMBEDDING_MODEL}"

qdrant: Optional[AsyncQdrantClient] = None
pg_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None
openai_client: Optional[AsyncOpenAI] = None
deepseek_client: Optional[AsyncOpenAI] = None
http_client: Optional[httpx.AsyncClient] = None
TEST_NOW_OVERRIDE: Optional[datetime] = None

app = FastAPI(title="AI Memory Brain", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/.well-known/oauth-authorization-server")
@app.get("/mcp/.well-known/oauth-authorization-server")
async def _oauth_not_supported():
    """Return proper 404 for OAuth discovery so MCP clients fall through to no-auth."""
    return Response(status_code=404)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal_error"})
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


class StructuredSearchRequest(SearchMemoryRequest):
    register_access: bool = False
    chain_hops: int = Field(default=0, ge=0, le=2)


class TestClockRequest(BaseModel):
    now: Optional[str] = None


class GraphSubgraphRequest(BaseModel):
    project: Optional[str] = None
    mode: str = "project_hot"
    query: str = ""
    center_memory_id: str = ""
    scope: str = "project"
    memory_type: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    depth: int = Field(default=1, ge=1, le=2)
    node_limit: int = Field(default=32, ge=1, le=80)
    edge_limit: int = Field(default=96, ge=1, le=200)
    min_weight: float = Field(default=RELATION_ACTIVE_THRESHOLD, ge=0.0, le=1.0)
    include_inactive: bool = False


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def now_utc() -> datetime:
    if TEST_NOW_OVERRIDE is not None:
        return TEST_NOW_OVERRIDE
    if AI_MEMORY_TEST_MODE and AI_MEMORY_TEST_NOW:
        return parse_datetime(AI_MEMORY_TEST_NOW)
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


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


def tokenize_text(text: str) -> list[str]:
    return TOKEN_RE.findall(str(text).lower())


def set_test_now_override(value: Optional[str]):
    global TEST_NOW_OVERRIDE
    if not value:
        TEST_NOW_OVERRIDE = None
        return
    TEST_NOW_OVERRIDE = parse_datetime(value)


def deterministic_embedding(text: str) -> list[float]:
    vector = [0.0] * VECTOR_DIM
    tokens = tokenize_text(text)
    if not tokens:
        tokens = ["__empty__"]
    for token, count in Counter(tokens).items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for slot_offset, sign_offset, multiplier in ((0, 6, 1.0), (2, 7, 0.6), (4, 8, 0.3)):
            slot = int.from_bytes(digest[slot_offset : slot_offset + 2], "big") % VECTOR_DIM
            sign = 1.0 if digest[sign_offset] % 2 == 0 else -1.0
            vector[slot] += sign * count * multiplier
    norm = math.sqrt(sum(component * component for component in vector)) or 1.0
    return [round(component / norm, 8) for component in vector]


def compute_text_overlap(left_text: str, right_text: str) -> float:
    left_tokens = set(tokenize_text(left_text))
    right_tokens = set(tokenize_text(right_text))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    baseline = max(1, min(len(left_tokens), len(right_tokens)))
    return round(clamp01(overlap / baseline), 4)


def format_search_results(query: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return f"No encontre memorias relevantes para '{query}'"
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


def _kw_match(kw: str, text: str) -> bool:
    """Matching preciso con word boundary para palabras simples, substring para frases."""
    if " " in kw:
        return kw in text
    return bool(re.search(r"\b" + re.escape(kw) + r"\b", text))


def infer_valence_arousal(content: str) -> tuple[float, float]:
    """[2] Infiere valencia (-1..+1) y arousal (0..1) del contenido de forma heurística."""
    text = content.lower()
    neg = sum(1 for kw in _NEGATIVE_KEYWORDS if _kw_match(kw, text))
    pos = sum(1 for kw in _POSITIVE_KEYWORDS if _kw_match(kw, text))
    high = sum(1 for kw in _HIGH_AROUSAL_KEYWORDS if _kw_match(kw, text))
    raw_valence = pos * 0.3 - neg * 0.3
    valence = max(-1.0, min(1.0, raw_valence))
    arousal = clamp01(0.4 + high * 0.2 + abs(valence) * 0.3)
    return round(valence, 3), round(arousal, 3)


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
        (now_utc() - last_accessed_at.astimezone(timezone.utc)).total_seconds() / 86400.0,
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
    # [L1] Use permeability-based resolution, falling back to bridges
    if pg_pool:
        try:
            async with pg_pool.acquire() as conn:
                permeable = await get_permeable_projects(conn, project_name)
                if permeable:
                    return [project_name, *[name for name in permeable if name != project_name]]
        except Exception:
            pass
    # Fallback to old bridges
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
        # [1] Ebbinghaus
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS review_count INT DEFAULT 0",
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS stability_halflife_days FLOAT DEFAULT 1.0",
        # [2] Valencia emocional
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS valence FLOAT DEFAULT 0.0",
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS arousal FLOAT DEFAULT 0.5",
        # [3] Sesgo de novedad
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS novelty_score FLOAT DEFAULT 0.5",
        # [6] Abstraction level para schemas
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS abstraction_level INT DEFAULT 0",
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
        "CREATE INDEX IF NOT EXISTS idx_memory_relations_active_source ON memory_relations(source_memory_id, weight DESC, updated_at DESC) WHERE active = TRUE",
        "CREATE INDEX IF NOT EXISTS idx_memory_relations_active_target ON memory_relations(target_memory_id, weight DESC, updated_at DESC) WHERE active = TRUE",
        "CREATE INDEX IF NOT EXISTS idx_memory_log_hotspots ON memory_log(project_id, manual_pin DESC, activation_score DESC, stability_score DESC, last_accessed_at DESC, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_project_bridges_project ON project_bridges(project_id, active)",
        "CREATE INDEX IF NOT EXISTS idx_project_bridges_related ON project_bridges(related_project_id, active)",
        # [2][3] Índices para valencia, arousal y novelty
        "CREATE INDEX IF NOT EXISTS idx_memory_log_arousal ON memory_log(project_id, arousal DESC) WHERE arousal > 0.6",
        "CREATE INDEX IF NOT EXISTS idx_memory_log_novelty ON memory_log(project_id, novelty_score DESC) WHERE novelty_score > 0.6",
        # [7] Tabla de contradicciones
        """
        CREATE TABLE IF NOT EXISTS contradiction_queue (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            memory_a_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
            memory_b_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
            resolution_status VARCHAR(20) DEFAULT 'pending',
            resolution_type VARCHAR(30),
            resolution_memory_id UUID REFERENCES memory_log(id) ON DELETE SET NULL,
            condition_text TEXT,
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT contradiction_queue_unique UNIQUE (memory_a_id, memory_b_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_contradiction_pending ON contradiction_queue(resolution_status) WHERE resolution_status = 'pending'",
        # [6] Tabla de fuentes de esquemas
        """
        CREATE TABLE IF NOT EXISTS schema_sources (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            schema_memory_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
            source_memory_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT schema_sources_unique UNIQUE (schema_memory_id, source_memory_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_schema_sources_schema ON schema_sources(schema_memory_id)",
        # [8] Tabla de deep sleep runs
        """
        CREATE TABLE IF NOT EXISTS deep_sleep_runs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            memories_scanned INT DEFAULT 0,
            schemas_created INT DEFAULT 0,
            contradictions_resolved INT DEFAULT 0,
            memories_pruned INT DEFAULT 0,
            relations_reinforced INT DEFAULT 0,
            error TEXT,
            started_at TIMESTAMPTZ DEFAULT NOW(),
            finished_at TIMESTAMPTZ
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_deep_sleep_runs_status ON deep_sleep_runs(status, started_at DESC)",
        # [L0] Keyphrases column
        "ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS keyphrases TEXT[] DEFAULT '{}'",
        # [L1] Myelination columns on memory_relations
        "ALTER TABLE memory_relations ADD COLUMN IF NOT EXISTS myelin_score FLOAT DEFAULT 0.0",
        "ALTER TABLE memory_relations ADD COLUMN IF NOT EXISTS myelin_last_updated TIMESTAMPTZ DEFAULT NOW()",
        # [L0] Synapse candidates table
        """
        CREATE TABLE IF NOT EXISTS synapse_candidates (
            id SERIAL PRIMARY KEY,
            source_memory_id UUID NOT NULL REFERENCES memory_log(id) ON DELETE CASCADE,
            target_memory_id UUID NOT NULL REFERENCES memory_log(id) ON DELETE CASCADE,
            semantic_score FLOAT NOT NULL,
            domain_score FLOAT NOT NULL,
            lexical_overlap FLOAT NOT NULL,
            emotional_proximity FLOAT NOT NULL,
            importance_attraction FLOAT NOT NULL,
            temporal_proximity FLOAT NOT NULL,
            type_compatibility FLOAT NOT NULL,
            combined_score FLOAT NOT NULL,
            suggested_type VARCHAR(50),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            reviewed_at TIMESTAMPTZ,
            CONSTRAINT synapse_candidates_unique UNIQUE (source_memory_id, target_memory_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_synapse_candidates_status ON synapse_candidates(status)",
        "CREATE INDEX IF NOT EXISTS idx_synapse_candidates_score ON synapse_candidates(combined_score DESC)",
        # [L1] Project permeability
        """
        CREATE TABLE IF NOT EXISTS project_permeability (
            id SERIAL PRIMARY KEY,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            related_project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            permeability_score FLOAT DEFAULT 0.0,
            organic_origin BOOLEAN DEFAULT TRUE,
            formation_reason TEXT,
            last_activity TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT project_permeability_unique UNIQUE (project_id, related_project_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_project_permeability_score ON project_permeability(permeability_score DESC)",
        # [L1] Myelination events
        """
        CREATE TABLE IF NOT EXISTS myelination_events (
            id SERIAL PRIMARY KEY,
            relation_id UUID REFERENCES memory_relations(id) ON DELETE CASCADE,
            permeability_id INTEGER REFERENCES project_permeability(id) ON DELETE CASCADE,
            event_type VARCHAR(50) NOT NULL,
            delta FLOAT NOT NULL,
            new_score FLOAT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_myelination_events_relation ON myelination_events(relation_id)",
        "CREATE INDEX IF NOT EXISTS idx_myelination_events_created ON myelination_events(created_at)",
        # [L2] Sleep cycles
        """
        CREATE TABLE IF NOT EXISTS sleep_cycles (
            id SERIAL PRIMARY KEY,
            cycle_type VARCHAR(10) NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            trigger_reason TEXT,
            projects_processed TEXT[],
            stats JSONB DEFAULT '{}'::jsonb
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_sleep_cycles_type ON sleep_cycles(cycle_type)",
        "CREATE INDEX IF NOT EXISTS idx_sleep_cycles_started ON sleep_cycles(started_at DESC)",
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
        async with conn.transaction():
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
    cache_key = EMBEDDING_CACHE_NAMESPACE + ":" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    if redis_client:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    if AI_MEMORY_TEST_MODE:
        embedding = deterministic_embedding(text)
    else:
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
    try:
        response = await qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=embedding,
            using="content",
            query_filter=Filter(must=conditions),
            limit=1,
            with_payload=True,
            score_threshold=threshold,
        )
    except Exception:
        # Fallback for old single-vector collections
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
                ml.manual_pin,
                COALESCE(ml.review_count, 0) AS review_count,
                COALESCE(ml.stability_halflife_days, 1.0) AS stability_halflife_days,
                COALESCE(ml.valence, 0.0) AS valence,
                COALESCE(ml.arousal, 0.5) AS arousal,
                COALESCE(ml.novelty_score, 0.5) AS novelty_score,
                COALESCE(ml.abstraction_level, 0) AS abstraction_level,
                COALESCE(ml.keyphrases, '{}') AS keyphrases
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
            "review_count": int(row["review_count"] or 0),
            "stability_halflife_days": float(row["stability_halflife_days"] or 1.0),
            "valence": float(row["valence"] or 0.0),
            "arousal": float(row["arousal"] or 0.5),
            "novelty_score": float(row["novelty_score"] or 0.5),
            "abstraction_level": int(row["abstraction_level"] or 0),
            "keyphrases": list(row["keyphrases"] or []),
        }
    return records


def serialize_memory_record(record: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, datetime):
            serialized[key] = value.astimezone(timezone.utc).isoformat()
        else:
            serialized[key] = value
    return serialized


def memory_content_preview(content: str, max_length: int = 220) -> str:
    normalized = " ".join(str(content or "").split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "…"


def compute_memory_prominence(record: dict[str, Any]) -> float:
    recency_frequency = compute_recency_frequency(
        int(record.get("access_count", 0) or 0),
        record.get("last_accessed_at"),
    )
    manual_boost = 1.0 if record.get("manual_pin") else 0.0
    # [2] Valencia emocional: memorias con alta carga afectiva son más prominentes
    arousal = float(record.get("arousal", 0.5) or 0.5)
    valence_abs = abs(float(record.get("valence", 0.0) or 0.0))
    prominence = clamp01(
        0.34 * manual_boost
        + 0.22 * float(record.get("activation_score", 0.0) or 0.0)
        + 0.16 * float(record.get("stability_score", 0.5) or 0.5)
        + 0.12 * recency_frequency
        + 0.08 * float(record.get("importance", 0.5) or 0.5)
        + 0.05 * arousal
        + 0.03 * valence_abs
    )
    return round(prominence, 4)


def build_graph_node(record: dict[str, Any]) -> dict[str, Any]:
    serialized = serialize_memory_record(record)
    return {
        "memory_id": serialized["id"],
        "project": serialized.get("project"),
        "memory_type": serialized.get("memory_type"),
        "content_preview": memory_content_preview(str(serialized.get("content") or serialized.get("summary") or "")),
        "tags": serialized.get("tags", []),
        "activation_score": round(float(serialized.get("activation_score", 0.0) or 0.0), 4),
        "stability_score": round(float(serialized.get("stability_score", 0.5) or 0.5), 4),
        "access_count": int(serialized.get("access_count", 0) or 0),
        "manual_pin": bool(serialized.get("manual_pin", False)),
        "prominence": compute_memory_prominence(record),
        "keyphrases": serialized.get("keyphrases", []) or [],
    }


def canonical_memory_id_pairs(memory_ids: list[str], limit_pairs: int = 6) -> list[tuple[str, str]]:
    unique_ids = list(dict.fromkeys(str(memory_id).strip() for memory_id in memory_ids if str(memory_id).strip()))
    pairs: list[tuple[str, str]] = []
    for index, left_id in enumerate(unique_ids):
        for right_id in unique_ids[index + 1 :]:
            pairs.append(canonical_memory_pair(left_id, right_id))
            if len(pairs) >= limit_pairs:
                return pairs
    return pairs


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


async def reinforce_relation_pairs(
    memory_ids: list[str],
    weight_delta: float = 0.02,
    activation_time: Optional[datetime] = None,
) -> int:
    if not pg_pool:
        return 0
    pairs = canonical_memory_id_pairs(memory_ids)
    if not pairs:
        return 0
    activation_time = activation_time or now_utc()
    source_ids = [uuid.UUID(source_id) for source_id, _ in pairs]
    target_ids = [uuid.UUID(target_id) for _, target_id in pairs]
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH pairs AS (
                SELECT *
                FROM unnest($1::uuid[], $2::uuid[]) AS pair(source_memory_id, target_memory_id)
            )
            UPDATE memory_relations mr
            SET reinforcement_count = mr.reinforcement_count + 1,
                last_activated_at = $3::timestamptz,
                weight = CASE
                    WHEN mr.origin = 'manual' THEN mr.weight
                    ELSE LEAST(1.0, mr.weight + $4)
                END,
                active = TRUE,
                updated_at = $3::timestamptz
            FROM pairs
            WHERE mr.source_memory_id = pairs.source_memory_id
              AND mr.target_memory_id = pairs.target_memory_id
            RETURNING mr.id
            """,
            source_ids,
            target_ids,
            activation_time,
            weight_delta,
        )
    return len(rows)


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
    current_time = now_utc()
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO memory_relations
            (source_memory_id, target_memory_id, relation_type, weight, origin, evidence_json, reinforcement_count, last_activated_at, active)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, 1, CASE WHEN $7 THEN $8::timestamptz ELSE NULL END, $9)
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
                    WHEN $7 THEN $8::timestamptz
                    ELSE memory_relations.last_activated_at
                END,
                active = CASE
                    WHEN memory_relations.origin = 'manual' THEN TRUE
                    ELSE (LEAST(1.0, GREATEST(memory_relations.weight, EXCLUDED.weight)) >= $10)
                END,
                updated_at = $8::timestamptz
            RETURNING id, source_memory_id, target_memory_id, relation_type, weight, origin, reinforcement_count, active
            """,
            uuid.UUID(source_id),
            uuid.UUID(target_id),
            relation_type,
            clamp01(weight),
            origin,
            json.dumps(evidence or {}, ensure_ascii=False),
            mark_activated,
            current_time,
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
        # [7] Encolar contradicción dentro de la misma conexión, sin overhead de segunda adquisición
        if relation_type == "contradicts":
            try:
                await conn.execute(
                    """
                    INSERT INTO contradiction_queue (memory_a_id, memory_b_id)
                    VALUES ($1::uuid, $2::uuid)
                    ON CONFLICT (memory_a_id, memory_b_id) DO NOTHING
                    """,
                    uuid.UUID(source_id),
                    uuid.UUID(target_id),
                )
            except Exception as exc:
                logger.debug("Error encolando contradiccion: %s", exc)
    return serialize_row(row) or {}


async def decay_project_relations(project_name: str, stale_days: int = 21) -> int:
    if not pg_pool or not project_name:
        return 0
    current_time = now_utc()
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
                updated_at = $4::timestamptz
            WHERE mr.origin <> 'manual'
              AND (
                  mr.source_memory_id IN (SELECT id FROM project_memories)
                  OR mr.target_memory_id IN (SELECT id FROM project_memories)
              )
              AND COALESCE(mr.last_activated_at, mr.created_at) < ($4::timestamptz - make_interval(days => $3::int))
            """,
            project_name,
            RELATION_ACTIVE_THRESHOLD,
            stale_days,
            current_time,
        )
    return int(result.split()[-1])


async def decay_memory_stability(project_name: str) -> int:
    """[1] Aplica decay exponencial (Ebbinghaus) a stability_score de memorias no accedidas.
    Las memorias con arousal > 0.7 o manual_pin están protegidas."""
    if not pg_pool or not project_name:
        return 0
    current_time = now_utc()
    async with pg_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE memory_log ml
            SET stability_score = GREATEST(
                0.05,
                ml.stability_score * exp(
                    -- Clip at -700 to prevent FLOAT8 underflow (exp(-746) is below subnormal)
                    GREATEST(
                        -700.0,
                        -EXTRACT(EPOCH FROM ($2::timestamptz - COALESCE(ml.last_accessed_at, ml.created_at))) / 86400.0
                        / GREATEST(1.0, COALESCE(ml.stability_halflife_days, 1.0))
                    )
                )
            )
            FROM projects p
            WHERE p.id = ml.project_id
              AND p.name = $1
              AND ml.manual_pin = FALSE
              AND COALESCE(ml.arousal, 0.5) <= 0.7
              AND EXTRACT(EPOCH FROM ($2::timestamptz - COALESCE(ml.last_accessed_at, ml.created_at))) / 86400.0
                  >= GREATEST(1.0, COALESCE(ml.stability_halflife_days, 1.0)) * 0.5
            """,
            project_name,
            current_time,
        )
    return int(result.split()[-1]) if result else 0


async def propagate_activation(memory_id: str, depth: int = 2, decay_factor: float = ACTIVATION_PROPAGATION_DECAY) -> int:
    """[4][L3] Spreading activation with myelinic resistance for cross-project relations.
    La energía se almacena en Redis con TTL de 15 min para usarse como priming en búsquedas.
    Cross-project relations modulate decay by myelin_score."""
    if not pg_pool or not redis_client:
        return 0
    frontier: list[tuple[str, float]] = [(memory_id, 1.0)]
    visited: dict[str, float] = {memory_id: 1.0}
    propagated_count = 0
    async with pg_pool.acquire() as conn:
        # Get source memory's project
        source_row = await conn.fetchrow(
            "SELECT p.name as project FROM memory_log m JOIN projects p ON p.id = m.project_id WHERE m.id = $1",
            uuid.UUID(memory_id),
        )
        source_project = str(source_row["project"]) if source_row else ""

        for hop in range(depth):
            if not frontier:
                break
            frontier_ids = [uuid.UUID(mid) for mid, _ in frontier]
            energy_map = {mid: energy for mid, energy in frontier}
            rows = await conn.fetch(
                """
                SELECT mr.source_memory_id::text AS src, mr.target_memory_id::text AS tgt,
                       mr.weight, COALESCE(mr.myelin_score, 0.0) AS myelin_score,
                       ps.name AS src_project, pt.name AS tgt_project
                FROM memory_relations mr
                JOIN memory_log ms ON ms.id = mr.source_memory_id
                JOIN memory_log mt ON mt.id = mr.target_memory_id
                LEFT JOIN projects ps ON ps.id = ms.project_id
                LEFT JOIN projects pt ON pt.id = mt.project_id
                WHERE mr.active = TRUE
                  AND (mr.source_memory_id = ANY($1::uuid[]) OR mr.target_memory_id = ANY($1::uuid[]))
                """,
                frontier_ids,
            )
            next_frontier: list[tuple[str, float]] = []
            for row in rows:
                src, tgt = str(row["src"]), str(row["tgt"])
                weight = float(row["weight"])
                myelin = float(row["myelin_score"])
                src_proj = str(row["src_project"] or "")
                tgt_proj = str(row["tgt_project"] or "")

                if src in energy_map:
                    neighbor, source_energy = tgt, energy_map[src]
                    neighbor_project = tgt_proj
                else:
                    neighbor, source_energy = src, energy_map.get(tgt, 0.0)
                    neighbor_project = src_proj

                is_cross = source_project and neighbor_project and neighbor_project != source_project
                if is_cross:
                    # [L3] Myelinic resistance: myelin modulates cross-project decay
                    effective_decay = decay_factor * myelin
                else:
                    effective_decay = decay_factor

                propagated_energy = source_energy * effective_decay * weight
                if propagated_energy < 0.05:
                    continue
                if propagated_energy > visited.get(neighbor, 0.0):
                    visited[neighbor] = propagated_energy
                    next_frontier.append((neighbor, propagated_energy))
                    propagated_count += 1
            frontier = next_frontier

    # --- Lateral Inhibition (winner-take-all) ---
    # After propagation, suppress weakly activated memories so only the
    # strongest survive. Inspired by SYNAPSE (arXiv:2601.02744).
    if len(visited) > 1:
        energies = [e for mid, e in visited.items() if mid != memory_id]
        if energies:
            mean_energy = sum(energies) / len(energies)
            std_energy = (sum((e - mean_energy) ** 2 for e in energies) / len(energies)) ** 0.5
            threshold = mean_energy + std_energy
            INHIBITION_FACTOR = 0.3

            inhibited: dict[str, float] = {memory_id: visited[memory_id]}
            for mid, energy in visited.items():
                if mid == memory_id:
                    continue
                # Lateral inhibition: subtract mean of others scaled by factor
                suppressed = energy - INHIBITION_FACTOR * mean_energy
                # Sigmoid gate: sharp cutoff around threshold
                if suppressed > 0:
                    steepness = 10.0
                    gated = 1.0 / (1.0 + math.exp(-(suppressed - threshold) * steepness))
                    if gated > 0.05:
                        inhibited[mid] = round(gated, 4)
            visited = inhibited

    # Escribir activación propagada en Redis con TTL
    try:
        pipeline = redis_client.pipeline()
        for mid, energy in visited.items():
            if mid == memory_id:
                continue
            pipeline.set(f"activation_propagation:{mid}", str(round(energy, 4)), ex=ACTIVATION_PROPAGATION_TTL)
        await pipeline.execute()
    except Exception as exc:
        logger.debug("Error escribiendo activacion propagada en Redis: %s", exc)
    return propagated_count


async def expand_search_with_hops(
    base_results: list[dict[str, Any]],
    chain_hops: int,
    allowed_projects: set[str],
    exclude_ids: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    """[5] Expande resultados de búsqueda siguiendo relaciones activas (associative chaining).
    Resultados en hop N tienen score *= 0.7^N respecto al resultado semántico original."""
    if chain_hops == 0 or not base_results or not pg_pool:
        return base_results
    all_results: dict[str, dict[str, Any]] = {item["id"]: item for item in base_results}
    current_hop_ids = [item["id"] for item in base_results[:3]]
    for hop in range(1, chain_hops + 1):
        if not current_hop_ids:
            break
        hop_discount = 0.7 ** hop
        async with pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT source_memory_id::text AS src, target_memory_id::text AS tgt, weight
                FROM memory_relations
                WHERE active = TRUE
                  AND weight > 0.35
                  AND (source_memory_id = ANY($1::uuid[]) OR target_memory_id = ANY($1::uuid[]))
                ORDER BY weight DESC
                LIMIT 24
                """,
                [uuid.UUID(mid) for mid in current_hop_ids],
            )
        neighbor_ids: list[str] = []
        for row in rows:
            for nid in (str(row["src"]), str(row["tgt"])):
                if nid not in all_results and nid not in exclude_ids:
                    neighbor_ids.append(nid)
        if not neighbor_ids:
            break
        # Cap neighbors per hop to prevent exponential growth
        neighbor_ids = list(dict.fromkeys(neighbor_ids))[:12]
        neighbor_records = await fetch_memory_records(neighbor_ids)
        for mid, record in neighbor_records.items():
            if allowed_projects and record.get("project") not in allowed_projects:
                continue
            base_score = float(record.get("activation_score", 0.0) or 0.0)
            hop_score = round(max(base_score, 0.35) * hop_discount, 4)
            all_results[mid] = {
                "id": mid,
                "project": record.get("project", ""),
                "memory_type": record.get("memory_type", "general"),
                "content": record.get("content", record.get("summary", "")),
                "tags": record.get("tags", []),
                "semantic_score": 0.0,
                "hybrid_score": hop_score,
                "relation_weight": 0.0,
                "recency_frequency": compute_recency_frequency(
                    int(record.get("access_count", 0)),
                    record.get("last_accessed_at"),
                ),
                "tag_overlap": 0.0,
                "importance": float(record.get("importance", 0.5) or 0.5),
                "stability_score": float(record.get("stability_score", 0.5) or 0.5),
                "manual_pin": bool(record.get("manual_pin", False)),
                "hop_distance": hop,
            }
        current_hop_ids = list(dict.fromkeys(neighbor_ids))
    combined = list(all_results.values())
    combined.sort(key=lambda x: (x.get("hybrid_score", 0.0), x.get("semantic_score", 0.0)), reverse=True)
    return combined[:limit]


async def register_memory_access(results: list[dict[str, Any]]):
    if not pg_pool or not results:
        return
    current_time = now_utc()
    unique_results = list({str(item["id"]): item for item in results}.values())
    memory_ids = [uuid.UUID(str(item["id"])) for item in unique_results]
    activation_scores = [float(item["hybrid_score"]) for item in unique_results]
    stability_scores = [
        clamp01(max(float(item["hybrid_score"]), float(item.get("stability_score", 0.5))))
        for item in unique_results
    ]
    async with pg_pool.acquire() as conn:
        await conn.execute(
            """
            WITH updates AS (
                SELECT *
                FROM unnest($1::uuid[], $2::float8[], $3::float8[]) AS item(id, activation_score, stability_score)
            )
            UPDATE memory_log ml
            SET access_count = ml.access_count + 1,
                last_accessed_at = $4::timestamptz,
                activation_score = GREATEST(COALESCE(ml.activation_score, 0), updates.activation_score),
                stability_score = CASE
                    WHEN ml.manual_pin THEN 1.0
                    ELSE LEAST(1.0, GREATEST(COALESCE(ml.stability_score, 0.3), updates.stability_score))
                END,
                review_count = COALESCE(ml.review_count, 0) + 1,
                stability_halflife_days = CASE
                    WHEN ml.manual_pin THEN COALESCE(ml.stability_halflife_days, 1.0)
                    ELSE LEAST(512.0, COALESCE(ml.stability_halflife_days, 1.0) * 2.0)
                END
            FROM updates
            WHERE ml.id = updates.id
            """,
            memory_ids,
            activation_scores,
            stability_scores,
            current_time,
        )
    await reinforce_relation_pairs([str(item["id"]) for item in unique_results[:4]], activation_time=current_time)


async def structured_search_memories(
    query: str,
    project: Optional[str] = None,
    memory_type: Optional[str] = None,
    limit: int = 8,
    scope: str = "project",
    tags: str | list[str] = "",
    score_threshold: float = 0.35,
    exclude_memory_ids: Optional[list[str]] = None,
    chain_hops: int = 0,
) -> list[dict[str, Any]]:
    normalized_scope = validate_search_scope(scope)
    normalized_tags = normalize_tags(tags)
    allowed_projects = set(await resolve_scope_projects(project, normalized_scope))
    exclude_ids = {str(memory_id) for memory_id in (exclude_memory_ids or [])}
    query_embedding = await get_embedding(query)

    # SDR Pre-filter: narrow candidates via keyphrase overlap in Postgres
    prefilter_ids: list[str] | None = None
    if pg_pool and project:
        try:
            query_keyphrases = extract_keyphrases(query, normalize_tags(tags))
            if query_keyphrases:
                prefilter_raw_limit = max(limit * 6, 24)
                async with pg_pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT ml.id::text
                        FROM memory_log ml
                        JOIN projects p ON p.id = ml.project_id
                        WHERE p.name = $1
                          AND ml.keyphrases && $2::text[]
                        ORDER BY array_length(
                            ARRAY(SELECT unnest(ml.keyphrases) INTERSECT SELECT unnest($2::text[])),
                            1
                        ) DESC NULLS LAST
                        LIMIT $3
                        """,
                        project,
                        query_keyphrases,
                        prefilter_raw_limit,
                    )
                    if len(rows) >= limit:
                        prefilter_ids = [str(row["id"]) for row in rows]
        except Exception as exc:
            logger.debug("Keyphrase pre-filter failed, using full search: %s", exc)

    conditions: list[FieldCondition] = []
    project_conditions: list[FieldCondition] = []
    if project and normalized_scope == "project":
        conditions.append(FieldCondition(key="project_id", match=MatchValue(value=project)))
    elif allowed_projects:
        project_conditions = [
            FieldCondition(key="project_id", match=MatchValue(value=project_name))
            for project_name in sorted(allowed_projects)
        ]
    if memory_type:
        conditions.append(FieldCondition(key="memory_type", match=MatchValue(value=memory_type)))
    if project_conditions:
        query_filter = Filter(must=conditions, should=project_conditions)
    else:
        query_filter = Filter(must=conditions) if conditions else None
    raw_limit = max(limit * 6, 24)
    if project_conditions:
        raw_limit = max(raw_limit, limit * max(6, len(project_conditions) * 3))

    # Apply keyphrase pre-filter to Qdrant query
    if prefilter_ids is not None:
        has_id_condition = HasIdCondition(has_id=prefilter_ids)
        if query_filter is None:
            query_filter = Filter(must=[has_id_condition])
        else:
            existing_must = list(query_filter.must or [])
            existing_must.append(has_id_condition)
            query_filter = Filter(must=existing_must, should=query_filter.should)
    # [L0] Fusion search: dual-vector with RRF, fallback to single-vector
    try:
        response = await qdrant.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                Prefetch(query=query_embedding, using="content", limit=raw_limit),
                Prefetch(query=query_embedding, using="domain", limit=raw_limit),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            query_filter=query_filter,
            limit=raw_limit,
            with_payload=True,
        )
    except Exception as fusion_exc:
        logger.debug("Fusion search failed, falling back to single-vector: %s", fusion_exc)
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

    # [4] Spreading Activation: cargar bonuses de priming desde Redis de una vez
    propagation_bonuses: dict[str, float] = {}
    if redis_client and points:
        try:
            pipe = redis_client.pipeline()
            point_ids = [str(p.id) for p in points]
            for pid in point_ids:
                pipe.get(f"activation_propagation:{pid}")
            prop_values = await pipe.execute()
            propagation_bonuses = {
                pid: clamp01(float(val))
                for pid, val in zip(point_ids, prop_values)
                if val is not None
            }
        except Exception as exc:
            logger.debug("Error leyendo activacion propagada de Redis: %s", exc)

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
        # [4] Propagation bonus desde spreading activation
        propagation_bonus = propagation_bonuses.get(memory_id, 0.0)
        hybrid_score = round(
            clamp01(
                0.5 * semantic_relevance
                + 0.2 * relation_weight
                + 0.2 * recency_frequency
                + 0.1 * tag_overlap
            ),
            4,
        )
        if propagation_bonus > 0.0:
            hybrid_score = round(clamp01(hybrid_score + 0.15 * propagation_bonus), 4)
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
                "valence": float(payload.get("valence") or meta.get("valence") or 0.0),
                "arousal": float(payload.get("arousal") or meta.get("arousal") or 0.5),
                "created_at": payload.get("created_at") or meta.get("created_at"),
                "stability_score": float(meta.get("stability_score", 0.5) or 0.5),
                "manual_pin": bool(meta.get("manual_pin", False)),
            }
        )
    results.sort(key=lambda item: (item["hybrid_score"], item["semantic_score"], item["importance"]), reverse=True)
    base_results = results[:limit]
    # [5] Multi-hop: expandir siguiendo relaciones si se solicita chain_hops > 0
    if chain_hops > 0:
        return await expand_search_with_hops(base_results, chain_hops, allowed_projects, exclude_ids, limit)
    return base_results


async def classify_relation_with_llm(
    source: dict[str, Any],
    candidate: dict[str, Any],
    semantic_score: float,
    shared_tags: list[str],
) -> Optional[dict[str, Any]]:
    if AI_MEMORY_TEST_MODE:
        return None
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
    source_tags = normalize_tags(source.get("tags", []))
    candidate_tags = normalize_tags(candidate.get("tags", []))
    same_type = source.get("memory_type") == candidate.get("memory_type")
    lexical_overlap = compute_text_overlap(source_text, candidate_text)
    cross_project = source.get("project") != candidate.get("project")
    tag_coverage = len(shared_tags) / max(1, min(len(source_tags), len(candidate_tags)))
    if semantic_score >= 0.95 and (same_type or shared_tags):
        return {"relation_type": "same_concept", "weight": clamp01(semantic_score), "reason": "high_semantic_overlap"}
    if shared_tags and same_type and lexical_overlap >= 0.45:
        relation_type = "derived_from" if cross_project else "same_concept"
        return {
            "relation_type": relation_type,
            "weight": clamp01(max(semantic_score, 0.82 if cross_project else 0.86)),
            "reason": "lexical_overlap_shared_tags",
        }
    if same_type and tag_coverage >= 0.66 and semantic_score >= 0.48:
        relation_type = "derived_from" if cross_project else "supports"
        return {
            "relation_type": relation_type,
            "weight": clamp01(max(semantic_score, 0.72 if cross_project else 0.76)),
            "reason": "dense_tag_overlap",
        }
    if semantic_score >= 0.9 and shared_tags:
        return {"relation_type": "extends", "weight": clamp01(semantic_score - 0.05), "reason": "shared_tags"}
    if any(token in source_text for token in ["builds on", "extends", "expands"]) or any(
        token in candidate_text for token in ["builds on", "extends", "expands"]
    ):
        return {"relation_type": "extends", "weight": clamp01(max(0.7, semantic_score)), "reason": "extension_language"}
    if shared_tags and lexical_overlap >= 0.35:
        relation_type = "derived_from" if cross_project else "supports"
        return {
            "relation_type": relation_type,
            "weight": clamp01(max(semantic_score, 0.74 if cross_project else 0.78)),
            "reason": "moderate_lexical_overlap",
        }
    if same_type and shared_tags and semantic_score >= 0.84:
        return {"relation_type": "supports", "weight": clamp01(semantic_score - 0.04), "reason": "same_type_shared_tags"}
    if shared_tags and semantic_score >= 0.82:
        return {"relation_type": "applies_to", "weight": clamp01(semantic_score - 0.08), "reason": "tag_supported_similarity"}
    if semantic_score >= 0.88 and cross_project:
        return {"relation_type": "derived_from", "weight": clamp01(semantic_score - 0.06), "reason": "cross_project_reuse"}
    if same_type and shared_tags and semantic_score >= 0.72:
        return {
            "relation_type": "supports",
            "weight": clamp01(max(semantic_score, 0.72)),
            "reason": "same_type_shared_tags_fallback",
        }
    return None


async def infer_relations_from_candidates(
    source_memory: dict[str, Any],
    candidates: list[dict[str, Any]],
    allowed_projects: set[str],
    origin: str,
    max_links: Optional[int] = None,
) -> list[dict[str, Any]]:
    """[L0] Multi-signal cascade replaces tag-gated synapse formation."""
    created: list[dict[str, Any]] = []
    source_text = str(source_memory.get("content", "")).lower()
    for candidate in candidates:
        try:
            if candidate["project"] not in allowed_projects:
                continue
            candidate_text = str(candidate.get("content", "")).lower()
            cross_project = source_memory.get("project") != candidate.get("project")

            # Compute all 7 signals
            signals = {
                "semantic_score": float(candidate.get("semantic_score", 0.0)),
                "domain_score": float(candidate.get("domain_score", candidate.get("semantic_score", 0.0))),
                "lexical_overlap": compute_text_overlap(source_text, candidate_text),
                "emotional_proximity": sc_emotional_proximity(source_memory, candidate),
                "importance_attraction": sc_importance_attraction(source_memory, candidate),
                "temporal_proximity": sc_temporal_proximity(source_memory, candidate),
                "type_compatibility": sc_type_compatibility(source_memory, candidate),
            }

            result = classify_synapse_cascade(signals, cross_project)
            if result is None:
                continue

            # Tier 3: store as candidate for sleep validation
            if result["tier"] == 3 and pg_pool:
                try:
                    async with pg_pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO synapse_candidates
                            (source_memory_id, target_memory_id, semantic_score, domain_score,
                             lexical_overlap, emotional_proximity, importance_attraction,
                             temporal_proximity, type_compatibility, combined_score, suggested_type)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            ON CONFLICT (source_memory_id, target_memory_id) DO UPDATE
                                SET combined_score = EXCLUDED.combined_score,
                                    status = 'pending'
                            """,
                            uuid.UUID(source_memory["id"]),
                            uuid.UUID(candidate["id"]),
                            signals["semantic_score"],
                            signals["domain_score"],
                            signals["lexical_overlap"],
                            signals["emotional_proximity"],
                            signals["importance_attraction"],
                            signals["temporal_proximity"],
                            signals["type_compatibility"],
                            result["combined_score"],
                            result["relation_type"],
                        )
                except Exception as exc:
                    logger.debug("Failed to store synapse candidate: %s", exc)
                continue  # Don't create relation yet - sleep validates

            # Tier 1 & 2: create relation immediately
            relation_data = await upsert_memory_relation(
                source_memory_id=source_memory["id"],
                target_memory_id=candidate["id"],
                relation_type=result["relation_type"],
                weight=float(result["weight"]),
                origin=origin,
                evidence={
                    "reason": result["reason"],
                    "tier": result["tier"],
                    "signals": signals,
                    "source_project": source_memory.get("project"),
                    "target_project": candidate["project"],
                },
            )
            created.append(relation_data)

            # Cross-project: increment permeability
            if cross_project and pg_pool:
                try:
                    async with pg_pool.acquire() as conn:
                        await increment_permeability(
                            conn,
                            source_memory.get("project", ""),
                            candidate["project"],
                        )
                except Exception as exc:
                    logger.debug("Failed to increment permeability: %s", exc)

            if max_links is not None and len(created) >= max_links:
                break
        except Exception as exc:
            logger.warning("No fue posible enlazar %s con %s: %s", source_memory.get("id"), candidate.get("id"), exc)
    return created


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
    auto_link_score_threshold = 0.35 if AI_MEMORY_TEST_MODE else AUTO_LINK_SCORE_THRESHOLD
    # Fetch full metadata for cascade signal computation
    source_meta: dict[str, Any] = {}
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT valence, arousal, importance, created_at FROM memory_log WHERE id = $1",
            uuid.UUID(memory_id),
        )
        if row:
            source_meta = dict(row)
    source_memory = {
        "id": memory_id,
        "project": project,
        "memory_type": memory_type,
        "content": content,
        "tags": normalized_tags,
        "valence": source_meta.get("valence", 0.0),
        "arousal": source_meta.get("arousal", 0.5),
        "importance": source_meta.get("importance", 0.7),
        "created_at": source_meta.get("created_at"),
    }
    candidates = await structured_search_memories(
        query=content,
        project=project,
        memory_type=None,
        limit=AUTO_LINK_CANDIDATE_LIMIT,
        scope="bridged",
        tags="",
        score_threshold=auto_link_score_threshold,
        exclude_memory_ids=[memory_id],
    )
    return await infer_relations_from_candidates(source_memory, candidates, allowed_projects, origin)


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
    # [L1] Also create/update permeability entry for manual bridges
    if active:
        try:
            async with pg_pool.acquire() as conn:
                from myelination import PERMEABILITY_MANUAL_BRIDGE
                perm_id = await ensure_permeability(
                    conn, left_name, right_name, organic=False, reason=reason.strip()
                )
                await conn.execute(
                    """
                    UPDATE project_permeability
                    SET permeability_score = GREATEST(permeability_score, $2),
                        last_activity = NOW()
                    WHERE id = $1
                    """,
                    perm_id,
                    PERMEABILITY_MANUAL_BRIDGE,
                )
        except Exception as exc:
            logger.debug("Failed to create permeability for bridge: %s", exc)
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


async def get_relations_for_memory(memory_id: str) -> list[dict[str, Any]]:
    if not pg_pool:
        return []
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                mr.id,
                mr.source_memory_id,
                mr.target_memory_id,
                mr.relation_type,
                mr.weight,
                mr.origin,
                mr.evidence_json,
                mr.myelin_score,
                mr.reinforcement_count,
                mr.last_activated_at,
                mr.active,
                src.summary AS source_summary,
                dst.summary AS target_summary,
                src_p.name AS source_project,
                dst_p.name AS target_project
            FROM memory_relations mr
            JOIN memory_log src ON src.id = mr.source_memory_id
            JOIN memory_log dst ON dst.id = mr.target_memory_id
            LEFT JOIN projects src_p ON src_p.id = src.project_id
            LEFT JOIN projects dst_p ON dst_p.id = dst.project_id
            WHERE mr.source_memory_id = $1::uuid OR mr.target_memory_id = $1::uuid
            ORDER BY mr.weight DESC, mr.reinforcement_count DESC, mr.updated_at DESC
            """,
            uuid.UUID(memory_id),
        )
    relations: list[dict[str, Any]] = []
    for row in rows:
        serialized = serialize_row(row) or {}
        other_id = serialized["target_memory_id"] if serialized["source_memory_id"] == memory_id else serialized["source_memory_id"]
        other_summary = serialized["target_summary"] if serialized["source_memory_id"] == memory_id else serialized["source_summary"]
        other_project = serialized["target_project"] if serialized["source_memory_id"] == memory_id else serialized["source_project"]
        serialized["other_memory_id"] = other_id
        serialized["other_summary"] = other_summary
        serialized["other_project"] = other_project
        relations.append(serialized)
    return relations


async def list_project_bridges(project: str) -> list[dict[str, Any]]:
    if not pg_pool:
        return []
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                pb.id,
                pb.reason,
                pb.active,
                pb.created_by,
                pb.created_at,
                pb.updated_at,
                left_p.name AS project,
                right_p.name AS related_project
            FROM project_bridges pb
            JOIN projects left_p ON left_p.id = pb.project_id
            JOIN projects right_p ON right_p.id = pb.related_project_id
            WHERE left_p.name = $1 OR right_p.name = $1
            ORDER BY pb.updated_at DESC, pb.created_at DESC
            """,
            project,
        )
    bridges: list[dict[str, Any]] = []
    for row in rows:
        serialized = serialize_row(row) or {}
        if serialized.get("related_project") == project:
            serialized["project"], serialized["related_project"] = serialized["related_project"], serialized["project"]
        bridges.append(serialized)
    return bridges


def validate_graph_mode(mode: str) -> str:
    normalized = str(mode or "project_hot").strip().lower()
    if normalized not in VALID_GRAPH_MODES:
        raise ValueError(f"invalid_graph_mode:{mode}")
    return normalized


async def get_memory_detail_payload(memory_id: str) -> Optional[dict[str, Any]]:
    record = (await fetch_memory_records([memory_id])).get(memory_id)
    if not record:
        return None
    serialized = serialize_memory_record(record)
    relations = await get_relations_for_memory(memory_id)
    return {
        "memory": {
            "memory_id": serialized["id"],
            "project": serialized.get("project"),
            "agent_id": serialized.get("agent_id"),
            "memory_type": serialized.get("memory_type"),
            "summary": serialized.get("summary"),
            "content": serialized.get("content"),
            "content_preview": memory_content_preview(str(serialized.get("content") or serialized.get("summary") or "")),
            "importance": round(float(serialized.get("importance", 0.5) or 0.5), 4),
            "tags": serialized.get("tags", []),
            "access_count": int(serialized.get("access_count", 0) or 0),
            "last_accessed_at": serialized.get("last_accessed_at"),
            "activation_score": round(float(serialized.get("activation_score", 0.0) or 0.0), 4),
            "stability_score": round(float(serialized.get("stability_score", 0.5) or 0.5), 4),
            "manual_pin": bool(serialized.get("manual_pin", False)),
            "prominence": compute_memory_prominence(record),
            # [1] Ebbinghaus
            "review_count": int(serialized.get("review_count", 0) or 0),
            "stability_halflife_days": round(float(serialized.get("stability_halflife_days", 1.0) or 1.0), 3),
            # [2] Valencia emocional
            "valence": round(float(serialized.get("valence", 0.0) or 0.0), 3),
            "arousal": round(float(serialized.get("arousal", 0.5) or 0.5), 3),
            # [3] Novedad
            "novelty_score": round(float(serialized.get("novelty_score", 0.5) or 0.5), 3),
            # [6] Abstracción
            "abstraction_level": int(serialized.get("abstraction_level", 0) or 0),
            # [L0] Keyphrases
            "keyphrases": serialized.get("keyphrases", []) or [],
        },
        "relation_count": len(relations),
        "relations": relations[:20],
    }


async def fetch_project_hot_memory_ids(
    project: str,
    memory_type: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 24,
) -> list[str]:
    if not pg_pool or not project:
        return []
    normalized_tags = normalize_tags(tags or [])
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ml.id
            FROM memory_log ml
            JOIN projects p ON p.id = ml.project_id
            WHERE p.name = $1
              AND ($2::text IS NULL OR ml.action_type = $2::text)
              AND ($3::text[] IS NULL OR ml.tags && $3::text[])
            ORDER BY
                ml.manual_pin DESC,
                ml.activation_score DESC,
                ml.stability_score DESC,
                ml.last_accessed_at DESC NULLS LAST,
                ml.importance DESC,
                ml.created_at DESC
            LIMIT $4
            """,
            project,
            memory_type,
            normalized_tags or None,
            limit,
        )
    return [str(row["id"]) for row in rows]


def graph_relation_sort_key(row: dict[str, Any]) -> tuple[int, float, int, str]:
    return (
        1 if row.get("origin") == "manual" else 0,
        float(row.get("weight") or 0.0),
        int(row.get("reinforcement_count") or 0),
        str(row.get("updated_at") or ""),
    )


async def fetch_relation_rows_touching(
    memory_ids: list[str],
    allowed_projects: Optional[set[str]],
    include_inactive: bool,
    min_weight: float,
    limit: int,
) -> list[dict[str, Any]]:
    if not pg_pool or not memory_ids:
        return []
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                mr.id,
                mr.source_memory_id,
                mr.target_memory_id,
                mr.relation_type,
                mr.weight,
                mr.origin,
                mr.evidence_json,
                mr.myelin_score,
                mr.reinforcement_count,
                mr.last_activated_at,
                mr.active,
                mr.updated_at,
                src_p.name AS source_project,
                dst_p.name AS target_project
            FROM memory_relations mr
            JOIN memory_log src ON src.id = mr.source_memory_id
            JOIN memory_log dst ON dst.id = mr.target_memory_id
            LEFT JOIN projects src_p ON src_p.id = src.project_id
            LEFT JOIN projects dst_p ON dst_p.id = dst.project_id
            WHERE (mr.source_memory_id = ANY($1::uuid[]) OR mr.target_memory_id = ANY($1::uuid[]))
              AND ($2::text[] IS NULL OR COALESCE(src_p.name, '') = ANY($2::text[]))
              AND ($2::text[] IS NULL OR COALESCE(dst_p.name, '') = ANY($2::text[]))
              AND ($3 OR mr.active = TRUE)
              AND (mr.origin = 'manual' OR mr.weight >= $4)
            ORDER BY
                CASE WHEN mr.origin = 'manual' THEN 1 ELSE 0 END DESC,
                mr.weight DESC,
                mr.reinforcement_count DESC,
                mr.updated_at DESC
            LIMIT $5
            """,
            [uuid.UUID(memory_id) for memory_id in memory_ids],
            sorted(allowed_projects) if allowed_projects else None,
            include_inactive,
            min_weight,
            limit,
        )
    return [serialize_row(row) or {} for row in rows]


async def fetch_relation_rows_between(
    memory_ids: list[str],
    allowed_projects: Optional[set[str]],
    include_inactive: bool,
    min_weight: float,
    limit: int,
) -> list[dict[str, Any]]:
    if not pg_pool or not memory_ids:
        return []
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                mr.id,
                mr.source_memory_id,
                mr.target_memory_id,
                mr.relation_type,
                mr.weight,
                mr.origin,
                mr.evidence_json,
                mr.myelin_score,
                mr.reinforcement_count,
                mr.last_activated_at,
                mr.active,
                mr.updated_at,
                src_p.name AS source_project,
                dst_p.name AS target_project
            FROM memory_relations mr
            JOIN memory_log src ON src.id = mr.source_memory_id
            JOIN memory_log dst ON dst.id = mr.target_memory_id
            LEFT JOIN projects src_p ON src_p.id = src.project_id
            LEFT JOIN projects dst_p ON dst_p.id = dst.project_id
            WHERE mr.source_memory_id = ANY($1::uuid[])
              AND mr.target_memory_id = ANY($1::uuid[])
              AND ($2::text[] IS NULL OR COALESCE(src_p.name, '') = ANY($2::text[]))
              AND ($2::text[] IS NULL OR COALESCE(dst_p.name, '') = ANY($2::text[]))
              AND ($3 OR mr.active = TRUE)
              AND (mr.origin = 'manual' OR mr.weight >= $4)
            ORDER BY
                CASE WHEN mr.origin = 'manual' THEN 1 ELSE 0 END DESC,
                mr.weight DESC,
                mr.reinforcement_count DESC,
                mr.updated_at DESC
            LIMIT $5
            """,
            [uuid.UUID(memory_id) for memory_id in memory_ids],
            sorted(allowed_projects) if allowed_projects else None,
            include_inactive,
            min_weight,
            limit,
        )
    return [serialize_row(row) or {} for row in rows]


def build_graph_edge(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_memory_id": row["source_memory_id"],
        "target_memory_id": row["target_memory_id"],
        "relation_type": row["relation_type"],
        "weight": round(float(row.get("weight", 0.0) or 0.0), 4),
        "origin": row.get("origin"),
        "active": bool(row.get("active", False)),
        "reinforcement_count": int(row.get("reinforcement_count", 0) or 0),
        "last_activated_at": row.get("last_activated_at"),
        "myelin_score": round(float(row.get("myelin_score", 0.0) or 0.0), 4),
        "evidence_json": row.get("evidence_json") or None,
    }


async def build_graph_subgraph(payload: GraphSubgraphRequest) -> dict[str, Any]:
    mode = validate_graph_mode(payload.mode)
    project_name = (payload.project or "").strip() or None
    center_memory_id = payload.center_memory_id.strip()

    if mode == "memory_focus":
        if not center_memory_id:
            raise ValueError("center_memory_id_required")
        center_record = (await fetch_memory_records([center_memory_id])).get(center_memory_id)
        if not center_record:
            raise ValueError("memory_not_found")
        project_name = project_name or str(center_record.get("project") or "")

    if mode in {"project_hot", "search"} and not project_name:
        raise ValueError("project_required")
    if mode == "search" and not payload.query.strip():
        raise ValueError("query_required")

    normalized_scope = validate_search_scope(payload.scope)
    allowed_projects = set(await resolve_scope_projects(project_name, normalized_scope)) if project_name and normalized_scope != "global" else set()

    if mode == "project_hot":
        seed_limit = min(payload.node_limit, max(8, min(24, payload.node_limit // 2 or 1)))
        seed_ids = await fetch_project_hot_memory_ids(
            project=project_name or "",
            memory_type=payload.memory_type,
            tags=payload.tags,
            limit=seed_limit,
        )
    elif mode == "search":
        seed_results = await structured_search_memories(
            query=payload.query,
            project=project_name,
            memory_type=payload.memory_type,
            limit=min(payload.node_limit, 18),
            scope=normalized_scope,
            tags=payload.tags,
            score_threshold=0.35,
        )
        seed_ids = [item["id"] for item in seed_results]
    else:
        seed_ids = [center_memory_id]

    unique_seed_ids = list(dict.fromkeys(seed_ids))
    if not unique_seed_ids:
        return {
            "nodes": [],
            "edges": [],
            "summary": {
                "mode": mode,
                "project": project_name,
                "scope": normalized_scope,
                "query": payload.query.strip() or None,
                "center_memory_id": center_memory_id or None,
                "node_count": 0,
                "edge_count": 0,
                "seed_count": 0,
                "requested_node_limit": payload.node_limit,
                "requested_edge_limit": payload.edge_limit,
                "truncated_nodes": False,
                "truncated_edges": False,
                "allowed_projects": sorted(allowed_projects),
            },
        }

    selected_ids: list[str] = unique_seed_ids[: payload.node_limit]
    selected_set = set(selected_ids)
    frontier = list(selected_ids)
    for _ in range(payload.depth):
        if not frontier or len(selected_ids) >= payload.node_limit:
            break
        relation_rows = await fetch_relation_rows_touching(
            frontier,
            allowed_projects or None,
            payload.include_inactive,
            payload.min_weight,
            max(payload.edge_limit * 3, payload.node_limit * 4),
        )
        relation_rows.sort(key=graph_relation_sort_key, reverse=True)
        next_frontier: list[str] = []
        for row in relation_rows:
            for candidate_id in (row["source_memory_id"], row["target_memory_id"]):
                if candidate_id in selected_set:
                    continue
                selected_ids.append(candidate_id)
                selected_set.add(candidate_id)
                next_frontier.append(candidate_id)
                if len(selected_ids) >= payload.node_limit:
                    break
            if len(selected_ids) >= payload.node_limit:
                break
        frontier = next_frontier

    records = await fetch_memory_records(selected_ids)
    ordered_nodes = [records[memory_id] for memory_id in selected_ids if memory_id in records]
    ordered_nodes.sort(key=compute_memory_prominence, reverse=True)
    node_ids = [node["id"] for node in ordered_nodes]
    edge_rows = await fetch_relation_rows_between(
        node_ids,
        allowed_projects or None,
        payload.include_inactive,
        payload.min_weight,
        payload.edge_limit,
    )
    edge_rows.sort(key=graph_relation_sort_key, reverse=True)

    return {
        "nodes": [build_graph_node(record) for record in ordered_nodes],
        "edges": [build_graph_edge(row) for row in edge_rows[: payload.edge_limit]],
        "summary": {
            "mode": mode,
            "project": project_name,
            "scope": normalized_scope,
            "query": payload.query.strip() or None,
            "center_memory_id": center_memory_id or None,
            "node_count": len(ordered_nodes),
            "edge_count": min(len(edge_rows), payload.edge_limit),
            "seed_count": len(unique_seed_ids),
            "requested_node_limit": payload.node_limit,
            "requested_edge_limit": payload.edge_limit,
            "truncated_nodes": len(unique_seed_ids) > payload.node_limit or len(ordered_nodes) >= payload.node_limit,
            "truncated_edges": len(edge_rows) > payload.edge_limit,
            "allowed_projects": sorted(allowed_projects),
        },
    }


async def get_graph_metrics(project: Optional[str] = None) -> dict[str, Any]:
    if not pg_pool:
        raise RuntimeError("postgres_unavailable")
    async with pg_pool.acquire() as conn:
        memory_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*)::int AS memory_count,
                COUNT(*) FILTER (WHERE manual_pin)::int AS pinned_memory_count,
                COUNT(*) FILTER (
                    WHERE manual_pin
                       OR activation_score >= 0.55
                       OR stability_score >= 0.8
                       OR access_count >= 3
                )::int AS hot_memory_count,
                AVG(activation_score) AS avg_activation_score,
                AVG(stability_score) AS avg_stability_score
            FROM memory_log ml
            LEFT JOIN projects p ON p.id = ml.project_id
            WHERE ($1::text IS NULL OR p.name = $1)
            """,
            project,
        )
        relation_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*)::int AS relation_count,
                COUNT(*) FILTER (WHERE mr.active)::int AS active_relation_count
            FROM memory_relations mr
            JOIN memory_log src ON src.id = mr.source_memory_id
            JOIN memory_log dst ON dst.id = mr.target_memory_id
            LEFT JOIN projects src_p ON src_p.id = src.project_id
            LEFT JOIN projects dst_p ON dst_p.id = dst.project_id
            WHERE (
                $1::text IS NULL
                OR src_p.name = $1
                OR dst_p.name = $1
            )
            """,
            project,
        )
        type_rows = await conn.fetch(
            """
            SELECT ml.action_type AS memory_type, COUNT(*)::int AS count
            FROM memory_log ml
            LEFT JOIN projects p ON p.id = ml.project_id
            WHERE ($1::text IS NULL OR p.name = $1)
            GROUP BY ml.action_type
            ORDER BY count DESC, ml.action_type ASC
            LIMIT 6
            """,
            project,
        )
    bridges = await list_project_bridges(project) if project else []
    return {
        "project": project,
        "memory_count": int(memory_row["memory_count"] or 0),
        "relation_count": int(relation_row["relation_count"] or 0),
        "active_relation_count": int(relation_row["active_relation_count"] or 0),
        "pinned_memory_count": int(memory_row["pinned_memory_count"] or 0),
        "hot_memory_count": int(memory_row["hot_memory_count"] or 0),
        "avg_activation_score": round(float(memory_row["avg_activation_score"] or 0.0), 4),
        "avg_stability_score": round(float(memory_row["avg_stability_score"] or 0.0), 4),
        "bridge_count": len([item for item in bridges if item.get("active")]),
        "top_memory_types": [serialize_row(row) or {} for row in type_rows],
        "generated_at": now_iso(),
    }


async def get_graph_facets(project: Optional[str] = None) -> dict[str, Any]:
    if not pg_pool:
        raise RuntimeError("postgres_unavailable")
    async with pg_pool.acquire() as conn:
        project_rows = await conn.fetch(
            """
            SELECT
                p.name AS project,
                COUNT(ml.id)::int AS memory_count,
                COUNT(ml.id) FILTER (WHERE ml.manual_pin)::int AS pinned_memory_count
            FROM projects p
            LEFT JOIN memory_log ml ON ml.project_id = p.id
            WHERE ($1::text IS NULL OR p.name = $1 OR ml.id IS NOT NULL)
            GROUP BY p.name
            HAVING COUNT(ml.id) > 0
            ORDER BY
                CASE WHEN $1::text IS NOT NULL AND p.name = $1 THEN 0 ELSE 1 END,
                COUNT(ml.id) DESC,
                p.name ASC
            LIMIT 100
            """,
            project,
        )
        type_rows = await conn.fetch(
            """
            SELECT ml.action_type AS memory_type, COUNT(*)::int AS count
            FROM memory_log ml
            LEFT JOIN projects p ON p.id = ml.project_id
            WHERE ($1::text IS NULL OR p.name = $1)
            GROUP BY ml.action_type
            ORDER BY count DESC, ml.action_type ASC
            LIMIT 12
            """,
            project,
        )
        tag_rows = await conn.fetch(
            """
            SELECT tag, COUNT(*)::int AS count
            FROM (
                SELECT unnest(COALESCE(ml.tags, '{}'::text[])) AS tag
                FROM memory_log ml
                LEFT JOIN projects p ON p.id = ml.project_id
                WHERE ($1::text IS NULL OR p.name = $1)
            ) tags
            WHERE tag IS NOT NULL AND tag <> ''
            GROUP BY tag
            ORDER BY count DESC, tag ASC
            LIMIT 16
            """,
            project,
        )
        hot_rows = await conn.fetch(
            """
            SELECT
                ml.id,
                p.name AS project,
                ml.action_type AS memory_type,
                ml.summary,
                ml.details,
                ml.manual_pin,
                ml.activation_score,
                ml.stability_score,
                ml.access_count,
                ml.last_accessed_at,
                ml.importance,
                ml.tags
            FROM memory_log ml
            LEFT JOIN projects p ON p.id = ml.project_id
            WHERE ($1::text IS NULL OR p.name = $1)
            ORDER BY
                ml.manual_pin DESC,
                ml.activation_score DESC,
                ml.stability_score DESC,
                ml.last_accessed_at DESC NULLS LAST,
                ml.importance DESC,
                ml.created_at DESC
            LIMIT 12
            """,
            project,
        )

    hot_memories: list[dict[str, Any]] = []
    for row in hot_rows:
        details = row["details"] if isinstance(row["details"], dict) else {}
        record = {
            "id": str(row["id"]),
            "project": row["project"],
            "memory_type": row["memory_type"],
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
        hot_memories.append(
            {
                "memory_id": record["id"],
                "project": record["project"],
                "memory_type": record["memory_type"],
                "content_preview": memory_content_preview(str(record["content"])),
                "tags": record["tags"],
                "manual_pin": record["manual_pin"],
                "prominence": compute_memory_prominence(record),
            }
        )

    return {
        "project": project,
        "projects": [serialize_row(row) or {} for row in project_rows],
        "memory_types": [serialize_row(row) or {} for row in type_rows],
        "top_tags": [serialize_row(row) or {} for row in tag_rows],
        "hot_memories": hot_memories,
        "generated_at": now_iso(),
    }


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

    selected = sorted(activated.values(), key=lambda item: item["hybrid_score"], reverse=True)[:4]
    reinforced_pairs = 0
    expanded_links = 0
    if selected:
        await register_memory_access(selected)
        reinforced_pairs = await reinforce_relation_pairs([item["id"] for item in selected], weight_delta=0.015)

        # [4] Spreading activation desde las memorias activadas
        for mem in selected[:3]:
            asyncio.create_task(propagate_activation(mem["id"]))

        primary = selected[0]
        primary_source = {
            "id": primary["id"],
            "project": primary["project"],
            "memory_type": primary["memory_type"],
            "content": primary["content"],
            "tags": primary.get("tags", []),
        }
        expansion_candidates = await structured_search_memories(
            query=primary["content"],
            project=primary["project"],
            memory_type=None,
            limit=5,
            scope="bridged",
            tags=primary.get("tags", []),
            score_threshold=max(0.5, AUTO_LINK_SCORE_THRESHOLD - 0.04),
            exclude_memory_ids=[item["id"] for item in selected],
        )
        allowed_projects = set(await resolve_scope_projects(primary["project"], "bridged"))
        expanded = await infer_relations_from_candidates(
            primary_source,
            expansion_candidates,
            allowed_projects,
            origin="reflection",
            max_links=2,
        )
        expanded_links = len(expanded)
    decayed = await decay_project_relations(payload.project)
    # [1] Ebbinghaus: decay exponencial de stability_score para memorias no accedidas
    decayed_stability = await decay_memory_stability(payload.project)
    return {
        "activated_memories": len(selected),
        "reinforced_pairs": reinforced_pairs,
        "expanded_links": expanded_links,
        "decayed_relations": decayed,
        "decayed_stability": decayed_stability,
    }

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
    timeout_seconds = max(0.2, PROJECT_CONTEXT_WORKING_MEMORY_TIMEOUT_SECONDS)
    payload: dict[str, Any] = {
        "query": query,
        "user_id": project,
        "limit": max(1, limit),
        "enable_graph": PROJECT_CONTEXT_WORKING_MEMORY_USE_GRAPH,
    }
    if agent_id:
        payload["agent_id"] = agent_id
    try:
        response = await http_client.post(f"{MEM0_URL}/search", json=payload, timeout=timeout_seconds)
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
            "enable_graph": not AI_MEMORY_TEST_MODE,
        }
        response = await http_client.post(
            f"{MEM0_URL}/memories",
            json=body,
            timeout=SESSION_MEM0_TIMEOUT_SECONDS,
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

        if AI_MEMORY_TEST_MODE:
            logger.warning("Mem0 devolvio results vacio para session summary %s en test_mode", payload.session_id)
            return False, "mem0_empty_results"

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
    age = (now_utc() - heartbeat_dt.astimezone(timezone.utc)).total_seconds()
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
    if request.method == "OPTIONS":
        return await call_next(request)
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
            vectors_config={
                "content": VectorParams(
                    size=VECTOR_DIM,
                    distance=Distance.COSINE,
                    on_disk=True,
                ),
                "domain": VectorParams(
                    size=VECTOR_DIM,
                    distance=Distance.COSINE,
                    on_disk=True,
                ),
            },
        )
        logger.info("Coleccion '%s' creada en Qdrant (dual-vector)", COLLECTION_NAME)
    else:
        # Check if old single-vector format needs migration to dual-vector
        try:
            collection_info = await qdrant.get_collection(COLLECTION_NAME)
            vectors_config = collection_info.config.params.vectors
            if not isinstance(vectors_config, dict):
                logger.warning(
                    "Detected single-vector collection '%s'. Recreating with dual-vector config.",
                    COLLECTION_NAME,
                )
                await qdrant.delete_collection(COLLECTION_NAME)
                await qdrant.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config={
                        "content": VectorParams(
                            size=VECTOR_DIM,
                            distance=Distance.COSINE,
                            on_disk=True,
                        ),
                        "domain": VectorParams(
                            size=VECTOR_DIM,
                            distance=Distance.COSINE,
                            on_disk=True,
                        ),
                    },
                )
                logger.info("Collection '%s' recreated with dual-vector config", COLLECTION_NAME)
        except Exception:
            pass
    for field in ["project_id", "agent_id", "memory_type", "tags", "keyphrases"]:
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
        "openai_configured": AI_MEMORY_TEST_MODE or has_real_secret(OPENAI_API_KEY),
        "deepseek_configured": AI_MEMORY_TEST_MODE or has_real_secret(DEEPSEEK_API_KEY),
        "test_mode": AI_MEMORY_TEST_MODE,
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
    - `MERGED ...` si se encontró una memoria casi idéntica y se reforzó la existente.
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

        # Check for near-duplicate to merge into (novelty-based dedup)
        merge_target = None
        try:
            merge_candidates = await qdrant.query_points(
                collection_name=COLLECTION_NAME,
                query=embedding,
                using="content",
                query_filter=Filter(must=[
                    FieldCondition(key="project_id", match=MatchValue(value=project)),
                    FieldCondition(key="memory_type", match=MatchValue(value=memory_type)),
                ]),
                limit=1,
                with_payload=True,
                score_threshold=0.85,
            )
            if merge_candidates.points:
                top = merge_candidates.points[0]
                novelty = round(1.0 - float(top.score), 3)
                if novelty < NOVELTY_MERGE_THRESHOLD:
                    merge_target = top
        except Exception:
            logger.debug("Novelty merge check failed, proceeding with normal store")

        if merge_target is not None:
            existing_id = str(merge_target.id)
            existing_payload = merge_target.payload or {}
            existing_importance = float(existing_payload.get("importance", 0.5))
            merged_importance = round(min(1.0, max(existing_importance, importance) + 0.05), 3)
            await qdrant.set_payload(
                collection_name=COLLECTION_NAME,
                payload={"importance": merged_importance},
                points=[existing_id],
            )
            if pg_pool:
                async with pg_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE memory_log SET importance = $1 WHERE id = $2",
                        merged_importance, uuid.UUID(existing_id),
                    )
            logger.info(
                "Novelty merge: new memory merged into %s (novelty=%.3f, importance %.2f→%.2f)",
                existing_id, 1.0 - float(merge_target.score), existing_importance, merged_importance,
            )
            return f"MERGED into={existing_id} project={project} type={memory_type} novelty={1.0 - float(merge_target.score):.3f}"

        # [L0] Extract keyphrases and compute domain embedding
        keyphrases = extract_keyphrases(content, tags_list)
        domain_text = " ".join(keyphrases) if keyphrases else content
        domain_embedding = await get_embedding(domain_text)
        memory_id = str(uuid.uuid4())
        # [2] Valencia emocional: inferir carga afectiva del contenido
        valence, arousal = infer_valence_arousal(content)
        # [3] Sesgo de novedad: ajustar importance según similitud con memorias existentes
        novelty_score = 0.5
        try:
            novelty_candidates = await structured_search_memories(
                query=content, project=project, limit=1, scope="project", score_threshold=0.25,
            )
            if novelty_candidates:
                max_sim = novelty_candidates[0]["semantic_score"]
                novelty_score = round(1.0 - max_sim, 3)
                if max_sim < 0.50:
                    importance = min(1.0, importance + 0.15 * novelty_score)
                elif max_sim > 0.90 and not skip_similar:
                    importance = max(0.3, importance - 0.1)
            else:
                novelty_score = 0.9
                importance = min(1.0, importance + 0.08)
        except Exception:
            logger.debug("Calculo de novelty_score fallo, usando default")
        payload = {
            "content": content,
            "project_id": project,
            "agent_id": agent_id,
            "memory_type": memory_type,
            "tags": tags_list,
            "keyphrases": keyphrases,
            "importance": importance,
            "created_at": now_iso(),
            "access_count": 0,
            "valence": valence,
            "arousal": arousal,
            "novelty_score": novelty_score,
        }
        await qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(
                id=memory_id,
                vector={"content": embedding, "domain": domain_embedding},
                payload=payload,
            )],
        )
        if pg_pool:
            async with pg_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO memory_log
                    (
                        id, project_id, agent_id, action_type, summary, details, importance, tags,
                        access_count, activation_score, stability_score, manual_pin,
                        valence, arousal, novelty_score, review_count, stability_halflife_days,
                        keyphrases, created_at
                    )
                    VALUES (
                        $1,
                        (SELECT id FROM projects WHERE name = $2 LIMIT 1),
                        $3, $4, $5, $6::jsonb, $7, $8, 0, 0, $9, FALSE,
                        $10, $11, $12, 0, 1.0,
                        $13, $14::timestamptz
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
                    valence,
                    arousal,
                    novelty_score,
                    keyphrases,
                    now_utc(),
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
        return format_search_results(query, results)
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

        semantic_query = f"context architecture overview {project_name}"
        semantic_future = structured_search_memories(
            query=semantic_query,
            project=project_name,
            limit=5,
            scope="project",
            score_threshold=0.35,
        )
        working_memory_future = (
            mem0_search_context(
                query=f"recent work, active context, open loops, errors and decisions for project {project_name}",
                project=project_name,
                agent_id=agent_id,
                limit=PROJECT_CONTEXT_WORKING_MEMORY_LIMIT,
            )
            if agent_id
            else asyncio.sleep(0, result=[])
        )
        related_ideas_future = get_related_ideas(project_name, limit=5) if include_related else asyncio.sleep(0, result=[])
        semantic_result, working_memory_result, related_ideas_result = await asyncio.gather(
            semantic_future,
            working_memory_future,
            related_ideas_future,
            return_exceptions=True,
        )

        semantic_results: list[dict[str, Any]] = []
        if isinstance(semantic_result, Exception):
            logger.warning("Busqueda semantica fallo en get_project_context para %s: %s", project_name, semantic_result)
        else:
            semantic_results = semantic_result
            if semantic_results:
                await register_memory_access(semantic_results)

        if isinstance(working_memory_result, Exception):
            logger.warning("Working memory fallo en get_project_context para %s: %s", project_name, working_memory_result)
            working_memory_result = []
        if working_memory_result:
            output.append("WORKING MEMORY")
            output.extend(working_memory_result)

        output.append("MEMORY SEARCH")
        output.append(format_search_results(semantic_query, semantic_results))
        if include_related:
            if isinstance(related_ideas_result, Exception):
                logger.warning("Related ideas fallo en get_project_context para %s: %s", project_name, related_ideas_result)
                related_ideas_result = []
            if related_ideas_result:
                output.append("RELATED IDEAS")
                output.extend(related_ideas_result)
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
    return {"status": "ok", "timestamp": now_iso(), "test_mode": AI_MEMORY_TEST_MODE}


@app.get("/brain/health")
async def brain_health_endpoint():
    """[L5] Full biological health metrics for the brain."""
    if not pg_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    from brain_health import compute_brain_health
    async with pg_pool.acquire() as conn:
        return await compute_brain_health(conn)


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
    if result.startswith("MERGED"):
        return {
            "result": result,
            "action": "merged",
            "merged_into": fields.get("into", ""),
            "memory_id": fields.get("into", ""),
        }
    return {"result": result, "memory_id": fields.get("memory_id")}


@app.get("/api/memories/{memory_id}")
async def api_memory_detail(memory_id: str):
    try:
        payload = await get_memory_detail_payload(memory_id)
    except Exception as exc:
        logger.exception("api_memory_detail fallo")
        raise HTTPException(status_code=400, detail=str(exc))
    if payload is None:
        raise HTTPException(status_code=404, detail="memory_not_found")
    return payload


@app.post("/api/search")
async def api_search_memory(payload: SearchMemoryRequest):
    result = await search_memory(**payload.model_dump())
    if result.startswith("ERROR"):
        raise HTTPException(status_code=500, detail=result)
    return {"result": result}


@app.post("/api/search/structured")
async def api_search_memory_structured(payload: StructuredSearchRequest):
    try:
        results = await structured_search_memories(
            query=payload.query,
            project=payload.project,
            memory_type=payload.memory_type,
            limit=payload.limit,
            scope=payload.scope,
            tags=payload.tags,
            score_threshold=0.35,
        )
        if payload.register_access:
            await register_memory_access(results)
        # Uncertainty-aware confidence scoring
        if results:
            scores = [item["hybrid_score"] for item in results]
            max_score = max(scores)
            mean_score = sum(scores) / len(scores)
            confidence = round(max_score / max(mean_score, 0.001), 4)
        else:
            confidence = 0.0
        low_confidence = confidence < CONFIDENCE_THRESHOLD
        return {
            "query": payload.query,
            "scope": payload.scope,
            "project": payload.project,
            "count": len(results),
            "confidence": confidence,
            "low_confidence": low_confidence,
            "results": [
                {
                    "memory_id": item["id"],
                    "project": item["project"],
                    "memory_type": item["memory_type"],
                    "semantic_score": item["semantic_score"],
                    "hybrid_score": item["hybrid_score"],
                    "relation_weight": item["relation_weight"],
                    "recency_frequency": item["recency_frequency"],
                    "tag_overlap": item["tag_overlap"],
                    "tags": item["tags"],
                    "content": item["content"],
                    "manual_pin": item["manual_pin"],
                    "importance": item.get("importance", 0.5),
                    "valence": item.get("valence", 0.0),
                    "arousal": item.get("arousal", 0.5),
                    "created_at": item.get("created_at"),
                }
                for item in results
            ],
        }
    except Exception as exc:
        logger.exception("api_search_memory_structured fallo")
        raise HTTPException(status_code=500, detail=str(exc))


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


@app.get("/api/relations")
async def api_list_relations(memory_id: str):
    try:
        return {"memory_id": memory_id, "relations": await get_relations_for_memory(memory_id)}
    except Exception as exc:
        logger.exception("api_list_relations fallo")
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/graph/metrics")
async def api_graph_metrics(project: Optional[str] = None):
    try:
        return await get_graph_metrics(project=project)
    except Exception as exc:
        logger.exception("api_graph_metrics fallo")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/graph/facets")
async def api_graph_facets(project: Optional[str] = None):
    try:
        return await get_graph_facets(project=project)
    except Exception as exc:
        logger.exception("api_graph_facets fallo")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/graph/subgraph")
async def api_graph_subgraph(payload: GraphSubgraphRequest):
    try:
        return await build_graph_subgraph(payload)
    except ValueError as exc:
        logger.warning("api_graph_subgraph validacion fallo: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("api_graph_subgraph fallo")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/project-bridges")
async def api_bridge_projects(payload: BridgeProjectsRequest):
    try:
        bridge = await bridge_projects_internal(**payload.model_dump())
        return {"result": "OK", "bridge": bridge}
    except Exception as exc:
        logger.exception("api_bridge_projects fallo")
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/project-bridges")
async def api_list_project_bridges(project: str):
    try:
        return {"project": project, "bridges": await list_project_bridges(project)}
    except Exception as exc:
        logger.exception("api_list_project_bridges fallo")
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


@app.post("/api/test/clock")
async def api_test_clock(payload: TestClockRequest):
    if not AI_MEMORY_TEST_MODE:
        raise HTTPException(status_code=404, detail="test_mode_disabled")
    try:
        set_test_now_override(payload.now)
        return {"result": "OK", "now": now_iso(), "test_mode": True}
    except Exception as exc:
        logger.exception("api_test_clock fallo")
        raise HTTPException(status_code=400, detail=str(exc))


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
    if AI_MEMORY_TEST_MODE and AI_MEMORY_TEST_NOW:
        set_test_now_override(AI_MEMORY_TEST_NOW)
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    deepseek_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY or "change-me", base_url=DEEPSEEK_BASE_URL)
    http_client = httpx.AsyncClient(timeout=10.0)

    async def init_postgres():
        return await asyncpg.create_pool(
            POSTGRES_URL,
            min_size=PG_POOL_MIN_SIZE,
            max_size=PG_POOL_MAX_SIZE,
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
