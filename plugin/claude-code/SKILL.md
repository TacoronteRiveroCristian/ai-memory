---
name: memory-brain
description: Proactive memory save protocol for AI Memory Brain — teaches agents when and how to persist knowledge automatically.
---

# Proactive Memory Save Protocol

You are connected to **AI Memory Brain**, a persistent memory system shared across agents and sessions. Your responsibility is to save knowledge proactively as you work — do not wait to be asked.

## Core Principle

Every insight, decision, error, and pattern you encounter should be evaluated for persistence. If a future agent (or future-you) would benefit from knowing it, save it now.

---

## Session Lifecycle

### 1. Session Start

Immediately call `get_project_context` to load prior knowledge:

```json
{
  "project_name": "my-project",
  "include_related": true
}
```

This returns recent memories, active tasks, open errors, and cross-project bridges. Read it carefully — avoid duplicating what already exists.

### 2. During the Session

Save continuously as triggers fire. Do NOT batch saves at the end of the session — you may be interrupted, and unsaved knowledge is lost.

### 3. Session End

Call `record_session_summary` with a concise summary of what was accomplished:

```json
{
  "project": "my-project",
  "session_summary": "Migrated user auth from JWT to session cookies. Fixed CORS regression on /api/login. Discovered that Redis session store needs TTL tuning.",
  "agent_id": "claude-code"
}
```

---

## Triggers and Actions

### Decision Made -> `store_decision`

When you make or observe a meaningful technical decision.

```json
{
  "project": "my-project",
  "decision": "Use connection pooling via pgBouncer instead of per-request Postgres connections",
  "alternatives": "1) Direct connections with higher pool size — rejected due to PG max_connections limit. 2) Application-level pooling — rejected because pgBouncer handles failover better.",
  "context": "Load testing showed connection exhaustion at 200 concurrent users. P95 latency spiked to 4s.",
  "importance": 0.85,
  "tags": "backend/postgres,pattern/scaling,infra/pgbouncer"
}
```

### Bug / Error Found -> `store_error`

When you encounter a bug, exception, or unexpected behavior.

```json
{
  "project": "my-project",
  "error_text": "RuntimeError: Event loop is closed — raised in aiohttp cleanup when mixing sync/async test fixtures",
  "context": "Occurs only when pytest-asyncio runs after synchronous tests that imported aiohttp. Root cause: aiohttp registers an atexit handler that closes the default loop.",
  "resolution": "Use a dedicated event loop per test via @pytest.fixture(scope='function') with loop_factory.",
  "severity": "medium",
  "tags": "bug/resolved,backend/testing,tech/asyncio"
}
```

### Pattern / Insight Discovered -> `store_memory` (type=observation)

When you notice a recurring pattern, non-obvious behavior, or architectural insight.

```json
{
  "content": "Redis SCAN with large MATCH patterns degrades to O(N) on keyspaces > 1M keys. For the activation-propagation cache, prefix keys with 'act:{project}:' and use a dedicated Redis DB to keep the keyspace small.",
  "project": "my-project",
  "memory_type": "observation",
  "tags": "pattern/performance,backend/redis,concept/keyspace-design",
  "importance": 0.7
}
```

### Architecture Discussed -> `store_memory` (type=decision)

When architectural choices are made or clarified during conversation.

```json
{
  "content": "The reflection worker runs as a separate container rather than a FastAPI background task because: (1) it needs its own resource limits (DeepSeek calls are CPU-heavy), (2) it must survive API server restarts, (3) it can be scaled independently.",
  "project": "my-project",
  "memory_type": "decision",
  "tags": "concept/architecture,backend/workers,pattern/separation-of-concerns",
  "importance": 0.85
}
```

### Task State Changes -> `update_task_state`

When a task moves to a new phase (started, blocked, completed).

```json
{
  "task_id": "abc-123",
  "new_state": "completed",
  "note": "All endpoints migrated to v2 schema. Backward-compat shim left for /api/v1/search."
}
```

### Error Resolved -> `store_error` (with resolution)

Same as bug found, but include the resolution field. This is critical — future agents need both the problem AND the fix.

### Cross-Project Connection -> `bridge_projects`

When you discover that knowledge in one project is relevant to another.

```json
{
  "project_a": "ai-memory",
  "project_b": "data-pipeline",
  "bridge_context": "Both projects use Qdrant for vector search. The embedding cache strategy from ai-memory (Redis namespace + TTL) would solve the duplicate-embedding problem in data-pipeline.",
  "importance": 0.7
}
```

### Memories Relate -> `link_memories`

When two existing memories are conceptually connected.

```json
{
  "source_memory_id": "mem-111",
  "target_memory_id": "mem-222",
  "relation_type": "extends",
  "weight": 0.8
}
```

---

## Importance Calibration

| Score | Level    | Examples                                                       |
|-------|----------|----------------------------------------------------------------|
| 0.5   | Routine  | Code style fix, minor refactor, dependency bump                |
| 0.7   | Notable  | New endpoint added, config change, test coverage gap found     |
| 0.85  | Important| Architectural decision, tricky bug with non-obvious root cause |
| 0.95  | Critical | Data-loss risk, security vulnerability, breaking API change    |

When in doubt, round up. It is better to slightly over-value a memory than to lose an important one to decay.

---

## Tag Vocabulary

Use hierarchical, descriptive tags. Common prefixes:

| Prefix      | Usage                                    | Examples                          |
|-------------|------------------------------------------|-----------------------------------|
| `backend/`  | Server-side components                   | backend/api, backend/postgres     |
| `frontend/` | Client-side components                   | frontend/react, frontend/css      |
| `bug/`      | Bug status                               | bug/open, bug/resolved, bug/flaky |
| `pattern/`  | Recurring patterns and practices         | pattern/retry, pattern/caching    |
| `tech/`     | Specific technologies                    | tech/redis, tech/docker           |
| `concept/`  | Abstract concepts and principles         | concept/architecture, concept/security |
| `infra/`    | Infrastructure and deployment            | infra/ci, infra/k8s               |

Combine multiple tags: `backend/api,bug/resolved,tech/fastapi`

---

## Anti-Patterns (Do NOT Save)

- **Conversation summaries** — the session summary tool handles this; don't store chat recaps as memories.
- **Obvious code facts** — "this function takes two arguments" adds no value; save the *why* behind non-obvious signatures.
- **Temporary debug info** — print statements, temp logging, scratch calculations belong in the session, not in memory.
- **Things already in git** — code diffs, commit messages, and file contents are versioned; save the *reasoning* behind changes, not the changes themselves.
- **Trivial decisions** — "used camelCase because that's the project style" is not worth persisting.

---

## Quality Guidelines

1. **Self-contained content**: Each memory should make sense without reading the conversation. Include enough context that a different agent can understand it.
2. **WHY over WHAT**: "We chose Redis for the cache because its TTL semantics match our decay model" beats "Added Redis cache."
3. **Include alternatives for decisions**: Future agents need to know what was rejected and why, not just what was chosen.
4. **Error signatures**: Always include the exact error message or traceback — it enables future pattern matching.
5. **Atomic memories**: One concept per memory. If you have three insights, make three saves.
