"""HTTP client for heartbeat monitor — talks to the AI Memory Brain API."""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger("heartbeat-monitor")


class HeartbeatClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    def close(self):
        self._client.close()

    def get(self, path: str, **kwargs) -> dict[str, Any]:
        response = self._client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    def delete(self, path: str) -> dict[str, Any]:
        response = self._client.delete(path)
        response.raise_for_status()
        return response.json()

    def create_memory(self, **kwargs) -> dict[str, Any]:
        return self.post("/api/memories", kwargs)

    def memory_detail(self, memory_id: str) -> dict[str, Any]:
        return self.get(f"/api/memories/{memory_id}")

    def relations(self, memory_id: str) -> dict[str, Any]:
        return self.get("/api/relations", params={"memory_id": memory_id})

    def bridge_projects(self, **kwargs) -> dict[str, Any]:
        return self.post("/api/project-bridges", kwargs)

    def record_session(self, **kwargs) -> dict[str, Any]:
        return self.post("/api/sessions", kwargs)

    def apply_session_plasticity(self, **kwargs) -> dict[str, Any]:
        return self.post("/api/plasticity/session", kwargs)

    def brain_health(self) -> dict[str, Any]:
        return self.get("/brain/health")

    def delete_project(self, name: str) -> Optional[dict[str, Any]]:
        try:
            return self.delete(f"/api/projects/{name}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    def structured_search(self, **kwargs) -> dict[str, Any]:
        return self.post("/api/search/structured", kwargs)

    def set_test_clock(self, when: Optional[str]) -> dict[str, Any]:
        return self.post("/api/test/clock", {"now": when})

    def trigger_deep_sleep(self) -> dict[str, Any]:
        return self.post("/api/test/trigger-deep-sleep", {})

    def deep_sleep_status(self, run_id: str) -> dict[str, Any]:
        return self.get(f"/api/test/deep-sleep-status/{run_id}")

    def report_cycle(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/api/heartbeat/report", payload)

    def heartbeat_status(self) -> dict[str, Any]:
        return self.get("/api/heartbeat/status")
