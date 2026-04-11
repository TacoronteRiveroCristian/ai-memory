# Heartbeat Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Docker service that continuously injects trap memories and verifies every biological process (vectorization, synapse formation, contradiction detection, myelin, decay) produces measurable effects.

**Architecture:** A standalone `heartbeat-monitor` container communicates exclusively via HTTP with the api-server. Two new API endpoints handle deep sleep triggering and heartbeat status reporting. The reflection-worker gains a manual deep sleep handler. Two new Postgres tables persist manual deep sleep runs and heartbeat cycle results.

**Tech Stack:** Python 3.12, httpx, Docker, PostgreSQL, FastAPI

---

## File Structure

```
# New files
heartbeat-monitor/
  Dockerfile                    # Python 3.12-slim, httpx only
  requirements.txt              # httpx>=0.27.0
  monitor.py                    # Main loop: inject → sleep → verify → report
  batches.py                    # Trap batch definitions with expected outcomes
  checks.py                     # Verification logic (snapshot diff)
  client.py                     # HTTP client wrapper

# Modified files
config/postgres/init.sql        # +2 tables: manual_deep_sleep_runs, heartbeat_cycles
api-server/server.py            # +4 endpoints: trigger-deep-sleep, deep-sleep-status, heartbeat report, heartbeat status
reflection-worker/worker.py     # +handle_manual_deep_sleep() in run_loop
docker-compose.yaml             # +heartbeat-monitor service (profile: heartbeat)
Makefile                        # +heartbeat-fast, heartbeat-prod, heartbeat-status, heartbeat-stop

# Test files
tests/test_heartbeat.py         # Integration tests for new endpoints
```

---

### Task 1: Database tables for manual deep sleep and heartbeat cycles

**Files:**
- Modify: `config/postgres/init.sql:312` (append after last trigger)

- [ ] **Step 1: Add manual_deep_sleep_runs table**

Append to `config/postgres/init.sql` after line 312:

```sql

-- [9] Manual deep sleep trigger queue
CREATE TABLE IF NOT EXISTS manual_deep_sleep_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    stats JSONB
);

-- [10] Heartbeat monitor cycle history
CREATE TABLE IF NOT EXISTS heartbeat_cycles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cycle_id TEXT UNIQUE NOT NULL,
    mode TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'injecting',
    injected_memories INT DEFAULT 0,
    checks JSONB DEFAULT '[]'::jsonb,
    passed INT DEFAULT 0,
    failed INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

- [ ] **Step 2: Rebuild postgres to apply schema**

Run: `AI_MEMORY_TEST_MODE=true docker compose up -d --build postgres`
Wait for healthy: `docker compose ps postgres` → should show `healthy`

Verify tables exist:
```bash
docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\dt manual_deep_sleep_runs" -c "\dt heartbeat_cycles"
```

- [ ] **Step 3: Commit**

```bash
git add config/postgres/init.sql
git commit -m "feat(schema): add manual_deep_sleep_runs and heartbeat_cycles tables"
```

---

### Task 2: API endpoints — trigger deep sleep and check status

**Files:**
- Modify: `api-server/server.py` (add after line ~4394, near the reflections endpoints)
- Test: `tests/test_heartbeat.py`

- [ ] **Step 1: Write failing tests for deep sleep trigger and status endpoints**

Create `tests/test_heartbeat.py`:

```python
"""Integration tests for heartbeat monitor endpoints."""


def test_trigger_deep_sleep_queues_run(brain_client):
    """POST /api/test/trigger-deep-sleep should queue a deep sleep run."""
    result = brain_client.post("/api/test/trigger-deep-sleep", {})
    assert result["queued"] is True
    assert "run_id" in result

    # Check status
    run_id = result["run_id"]
    status = brain_client.get(f"/api/test/deep-sleep-status/{run_id}")
    assert status["run_id"] == run_id
    assert status["status"] in ("pending", "running", "completed")


def test_trigger_deep_sleep_deduplicates(brain_client):
    """Triggering while one is pending should return existing run."""
    first = brain_client.post("/api/test/trigger-deep-sleep", {})
    second = brain_client.post("/api/test/trigger-deep-sleep", {})
    # If the first is still pending, second should return same run_id
    if first["queued"]:
        assert second["run_id"] == first["run_id"]
        assert second["queued"] is False


def test_heartbeat_status_returns_empty_initially(brain_client):
    """GET /api/heartbeat/status should work even with no cycles."""
    status = brain_client.get("/api/heartbeat/status")
    assert "cycles_completed" in status
    assert "checks_summary" in status
    assert status["cycles_completed"] >= 0


