import os
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import pytest
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class BrainClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    def close(self):
        self._client.close()

    def get(self, path: str, **kwargs):
        response = self._client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any]):
        response = self._client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    def health(self):
        return self.get("/health")

    def create_memory(self, **payload):
        return self.post("/api/memories", payload)

    def structured_search(self, **payload):
        return self.post("/api/search/structured", payload)

    def link_memories(self, **payload):
        return self.post("/api/relations", payload)

    def relations(self, memory_id: str):
        return self.get("/api/relations", params={"memory_id": memory_id})

    def bridge_projects(self, **payload):
        return self.post("/api/project-bridges", payload)

    def list_bridges(self, project: str):
        return self.get("/api/project-bridges", params={"project": project})

    def project_context(self, project_name: str, include_related: bool = True):
        return self.get(
            "/api/project-context",
            params={"project_name": project_name, "include_related": str(include_related).lower()},
        )

    def apply_session_plasticity(self, **payload):
        return self.post("/api/plasticity/session", payload)

    def set_test_clock(self, when: Optional[str]):
        return self.post("/api/test/clock", {"now": when})


@pytest.fixture(scope="session")
def brain_client():
    base_url = os.getenv("AI_MEMORY_BASE_URL", "http://127.0.0.1:8050")
    api_key = os.getenv("MEMORY_API_KEY", "")
    if not api_key:
        pytest.skip("MEMORY_API_KEY no configurada; no se puede ejecutar la suite de integración.")
    client = BrainClient(base_url, api_key)
    try:
        client.health()
    except Exception as exc:  # pragma: no cover - infraestructura
        pytest.skip(f"No se pudo contactar con el API server en {base_url}: {exc}")
    yield client
    client.close()


@pytest.fixture(autouse=True)
def require_test_mode(brain_client: BrainClient):
    health = brain_client.health()
    if not health.get("test_mode"):
        pytest.skip("La suite determinista requiere AI_MEMORY_TEST_MODE=true en el API server.")
    yield
    brain_client.set_test_clock(None)


@pytest.fixture
def unique_project_name():
    def factory(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    return factory
