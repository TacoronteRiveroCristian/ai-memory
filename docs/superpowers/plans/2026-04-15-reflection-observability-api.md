# Reflection Observability API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose what the reflection worker has consolidated and what contradictions it has detected, via REST endpoints and MCP tools, so the user can ask "¿qué se consolidó?" / "¿hay contradicciones?" and see actual logs.

**Architecture:** Three new read-only endpoints on `api-server/server.py` backed by existing Postgres tables (`reflection_runs`, `reflection_promotions`, `contradiction_queue`). Each endpoint has a twin MCP tool that wraps the same payload helper. No schema changes. No UI.

**Tech Stack:** FastAPI + FastMCP (already wired), asyncpg, pytest against live test-mode stack.

---

## Context the implementer needs

**Existing observability surface** (`api-server/server.py:3151`): `get_reflection_status_payload()` returns worker heartbeat + last run. That's the only window currently exposed. Everything else below is written to Postgres but never read back out.

**Tables already populated** (see `config/postgres/init.sql`):

- `reflection_runs` (`:94`) — one row per reflection worker execution. Columns: `id, mode, status, model, input_count, promoted_count, error, started_at, finished_at`.
- `reflection_promotions` (`:119`) — one row per item the worker promoted in a run. Columns: `id, run_id, project_id, item_type, item_hash, target_ref, created_at`. Written by `reflection-worker/worker.py:321` (`record_promotion`). **Important:** `target_ref` is a free-form string ("stored", etc.), NOT a FK to `memory_log` — do not try to join it to memory content.
- `contradiction_queue` (`:164`) — pairs of conflicting memories. Columns: `id, memory_a_id, memory_b_id, resolution_status, resolution_type, resolution_memory_id, condition_text, resolved_at, created_at`. `memory_a_id` / `memory_b_id` ARE real FKs to `memory_log(id)` — join to fetch summaries. Written from two places: `api-server/server.py:1980` (suspected during auto-link) and proactive detection paths, plus the reflection worker.
- `projects` — `id, name`. Join `project_id` → `name` when filtering by project.

**Existing patterns to imitate:**

- Payload helper pattern: `get_reflection_status_payload()` at `api-server/server.py:3151`. Returns plain dict, uses `serialize_row()` (`:522`) to convert `datetime`/`UUID` to JSON-safe values.
- REST endpoint pattern: `api_reflection_status()` at `api-server/server.py:4609`. Just wraps the helper. Auth is enforced globally by `enforce_api_key` middleware (`:3211`) for any `/api/*` path.
- MCP tool pattern: `get_reflection_status()` at `api-server/server.py:4078`. Registered with `@mcp.tool()`, returns `json.dumps(...)` on success or `f"ERROR {exc}"` on failure. Dense Spanish docstrings with "Cuándo usar / Cómo usar / Devuelve" — match that style.
- Test client pattern: `tests/conftest.py:14` (`BrainClient`). Add new methods alongside `reflection_status()` (`:95`).

**Test mode:** `make stack-test-up` starts deterministic stack. Tests in `tests/` run against it via `AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/<file>`. `test_contradiction_detection.py` already creates two contradictory memories and triggers the suspected-contradictions insert — useful as a reference fixture strategy.

**DRY constraint:** all three helpers MUST share one serialization path (`serialize_row`) and a shared `_resolve_project_id(conn, project)` micro-helper you'll create in Task 1. Do not copy-paste SQL skeletons.

---

## File structure

- **Modify** `api-server/server.py`:
  - New helper `_resolve_project_id` (near `serialize_row`, around `:535`).
  - Three new payload helpers next to `get_reflection_status_payload` (`:3151`): `list_reflection_runs_payload`, `list_contradictions_payload`, `get_brain_activity_payload`.
  - Three new REST endpoints next to `api_reflection_status` (`:4609`).
  - Three new MCP tools next to `get_reflection_status` (`:4078`).
