# Heartbeat Monitor — Living Proof System

## Overview

A Docker service (`heartbeat-monitor`) that periodically injects domain-realistic trap memories into the brain and verifies that every biological process (vectorization, synapse formation, contradiction detection, consolidation, myelin strengthening, Ebbinghaus decay, REM pruning) is working correctly. Exposes results via a new `/api/heartbeat/status` endpoint.

## Goals

1. **Prove the biology works** — automated, continuous verification that every biological process produces measurable effects on injected memories.
2. **Two modes** — accelerated (demo in ~10min) and production (long-running, hourly injection).
3. **Observable** — console logs for real-time, API endpoint for historical status, queryable from Brain UI or curl.

## Architecture

```
heartbeat-monitor (Docker, profile: heartbeat)
  │
  ├─ Phase 1: INJECT → POST /api/memories (trap batches)
  │                    POST /api/sessions, /api/plasticity/session
  │                    POST /api/project-bridges
  │
  ├─ Phase 2: SLEEP  → POST /api/test/trigger-deep-sleep
  │                    (polls until deep sleep completes)
  │
  ├─ Phase 3: VERIFY → GET /brain/health
  │                    GET /api/memories/{id}
  │                    GET /api/relations?memory_id={id}
  │                    POST /api/heartbeat/report (persist results)
  │
  └─ Loop back to Phase 1

reflection-worker
  │
  └─ handle_manual_deep_sleep() — polls manual_deep_sleep_runs table,
     triggers NREM+REM on demand
```

The heartbeat-monitor is a pure HTTP client. It never touches Postgres or Redis directly.

## Trap Batches

Each cycle injects 5 batches designed to provoke specific biological processes. All content uses the photovoltaic/SCADA/industrial domain.

### Batch 1 — Cluster base (3 memories, same project)

| # | content | memory_type | tags |
|---|---------|-------------|------|
| 1 | "La monitorización de inversores fotovoltaicos requiere lectura de registros Modbus TCP cada 10 segundos para detectar fallos de string" | architecture | inversores,modbus,monitorización |
| 2 | "Decidimos usar polling síncrono para la lectura de inversores porque el firmware no soporta notificaciones push" | decision | inversores,polling,firmware |
| 3 | "Los inversores Huawei SUN2000 reportan potencia activa en el registro 32080 con factor de escala 1000" | observation | inversores,huawei,registros |

**Provokes:** automatic relationship formation (synapse tiers 1-2), keyphrase extraction, embedding vectorization.

### Batch 2 — Contradiction (2 memories, same project)

| # | content | memory_type | tags |
|---|---------|-------------|------|
| 4 | "Usar polling SCADA cada 5 segundos es la mejor práctica para monitorización en tiempo real de inversores" | decision | scada,polling,inversores |
| 5 | "No usar polling SCADA, implementar arquitectura event-driven con MQTT porque el polling cada 5 segundos satura el bus de comunicaciones" | decision | scada,polling,mqtt,inversores |

**Provokes:** contradiction detection (negation patterns + semantic overlap), contradiction queue entry, NREM resolution.

### Batch 3 — Cross-project (2 memories in new project + bridge)

| # | content | memory_type | tags |
|---|---------|-------------|------|
| 6 | "El sistema de mantenimiento predictivo usa los mismos registros Modbus de inversores para calcular degradación de paneles" | architecture | mantenimiento-predictivo,modbus,inversores |
| 7 | "La correlación entre temperatura de módulo y potencia de salida permite predecir fallos antes de que ocurran" | observation | mantenimiento-predictivo,temperatura,predicción |

Bridge reason: "Los datos de monitorización de inversores alimentan el modelo de mantenimiento predictivo."

**Provokes:** cross-project bridge creation, permeability scoring, cross-project myelin (after co-activation in NREM).

### Batch 4 — Reinforcement (plasticity session accessing batch 1 memories)

A plasticity session with `summary`, `goal`, `outcome` referencing batch 1 content. Triggers `apply_session_plasticity()`.

**Provokes:** activation propagation, reinforcement_count increment, stability_score increase (Ebbinghaus review), consolidated_activations.

### Batch 5 — Cold memory (1 memory, never accessed)

| # | content | memory_type | tags |
|---|---------|-------------|------|
| 8 | "El protocolo IEC 61850 fue evaluado como alternativa a Modbus pero descartado por complejidad de implementación" | observation | iec-61850,descartado,evaluación |

**Provokes:** decay target. After REM phase, this memory should have lower stability_score than initially.

## Verification Checks

After deep sleep, the heartbeat takes a snapshot and runs these checks:

| Check ID | What it verifies | Pass condition |
|----------|-----------------|----------------|
| `relationships_formed` | Batch 1 memories auto-linked | At least 2 relations exist between the 3 memories |
| `contradiction_detected` | Batch 2 produced contradiction signal | Any relation between mem 4-5 has `contradiction_score > 0` OR `relation_type = contradicts` OR entry exists in contradiction queue |
| `contradiction_resolved` | NREM resolved the contradiction | After deep sleep: contradiction queue entry status is `resolved`, OR a synthesis memory exists with `derived_from` relation to mem 4 or 5 |
| `cross_project_myelin` | Batch 3 cross-project relations strengthened | At least 1 cross-project relation has `myelin_score > 0` after NREM co-activation strengthening |
| `reinforcement_applied` | Batch 4 plasticity session reinforced batch 1 | At least 1 memory from batch 1 has `reinforcement_count > initial` (checked via relations endpoint) |
| `stability_increased` | Accessed memories gained stability | At least 1 memory from batch 1 has higher `stability_score` than initial snapshot |
| `cold_memory_decayed` | Batch 5 memory lost stability after REM | Memory 8 has `stability_score` lower than initial snapshot after REM decay pass |
| `overall_health_stable` | Brain health didn't degrade | `overall_health` from `/brain/health` is >= previous cycle's value (or >= 0.3 on first cycle) |

