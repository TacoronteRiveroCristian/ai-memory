import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from mem0 import Memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ai-memory-mem0")

load_dotenv()

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "postgres")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
POSTGRES_COLLECTION_NAME = os.environ.get("POSTGRES_COLLECTION_NAME", "memories")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-reasoner")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
HISTORY_DB_PATH = os.environ.get("HISTORY_DB_PATH", "/app/history/history.db")

os.makedirs(os.path.dirname(HISTORY_DB_PATH), exist_ok=True)

DEFAULT_CONFIG = {
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

MEMORY_INSTANCE: Optional[Memory] = None
MEMORY_INIT_ERROR: Optional[str] = None


def init_memory_instance(config: Dict[str, Any]):
    global MEMORY_INSTANCE, MEMORY_INIT_ERROR
    try:
        MEMORY_INSTANCE = Memory.from_config(config)
        MEMORY_INIT_ERROR = None
        logger.info(
            "Mem0 configurado con llm=%s:%s embedder=%s:%s",
            config["llm"]["provider"],
            config["llm"]["config"]["model"],
            config["embedder"]["provider"],
            config["embedder"]["config"]["model"],
        )
    except Exception as exc:
        MEMORY_INSTANCE = None
        MEMORY_INIT_ERROR = str(exc)
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


class SearchRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    limit: int = Field(default=5, ge=1, le=10)


@app.get("/health")
def health():
    payload = {
        "status": "ok" if MEMORY_INSTANCE is not None else "degraded",
        "llm_provider": DEFAULT_CONFIG["llm"]["provider"],
        "llm_model": DEFAULT_CONFIG["llm"]["config"]["model"],
        "embedder_provider": DEFAULT_CONFIG["embedder"]["provider"],
        "embedder_model": DEFAULT_CONFIG["embedder"]["config"]["model"],
        "history_db_path": HISTORY_DB_PATH,
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
    params = {k: v for k, v in memory_create.model_dump().items() if v is not None and k != "messages"}
    try:
        memory = require_memory()
        response = memory.add(messages=[message.model_dump() for message in memory_create.messages], **params)
        return JSONResponse(content=response)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in add_memory")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/memories")
def get_all_memories(user_id: Optional[str] = None, run_id: Optional[str] = None, agent_id: Optional[str] = None):
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    params = {k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None}
    try:
        memory = require_memory()
        return memory.get_all(**params)
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
        params = {k: v for k, v in search_req.model_dump().items() if v is not None and k not in {"query", "limit"}}
        memory = require_memory()
        return memory.search(query=search_req.query, limit=search_req.limit, **params)
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