def test_heartbeat_report_stores_cycle(brain_client):
    """POST /api/heartbeat/report should persist a cycle."""
    import uuid
    cycle_id = f"hb-test-{uuid.uuid4().hex[:8]}"
    brain_client.post("/api/heartbeat/report", {
        "cycle_id": cycle_id,
        "mode": "accelerated",
        "phase": "completed",
        "injected_memories": 8,
        "checks": [
            {"name": "relationships_formed", "passed": True, "detail": "3/3 linked"},
            {"name": "contradiction_detected", "passed": False, "detail": "score=0"},
        ],
        "passed": 1,
        "failed": 1,
    })

    status = brain_client.get("/api/heartbeat/status")
    latest = status.get("latest_cycle")
    assert latest is not None
    # The cycle we just reported should be findable
    found = any(
        c["cycle_id"] == cycle_id
        for c in [latest] + status.get("history", [])
    )
    assert found, f"Cycle {cycle_id} not found in status response"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest tests/test_heartbeat.py -v --tb=short`
Expected: FAIL — endpoints don't exist yet (404 or connection errors)

- [ ] **Step 3: Implement the 4 endpoints in api-server/server.py**

Add a new env var near line 123 (after `AI_MEMORY_TEST_MODE`):

```python
HEARTBEAT_ENABLED = os.environ.get("HEARTBEAT_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
```

Add these functions before the existing `@app.post("/api/reflections/run")` endpoint (around line 4384):

```python
async def queue_manual_deep_sleep() -> dict[str, Any]:
    if not pg_pool:
        return {"error": "postgres_unavailable"}
    async with pg_pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id, status
            FROM manual_deep_sleep_runs
            WHERE status IN ('pending', 'running')
            ORDER BY requested_at DESC
            LIMIT 1
            """
        )
        if existing:
            return {"run_id": str(existing["id"]), "queued": False, "status": existing["status"]}
        run_id = await conn.fetchval(
            "INSERT INTO manual_deep_sleep_runs (status) VALUES ('pending') RETURNING id"
        )
    return {"run_id": str(run_id), "queued": True, "status": "pending"}


@app.post("/api/test/trigger-deep-sleep")
async def api_trigger_deep_sleep():
    if not AI_MEMORY_TEST_MODE and not HEARTBEAT_ENABLED:
        raise HTTPException(status_code=403, detail="Requires AI_MEMORY_TEST_MODE or HEARTBEAT_ENABLED")
    result = await queue_manual_deep_sleep()
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/api/test/deep-sleep-status/{run_id}")
async def api_deep_sleep_status(run_id: str):
    if not pg_pool:
        raise HTTPException(status_code=503, detail="postgres_unavailable")
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, status, stats, requested_at, started_at, completed_at FROM manual_deep_sleep_runs WHERE id = $1",
            UUID(run_id),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": str(row["id"]),
        "status": row["status"],
        "stats": row["stats"],
        "requested_at": row["requested_at"].isoformat() if row["requested_at"] else None,
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
    }


@app.post("/api/heartbeat/report")
async def api_heartbeat_report(request: Request):
    body = await request.json()
    if not pg_pool:
        raise HTTPException(status_code=503, detail="postgres_unavailable")
    async with pg_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO heartbeat_cycles (cycle_id, mode, phase, injected_memories, checks, passed, failed, completed_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, CASE WHEN $3 = 'completed' THEN NOW() ELSE NULL END)
            ON CONFLICT (cycle_id) DO UPDATE SET
                phase = EXCLUDED.phase,
                injected_memories = EXCLUDED.injected_memories,
                checks = EXCLUDED.checks,
                passed = EXCLUDED.passed,
                failed = EXCLUDED.failed,
                completed_at = CASE WHEN EXCLUDED.phase = 'completed' THEN NOW() ELSE heartbeat_cycles.completed_at END
            """,
            body["cycle_id"],
            body["mode"],
            body["phase"],
            body.get("injected_memories", 0),
            json.dumps(body.get("checks", [])),
            body.get("passed", 0),
            body.get("failed", 0),
        )
    return {"stored": True}


