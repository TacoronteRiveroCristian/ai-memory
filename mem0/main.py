import logging
import os
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from mem0 import Memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ai-memory-mem0")

load_dotenv()

def env_text(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


POSTGRES_HOST = env_text("POSTGRES_HOST", "postgres")
POSTGRES_PORT = env_text("POSTGRES_PORT", "5432")
POSTGRES_DB = env_text("POSTGRES_DB", "postgres")
POSTGRES_USER = env_text("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = env_text("POSTGRES_PASSWORD", "postgres")
POSTGRES_COLLECTION_NAME = env_text("POSTGRES_COLLECTION_NAME", "memories")
OPENAI_API_KEY = env_text("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = env_text("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DEEPSEEK_API_KEY = env_text("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = env_text("DEEPSEEK_MODEL", "deepseek-reasoner")
DEEPSEEK_BASE_URL = env_text("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
HISTORY_DB_PATH = env_text("HISTORY_DB_PATH", "/app/history/history.db")
MEM0_GRAPH_ENABLED = os.environ.get("MEM0_GRAPH_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
MEM0_GRAPH_DB_PATH = env_text("MEM0_GRAPH_DB_PATH", "/app/history/graph.kuzu")

os.makedirs(os.path.dirname(HISTORY_DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(MEM0_GRAPH_DB_PATH), exist_ok=True)

def build_default_config() -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "version": "v1.1",
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": POSTGRES_HOST,
                "port": int(POSTGRES_PORT),
                "dbname": POSTGRES_DB,
                "user": POSTGRES_USER,
                "password": POSTGRES_PASSWORD,
                "collection_name": POSTGRES_COLLECTION_NAME,
            },
        },
        "llm": {
            "provider": "deepseek",
            "config": {
                "api_key": DEEPSEEK_API_KEY,
                "model": DEEPSEEK_MODEL,
                "temperature": 0.2,
                "deepseek_base_url": DEEPSEEK_BASE_URL,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "api_key": OPENAI_API_KEY,
                "model": OPENAI_EMBEDDING_MODEL,
            },
        },
        "history_db_path": HISTORY_DB_PATH,
    }
    if MEM0_GRAPH_ENABLED:
        config["graph_store"] = {
            "provider": "kuzu",
            "config": {
                "db": MEM0_GRAPH_DB_PATH,
            },
        }
    return config


DEFAULT_CONFIG = build_default_config()

MEMORY_INSTANCE: Optional[Memory] = None
MEMORY_INIT_ERROR: Optional[str] = None
MEMORY_GRAPH_ACTIVE = False
MEMORY_GRAPH_ERROR: Optional[str] = None


def strip_graph_config(config: Dict[str, Any]) -> Dict[str, Any]:
    fallback = dict(config)
    fallback.pop("graph_store", None)
    return fallback


def should_retry_without_graph(exc: Exception) -> bool:
    text = str(exc).lower()
    graph_markers = ("graph", "neo4j", "memgraph", "kuzu", "apache age", "relation")
    return any(marker in text for marker in graph_markers)


def init_memory_instance(config: Dict[str, Any]):
    global MEMORY_INSTANCE, MEMORY_INIT_ERROR, MEMORY_GRAPH_ACTIVE, MEMORY_GRAPH_ERROR
    try:
        MEMORY_INSTANCE = Memory.from_config(config)
        MEMORY_INIT_ERROR = None
        MEMORY_GRAPH_ACTIVE = "graph_store" in config
        MEMORY_GRAPH_ERROR = None
        logger.info(
            "Mem0 configurado con llm=%s:%s embedder=%s:%s graph=%s",
            config["llm"]["provider"],
            config["llm"]["config"]["model"],
            config["embedder"]["provider"],
            config["embedder"]["config"]["model"],
            "enabled" if MEMORY_GRAPH_ACTIVE else "disabled",
        )
    except Exception as exc:
        if "graph_store" in config:
            MEMORY_GRAPH_ERROR = str(exc)
            logger.warning("No fue posible inicializar Mem0 con graph store, reintentando en modo vector-only: %s", exc)
            try:
                fallback_config = strip_graph_config(config)
                MEMORY_INSTANCE = Memory.from_config(fallback_config)
                MEMORY_INIT_ERROR = None
                MEMORY_GRAPH_ACTIVE = False
                logger.info("Mem0 recuperado en modo vector-only tras fallo del graph store")
                return
            except Exception as fallback_exc:
                exc = fallback_exc
        MEMORY_INSTANCE = None
        MEMORY_INIT_ERROR = str(exc)
        MEMORY_GRAPH_ACTIVE = False
        logger.exception("No fue posible inicializar Mem0")


def require_memory() -> Memory:
    if MEMORY_INSTANCE is None:
        raise HTTPException(status_code=503, detail=MEMORY_INIT_ERROR or "Memory instance not initialized.")
    return MEMORY_INSTANCE


init_memory_instance(DEFAULT_CONFIG)

app = FastAPI(title="Mem0 REST APIs", version="1.1.0")


class Message(BaseModel):
    role: str = Field(..., description="Role of the message.")
    content: str = Field(..., description="Message content.")


class MemoryCreate(BaseModel):
    messages: List[Message]
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    enable_graph: Optional[bool] = None


class SearchRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    limit: int = Field(default=5, ge=1, le=10)
    enable_graph: Optional[bool] = None


def execute_memory_call(
    action_name: str,
    callback: Callable[[Memory, Dict[str, Any]], Any],
    params: Dict[str, Any],
    enable_graph: Optional[bool],
):
    memory = require_memory()
    kwargs = dict(params)
    if enable_graph is not None and MEMORY_GRAPH_ACTIVE:
        kwargs["enable_graph"] = enable_graph
    try:
        return callback(memory, kwargs)
    except TypeError as exc:
        if "enable_graph" in kwargs:
            logger.warning("%s no acepta enable_graph; reintentando sin grafo: %s", action_name, exc)
            kwargs.pop("enable_graph", None)
            return callback(memory, kwargs)
        raise
    except Exception as exc:
        if "enable_graph" in kwargs and should_retry_without_graph(exc):
            logger.warning("%s fallo con grafo; reintentando sin grafo: %s", action_name, exc)
            kwargs.pop("enable_graph", None)
            return callback(memory, kwargs)
        raise


@app.get("/health")
def health():
    payload = {
        "status": "ok" if MEMORY_INSTANCE is not None else "degraded",
        "llm_provider": DEFAULT_CONFIG["llm"]["provider"],
        "llm_model": DEFAULT_CONFIG["llm"]["config"]["model"],
        "embedder_provider": DEFAULT_CONFIG["embedder"]["provider"],
        "embedder_model": DEFAULT_CONFIG["embedder"]["config"]["model"],
        "history_db_path": HISTORY_DB_PATH,
        "graph_requested": MEM0_GRAPH_ENABLED,
        "graph_active": MEMORY_GRAPH_ACTIVE,
        "graph_provider": "kuzu" if MEM0_GRAPH_ENABLED else None,
        "graph_db_path": MEM0_GRAPH_DB_PATH if MEM0_GRAPH_ENABLED else None,
        "graph_error": MEMORY_GRAPH_ERROR,
        "error": MEMORY_INIT_ERROR,
    }
    status_code = 200 if MEMORY_INSTANCE is not None else 503
    return JSONResponse(status_code=status_code, content=payload)


@app.post("/configure")
def set_config(config: Dict[str, Any]):
    init_memory_instance(config)
    if MEMORY_INSTANCE is None:
        raise HTTPException(status_code=400, detail=MEMORY_INIT_ERROR or "Configuration failed.")
    return {"message": "Configuration set successfully"}


@app.post("/memories")
def add_memory(memory_create: MemoryCreate):
    if not any([memory_create.user_id, memory_create.agent_id, memory_create.run_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    params = {
        k: v
        for k, v in memory_create.model_dump().items()
        if v is not None and k not in {"messages", "enable_graph"}
    }
    try:
        response = execute_memory_call(
            "add_memory",
            lambda memory, kwargs: memory.add(messages=[message.model_dump() for message in memory_create.messages], **kwargs),
            params,
            memory_create.enable_graph,
        )
        return JSONResponse(content=response)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in add_memory")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/memories")
def get_all_memories(
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    enable_graph: Optional[bool] = None,
):
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    params = {k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None}
    try:
        return execute_memory_call("get_all_memories", lambda memory, kwargs: memory.get_all(**kwargs), params, enable_graph)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in get_all_memories")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/memories/{memory_id}")
def get_memory(memory_id: str):
    try:
        memory = require_memory()
        return memory.get(memory_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in get_memory")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/search")
def search_memories(search_req: SearchRequest):
    try:
        params = {
            k: v
            for k, v in search_req.model_dump().items()
            if v is not None and k not in {"query", "limit", "enable_graph"}
        }
        return execute_memory_call(
            "search_memories",
            lambda memory, kwargs: memory.search(query=search_req.query, limit=search_req.limit, **kwargs),
            params,
            search_req.enable_graph,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in search_memories")
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/memories/{memory_id}")
def delete_memory(memory_id: str):
    try:
        memory = require_memory()
        memory.delete(memory_id)
        return {"message": "Memory deleted successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in delete_memory")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/docs")