- **Modify** `tests/conftest.py`: add four `BrainClient` methods (`list_reflection_runs`, `list_contradictions`, `brain_activity`, plus a small seeding helper is NOT needed — use existing `create_memory`).
- **Create** `tests/test_reflection_observability.py`: integration tests for all three endpoints against the test-mode stack.
- **Modify** `CLAUDE.md`: one-line note under "Plasticity Concepts" pointing at the new tools.

---

## Task 1: `_resolve_project_id` helper + unit-style guard

**Files:**
- Modify: `api-server/server.py` — insert after `serialize_row` (`:533`).

- [ ] **Step 1: Add the helper**

Insert at `api-server/server.py:534` (immediately after `serialize_row`'s closing `return result`):

```python
async def _resolve_project_id(conn, project: Optional[str]) -> Optional[uuid.UUID]:
    """Lookup a project UUID by name. Returns None if project is None or not found.

    Callers should treat a None return for a non-None input as 'no such project'
    and short-circuit to an empty result set rather than erroring.
    """
    if not project:
        return None
    row = await conn.fetchrow("SELECT id FROM projects WHERE name = $1 LIMIT 1", project)
    return row["id"] if row else None
```

- [ ] **Step 2: Commit**

```bash
git add api-server/server.py
git commit -m "refactor(api): add _resolve_project_id helper for observability endpoints"
```

---

## Task 2: `list_reflection_runs_payload` helper

**Files:**
- Modify: `api-server/server.py` — insert after `get_reflection_status_payload` (`:3182`).

- [ ] **Step 1: Add the payload helper**

Insert immediately after the closing `return {...}` of `get_reflection_status_payload`:

```python
async def list_reflection_runs_payload(
    limit: int = 20,
    project: Optional[str] = None,
    include_promotions: bool = True,
) -> dict[str, Any]:
    """Return the most recent reflection runs and (optionally) their promotions.

    - `limit`: capped to [1, 100].
    - `project`: if provided, only runs that produced at least one promotion for
      that project are returned. An unknown project yields an empty list.
    - `include_promotions`: when True, each run carries its promotions list.
    """
    limit = max(1, min(int(limit), 100))
    if not pg_pool:
        return {"runs": [], "count": 0, "filter": {"project": project, "limit": limit}}

    async with pg_pool.acquire() as conn:
        project_id = await _resolve_project_id(conn, project)
        if project and project_id is None:
            return {"runs": [], "count": 0, "filter": {"project": project, "limit": limit}}

        if project_id is None:
            run_rows = await conn.fetch(
                """
                SELECT id, mode, status, model, input_count, promoted_count,
                       error, started_at, finished_at
                FROM reflection_runs
                ORDER BY started_at DESC
                LIMIT $1
                """,
                limit,
            )
        else:
            run_rows = await conn.fetch(
                """
                SELECT DISTINCT r.id, r.mode, r.status, r.model, r.input_count,
                       r.promoted_count, r.error, r.started_at, r.finished_at
                FROM reflection_runs r
                JOIN reflection_promotions p ON p.run_id = r.id
                WHERE p.project_id = $1
                ORDER BY r.started_at DESC
                LIMIT $2
                """,
                project_id,
                limit,
            )

        runs = [serialize_row(r) for r in run_rows]

        if include_promotions and runs:
            run_ids = [uuid.UUID(r["id"]) for r in runs]
            promo_query = """
                SELECT rp.id, rp.run_id, rp.item_type, rp.item_hash,
                       rp.target_ref, rp.created_at, p.name AS project
                FROM reflection_promotions rp
                LEFT JOIN projects p ON p.id = rp.project_id
                WHERE rp.run_id = ANY($1::uuid[])
            """
            params: list[Any] = [run_ids]
            if project_id is not None:
                promo_query += " AND rp.project_id = $2"
                params.append(project_id)
            promo_query += " ORDER BY rp.created_at ASC"
            promo_rows = await conn.fetch(promo_query, *params)

            by_run: dict[str, list[dict[str, Any]]] = {r["id"]: [] for r in runs}
            for row in promo_rows:
                serialized = serialize_row(row) or {}
                run_key = serialized.pop("run_id", None)
                if run_key in by_run:
                    by_run[run_key].append(serialized)
            for run in runs:
                run["promotions"] = by_run.get(run["id"], [])

    return {
        "runs": runs,
        "count": len(runs),
        "filter": {"project": project, "limit": limit, "include_promotions": include_promotions},
    }
```

- [ ] **Step 2: Add REST endpoint**

Insert at `api-server/server.py` immediately after `api_reflection_status` (`:4611`):

```python
@app.get("/api/reflections/runs")
async def api_list_reflection_runs(
    limit: int = 20,
    project: Optional[str] = None,
    include_promotions: bool = True,
):
    return await list_reflection_runs_payload(
        limit=limit, project=project, include_promotions=include_promotions
    )
```

- [ ] **Step 3: Add MCP tool**

Insert immediately after the `get_reflection_status` MCP tool (`:4099`):

```python
@mcp.tool()
async def list_recent_consolidations(
    limit: int = 10,
    project: Optional[str] = None,
) -> str:
    """Lista las últimas ejecuciones del worker de reflexión y qué se consolidó en cada una.

    Cuándo usar:
    - Cuando quieras saber qué ha pasado en el cerebro en las últimas horas.
    - Para auditar qué decisiones/errores/tareas/memorias fueron promovidas.
    - Antes de tomar decisiones que dependan de "qué recordaba el sistema".

    Cómo usar:
    - `limit`: número máximo de runs a devolver (1..100, default 10).
    - `project`: opcional, filtra a runs que promovieron algo en ese proyecto.

    Devuelve:
    - JSON con lista `runs`, cada uno con sus `promotions` (item_type, item_hash,
      target_ref, project, created_at).
    - `ERROR ...` si no puede obtenerse la información.
    """
    try:
        payload = await list_reflection_runs_payload(
            limit=limit, project=project, include_promotions=True
        )
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.exception("list_recent_consolidations fallo")
        return f"ERROR {exc}"
```

- [ ] **Step 4: Add BrainClient helper**

Edit `tests/conftest.py`, insert after `reflection_status` (`:96`):

```python
    def list_reflection_runs(self, limit: int = 20, project: Optional[str] = None,
                             include_promotions: bool = True):
        params: dict[str, Any] = {"limit": limit, "include_promotions": str(include_promotions).lower()}
        if project:
            params["project"] = project
        return self.get("/api/reflections/runs", params=params)
```

- [ ] **Step 5: Write integration test**

Create `tests/test_reflection_observability.py`:

```python
"""Tests for reflection observability endpoints (runs, promotions, contradictions)."""

import time


def test_list_reflection_runs_smoke(brain_client):
    payload = brain_client.list_reflection_runs(limit=5)
    assert "runs" in payload
    assert "count" in payload
    assert payload["count"] == len(payload["runs"])
    assert payload["filter"]["limit"] == 5


def test_list_reflection_runs_returns_manual_run(brain_client):
    queued = brain_client.run_reflection()
    assert "run_id" in queued
    # The run exists in reflection_runs even if the worker hasn't picked it up yet.
    payload = brain_client.list_reflection_runs(limit=10)
    run_ids = [r["id"] for r in payload["runs"]]
    assert queued["run_id"] in run_ids


def test_list_reflection_runs_unknown_project_is_empty(brain_client):
    payload = brain_client.list_reflection_runs(project="does-not-exist-zzz")
    assert payload["runs"] == []
    assert payload["count"] == 0


def test_list_reflection_runs_limit_is_clamped(brain_client):
    payload = brain_client.list_reflection_runs(limit=999)
    assert payload["filter"]["limit"] == 100
```

- [ ] **Step 6: Run the tests**

```bash
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_reflection_observability.py -v
```

Expected: 4 passed. If the worker hasn't executed any run yet, `test_list_reflection_runs_returns_manual_run` still passes because queueing inserts a row immediately (see `queue_manual_reflection` at `api-server/server.py:3202`).

- [ ] **Step 7: Commit**

```bash
git add api-server/server.py tests/conftest.py tests/test_reflection_observability.py
git commit -m "feat(api): expose recent consolidations via REST and MCP"
```

---

## Task 3: `list_contradictions_payload` helper

**Files:**
- Modify: `api-server/server.py` — insert after `list_reflection_runs_payload`.
- Modify: `tests/conftest.py`.
- Modify: `tests/test_reflection_observability.py`.

- [ ] **Step 1: Add the payload helper**

Insert after `list_reflection_runs_payload`:

```python
async def list_contradictions_payload(
    status: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return entries from the contradiction queue with summaries of the memories involved.

    - `status`: filter by `resolution_status` (`pending`, `suspected`, `resolved`).
      None returns all.
    - `project`: if provided, only contradictions where EITHER memory belongs to
      that project are returned. An unknown project yields an empty list.
    - `limit`: capped to [1, 200].
    """
    allowed_status = {"pending", "suspected", "resolved"}
    if status is not None and status not in allowed_status:
        return {"contradictions": [], "count": 0, "error": f"invalid status: {status}"}
    limit = max(1, min(int(limit), 200))

    if not pg_pool:
        return {"contradictions": [], "count": 0, "filter": {"status": status, "project": project, "limit": limit}}

    async with pg_pool.acquire() as conn:
        project_id = await _resolve_project_id(conn, project)
        if project and project_id is None:
            return {"contradictions": [], "count": 0, "filter": {"status": status, "project": project, "limit": limit}}

        query = """
            SELECT
                cq.id,
                cq.memory_a_id,
                cq.memory_b_id,
                cq.resolution_status,
                cq.resolution_type,
                cq.resolution_memory_id,
                cq.condition_text,
                cq.created_at,
                cq.resolved_at,
                ma.summary        AS memory_a_summary,
                ma.project_id     AS memory_a_project_id,
                pa.name           AS memory_a_project,
                mb.summary        AS memory_b_summary,
                mb.project_id     AS memory_b_project_id,
                pb.name           AS memory_b_project
            FROM contradiction_queue cq
            LEFT JOIN memory_log ma ON ma.id = cq.memory_a_id
            LEFT JOIN memory_log mb ON mb.id = cq.memory_b_id
            LEFT JOIN projects  pa ON pa.id = ma.project_id
            LEFT JOIN projects  pb ON pb.id = mb.project_id
            WHERE 1=1
        """
        params: list[Any] = []
        if status is not None:
            params.append(status)
            query += f" AND cq.resolution_status = ${len(params)}"
        if project_id is not None:
            params.append(project_id)
            query += f" AND (ma.project_id = ${len(params)} OR mb.project_id = ${len(params)})"
        params.append(limit)
        query += f" ORDER BY cq.created_at DESC LIMIT ${len(params)}"

        rows = await conn.fetch(query, *params)

    contradictions = []
    for row in rows:
        data = serialize_row(row) or {}
        # Restructure into nested memory_a / memory_b blocks for readability.
        memory_a = {
            "id": data.pop("memory_a_id", None),
            "summary": data.pop("memory_a_summary", None),
            "project": data.pop("memory_a_project", None),
        }
        data.pop("memory_a_project_id", None)
        memory_b = {
            "id": data.pop("memory_b_id", None),
            "summary": data.pop("memory_b_summary", None),
            "project": data.pop("memory_b_project", None),
        }
        data.pop("memory_b_project_id", None)
        data["memory_a"] = memory_a
        data["memory_b"] = memory_b
        contradictions.append(data)

    return {
        "contradictions": contradictions,
        "count": len(contradictions),
        "filter": {"status": status, "project": project, "limit": limit},
    }
```

- [ ] **Step 2: Add REST endpoint**

Insert after `api_list_reflection_runs`:

```python
@app.get("/api/contradictions")
async def api_list_contradictions(
    status: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 50,
):
    payload = await list_contradictions_payload(status=status, project=project, limit=limit)
    if payload.get("error"):
        raise HTTPException(status_code=400, detail=payload["error"])
    return payload
```

- [ ] **Step 3: Add MCP tool**

Insert after `list_recent_consolidations`:

```python
@mcp.tool()
async def list_contradictions(
    status: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Lista contradicciones detectadas entre memorias, con resumen de cada una.

    Cuándo usar:
    - Para auditar si el cerebro ha encontrado información incompatible.
    - Antes de tomar una decisión que dependa de una memoria "confiable".
    - Cuando el usuario pregunte "¿hay contradicciones pendientes?".

    Cómo usar:
    - `status`: opcional, uno de `pending`, `suspected`, `resolved`. None devuelve todas.
    - `project`: opcional, filtra a contradicciones donde cualquiera de las dos
      memorias pertenece a ese proyecto.
    - `limit`: número máximo a devolver (1..200, default 20).

    Devuelve:
    - JSON con lista `contradictions`, cada una con `memory_a` / `memory_b`
      (id, summary, project), `resolution_status`, `resolution_type`,
      `condition_text`, `created_at`, `resolved_at`.
    - `ERROR ...` si no puede obtenerse la información.
    """
    try:
        payload = await list_contradictions_payload(status=status, project=project, limit=limit)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.exception("list_contradictions fallo")
        return f"ERROR {exc}"
```

- [ ] **Step 4: Add BrainClient helper**

Edit `tests/conftest.py`, after `list_reflection_runs`:

```python
    def list_contradictions(self, status: Optional[str] = None,
                            project: Optional[str] = None, limit: int = 50):
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if project:
            params["project"] = project
        return self.get("/api/contradictions", params=params)
```

- [ ] **Step 5: Write integration tests**

Append to `tests/test_reflection_observability.py`:

```python
def test_list_contradictions_smoke(brain_client):
    payload = brain_client.list_contradictions(limit=10)
    assert "contradictions" in payload
    assert payload["count"] == len(payload["contradictions"])


def test_list_contradictions_rejects_bad_status(brain_client):
    import httpx
    try:
        brain_client.list_contradictions(status="nope")
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 400
    else:
        raise AssertionError("expected 400 for invalid status")


def test_list_contradictions_surfaces_suspected_pair(brain_client, unique_project_name):
    project = unique_project_name("contra-obs")
    mem_a = brain_client.create_memory(
        content="Siempre usar Redis para cache de embeddings en producción",
        project=project, memory_type="decision",
        tags="redis,cache,embeddings", importance=0.85, agent_id="pytest",
    )["memory_id"]
    time.sleep(0.5)
    mem_b = brain_client.create_memory(
        content="Nunca usar Redis para cache; preferir Memcached por consumo de memoria",
        project=project, memory_type="decision",
        tags="redis,cache,memcached", importance=0.85, agent_id="pytest",
    )["memory_id"]
    time.sleep(1.0)

    payload = brain_client.list_contradictions(project=project, limit=50)
    # We accept that the pair may land as a direct `contradicts` relation instead
    # of a queue entry. The test passes if EITHER the queue has the pair OR the
    # relation exists on one of the memories.
    queue_pair_ids = {
        (c["memory_a"]["id"], c["memory_b"]["id"])
        for c in payload["contradictions"]
    }
    in_queue = (mem_a, mem_b) in queue_pair_ids or (mem_b, mem_a) in queue_pair_ids
    if not in_queue:
        rels = brain_client.relations(mem_a).get("relations", []) + \
               brain_client.relations(mem_b).get("relations", [])
        assert any(r.get("relation_type") == "contradicts" for r in rels), \
            f"neither queue entry nor contradicts relation found for {mem_a}/{mem_b}"


def test_list_contradictions_unknown_project_is_empty(brain_client):
    payload = brain_client.list_contradictions(project="does-not-exist-zzz")
    assert payload["contradictions"] == []
```

Note: `unique_project_name` fixture already exists (used in `tests/test_contradiction_detection.py:10`). If it doesn't, the implementer must add it — check `tests/conftest.py` first; if missing, define it as a session fixture returning `lambda prefix: f"{prefix}-{uuid.uuid4().hex[:8]}"`.

- [ ] **Step 6: Run the tests**

```bash
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_reflection_observability.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add api-server/server.py tests/conftest.py tests/test_reflection_observability.py
git commit -m "feat(api): expose contradiction queue via REST and MCP"
```

---

## Task 4: `get_brain_activity_payload` — combined timeline

**Files:**
- Modify: `api-server/server.py`.
- Modify: `tests/conftest.py`.
- Modify: `tests/test_reflection_observability.py`.

This task composes the two previous helpers into a single "what happened in the last N hours" view — the primary UX the user asked for.

- [ ] **Step 1: Add the payload helper**

Insert after `list_contradictions_payload`:

```python
async def get_brain_activity_payload(
    hours: int = 24,
    project: Optional[str] = None,
) -> dict[str, Any]:
    """One-shot view of brain activity over the last N hours.

    Composes reflection_runs (finished within window), their promotions, and
    contradictions created within the window. `hours` is capped to [1, 168].
    """
    hours = max(1, min(int(hours), 168))
    if not pg_pool:
        return {
            "window_hours": hours,
            "project": project,
            "reflection_runs": [],
            "contradictions_new": [],
            "contradictions_resolved": [],
            "stats": {"runs": 0, "promotions": 0, "new_contradictions": 0, "resolved_contradictions": 0},
        }

    cutoff_sql = f"NOW() - INTERVAL '{hours} hours'"

    async with pg_pool.acquire() as conn:
        project_id = await _resolve_project_id(conn, project)
        if project and project_id is None:
            return {
                "window_hours": hours,
                "project": project,
                "reflection_runs": [],
                "contradictions_new": [],
                "contradictions_resolved": [],
                "stats": {"runs": 0, "promotions": 0, "new_contradictions": 0, "resolved_contradictions": 0},
            }

        # Reflection runs in window.
        if project_id is None:
            run_rows = await conn.fetch(
                f"""
                SELECT id, mode, status, model, input_count, promoted_count,
                       error, started_at, finished_at
                FROM reflection_runs
                WHERE started_at >= {cutoff_sql}
                ORDER BY started_at DESC
                """
            )
        else:
            run_rows = await conn.fetch(
                f"""
                SELECT DISTINCT r.id, r.mode, r.status, r.model, r.input_count,
                       r.promoted_count, r.error, r.started_at, r.finished_at
                FROM reflection_runs r
                JOIN reflection_promotions p ON p.run_id = r.id
                WHERE r.started_at >= {cutoff_sql} AND p.project_id = $1
                ORDER BY r.started_at DESC
                """,
                project_id,
            )

        runs = [serialize_row(r) for r in run_rows]
        promotion_total = 0
        if runs:
            run_ids = [uuid.UUID(r["id"]) for r in runs]
            promo_query = """
                SELECT rp.run_id, rp.item_type, rp.item_hash, rp.target_ref,
                       rp.created_at, p.name AS project
                FROM reflection_promotions rp
                LEFT JOIN projects p ON p.id = rp.project_id
                WHERE rp.run_id = ANY($1::uuid[])
            """
            params: list[Any] = [run_ids]
            if project_id is not None:
                promo_query += " AND rp.project_id = $2"
                params.append(project_id)
            promo_query += " ORDER BY rp.created_at ASC"
            promo_rows = await conn.fetch(promo_query, *params)
            by_run: dict[str, list[dict[str, Any]]] = {r["id"]: [] for r in runs}
            for row in promo_rows:
                serialized = serialize_row(row) or {}
                run_key = serialized.pop("run_id", None)
                if run_key in by_run:
                    by_run[run_key].append(serialized)
                    promotion_total += 1
            for run in runs:
                run["promotions"] = by_run.get(run["id"], [])

        # Contradictions created in window.
        contra_new_query = f"""
            SELECT cq.id, cq.memory_a_id, cq.memory_b_id, cq.resolution_status,
                   cq.condition_text, cq.created_at,
                   ma.summary AS memory_a_summary, pa.name AS memory_a_project,
                   mb.summary AS memory_b_summary, pb.name AS memory_b_project
            FROM contradiction_queue cq
            LEFT JOIN memory_log ma ON ma.id = cq.memory_a_id
            LEFT JOIN memory_log mb ON mb.id = cq.memory_b_id
            LEFT JOIN projects  pa ON pa.id = ma.project_id
            LEFT JOIN projects  pb ON pb.id = mb.project_id
            WHERE cq.created_at >= {cutoff_sql}
        """
        contra_params: list[Any] = []
        if project_id is not None:
            contra_params.append(project_id)
            contra_new_query += f" AND (ma.project_id = ${len(contra_params)} OR mb.project_id = ${len(contra_params)})"
        contra_new_query += " ORDER BY cq.created_at DESC LIMIT 100"
        new_rows = await conn.fetch(contra_new_query, *contra_params)

        # Contradictions resolved in window.
        contra_resolved_query = f"""
            SELECT cq.id, cq.memory_a_id, cq.memory_b_id, cq.resolution_status,
                   cq.resolution_type, cq.resolved_at, cq.condition_text,
                   ma.summary AS memory_a_summary, pa.name AS memory_a_project,
                   mb.summary AS memory_b_summary, pb.name AS memory_b_project
            FROM contradiction_queue cq
            LEFT JOIN memory_log ma ON ma.id = cq.memory_a_id
            LEFT JOIN memory_log mb ON mb.id = cq.memory_b_id
            LEFT JOIN projects  pa ON pa.id = ma.project_id
            LEFT JOIN projects  pb ON pb.id = mb.project_id
            WHERE cq.resolved_at IS NOT NULL AND cq.resolved_at >= {cutoff_sql}
        """
        resolved_params: list[Any] = []
        if project_id is not None:
            resolved_params.append(project_id)
            contra_resolved_query += f" AND (ma.project_id = ${len(resolved_params)} OR mb.project_id = ${len(resolved_params)})"
        contra_resolved_query += " ORDER BY cq.resolved_at DESC LIMIT 100"
        resolved_rows = await conn.fetch(contra_resolved_query, *resolved_params)

    def _pack(row):
        data = serialize_row(row) or {}
        data["memory_a"] = {
            "id": data.pop("memory_a_id", None),
            "summary": data.pop("memory_a_summary", None),
            "project": data.pop("memory_a_project", None),
        }
        data["memory_b"] = {
            "id": data.pop("memory_b_id", None),
            "summary": data.pop("memory_b_summary", None),
            "project": data.pop("memory_b_project", None),
        }
        return data

    contradictions_new = [_pack(r) for r in new_rows]
    contradictions_resolved = [_pack(r) for r in resolved_rows]

    return {
        "window_hours": hours,
        "project": project,
        "reflection_runs": runs,
        "contradictions_new": contradictions_new,
        "contradictions_resolved": contradictions_resolved,
        "stats": {
            "runs": len(runs),
            "promotions": promotion_total,
            "new_contradictions": len(contradictions_new),
            "resolved_contradictions": len(contradictions_resolved),
        },
    }
```

- [ ] **Step 2: Add REST endpoint**

Insert after `api_list_contradictions`:

```python
@app.get("/api/brain/activity")
async def api_brain_activity(hours: int = 24, project: Optional[str] = None):
    return await get_brain_activity_payload(hours=hours, project=project)
```

- [ ] **Step 3: Add MCP tool**

Insert after `list_contradictions`:

```python
@mcp.tool()
async def get_brain_activity(hours: int = 24, project: Optional[str] = None) -> str:
    """Resumen de actividad del cerebro en las últimas N horas: consolidaciones + contradicciones.

    Cuándo usar:
    - Cuando el usuario pregunte "¿qué ha pasado en mi cerebro hoy?".
    - Para un informe rápido antes de empezar a trabajar con memoria.
    - Para auditar cambios tras un ciclo de reflexión.

    Cómo usar:
    - `hours`: ventana temporal (1..168, default 24).
    - `project`: opcional, filtra todo al proyecto dado.

    Devuelve:
    - JSON con `reflection_runs` (con sus promotions), `contradictions_new`,
      `contradictions_resolved` y `stats` agregadas.
    - `ERROR ...` si no puede obtenerse la información.
    """
    try:
        payload = await get_brain_activity_payload(hours=hours, project=project)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.exception("get_brain_activity fallo")
        return f"ERROR {exc}"
```

- [ ] **Step 4: Add BrainClient helper**

Edit `tests/conftest.py`, after `list_contradictions`:

```python
    def brain_activity(self, hours: int = 24, project: Optional[str] = None):
        params: dict[str, Any] = {"hours": hours}
        if project:
            params["project"] = project
        return self.get("/api/brain/activity", params=params)
```

- [ ] **Step 5: Write integration tests**

Append to `tests/test_reflection_observability.py`:

```python
def test_brain_activity_shape(brain_client):
    payload = brain_client.brain_activity(hours=24)
    assert payload["window_hours"] == 24
    assert set(["reflection_runs", "contradictions_new", "contradictions_resolved", "stats"]).issubset(payload)
    stats = payload["stats"]
    for key in ("runs", "promotions", "new_contradictions", "resolved_contradictions"):
        assert key in stats
        assert isinstance(stats[key], int)


def test_brain_activity_hours_clamped(brain_client):
    payload = brain_client.brain_activity(hours=9999)
    assert payload["window_hours"] == 168


def test_brain_activity_unknown_project_is_empty(brain_client):
    payload = brain_client.brain_activity(hours=24, project="does-not-exist-zzz")
    assert payload["reflection_runs"] == []
    assert payload["contradictions_new"] == []
    assert payload["contradictions_resolved"] == []
    assert payload["stats"]["runs"] == 0
```

- [ ] **Step 6: Run the full test file**

```bash
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_reflection_observability.py -v
```

Expected: all tests pass (Task 2 + Task 3 + Task 4 tests = 11 tests).

- [ ] **Step 7: Commit**

```bash
git add api-server/server.py tests/conftest.py tests/test_reflection_observability.py
git commit -m "feat(api): expose 24h brain activity timeline via REST and MCP"
```

---

## Task 5: Regression check + docs

**Files:**
- Modify: `CLAUDE.md`.

- [ ] **Step 1: Run the full deterministic suite**

```bash
make test-deterministic
```

Expected: no regressions. If anything in `test_memory_brain_behavior.py` or `test_contradiction_detection.py` breaks, it's a bug in the new code — fix before proceeding, do not retry in a loop.

- [ ] **Step 2: Add a one-line pointer in CLAUDE.md**

Edit `CLAUDE.md`. Under the "Plasticity Concepts" section, append a new subsection:

```markdown
## Observability

Three MCP tools / REST endpoints expose what the reflection worker has done:

- `list_recent_consolidations` → `GET /api/reflections/runs` — recent runs + what each promoted
- `list_contradictions` → `GET /api/contradictions` — detected conflicts (pending/suspected/resolved)
- `get_brain_activity` → `GET /api/brain/activity` — combined last-N-hours timeline

Use these to answer "¿qué se consolidó?" / "¿hay contradicciones?" without touching Postgres directly.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document reflection observability endpoints"
```

---

## Self-review notes (for the implementer)

- **No schema changes.** If you find yourself writing `CREATE TABLE` or `ALTER TABLE`, stop — the plan is only read-side.
- **No UI changes.** The user explicitly deferred UI work.
- **Parameterized SQL.** Every user input goes through `$N` placeholders. The only raw-interpolated values are the clamped integer `hours` inside `INTERVAL 'N hours'` (safe because it's clamped to `[1, 168]` and cast to int first). Do not relax this.
- **Project filter semantics:** "unknown project → empty result" (not 404). This matches the style of other `/api/*` endpoints and avoids leaking project existence.
- **Contradiction test is lenient by design.** The auto-link pipeline may decide to either enqueue to `contradiction_queue` (suspected) OR create a `contradicts` relation directly (strong), depending on score. The test accepts either outcome — do not tighten it.
- **Do NOT** try to join `reflection_promotions.target_ref` to `memory_log`. It's a free-form string, not a FK.