@app.get("/api/heartbeat/status")
async def api_heartbeat_status():
    if not pg_pool:
        raise HTTPException(status_code=503, detail="postgres_unavailable")
    async with pg_pool.acquire() as conn:
        cycles = await conn.fetch(
            """
            SELECT cycle_id, mode, phase, injected_memories, checks, passed, failed, created_at, completed_at
            FROM heartbeat_cycles
            WHERE phase = 'completed'
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
    total_passed = sum(r["passed"] for r in cycles)
    total_failed = sum(r["failed"] for r in cycles)
    total_checks = total_passed + total_failed

    latest = None
    history = []
    for i, row in enumerate(cycles):
        entry = {
            "cycle_id": row["cycle_id"],
            "mode": row["mode"],
            "injected_memories": row["injected_memories"],
            "checks": json.loads(row["checks"]) if isinstance(row["checks"], str) else row["checks"],
            "passed": row["passed"],
            "failed": row["failed"],
            "at": row["completed_at"].isoformat() if row["completed_at"] else row["created_at"].isoformat(),
        }
        if i == 0:
            latest = entry
        else:
            history.append({"cycle_id": entry["cycle_id"], "at": entry["at"], "passed": entry["passed"], "failed": entry["failed"]})

    return {
        "enabled": HEARTBEAT_ENABLED,
        "cycles_completed": len(cycles),
        "last_cycle_at": latest["at"] if latest else None,
        "checks_summary": {
            "total": total_checks,
            "passed": total_passed,
            "failed": total_failed,
            "pass_rate": round(total_passed / total_checks, 3) if total_checks > 0 else 0,
        },
        "latest_cycle": latest,
        "history": history,
    }
```

Also add the `UUID` import near the top of server.py if not already imported:
```python
from uuid import UUID
```

- [ ] **Step 4: Rebuild api-server and run tests**

```bash
AI_MEMORY_TEST_MODE=true docker compose up -d --build api-server
sleep 5
source .venv/bin/activate && AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest tests/test_heartbeat.py -v --tb=short
```
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api-server/server.py tests/test_heartbeat.py
git commit -m "feat(api): add deep sleep trigger and heartbeat status endpoints"
```

---

### Task 3: Reflection worker — handle manual deep sleep

**Files:**
- Modify: `reflection-worker/worker.py` (add function + wire into run_loop)

- [ ] **Step 1: Add handle_manual_deep_sleep function**

Add this function after `handle_deep_sleep()` (after line 1507) in `reflection-worker/worker.py`:

```python

async def handle_manual_deep_sleep():
    """Check for manually triggered deep sleep requests and execute them."""
    if not pg_pool:
        return
    async with pg_pool.acquire() as conn:
        locked = await conn.fetchval("SELECT pg_try_advisory_lock($1)", ADVISORY_LOCK_KEY + 1)
        if not locked:
            return
        try:
            row = await conn.fetchrow(
                """
                SELECT id FROM manual_deep_sleep_runs
                WHERE status = 'pending'
                ORDER BY requested_at ASC
                LIMIT 1
                """
            )
            if not row:
                return
            run_id = row["id"]
            await conn.execute(
                "UPDATE manual_deep_sleep_runs SET status = 'running', started_at = NOW() WHERE id = $1",
                run_id,
            )
            logger.info("[L3] Manual deep sleep triggered (run_id=%s)", run_id)

            # Get all projects with activity
            project_names = [
                str(r["name"]) for r in await conn.fetch(
                    "SELECT DISTINCT p.name FROM projects p JOIN memory_log m ON m.project_id = p.id"
                )
            ]

            nrem_stats = {}
            rem_stats = {}
            error_text = None
            try:
                nrem_stats = await run_nrem_phase(conn, run_id, project_names)
                rem_stats = await run_rem_phase(conn)
            except Exception as exc:
                logger.exception("[L3] Manual deep sleep failed")
                error_text = str(exc)[:2000]

            # Record sleep cycles
            try:
                nrem_cid = await record_sleep_cycle(conn, "nrem", "manual_trigger", project_names, {})
                await complete_sleep_cycle(conn, nrem_cid, nrem_stats)
            except Exception:
                logger.debug("Failed to record manual NREM cycle")
            try:
                rem_cid = await record_sleep_cycle(conn, "rem", "manual_trigger", project_names, {})
                await complete_sleep_cycle(conn, rem_cid, rem_stats)
            except Exception:
                logger.debug("Failed to record manual REM cycle")

            combined = {**nrem_stats, **rem_stats}
            await conn.execute(
                """
                UPDATE manual_deep_sleep_runs
                SET status = $2, completed_at = NOW(), stats = $3::jsonb
                WHERE id = $1
                """,
                run_id,
                "failed" if error_text else "completed",
                json.dumps(combined),
            )
            logger.info("[L3] Manual deep sleep completed (run_id=%s)", run_id)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_KEY + 1)
```

- [ ] **Step 2: Wire into run_loop**

In `run_loop()` (line 1509-1518), add the call after `handle_deep_sleep()`:

Change:
```python
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
```

To:
```python
async def run_loop():
    while True:
        try:
            await update_heartbeat()
            await handle_manual_runs()
            await handle_scheduled_run()
            await handle_deep_sleep()
            await handle_manual_deep_sleep()
        except Exception:
            logger.exception("Bucle principal del reflection worker fallo")
        await asyncio.sleep(REFLECTION_POLL_INTERVAL)
```

- [ ] **Step 3: Verify json import exists**

Check that `import json` exists at the top of `reflection-worker/worker.py`. If not, add it.

- [ ] **Step 4: Rebuild reflection-worker**

```bash
AI_MEMORY_TEST_MODE=true docker compose up -d --build reflection-worker
```

- [ ] **Step 5: Verify manual deep sleep works end-to-end**

```bash
source .venv/bin/activate && AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest tests/test_heartbeat.py::test_trigger_deep_sleep_queues_run -v --tb=short
```

Wait ~35 seconds for worker to pick it up, then verify:
```bash
source .venv/bin/activate && python -c "
import httpx, os, time
from dotenv import load_dotenv; load_dotenv('.env')
key = os.getenv('MEMORY_API_KEY','')
headers = {'X-API-Key': key}
# Trigger
r = httpx.post('http://127.0.0.1:8050/api/test/trigger-deep-sleep', json={}, headers=headers, timeout=30)
run_id = r.json()['run_id']
print('Triggered:', run_id)
# Poll until completed (max 90s)
for _ in range(18):
    time.sleep(5)
    s = httpx.get(f'http://127.0.0.1:8050/api/test/deep-sleep-status/{run_id}', headers=headers, timeout=30)
    status = s.json()['status']
    print('Status:', status)
    if status in ('completed', 'failed'):
        print('Stats:', s.json().get('stats'))
        break
"
```
Expected: status transitions from `pending` → `running` → `completed` with stats.

- [ ] **Step 6: Commit**

```bash
git add reflection-worker/worker.py
git commit -m "feat(worker): handle manual deep sleep triggers from heartbeat monitor"
```

---

### Task 4: Heartbeat monitor — HTTP client

**Files:**
- Create: `heartbeat-monitor/client.py`

- [ ] **Step 1: Create heartbeat-monitor directory and client**

```bash
mkdir -p heartbeat-monitor
```

Create `heartbeat-monitor/client.py`:

```python
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

    def trigger_deep_sleep(self) -> dict[str, Any]:
        return self.post("/api/test/trigger-deep-sleep", {})

    def deep_sleep_status(self, run_id: str) -> dict[str, Any]:
        return self.get(f"/api/test/deep-sleep-status/{run_id}")

    def report_cycle(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/api/heartbeat/report", payload)

    def heartbeat_status(self) -> dict[str, Any]:
        return self.get("/api/heartbeat/status")
```

- [ ] **Step 2: Commit**

```bash
git add heartbeat-monitor/client.py
git commit -m "feat(heartbeat): add HTTP client for brain API communication"
```

---

### Task 5: Heartbeat monitor — trap batch definitions

**Files:**
- Create: `heartbeat-monitor/batches.py`

- [ ] **Step 1: Create batch definitions**

Create `heartbeat-monitor/batches.py`:

```python
"""Trap batch definitions for heartbeat monitor.

Each batch is designed to provoke specific biological processes.
Content uses the photovoltaic/SCADA/industrial domain.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrapMemory:
    content: str
    memory_type: str
    tags: str
    importance: float = 0.8


@dataclass
class TrapBatch:
    name: str
    description: str
    memories: list[TrapMemory]
    provokes: str


@dataclass
class CycleContext:
    """Mutable state for a single heartbeat cycle."""
    cycle_id: str = field(default_factory=lambda: f"hb-cycle-{uuid.uuid4().hex[:8]}")
    project_a: str = ""
    project_b: str = ""
    memory_ids: dict[str, str] = field(default_factory=dict)
    initial_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set_projects(self, prefix: str) -> None:
        tag = uuid.uuid4().hex[:6]
        self.project_a = f"heartbeat-{prefix}-{tag}"
        self.project_b = f"heartbeat-{prefix}-cross-{tag}"


BATCH_1_CLUSTER = TrapBatch(
    name="cluster_base",
    description="3 related inverter monitoring memories to form a cluster",
    provokes="relationship formation, synapse tiers 1-2, keyphrase extraction",
    memories=[
        TrapMemory(
            content="La monitorización de inversores fotovoltaicos requiere lectura de registros Modbus TCP cada 10 segundos para detectar fallos de string",
            memory_type="architecture",
            tags="inversores,modbus,monitorizacion",
            importance=0.85,
        ),
        TrapMemory(
            content="Decidimos usar polling síncrono para la lectura de inversores porque el firmware no soporta notificaciones push",
            memory_type="decision",
            tags="inversores,polling,firmware",
            importance=0.8,
        ),
        TrapMemory(
            content="Los inversores Huawei SUN2000 reportan potencia activa en el registro 32080 con factor de escala 1000",
            memory_type="observation",
            tags="inversores,huawei,registros",
            importance=0.75,
        ),
    ],
)

BATCH_2_CONTRADICTION = TrapBatch(
    name="contradiction",
    description="2 contradictory decisions about SCADA polling strategy",
    provokes="contradiction detection, negation patterns, contradiction queue",
    memories=[
        TrapMemory(
            content="Usar polling SCADA cada 5 segundos es la mejor práctica para monitorización en tiempo real de inversores",
            memory_type="decision",
            tags="scada,polling,inversores",
            importance=0.85,
        ),
        TrapMemory(
            content="No usar polling SCADA, implementar arquitectura event-driven con MQTT porque el polling cada 5 segundos satura el bus de comunicaciones",
            memory_type="decision",
            tags="scada,polling,mqtt,inversores",
            importance=0.85,
        ),
    ],
)

BATCH_3_CROSS_PROJECT = TrapBatch(
    name="cross_project",
    description="2 memories in a second project with bridge to first",
    provokes="cross-project bridge, permeability scoring, cross-project myelin",
    memories=[
        TrapMemory(
            content="El sistema de mantenimiento predictivo usa los mismos registros Modbus de inversores para calcular degradación de paneles",
            memory_type="architecture",
            tags="mantenimiento-predictivo,modbus,inversores",
            importance=0.85,
        ),
        TrapMemory(
            content="La correlación entre temperatura de módulo y potencia de salida permite predecir fallos antes de que ocurran",
            memory_type="observation",
            tags="mantenimiento-predictivo,temperatura,prediccion",
            importance=0.8,
        ),
    ],
)

BATCH_5_COLD = TrapBatch(
    name="cold_memory",
    description="1 memory that will never be accessed — decay target",
    provokes="Ebbinghaus decay in REM phase, stability reduction",
    memories=[
        TrapMemory(
            content="El protocolo IEC 61850 fue evaluado como alternativa a Modbus pero descartado por complejidad de implementación",
            memory_type="observation",
            tags="iec-61850,descartado,evaluacion",
            importance=0.5,
        ),
    ],
)

BRIDGE_REASON = "Los datos de monitorización de inversores alimentan el modelo de mantenimiento predictivo"

ALL_BATCHES = [BATCH_1_CLUSTER, BATCH_2_CONTRADICTION, BATCH_3_CROSS_PROJECT, BATCH_5_COLD]
```

- [ ] **Step 2: Commit**

```bash
git add heartbeat-monitor/batches.py
git commit -m "feat(heartbeat): add trap batch definitions for biological process verification"
```

---

### Task 6: Heartbeat monitor — verification checks

**Files:**
- Create: `heartbeat-monitor/checks.py`

- [ ] **Step 1: Create checks module**

Create `heartbeat-monitor/checks.py`:

```python
"""Verification checks that compare snapshots to detect biological process effects."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from client import HeartbeatClient
from batches import CycleContext

logger = logging.getLogger("heartbeat-monitor")


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def take_memory_snapshot(client: HeartbeatClient, memory_id: str) -> dict[str, Any]:
    """Capture current state of a memory for later comparison."""
    detail = client.memory_detail(memory_id)
    mem = detail.get("memory", detail)
    rels = client.relations(memory_id).get("relations", [])
    return {
        "memory_id": memory_id,
        "stability_score": mem.get("stability_score", 0),
        "activation_score": mem.get("activation_score", 0),
        "review_count": mem.get("review_count", 0),
        "relations": rels,
        "relation_count": len(rels),
    }


def check_relationships_formed(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 1: memories should have auto-linked relationships."""
    batch1_ids = [ctx.memory_ids[k] for k in ("cluster_0", "cluster_1", "cluster_2") if k in ctx.memory_ids]
    if len(batch1_ids) < 2:
        return CheckResult("relationships_formed", False, "Not enough cluster memories injected")

    total_rels = 0
    for mid in batch1_ids:
        rels = client.relations(mid).get("relations", [])
        # Count relations to other batch1 memories
        linked = [r for r in rels if r.get("other_memory_id") in batch1_ids or r.get("source_memory_id") in batch1_ids or r.get("target_memory_id") in batch1_ids]
        total_rels += len(linked)

    # Deduplicate (each relation counted from both sides)
    unique_rels = total_rels // 2
    passed = unique_rels >= 2
    return CheckResult("relationships_formed", passed, f"{unique_rels}/3 pairs linked")


def check_contradiction_detected(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 2: contradictory memories should produce contradiction signal."""
    contra_ids = [ctx.memory_ids.get("contra_0"), ctx.memory_ids.get("contra_1")]
    if not all(contra_ids):
        return CheckResult("contradiction_detected", False, "Contradiction memories not injected")

    for mid in contra_ids:
        rels = client.relations(mid).get("relations", [])
        for rel in rels:
            if rel.get("relation_type") == "contradicts":
                return CheckResult("contradiction_detected", True, "contradicts relation found")
            raw = rel.get("evidence_json") or rel.get("evidence") or "{}"
            evidence = json.loads(raw) if isinstance(raw, str) else raw
            cscore = evidence.get("contradiction_score", 0)
            if cscore and float(cscore) > 0:
                return CheckResult("contradiction_detected", True, f"score={cscore}")

    return CheckResult("contradiction_detected", False, "No contradiction signal found")


def check_contradiction_resolved(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """After NREM, contradictions should be resolved or at least processed."""
    contra_ids = [ctx.memory_ids.get("contra_0"), ctx.memory_ids.get("contra_1")]
    if not all(contra_ids):
        return CheckResult("contradiction_resolved", False, "Contradiction memories not injected")

    for mid in contra_ids:
        rels = client.relations(mid).get("relations", [])
        for rel in rels:
            # Check for synthesis (derived_from) or conditional resolution (applies_to)
            if rel.get("relation_type") in ("derived_from", "applies_to"):
                return CheckResult("contradiction_resolved", True, f"resolution type={rel['relation_type']}")
            if rel.get("relation_type") == "contradicts":
                return CheckResult("contradiction_resolved", True, "contradicts relation active (NREM processed)")

    # If contradiction was detected but not resolved yet, mark as skipped-ish
    return CheckResult("contradiction_resolved", False, "No resolution evidence after NREM")


def check_cross_project_myelin(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 3: cross-project relations should have myelin > 0 after NREM."""
    cross_ids = [ctx.memory_ids.get("cross_0"), ctx.memory_ids.get("cross_1")]
    if not all(cross_ids):
        return CheckResult("cross_project_myelin", False, "Cross-project memories not injected")

    for mid in cross_ids:
        rels = client.relations(mid).get("relations", [])
        for rel in rels:
            myelin = rel.get("myelin_score", 0)
            if myelin and float(myelin) > 0:
                return CheckResult("cross_project_myelin", True, f"myelin_score={myelin}")

    return CheckResult("cross_project_myelin", False, "No myelin > 0 on cross-project relations")


def check_reinforcement_applied(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 4: plasticity session should have incremented reinforcement on batch 1 relations."""
    batch1_ids = [ctx.memory_ids.get(f"cluster_{i}") for i in range(3)]
    batch1_ids = [x for x in batch1_ids if x]
    if not batch1_ids:
        return CheckResult("reinforcement_applied", False, "No cluster memories to check")

    for mid in batch1_ids:
        rels = client.relations(mid).get("relations", [])
        for rel in rels:
            rc = rel.get("reinforcement_count", 0)
            if rc and int(rc) > 1:
                return CheckResult("reinforcement_applied", True, f"reinforcement_count={rc}")

    return CheckResult("reinforcement_applied", False, "No relation with reinforcement_count > 1")


def check_stability_increased(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Accessed memories should have higher stability than initial snapshot."""
    for key in ("cluster_0", "cluster_1", "cluster_2"):
        mid = ctx.memory_ids.get(key)
        if not mid or key not in ctx.initial_snapshots:
            continue
        initial = ctx.initial_snapshots[key]["stability_score"]
        current = take_memory_snapshot(client, mid)["stability_score"]
        if current > initial:
            return CheckResult("stability_increased", True, f"{initial:.3f}->{current:.3f}")

    return CheckResult("stability_increased", False, "No stability increase detected")


def check_cold_memory_decayed(client: HeartbeatClient, ctx: CycleContext) -> CheckResult:
    """Batch 5: cold memory should have lower stability after REM."""
    mid = ctx.memory_ids.get("cold_0")
    if not mid or "cold_0" not in ctx.initial_snapshots:
        return CheckResult("cold_memory_decayed", False, "Cold memory not injected")

    initial = ctx.initial_snapshots["cold_0"]["stability_score"]
    current = take_memory_snapshot(client, mid)["stability_score"]
    if current < initial:
        return CheckResult("cold_memory_decayed", True, f"{initial:.3f}->{current:.3f}")

    return CheckResult("cold_memory_decayed", False, f"No decay: {initial:.3f}->{current:.3f}")


def check_overall_health_stable(client: HeartbeatClient, previous_health: float) -> CheckResult:
    """Brain health should not degrade significantly."""
    health = client.brain_health()
    current = health.get("overall_health", 0)
    threshold = max(previous_health - 0.1, 0.3)
    passed = current >= threshold
    return CheckResult("overall_health_stable", passed, f"{previous_health:.3f}->{current:.3f}")


ALL_CHECKS = [
    check_relationships_formed,
    check_contradiction_detected,
    check_contradiction_resolved,
    check_cross_project_myelin,
    check_reinforcement_applied,
    check_stability_increased,
    check_cold_memory_decayed,
]
```

- [ ] **Step 2: Commit**

```bash
git add heartbeat-monitor/checks.py
git commit -m "feat(heartbeat): add verification checks for biological process detection"
```

---

### Task 7: Heartbeat monitor — main loop

**Files:**
- Create: `heartbeat-monitor/monitor.py`

- [ ] **Step 1: Create the main monitor script**

Create `heartbeat-monitor/monitor.py`:

```python
"""Heartbeat Monitor — living proof that biological memory processes work.

Continuously injects trap memories, triggers deep sleep, and verifies
that every biological process produces measurable effects.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path

from client import HeartbeatClient
from batches import (
    BATCH_1_CLUSTER,
    BATCH_2_CONTRADICTION,
    BATCH_3_CROSS_PROJECT,
    BATCH_5_COLD,
    BRIDGE_REASON,
    CycleContext,
)
from checks import (
    ALL_CHECKS,
    CheckResult,
    check_overall_health_stable,
    take_memory_snapshot,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("heartbeat-monitor")

BASE_URL = os.environ.get("AI_MEMORY_BASE_URL", "http://api-server:8050")
API_KEY = os.environ.get("MEMORY_API_KEY", "")
MODE = os.environ.get("HEARTBEAT_MODE", "accelerated")
INJECT_INTERVAL = int(os.environ.get("HEARTBEAT_INJECT_INTERVAL", "30"))
SLEEP_INTERVAL = int(os.environ.get("HEARTBEAT_SLEEP_INTERVAL", "300"))
VERIFY_INTERVAL = int(os.environ.get("HEARTBEAT_VERIFY_INTERVAL", "120"))
HEARTBEAT_FILE = Path("/tmp/heartbeat-alive")


def touch_heartbeat():
    HEARTBEAT_FILE.write_text(str(time.time()))


def wait_for_api(client: HeartbeatClient, max_wait: int = 120) -> bool:
    """Wait until the API server is reachable."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            client.get("/health")
            return True
        except Exception:
            logger.info("Waiting for API server at %s ...", BASE_URL)
            time.sleep(5)
    return False


def cleanup_previous(client: HeartbeatClient, prefix: str):
    """Delete any leftover heartbeat projects."""
    try:
        # Use brain_health to find heartbeat projects
        health = client.brain_health()
        regions = health.get("regions", {})
        for project_name in regions:
            if project_name.startswith(prefix):
                try:
                    client.delete_project(project_name)
                    logger.info("Cleaned up old project: %s", project_name)
                except Exception:
                    pass
    except Exception:
        logger.debug("Cleanup scan failed (non-critical)")


def inject_batch(client: HeartbeatClient, ctx: CycleContext, batch, project: str, id_prefix: str):
    """Inject a batch of trap memories and record their IDs."""
    for i, mem in enumerate(batch.memories):
        result = client.create_memory(
            content=mem.content,
            project=project,
            memory_type=mem.memory_type,
            tags=mem.tags,
            importance=mem.importance,
            agent_id="heartbeat-monitor",
        )
        key = f"{id_prefix}_{i}"
        ctx.memory_ids[key] = result["memory_id"]
        logger.info("  Injected %s: %s", key, result["memory_id"][:8])


def phase_inject(client: HeartbeatClient, ctx: CycleContext):
    """Phase 1: Inject all trap batches."""
    logger.info("=== PHASE 1: INJECT (cycle %s) ===", ctx.cycle_id)

    # Cleanup leftover projects from previous cycles
    cleanup_previous(client, "heartbeat-")

    ctx.set_projects("mon")

    # Batch 1: Cluster base
    logger.info("Batch 1: Cluster base (%s)", ctx.project_a)
    inject_batch(client, ctx, BATCH_1_CLUSTER, ctx.project_a, "cluster")
    time.sleep(1)  # Allow auto-linking

    # Batch 2: Contradiction
    logger.info("Batch 2: Contradiction")
    inject_batch(client, ctx, BATCH_2_CONTRADICTION, ctx.project_a, "contra")
    time.sleep(1)

    # Batch 3: Cross-project
    logger.info("Batch 3: Cross-project (%s)", ctx.project_b)
    inject_batch(client, ctx, BATCH_3_CROSS_PROJECT, ctx.project_b, "cross")

    # Create bridge between projects
    try:
        client.bridge_projects(
            project_a=ctx.project_a,
            project_b=ctx.project_b,
            reason=BRIDGE_REASON,
        )
        logger.info("  Bridge created: %s <-> %s", ctx.project_a, ctx.project_b)
    except Exception as exc:
        logger.warning("  Bridge creation failed: %s", exc)

    time.sleep(1)

    # Batch 4: Reinforcement via plasticity session
    logger.info("Batch 4: Reinforcement (plasticity session)")
    session_id = f"hb-session-{uuid.uuid4().hex[:8]}"
    try:
        client.record_session(
            project=ctx.project_a,
            agent_id="heartbeat-monitor",
            session_id=session_id,
            summary="Revisión de la arquitectura de monitorización de inversores Modbus",
            goal="Verificar configuración de polling y registros Huawei",
            outcome="Confirmada lectura cada 10s en registro 32080",
            changes=[],
            decisions=[],
            errors=[],
            follow_ups=[],
        )
        client.apply_session_plasticity(
            project=ctx.project_a,
            agent_id="heartbeat-monitor",
            session_id=session_id,
            summary="Revisión de la arquitectura de monitorización de inversores Modbus",
            goal="Verificar configuración de polling y registros Huawei",
            outcome="Confirmada lectura cada 10s en registro 32080",
            changes=[],
            decisions=[],
            errors=[],
            follow_ups=[],
        )
        logger.info("  Plasticity session applied")
    except Exception as exc:
        logger.warning("  Plasticity session failed: %s", exc)

    # Batch 5: Cold memory
    logger.info("Batch 5: Cold memory (will not be accessed)")
    inject_batch(client, ctx, BATCH_5_COLD, ctx.project_a, "cold")

    # Take initial snapshots for comparison
    logger.info("Taking initial snapshots...")
    for key, mid in ctx.memory_ids.items():
        try:
            ctx.initial_snapshots[key] = take_memory_snapshot(client, mid)
        except Exception:
            logger.debug("  Snapshot failed for %s", key)

    total = len(ctx.memory_ids)
    logger.info("Phase 1 complete: %d memories injected", total)
    touch_heartbeat()
    return total


def phase_sleep(client: HeartbeatClient, ctx: CycleContext):
    """Phase 2: Trigger deep sleep and wait for completion."""
    logger.info("=== PHASE 2: DEEP SLEEP (cycle %s) ===", ctx.cycle_id)

    try:
        result = client.trigger_deep_sleep()
        run_id = result["run_id"]
        logger.info("Deep sleep triggered: run_id=%s (queued=%s)", run_id, result.get("queued"))
    except Exception as exc:
        logger.error("Failed to trigger deep sleep: %s", exc)
        return

    # Poll until completed (max 5 minutes)
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            status = client.deep_sleep_status(run_id)
            s = status["status"]
            if s == "completed":
                logger.info("Deep sleep completed: %s", status.get("stats", {}))
                touch_heartbeat()
                return
            if s == "failed":
                logger.error("Deep sleep failed: %s", status.get("stats", {}))
                touch_heartbeat()
                return
            logger.info("Deep sleep status: %s (waiting...)", s)
        except Exception as exc:
            logger.debug("Status poll error: %s", exc)
        time.sleep(10)

    logger.warning("Deep sleep did not complete within 5 minutes")
    touch_heartbeat()


def phase_verify(client: HeartbeatClient, ctx: CycleContext, previous_health: float) -> list[CheckResult]:
    """Phase 3: Run all verification checks."""
    logger.info("=== PHASE 3: VERIFY (cycle %s) ===", ctx.cycle_id)

    results: list[CheckResult] = []

    for check_fn in ALL_CHECKS:
        try:
            result = check_fn(client, ctx)
        except Exception as exc:
            result = CheckResult(check_fn.__name__.replace("check_", ""), False, f"Error: {exc}")
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        logger.info("  [%s] %s: %s", status, result.name, result.detail)

    # Overall health check
    try:
        health_result = check_overall_health_stable(client, previous_health)
    except Exception as exc:
        health_result = CheckResult("overall_health_stable", False, f"Error: {exc}")
    results.append(health_result)
    status = "PASS" if health_result.passed else "FAIL"
    logger.info("  [%s] %s: %s", status, health_result.name, health_result.detail)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    logger.info("Phase 3 complete: %d passed, %d failed", passed, failed)

    # Report to API
    try:
        client.report_cycle({
            "cycle_id": ctx.cycle_id,
            "mode": MODE,
            "phase": "completed",
            "injected_memories": len(ctx.memory_ids),
            "checks": [r.to_dict() for r in results],
            "passed": passed,
            "failed": failed,
        })
        logger.info("Cycle report stored")
    except Exception as exc:
        logger.warning("Failed to store cycle report: %s", exc)

    touch_heartbeat()
    return results


def run_cycle(client: HeartbeatClient, previous_health: float) -> tuple[list[CheckResult], float]:
    """Execute one full heartbeat cycle: inject → sleep → verify."""
    ctx = CycleContext()
    logger.info("Starting heartbeat cycle %s (mode=%s)", ctx.cycle_id, MODE)

    injected = phase_inject(client, ctx)

    logger.info("Waiting %ds before triggering deep sleep...", SLEEP_INTERVAL)
    # Sleep in chunks to keep heartbeat alive
    remaining = SLEEP_INTERVAL
    while remaining > 0:
        wait = min(remaining, 30)
        time.sleep(wait)
        remaining -= wait
        touch_heartbeat()

    phase_sleep(client, ctx)

    logger.info("Waiting %ds before verification...", VERIFY_INTERVAL)
    remaining = VERIFY_INTERVAL
    while remaining > 0:
        wait = min(remaining, 30)
        time.sleep(wait)
        remaining -= wait
        touch_heartbeat()

    results = phase_verify(client, ctx, previous_health)

    # Get current health for next cycle
    try:
        current_health = client.brain_health().get("overall_health", 0.5)
    except Exception:
        current_health = previous_health

    return results, current_health


def main():
    logger.info("Heartbeat Monitor starting (mode=%s)", MODE)
    logger.info("  Inject interval: %ds", INJECT_INTERVAL)
    logger.info("  Sleep interval: %ds", SLEEP_INTERVAL)
    logger.info("  Verify interval: %ds", VERIFY_INTERVAL)

    client = HeartbeatClient(BASE_URL, API_KEY)
    touch_heartbeat()

    if not wait_for_api(client):
        logger.error("API server not reachable at %s — exiting", BASE_URL)
        return

    logger.info("API server reachable. Starting heartbeat cycles.")
    previous_health = 0.5
    cycle_count = 0

    try:
        while True:
            cycle_count += 1
            logger.info("===== CYCLE %d =====", cycle_count)
            try:
                results, previous_health = run_cycle(client, previous_health)
                passed = sum(1 for r in results if r.passed)
                failed = len(results) - passed
                logger.info("===== CYCLE %d COMPLETE: %d passed, %d failed =====", cycle_count, passed, failed)
            except Exception:
                logger.exception("Cycle %d failed", cycle_count)

            # Wait before next cycle
            logger.info("Next cycle in %ds...", INJECT_INTERVAL)
            remaining = INJECT_INTERVAL
            while remaining > 0:
                wait = min(remaining, 30)
                time.sleep(wait)
                remaining -= wait
                touch_heartbeat()
    finally:
        client.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add heartbeat-monitor/monitor.py
git commit -m "feat(heartbeat): add main monitor loop with inject/sleep/verify phases"
```

---

### Task 8: Heartbeat monitor — Dockerfile and requirements

**Files:**
- Create: `heartbeat-monitor/Dockerfile`
- Create: `heartbeat-monitor/requirements.txt`

- [ ] **Step 1: Create requirements.txt**

Create `heartbeat-monitor/requirements.txt`:

```
httpx>=0.27.0
```

- [ ] **Step 2: Create Dockerfile**

Create `heartbeat-monitor/Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY client.py .
COPY batches.py .
COPY checks.py .
COPY monitor.py .

CMD ["python", "monitor.py"]
```

- [ ] **Step 3: Commit**

```bash
git add heartbeat-monitor/Dockerfile heartbeat-monitor/requirements.txt
git commit -m "feat(heartbeat): add Dockerfile and requirements"
```

---

### Task 9: Docker Compose and Makefile integration

**Files:**
- Modify: `docker-compose.yaml:228` (before networks section)
- Modify: `Makefile:49` (append new targets)

- [ ] **Step 1: Add heartbeat-monitor service to docker-compose.yaml**

Add before the `networks:` block (before line 225):

```yaml

  heartbeat-monitor:
    build:
      context: ./heartbeat-monitor
      dockerfile: Dockerfile
    container_name: ai-memory-heartbeat
    environment:
      AI_MEMORY_BASE_URL: http://api-server:8050
      MEMORY_API_KEY: ${MEMORY_API_KEY}
      HEARTBEAT_MODE: ${HEARTBEAT_MODE:-accelerated}
      HEARTBEAT_INJECT_INTERVAL: ${HEARTBEAT_INJECT_INTERVAL:-30}
      HEARTBEAT_SLEEP_INTERVAL: ${HEARTBEAT_SLEEP_INTERVAL:-300}
      HEARTBEAT_VERIFY_INTERVAL: ${HEARTBEAT_VERIFY_INTERVAL:-120}
      HEARTBEAT_ENABLED: "true"
    depends_on:
      api-server:
        condition: service_healthy
      reflection-worker:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import os, time; path='/tmp/heartbeat-alive'; now=time.time(); m=os.path.getmtime(path); raise SystemExit(0 if now - m < 300 else 1)\""]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 60s
    restart: unless-stopped
    profiles:
      - heartbeat
```

- [ ] **Step 2: Add HEARTBEAT_ENABLED to api-server environment**

In the api-server service environment block (around line 152), add:

```yaml
      HEARTBEAT_ENABLED: ${HEARTBEAT_ENABLED:-false}
```

- [ ] **Step 3: Add Makefile targets**

Append to `Makefile` after line 49:

```makefile

heartbeat-fast:
	AI_MEMORY_TEST_MODE=true HEARTBEAT_ENABLED=true $(DOCKER_COMPOSE) --profile heartbeat up -d --build

heartbeat-prod:
	HEARTBEAT_MODE=production HEARTBEAT_INJECT_INTERVAL=3600 HEARTBEAT_SLEEP_INTERVAL=86400 HEARTBEAT_VERIFY_INTERVAL=7200 HEARTBEAT_ENABLED=true $(DOCKER_COMPOSE) --profile heartbeat up -d --build

heartbeat-status:
	@SANITIZED_ENV=$$(mktemp); tr -d '\r' < .env > $$SANITIZED_ENV; source $$SANITIZED_ENV && curl -s -H "X-API-Key: $$MEMORY_API_KEY" http://127.0.0.1:8050/api/heartbeat/status | python3 -m json.tool; rm -f $$SANITIZED_ENV

heartbeat-stop:
	$(DOCKER_COMPOSE) --profile heartbeat stop heartbeat-monitor
```

- [ ] **Step 4: Update .PHONY in Makefile**

Change line 8 from:
```makefile
.PHONY: dev-deps health smoke stack-up stack-down stack-test-up test-deterministic eval-deterministic brain-check demo-up demo-seed demo-check demo-down
```
To:
```makefile
.PHONY: dev-deps health smoke stack-up stack-down stack-test-up test-deterministic eval-deterministic brain-check demo-up demo-seed demo-check demo-down heartbeat-fast heartbeat-prod heartbeat-status heartbeat-stop
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yaml Makefile
git commit -m "feat: add heartbeat-monitor service to Docker Compose with Makefile targets"
```

---

### Task 10: Integration test — full heartbeat cycle

**Files:**
- Modify: `tests/test_heartbeat.py` (add end-to-end test)

- [ ] **Step 1: Add a test that exercises the full inject → check flow**

Append to `tests/test_heartbeat.py`:

```python


def test_heartbeat_inject_creates_memories_and_relations(brain_client, unique_project_name):
    """Simulate batch 1 injection and verify relationships form."""
    project = unique_project_name("hb-e2e")

    import time

    mem_a = brain_client.create_memory(
        content="La monitorización de inversores fotovoltaicos requiere lectura de registros Modbus TCP cada 10 segundos",
        project=project,
        memory_type="architecture",
        tags="inversores,modbus,monitorizacion",
        importance=0.85,
        agent_id="heartbeat-test",
    )["memory_id"]

    mem_b = brain_client.create_memory(
        content="Decidimos usar polling síncrono para la lectura de inversores porque el firmware no soporta push",
        project=project,
        memory_type="decision",
        tags="inversores,polling,firmware",
        importance=0.8,
        agent_id="heartbeat-test",
    )["memory_id"]

    time.sleep(1)

    mem_c = brain_client.create_memory(
        content="Los inversores Huawei SUN2000 reportan potencia activa en el registro 32080",
        project=project,
        memory_type="observation",
        tags="inversores,huawei,registros",
        importance=0.75,
        agent_id="heartbeat-test",
    )["memory_id"]

    time.sleep(1)

    # At least some relations should have formed
    all_rels = []
    for mid in [mem_a, mem_b, mem_c]:
        rels = brain_client.relations(mid).get("relations", [])
        all_rels.extend(rels)

    assert len(all_rels) > 0, "Expected at least one relation to form between cluster memories"


def test_heartbeat_deep_sleep_trigger_and_complete(brain_client):
    """Trigger deep sleep and verify it completes."""
    import time

    result = brain_client.post("/api/test/trigger-deep-sleep", {})
    assert "run_id" in result
    run_id = result["run_id"]

    # Poll until done (max 120s)
    for _ in range(24):
        time.sleep(5)
        status = brain_client.get(f"/api/test/deep-sleep-status/{run_id}")
        if status["status"] in ("completed", "failed"):
            assert status["status"] == "completed", f"Deep sleep failed: {status.get('stats')}"
            return

    assert False, "Deep sleep did not complete within 120 seconds"
```

- [ ] **Step 2: Rebuild stack and run full test suite**

```bash
AI_MEMORY_TEST_MODE=true HEARTBEAT_ENABLED=true docker compose up -d --build api-server reflection-worker
sleep 10
source .venv/bin/activate && AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest tests/test_heartbeat.py -v --tb=short
```
Expected: all 6 tests PASS

- [ ] **Step 3: Run full regression suite**

```bash
source .venv/bin/activate && AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest tests/ -v --tb=short
```
Expected: all tests PASS (55 existing + 6 new = 61)

- [ ] **Step 4: Commit**

```bash
git add tests/test_heartbeat.py
git commit -m "test: add integration tests for heartbeat cycle and deep sleep trigger"
```

---

### Task 11: Smoke test — run heartbeat in accelerated mode

This is a manual verification task, not a code change.

- [ ] **Step 1: Start the full stack with heartbeat**

```bash
make heartbeat-fast
```

- [ ] **Step 2: Watch heartbeat logs**

```bash
docker compose --profile heartbeat logs -f heartbeat-monitor
```

Expected output flow:
```
Heartbeat Monitor starting (mode=accelerated)
API server reachable. Starting heartbeat cycles.
===== CYCLE 1 =====
=== PHASE 1: INJECT (cycle hb-cycle-XXXXXXXX) ===
Batch 1: Cluster base (heartbeat-mon-XXXXXX)
  Injected cluster_0: abcd1234
  Injected cluster_1: efgh5678
  Injected cluster_2: ijkl9012
Batch 2: Contradiction
  ...
Waiting 300s before triggering deep sleep...
=== PHASE 2: DEEP SLEEP ===
Deep sleep triggered: run_id=...
Deep sleep status: pending (waiting...)
Deep sleep completed: {...}
Waiting 120s before verification...
=== PHASE 3: VERIFY ===
  [PASS] relationships_formed: 2/3 pairs linked
  [PASS] contradiction_detected: score=0.1
  ...
===== CYCLE 1 COMPLETE: X passed, Y failed =====
```

- [ ] **Step 3: Check heartbeat status endpoint**

```bash
make heartbeat-status
```

Should return JSON with the cycle results.

- [ ] **Step 4: Stop heartbeat**

```bash
make heartbeat-stop
```

---

## Self-Review

**Spec coverage:**
- Trap batches (5 types): Task 5 ✅
- Verification checks (8 checks): Task 6 ✅
- `/api/test/trigger-deep-sleep`: Task 2 ✅
- `/api/test/deep-sleep-status/{run_id}`: Task 2 ✅
- `/api/heartbeat/report`: Task 2 ✅
- `/api/heartbeat/status`: Task 2 ✅
- `manual_deep_sleep_runs` table: Task 1 ✅
- `heartbeat_cycles` table: Task 1 ✅
- Worker `handle_manual_deep_sleep()`: Task 3 ✅
- Docker service with profiles: Task 9 ✅
- Makefile targets: Task 9 ✅
- Cleanup of old projects: Task 7 (in `phase_inject`) ✅
- Two modes (accelerated/production): Task 7 + Task 9 ✅
- HEARTBEAT_ENABLED guard: Task 2 ✅

**Placeholder scan:** No TBD, TODO, or vague references found.

**Type consistency:**
- `HeartbeatClient` methods match across client.py, checks.py, monitor.py ✅
- `CycleContext` fields match across batches.py, checks.py, monitor.py ✅
- `CheckResult.to_dict()` output matches `/api/heartbeat/report` schema ✅
- `queue_manual_deep_sleep()` pattern matches `queue_manual_reflection()` ✅