A check that cannot be evaluated (e.g., deep sleep didn't run) is marked `skipped`, not `failed`.

## New API Endpoints

### `POST /api/test/trigger-deep-sleep`

**Guard:** Only available when `AI_MEMORY_TEST_MODE=true` or `HEARTBEAT_ENABLED=true`.

**Behavior:** Inserts a row into `manual_deep_sleep_runs` with status `pending`. The reflection-worker picks it up on next poll cycle (30s max).

**Response:**
```json
{"queued": true, "run_id": "uuid"}
```

### `GET /api/test/deep-sleep-status/{run_id}`

**Response:**
```json
{"run_id": "uuid", "status": "completed", "stats": {...}}
```

Used by heartbeat to poll until deep sleep finishes.

### `POST /api/heartbeat/report`

**Guard:** Requires API key.

**Body:**
```json
{
  "cycle_id": "hb-cycle-0012",
  "mode": "accelerated",
  "phase": "completed",
  "injected_memories": 8,
  "checks": [
    {"name": "relationships_formed", "passed": true, "detail": "3/3 memories linked"},
    ...
  ],
  "passed": 8,
  "failed": 1
}
```

**Behavior:** Upserts into `heartbeat_cycles` table.

### `GET /api/heartbeat/status`

**Response:**
```json
{
  "enabled": true,
  "mode": "accelerated",
  "cycles_completed": 12,
  "last_cycle_at": "2026-04-11T15:30:00Z",
  "checks_summary": {
    "total": 108,
    "passed": 102,
    "failed": 6,
    "pass_rate": 0.944
  },
  "latest_cycle": {
    "cycle_id": "hb-cycle-0012",
    "checks": [...]
  },
  "history": [
    {"cycle_id": "hb-cycle-0011", "at": "...", "passed": 9, "failed": 0}
  ]
}
```

## New Database Tables

### `manual_deep_sleep_runs`

```sql
CREATE TABLE manual_deep_sleep_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    stats JSONB
);
```

### `heartbeat_cycles`

```sql
CREATE TABLE heartbeat_cycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id TEXT UNIQUE NOT NULL,
    mode TEXT NOT NULL,
    phase TEXT NOT NULL,
    injected_memories INT DEFAULT 0,
    checks JSONB DEFAULT '[]',
    passed INT DEFAULT 0,
    failed INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

## Docker Integration

### New service in docker-compose.yaml

```yaml
heartbeat-monitor:
  build:
    context: .
    dockerfile: heartbeat-monitor/Dockerfile
  depends_on:
    api-server:
      condition: service_healthy
    reflection-worker:
      condition: service_healthy
  environment:
    - AI_MEMORY_BASE_URL=http://api-server:8050
    - MEMORY_API_KEY=${MEMORY_API_KEY}
    - HEARTBEAT_MODE=accelerated
    - HEARTBEAT_INJECT_INTERVAL=30
    - HEARTBEAT_SLEEP_INTERVAL=300
    - HEARTBEAT_VERIFY_INTERVAL=120
    - HEARTBEAT_ENABLED=true
  healthcheck:
    test: ["CMD-SHELL", "[ $$(( $$(date +%s) - $$(stat -c %Y /tmp/heartbeat-alive 2>/dev/null || echo 0) )) -lt 300 ]"]
    interval: 30s
    retries: 5
    start_period: 60s
  restart: unless-stopped
  profiles:
    - heartbeat
```

**Profile `heartbeat`** means it does NOT start with `docker compose up -d`. Requires explicit:

```bash
docker compose --profile heartbeat up -d
```

### Environment variable overrides

| Variable | Accelerated (default) | Production |
|----------|----------------------|------------|
| `HEARTBEAT_MODE` | `accelerated` | `production` |
| `HEARTBEAT_INJECT_INTERVAL` | `30` | `3600` |
| `HEARTBEAT_SLEEP_INTERVAL` | `300` | `86400` |
| `HEARTBEAT_VERIFY_INTERVAL` | `120` | `7200` |

### Makefile targets

```makefile
heartbeat-fast:   docker compose --profile heartbeat up -d --build
heartbeat-prod:   HEARTBEAT_MODE=production ... docker compose --profile heartbeat up -d --build
heartbeat-status: curl -s -H "X-API-Key: $$MEMORY_API_KEY" http://127.0.0.1:8050/api/heartbeat/status | python -m json.tool
heartbeat-stop:   docker compose --profile heartbeat stop heartbeat-monitor
```

## Reflection Worker Changes

Add `handle_manual_deep_sleep()` to the `run_loop()` polling cycle, same pattern as `handle_manual_runs()`:

1. Query `manual_deep_sleep_runs` for `status = 'pending'` ORDER BY `requested_at` LIMIT 1
2. If found, set status to `running`, execute `handle_deep_sleep()`, set status to `completed` with stats
3. On failure, set status to `failed`

## Cleanup

The heartbeat creates projects with prefix `heartbeat-`. At the start of each cycle, it deletes the previous cycle's projects via `DELETE /api/projects/{name}` before injecting new ones. This prevents unbounded data accumulation.

## File Structure

```
heartbeat-monitor/
  Dockerfile
  monitor.py          # Main loop: inject → sleep → verify
  batches.py          # Trap batch definitions (content, expected outcomes)
  checks.py           # Verification logic (snapshot comparison)
  client.py           # HTTP client wrapper (thin, reuses conftest pattern)
```
