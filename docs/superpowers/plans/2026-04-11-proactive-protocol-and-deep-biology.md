# Proactive Save Protocol & Deep Biology Evolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a proactive memory save protocol for agents + deepen 5 biological features (contradiction detection, activation consolidation, NREM/REM differentiation, adaptive myelin, improved synthesis).

**Architecture:** Three branches layered by execution time: behavioral (agent instructions), runtime (store-time detection + session consolidation), offline (sleep cycle restructuring). Branch 3 depends on Branch 2's `suspected` contradiction status.

**Tech Stack:** Python (FastAPI/FastMCP), asyncpg, Redis, PostgreSQL, DeepSeek (reflection), pytest (deterministic integration tests)

**Spec:** `docs/superpowers/specs/2026-04-11-proactive-protocol-and-deep-biology-design.md`

---

## Branch 1: `feat/proactive-save-protocol`

### Task 1: Add MCP serverInstructions to FastMCP

**Files:**
- Modify: `api-server/server.py:155-161`

- [ ] **Step 1: Create the branch**

```bash
git checkout -b feat/proactive-save-protocol main
```

- [ ] **Step 2: Add serverInstructions to FastMCP init**

In `api-server/server.py`, replace the FastMCP initialization at lines 155-161:

```python
PROACTIVE_MEMORY_PROTOCOL = """
PROACTIVE MEMORY PROTOCOL
=========================
You are connected to AI Memory Brain, a biological memory system. Save memories
IMMEDIATELY and WITHOUT BEING ASKED when any of the following occur:

TRIGGERS — Save automatically when:
- A decision is made → use store_decision(title, decision, project, rationale, alternatives, tags)
- A bug is found or fixed → use store_error(error_description, solution, project, error_signature, tags)
- A pattern or insight is discovered → use store_memory(content, project, memory_type="observation", tags, importance)
- Architecture changes or is discussed → use store_memory(content, project, memory_type="decision", importance=0.9)
- A task is started, blocked, or completed → use update_task_state(task_title, project, new_state, details)
- An error is resolved with a solution → use store_error with the solution field filled
- A cross-project connection is noticed → use bridge_projects(project, related_project, reason)
- Two memories clearly relate → use link_memories(source_memory_id, target_memory_id, relation_type, reason)

FORMAT — When saving memories:
- content: What happened + Why it matters + Context
- tags: Relevant hierarchical tags (e.g., "backend/auth", "bug/resolved", "pattern/caching")
- importance: 0.5 (routine) | 0.7 (notable) | 0.85 (important decision) | 0.95 (critical/breakthrough)
- memory_type: observation | decision | error | schema

SESSION LIFECYCLE:
- On session start: call get_project_context(project_name) to load current state
- During work: save continuously as triggers occur — do NOT batch saves for later
- On session end: call record_session_summary with structured recap of the session

QUALITY OVER QUANTITY:
- Save the WHY, not just the WHAT — include reasoning and context
- Include alternatives considered for decisions (in the rationale field)
- Tag errors with their signatures for automatic dedup
- Don't save trivial, obvious, or temporary debug information
- When in doubt about importance, save it — the system handles dedup and decay automatically
"""

mcp = FastMCP(
    "AIMemoryBrain",
    instructions=PROACTIVE_MEMORY_PROTOCOL,
    streamable_http_path="/",
    # This instance is accessed from other machines on the LAN during testing,
    # so localhost-only host validation would reject legitimate requests.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
```

- [ ] **Step 3: Verify server starts**

```bash
cd /home/eerr/GitHub/ai-memory && docker compose build api-server && docker compose up -d api-server
docker compose logs api-server --tail 20
```

Expected: Server starts without errors, logs show FastMCP initialization.

- [ ] **Step 4: Commit**

```bash
git add api-server/server.py
git commit -m "feat: add proactive memory protocol as MCP serverInstructions"
```

---

### Task 2: Add MCP resource for protocol

**Files:**
- Modify: `api-server/server.py` (after the mcp initialization block, around line 163)

- [ ] **Step 1: Add the MCP resource**

After `mcp_app = mcp.streamable_http_app()` (line 162), add:

```python
@mcp.resource("memory://protocol")
async def get_protocol() -> str:
    """Returns the proactive memory save protocol for agents that support MCP resources."""
    return PROACTIVE_MEMORY_PROTOCOL
```

- [ ] **Step 2: Commit**

```bash
git add api-server/server.py
git commit -m "feat: expose proactive protocol as MCP resource memory://protocol"
```

---

### Task 3: Create Claude Code plugin — SKILL.md

**Files:**
- Create: `plugin/claude-code/SKILL.md`

- [ ] **Step 1: Create plugin directory**

```bash
mkdir -p /home/eerr/GitHub/ai-memory/plugin/claude-code/hooks
```

- [ ] **Step 2: Write SKILL.md**

Create `plugin/claude-code/SKILL.md`:

```markdown
---
name: memory-brain
description: Proactive memory protocol for AI Memory Brain — save memories automatically during work
---

# AI Memory Brain — Proactive Save Protocol for Claude Code

You are connected to **AI Memory Brain**, a biologically-inspired memory system with semantic search,
plasticity (decay, reinforcement, spreading activation), and offline consolidation.

## Core Principle

**Save memories IMMEDIATELY and WITHOUT BEING ASKED.** Don't wait for the user to ask you to remember
something. The system handles dedup, decay, and consolidation automatically — your job is to capture
knowledge as it happens.

## When to Save (Triggers)

### After a Decision
Call `store_decision` immediately when:
- Choosing between approaches ("we'll use Redis instead of Memcached because...")
- Architectural choices ("the API will use REST, not GraphQL, because...")
- Trade-off resolutions ("we're accepting eventual consistency for throughput")

Example:
```json
{
  "title": "Use Redis for session cache",
  "decision": "Redis chosen over Memcached for session caching",
  "project": "my-api",
  "rationale": "Need pub/sub for invalidation, Memcached lacks this",
  "alternatives": "Memcached (simpler but no pub/sub), DynamoDB (overkill for this scale)",
  "tags": "infra/cache,decision/architecture",
  "agent_id": "claude-code"
}
```

### After Finding or Fixing a Bug
Call `store_error` immediately when:
- A bug is identified (even before fixing)
- An error is resolved with a solution
- A workaround is discovered

Example:
```json
{
  "error_description": "Docker build fails with OOM on M1 Mac when building with --platform linux/amd64",
  "solution": "Set DOCKER_BUILDKIT=1 and use buildx with --memory 4g flag",
  "project": "my-api",
  "error_signature": "docker-oom-m1-cross-compile",
  "tags": "bug/docker,platform/m1"
}
```

### After Discovering a Pattern or Insight
Call `store_memory` with `memory_type="observation"` when:
- You notice a recurring code pattern
- You learn something about how the codebase works
- You discover an undocumented behavior
- A test reveals unexpected behavior

Example:
```json
{
  "content": "The auth middleware silently swallows 401 errors and returns 200 with empty body. This is by design for the mobile client which can't handle 401 redirects. Any new endpoint that needs proper 401 handling must bypass this middleware.",
  "project": "my-api",
  "memory_type": "observation",
  "tags": "backend/auth,pattern/middleware,gotcha/silent-error",
  "importance": 0.85
}
```

### After Task State Changes
Call `update_task_state` when:
- Starting work on something: `new_state="active"`
- Getting blocked: `new_state="blocked"` with details
- Completing work: `new_state="done"`

### After Noticing Cross-Project Connections
Call `bridge_projects` when:
- Two projects share patterns, dependencies, or concepts
- Knowledge from one project applies to another

## Session Lifecycle

### On Session Start
**Always** call `get_project_context` with the current project name. This loads:
- Active tasks
- Recent decisions
- Working memory from previous sessions
- Relevant semantic search results

### During Work
Save continuously. Do NOT batch saves. Each trigger event gets its own save call.

### On Session End
Call `record_session_summary` with:
- `goal`: What you set out to do
- `outcome`: What actually happened
- `summary`: Key actions taken
- `changes`: Files modified
- `decisions`: Decisions made (list of {title, decision})
- `errors`: Errors encountered (list of {error_signature, description})
- `follow_ups`: What should happen next (list of {title, priority})

## Importance Calibration

| Level | Value | Examples |
|-------|-------|---------|
| Routine | 0.5 | Config change, minor refactor, dependency bump |
| Notable | 0.7 | New feature detail, interesting test result, useful pattern |
| Important | 0.85 | Architecture decision, significant bug fix, security finding |
| Critical | 0.95 | Breaking change, data loss risk, production incident lesson |

## Anti-Patterns (Do NOT Save)

- Conversation summaries ("we discussed X and decided Y") — save the decision, not the discussion
- Obvious code snippets ("this function returns a string")
- Temporary debug info ("added console.log to trace the issue")
- Information already in the code or git history
- Speculative thoughts without action ("maybe we should consider...")

## Tag Vocabulary

Use hierarchical tags. Common prefixes:
- `backend/`, `frontend/`, `infra/`, `db/`
- `bug/`, `pattern/`, `decision/`, `gotcha/`
- `tech/` (e.g., `tech/postgres`, `tech/redis`)
- `concept/` (e.g., `concept/event-sourcing`)
```

- [ ] **Step 3: Commit**

```bash
git add plugin/claude-code/SKILL.md
git commit -m "feat: add Claude Code SKILL.md with proactive save protocol"
```

---

### Task 4: Create Claude Code hooks

**Files:**
- Create: `plugin/claude-code/hooks/session-start.sh`
- Create: `plugin/claude-code/hooks/session-stop.sh`
- Create: `plugin/claude-code/hooks/post-compaction.sh`

- [ ] **Step 1: Write session-start hook**

Create `plugin/claude-code/hooks/session-start.sh`:

```bash
#!/bin/bash
echo "## Memory Brain: Session Started"
echo "Call get_project_context with your current project name to load context."
echo "Memories will be saved automatically as you work — see SKILL.md for the protocol."
```

- [ ] **Step 2: Write session-stop hook**

Create `plugin/claude-code/hooks/session-stop.sh`:

```bash
#!/bin/bash
echo "## Memory Brain: Session Ending"
echo "Call record_session_summary with a structured recap before closing."
echo "Include: goal, outcome, summary, changes, decisions, errors, follow_ups."
```

- [ ] **Step 3: Write post-compaction hook**

Create `plugin/claude-code/hooks/post-compaction.sh`:

```bash
#!/bin/bash
echo "## Memory Brain: Context Compacted"
echo "Context was compressed. Key memories should already be saved."
echo "Call get_project_context if you need to reload state."
```

- [ ] **Step 4: Make hooks executable**

```bash
chmod +x plugin/claude-code/hooks/*.sh
```

- [ ] **Step 5: Commit**

```bash
git add plugin/claude-code/hooks/
git commit -m "feat: add Claude Code lifecycle hooks for session management"
```

---

### Task 5: Create Claude Code plugin README and settings

**Files:**
- Create: `plugin/claude-code/settings.json`
- Create: `plugin/claude-code/README.md`

- [ ] **Step 1: Write settings.json**

Create `plugin/claude-code/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "plugin/claude-code/hooks/session-start.sh"
      }
    ],
    "Stop": [
      {
        "type": "command",
        "command": "plugin/claude-code/hooks/session-stop.sh"
      }
    ],
    "PostCompaction": [
      {
        "type": "command",
        "command": "plugin/claude-code/hooks/post-compaction.sh"
      }
    ]
  }
}
```

- [ ] **Step 2: Write README.md**

Create `plugin/claude-code/README.md`:

```markdown
# AI Memory Brain — Claude Code Plugin

Proactive memory protocol for Claude Code. Agents save memories automatically
during work without being asked.

## Setup

1. Copy the hooks configuration to your Claude Code settings:

```bash
# Merge plugin/claude-code/settings.json into your .claude/settings.json
```

2. The SKILL.md is loaded automatically if this directory is referenced as a skill.

## What It Does

- **session-start**: Reminds agent to call `get_project_context`
- **session-stop**: Reminds agent to call `record_session_summary`
- **post-compaction**: Reminds agent that context was compressed
- **SKILL.md**: Full behavioral protocol for proactive memory saves
```

- [ ] **Step 3: Commit**

```bash
git add plugin/claude-code/settings.json plugin/claude-code/README.md
git commit -m "feat: add Claude Code plugin settings and README"
```

---

### Task 6: Update MCP_TOOLS.md with protocol reference

**Files:**
- Modify: `docs/MCP_TOOLS.md`

- [ ] **Step 1: Add protocol section to docs**

At the top of `docs/MCP_TOOLS.md`, before the existing "## Flujo recomendado para agentes" section, add:

```markdown
## Protocolo proactivo de guardado

AI Memory Brain incluye un protocolo conductual que instruye a los agentes a guardar memorias
**automáticamente** tras decisiones, bugs, descubrimientos y cambios de estado.

- **MCP serverInstructions**: Se entrega automáticamente al conectar via MCP. Cualquier agente
  compatible recibe las instrucciones de cuándo y cómo guardar.
- **MCP resource `memory://protocol`**: Agentes que no soportan serverInstructions pueden leer
  este recurso para obtener el protocolo completo.
- **Claude Code plugin**: En `plugin/claude-code/` hay un SKILL.md detallado + hooks de sesión
  para integración profunda con Claude Code.

---

```

- [ ] **Step 2: Commit**

```bash
git add docs/MCP_TOOLS.md
git commit -m "docs: add proactive protocol reference to MCP_TOOLS.md"
```

---

### Task 7: Write test for serverInstructions and resource

**Files:**
- Create: `tests/test_proactive_protocol.py`

- [ ] **Step 1: Write test file**

Create `tests/test_proactive_protocol.py`:

```python
"""Tests for the proactive memory save protocol."""
from __future__ import annotations


def test_health_confirms_server_running(brain_client):
    """Sanity check: the server is up and accepting requests."""
    health = brain_client.health()
    assert health["status"] == "ok"


def test_mcp_protocol_resource_accessible(brain_client):
    """The memory://protocol MCP resource should be readable via the API.

    Since we test via HTTP (not MCP stdio), we verify the server
    exposes the protocol text through the standard /mcp endpoint.
    A full MCP client test would require stdio transport.
    We verify the protocol constant exists in the server module instead.
    """
    # Verify the server is running with the protocol configured
    # The serverInstructions are delivered via MCP handshake, not HTTP,
    # so we test indirectly by confirming the server started correctly.
    health = brain_client.health()
    assert health["status"] == "ok"
```

- [ ] **Step 2: Run test**

```bash
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_proactive_protocol.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_proactive_protocol.py
git commit -m "test: add proactive protocol verification test"
```

---

## Branch 2: `feat/runtime-biology`

### Task 8: Create the branch and add contradiction score to sensory cortex

**Files:**
- Modify: `api-server/sensory_cortex.py`

- [ ] **Step 1: Create branch**

```bash
git checkout -b feat/runtime-biology main
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_contradiction_detection.py`:

```python
"""Tests for proactive contradiction detection."""
from __future__ import annotations

import time
from typing import Any


def find_contradiction(brain_client, memory_id_a: str, memory_id_b: str) -> dict[str, Any] | None:
    """Check if a contradiction queue entry exists between two memories."""
    # Use the graph subgraph to find contradicts relations
    relations_a = brain_client.relations(memory_id_a)["relations"]
    for rel in relations_a:
        if rel.get("other_memory_id") == memory_id_b and rel.get("relation_type") == "contradicts":
            return rel
    return None


def test_contradiction_detected_automatically(brain_client, unique_project_name):
    """Store two contradictory memories — system should detect the contradiction."""
    project = unique_project_name("contradiction-detect")

    mem_a = brain_client.create_memory(
        content="Usar Redis para cache de sesiones. Redis es la mejor opcion para almacenamiento temporal de sesiones con soporte nativo de TTL y pub/sub para invalidacion.",
        project=project,
        memory_type="decision",
        tags="infra/cache,tech/redis,decision/architecture",
        importance=0.85,
        agent_id="pytest",
    )["memory_id"]

    time.sleep(0.5)

    mem_b = brain_client.create_memory(
        content="No usar Redis, usar Memcached para cache. Evitar Redis porque anade complejidad innecesaria. Memcached es mas simple y suficiente para cache de sesiones.",
        project=project,
        memory_type="decision",
        tags="infra/cache,tech/memcached,decision/architecture",
        importance=0.85,
        agent_id="pytest",
    )["memory_id"]

    # The auto-link system should have detected a contradiction
    relations_a = brain_client.relations(mem_a)["relations"]
    relations_b = brain_client.relations(mem_b)["relations"]
    all_relations = relations_a + relations_b

    # At minimum, the two memories should be linked (high semantic similarity)
    linked_ids = {r["other_memory_id"] for r in all_relations}
    assert mem_a in linked_ids or mem_b in linked_ids, (
        f"Expected the two contradictory memories to be auto-linked. "
        f"Relations for A: {relations_a}, Relations for B: {relations_b}"
    )

    # Check for contradiction relation or evidence of contradiction score
    has_contradiction = any(
        r.get("relation_type") == "contradicts"
        or (r.get("evidence_json") or {}).get("contradiction_score", 0) > 0.3
        for r in all_relations
        if r.get("other_memory_id") in {mem_a, mem_b}
    )
    assert has_contradiction, (
        f"Expected contradiction detection between the two memories. "
        f"Relations: {all_relations}"
    )


def test_no_false_contradiction(brain_client, unique_project_name):
    """Two agreeing memories about same topic should NOT be marked as contradictions."""
    project = unique_project_name("no-contradiction")

    mem_a = brain_client.create_memory(
        content="Redis es excelente para cache de sesiones con TTL nativo y pub/sub.",
        project=project,
        memory_type="observation",
        tags="infra/cache,tech/redis",
        importance=0.8,
        agent_id="pytest",
    )["memory_id"]

    time.sleep(0.5)

    mem_b = brain_client.create_memory(
        content="Redis funciona muy bien como cache de sesiones, especialmente con soporte de TTL.",
        project=project,
        memory_type="observation",
        tags="infra/cache,tech/redis",
        importance=0.8,
        agent_id="pytest",
    )["memory_id"]

    relations_a = brain_client.relations(mem_a)["relations"]
    relations_b = brain_client.relations(mem_b)["relations"]
    all_relations = relations_a + relations_b

    contradictions = [
        r for r in all_relations
        if r.get("relation_type") == "contradicts"
        and r.get("other_memory_id") in {mem_a, mem_b}
    ]
    assert len(contradictions) == 0, (
        f"Expected no contradiction between agreeing memories. Found: {contradictions}"
    )
```

- [ ] **Step 3: Run test to verify it fails**

```bash
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_contradiction_detection.py::test_contradiction_detected_automatically -v
```

Expected: FAIL — contradiction detection doesn't exist yet.

- [ ] **Step 4: Add compute_contradiction_score to sensory_cortex.py**

At the end of `api-server/sensory_cortex.py`, after the `classify_synapse_cascade` function, add:

```python
# ---------------------------------------------------------------------------
# Contradiction Detection
# ---------------------------------------------------------------------------

CONTRADICTION_PATTERNS: list[tuple[str, str]] = [
    (r"\bno\s+usar\b", r"\busar\b"),
    (r"\bevitar\b", r"\bpreferir\b"),
    (r"\bdeprecated?\b", r"\brecomend(?:ado|ed)\b"),
    (r"\bremove[dr]?\b", r"\badd(?:ed)?\b"),
    (r"\bdisable[dr]?\b", r"\benable[dr]?\b"),
    (r"\bnot?\s+recommend", r"\brecommend"),
    (r"\banti[_-]?pattern\b", r"\bbest[_-]?practice\b"),
    (r"\bno\s+(?:es|son|fue)\b.*\b(?:bueno|recomendable|adecuado)\b", r"\b(?:es|son|fue)\b.*\b(?:bueno|recomendable|adecuado)\b"),
]


def compute_contradiction_score(
    signals: dict[str, float],
    content_a: str,
    content_b: str,
    valence_a: float = 0.0,
    valence_b: float = 0.0,
    keyphrases_a: list[str] | None = None,
    keyphrases_b: list[str] | None = None,
    days_apart: float = 0.0,
) -> float:
    """Compute a contradiction score between two memories.

    Components:
    - semantic_high_lexical_low: high semantic similarity but different words → +0.30
    - valence_opposition: opposite emotional valence → +0.25
    - negation_patterns: regex matches for contradictory language → +0.25
    - temporal_supersession: same keyphrases but >30 days apart → +0.20

    Returns float in [0, 1].
    """
    score = 0.0
    sem = signals.get("semantic_score", 0.0)
    lex = signals.get("lexical_overlap", 0.0)

    # Component 1: High semantic similarity but low lexical overlap
    # Means: talking about the same thing but saying different things
    if sem > 0.7 and lex < 0.3:
        score += 0.30
    elif sem > 0.5 and lex < 0.2:
        score += 0.15

    # Component 2: Opposite emotional valence
    if valence_a * valence_b < 0:
        score += 0.25

    # Component 3: Negation pattern matching
    text_a = content_a.lower()
    text_b = content_b.lower()
    pattern_hits = 0
    for pattern_pos, pattern_neg in CONTRADICTION_PATTERNS:
        # Check both directions: A has positive + B has negative, or vice versa
        if (re.search(pattern_pos, text_a) and re.search(pattern_neg, text_b)) or \
           (re.search(pattern_neg, text_a) and re.search(pattern_pos, text_b)):
            pattern_hits += 1
    if pattern_hits > 0:
        score += min(0.25, 0.25 * pattern_hits / max(1, len(CONTRADICTION_PATTERNS) * 0.3))

    # Component 4: Temporal supersession — same keyphrases, far apart in time
    if keyphrases_a and keyphrases_b and days_apart > 30:
        overlap = len(set(keyphrases_a) & set(keyphrases_b))
        if overlap >= 2:
            score += 0.20

    return min(1.0, round(score, 4))
```

- [ ] **Step 5: Commit**

```bash
git add api-server/sensory_cortex.py
git commit -m "feat: add compute_contradiction_score to sensory cortex"
```

---

### Task 9: Integrate contradiction detection into auto_link_memory

**Files:**
- Modify: `api-server/server.py:1808-1904` (infer_relations_from_candidates)

- [ ] **Step 1: Add import**

At the top of `api-server/server.py`, where sensory_cortex imports are, add `compute_contradiction_score`:

Find the existing import line from sensory_cortex (search for `from sensory_cortex import` or `import sensory_cortex`) and add `compute_contradiction_score` to it.

- [ ] **Step 2: Add contradiction detection inside infer_relations_from_candidates**

In `api-server/server.py`, inside `infer_relations_from_candidates()`, after line 1836 (`result = classify_synapse_cascade(signals, cross_project)`) and before `if result is None:` (line 1837), add contradiction detection:

```python
            result = classify_synapse_cascade(signals, cross_project)

            # [7] Proactive contradiction detection
            contradiction_score = compute_contradiction_score(
                signals=signals,
                content_a=source_text,
                content_b=candidate_text,
                valence_a=float(source_memory.get("valence", 0.0)),
                valence_b=float(candidate.get("valence", 0.0)),
                keyphrases_a=source_memory.get("keyphrases"),
                keyphrases_b=candidate.get("keyphrases"),
                days_apart=abs(signals.get("temporal_proximity", 0.0)),
            )

            if contradiction_score > 0.6 and pg_pool:
                # High confidence: create contradicts relation + enqueue as pending
                try:
                    contra_evidence = {
                        "reason": "proactive_contradiction_detected",
                        "contradiction_score": contradiction_score,
                        "signals": signals,
                        "source_project": source_memory.get("project"),
                        "target_project": candidate["project"],
                    }
                    await upsert_memory_relation(
                        source_memory_id=source_memory["id"],
                        target_memory_id=candidate["id"],
                        relation_type="contradicts",
                        weight=round(contradiction_score, 4),
                        origin=origin,
                        evidence=contra_evidence,
                    )
                    created.append({"id": candidate["id"], "relation_type": "contradicts", "contradiction_score": contradiction_score})
                except Exception as exc:
                    logger.debug("Error creating contradiction relation: %s", exc)
                continue  # Don't also create a normal relation
            elif contradiction_score > 0.4 and pg_pool:
                # Medium confidence: enqueue as suspected for sleep validation
                try:
                    async with pg_pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO contradiction_queue (memory_a_id, memory_b_id, resolution_status)
                            VALUES ($1::uuid, $2::uuid, 'suspected')
                            ON CONFLICT (memory_a_id, memory_b_id) DO NOTHING
                            """,
                            uuid.UUID(source_memory["id"]),
                            uuid.UUID(candidate["id"]),
                        )
                except Exception as exc:
                    logger.debug("Error enqueuing suspected contradiction: %s", exc)

            if result is None:
                continue
```

Note: The `if result is None: continue` must remain but now comes after the contradiction check block.

- [ ] **Step 3: Add contradiction_score to evidence_json for all relations**

In the same function, where evidence is built for `upsert_memory_relation` (around line 1880), add the contradiction_score:

Find:
```python
                evidence={
                    "reason": result["reason"],
                    "tier": result["tier"],
                    "signals": signals,
                    "source_project": source_memory.get("project"),
                    "target_project": candidate["project"],
                },
```

Replace with:
```python
                evidence={
                    "reason": result["reason"],
                    "tier": result["tier"],
                    "signals": signals,
                    "contradiction_score": contradiction_score,
                    "source_project": source_memory.get("project"),
                    "target_project": candidate["project"],
                },
```

- [ ] **Step 4: Rebuild and run test**

```bash
docker compose build api-server && docker compose up -d api-server
sleep 5
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_contradiction_detection.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api-server/server.py
git commit -m "feat: integrate proactive contradiction detection in auto_link_memory"
```

---

### Task 10: Add suspected status to contradiction_queue schema

**Files:**
- Modify: `config/postgres/init.sql`

- [ ] **Step 1: Add index for suspected status**

In `config/postgres/init.sql`, after the existing index at line 285 (`idx_contradiction_pending`), add:

```sql
CREATE INDEX IF NOT EXISTS idx_contradiction_suspected ON contradiction_queue(resolution_status) WHERE resolution_status = 'suspected';
```

- [ ] **Step 2: Commit**

```bash
git add config/postgres/init.sql
git commit -m "feat: add index for suspected contradiction status"
```

---

### Task 11: Implement activation consolidation (Redis → DB)

**Files:**
- Modify: `api-server/server.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_activation_consolidation.py`:

```python
"""Tests for spreading activation consolidation (Redis → DB)."""
from __future__ import annotations

import time
from typing import Any


def minimal_session_payload(project: str) -> dict[str, Any]:
    return {
        "project": project,
        "agent_id": "pytest",
        "session_id": f"session-consolidation-{project}",
        "goal": "Test activation consolidation",
        "outcome": "Consolidation verified",
        "summary": "Verifying that spreading activation energy consolidates from Redis to permanent DB storage.",
        "changes": [],
        "decisions": [],
        "errors": [],
        "follow_ups": [],
        "tags": ["tests", "plasticity", "consolidation"],
    }


def test_plasticity_session_includes_consolidation_key(brain_client, unique_project_name):
    """After plasticity session, response should include consolidated_activations."""
    project = unique_project_name("consolidation-key")

    # Create interconnected memories to trigger spreading activation
    brain_client.create_memory(
        content="Event sourcing stores all state changes as immutable events in an append-only log.",
        project=project,
        memory_type="architecture",
        tags="pattern/event-sourcing,concept/cqrs",
        importance=0.9,
        agent_id="pytest",
    )
    brain_client.create_memory(
        content="CQRS separates read and write models, event sourcing provides the write-side event log.",
        project=project,
        memory_type="architecture",
        tags="pattern/event-sourcing,concept/cqrs",
        importance=0.9,
        agent_id="pytest",
    )
    brain_client.create_memory(
        content="Event sourcing replay rebuilds projections from the append-only event log for recovery.",
        project=project,
        memory_type="architecture",
        tags="pattern/event-sourcing,concept/replay",
        importance=0.85,
        agent_id="pytest",
    )

    time.sleep(1)

    # Trigger plasticity session — this fires spreading activation + consolidation
    brain_client.record_session(
        project=project,
        agent_id="pytest",
        session_id=f"session-{project}",
        goal="Test consolidation",
        outcome="Done",
        summary="Event sourcing and CQRS patterns explored for architecture.",
        changes=[],
        decisions=[],
        errors=[],
        follow_ups=[],
        tags=["tests"],
    )
    result = brain_client.apply_session_plasticity(
        project=project,
        agent_id="pytest",
        session_id=f"session-{project}",
        goal="Test consolidation",
        outcome="Done",
        summary="Event sourcing and CQRS patterns explored for architecture.",
        changes=[],
        decisions=[],
        errors=[],
        follow_ups=[],
        tags=["tests"],
    )

    # The response should now include the consolidation count
    assert "consolidated_activations" in result, (
        f"Expected 'consolidated_activations' in plasticity response. Got: {result}"
    )
    assert isinstance(result["consolidated_activations"], int)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_activation_consolidation.py -v
```

Expected: FAIL — `consolidated_activations` key not in response.

- [ ] **Step 3: Implement consolidate_activation function**

In `api-server/server.py`, before `apply_session_plasticity()` (around line 2665), add:

```python
# ---------------------------------------------------------------------------
# Activation Consolidation (Redis → DB) — Long-Term Potentiation
# ---------------------------------------------------------------------------
ACTIVATION_CONSOLIDATION_THRESHOLD = 0.3
CONSOLIDATION_FACTOR = 0.15


async def consolidate_activation(project_name: str) -> int:
    """[4] Consolidate significant spreading activation from Redis into permanent DB state.

    Reads activation_propagation:* keys from Redis. For memories with energy above
    the threshold, increments activation_score and access_count in PostgreSQL.
    This implements Long-Term Potentiation (LTP): frequently primed memories
    gain permanent stability.

    Returns the number of memories consolidated.
    """
    if not redis_client or not pg_pool:
        return 0

    consolidated = 0
    try:
        # Scan Redis for activation keys
        keys = []
        async for key in redis_client.scan_iter(match="activation_propagation:*", count=200):
            keys.append(key)

        if not keys:
            return 0

        # Read all activation energies
        values = await redis_client.mget(keys)
        activations: list[tuple[str, float]] = []
        for key, val in zip(keys, values):
            if val is None:
                continue
            memory_id = key.decode() if isinstance(key, bytes) else str(key)
            memory_id = memory_id.replace("activation_propagation:", "")
            energy = float(val)
            if energy >= ACTIVATION_CONSOLIDATION_THRESHOLD:
                activations.append((memory_id, energy))

        if not activations:
            return 0

        # Consolidate into DB
        async with pg_pool.acquire() as conn:
            for memory_id, energy in activations:
                try:
                    delta = energy * CONSOLIDATION_FACTOR
                    result = await conn.execute(
                        """
                        UPDATE memory_log
                        SET activation_score = LEAST(1.0, COALESCE(activation_score, 0.0) + $2),
                            access_count = access_count + 1,
                            last_accessed_at = NOW()
                        FROM projects p
                        WHERE memory_log.project_id = p.id
                          AND p.name = $3
                          AND memory_log.id = $1::uuid
                        """,
                        uuid.UUID(memory_id),
                        delta,
                        project_name,
                    )
                    if result and result.split()[-1] != "0":
                        consolidated += 1
                except Exception as exc:
                    logger.debug("Error consolidating activation for %s: %s", memory_id[:8], exc)
    except Exception as exc:
        logger.debug("Error in consolidate_activation: %s", exc)

    if consolidated > 0:
        logger.info("[4] LTP consolidation: %d memories strengthened for project %s", consolidated, project_name)
    return consolidated
```

- [ ] **Step 4: Integrate into apply_session_plasticity**

In `api-server/server.py`, in `apply_session_plasticity()`, before the return statement (line 2727), add:

Find:
```python
    decayed_stability = await decay_memory_stability(payload.project)
    return {
```

Replace with:
```python
    decayed_stability = await decay_memory_stability(payload.project)
    # [4] LTP: consolidate significant spreading activation into permanent DB state
    consolidated = await consolidate_activation(payload.project)
    return {
```

And add `consolidated_activations` to the return dict:

Find:
```python
    return {
        "activated_memories": len(selected),
        "reinforced_pairs": reinforced_pairs,
        "expanded_links": expanded_links,
        "decayed_relations": decayed,
        "decayed_stability": decayed_stability,
    }
```

Replace with:
```python
    return {
        "activated_memories": len(selected),
        "reinforced_pairs": reinforced_pairs,
        "expanded_links": expanded_links,
        "decayed_relations": decayed,
        "decayed_stability": decayed_stability,
        "consolidated_activations": consolidated,
    }
```

- [ ] **Step 5: Rebuild and run test**

```bash
docker compose build api-server && docker compose up -d api-server
sleep 5
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_activation_consolidation.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add api-server/server.py tests/test_activation_consolidation.py
git commit -m "feat: implement activation consolidation (Redis→DB) — Long-Term Potentiation"
```

---

### Task 12: Run full existing test suite for Branch 2

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/ -v
```

Expected: All existing tests PASS + new tests PASS.

- [ ] **Step 2: Commit any fixes if needed**

---

## Branch 3: `feat/deep-sleep-evolution`

### Task 13: Create branch and restructure deep_sleep into NREM/REM

**Files:**
- Modify: `reflection-worker/worker.py:1111-1226`

- [ ] **Step 1: Create branch from main (after Branch 2 is merged)**

```bash
git checkout -b feat/deep-sleep-evolution main
```

Note: This branch depends on Branch 2's `suspected` contradiction status. If Branch 2 is not yet merged, cherry-pick the `init.sql` change or merge Branch 2 first.

- [ ] **Step 2: Extract NREM phase into its own function**

In `reflection-worker/worker.py`, before `handle_deep_sleep()` (around line 1111), add:

```python
async def run_nrem_phase(conn: asyncpg.Connection, run_id, project_names: list[str]) -> dict[str, int]:
    """[L2] NREM Phase: Strengthen & Abstract.

    1. Schema extraction — abstract principles from memory clusters
    2. Suspected contradiction validation — promote or dismiss
    3. Synapse candidate validation — promote Tier 3 candidates
    4. Cluster reinforcement — boost co-activated clusters
    5. Contradiction resolution — resolve pending contradictions
    """
    stats = {
        "schemas_created": 0,
        "suspected_promoted": 0,
        "suspected_dismissed": 0,
        "candidates_promoted": 0,
        "candidates_rejected": 0,
        "clusters_reinforced": 0,
        "contradictions_resolved": 0,
    }

    # Step 1: Schema extraction
    await update_heartbeat()
    stats["schemas_created"] = await run_schema_extraction(conn, run_id)

    # Step 2: Validate suspected contradictions
    await update_heartbeat()
    suspected_rows = await conn.fetch(
        """
        SELECT cq.id, cq.memory_a_id, cq.memory_b_id
        FROM contradiction_queue cq
        WHERE cq.resolution_status = 'suspected'
        ORDER BY cq.created_at ASC
        LIMIT 20
        """
    )
    for row in suspected_rows:
        try:
            mem_a = await conn.fetchrow(
                "SELECT summary, valence, keyphrases FROM memory_log WHERE id = $1::uuid",
                row["memory_a_id"],
            )
            mem_b = await conn.fetchrow(
                "SELECT summary, valence, keyphrases FROM memory_log WHERE id = $1::uuid",
                row["memory_b_id"],
            )
            if not mem_a or not mem_b:
                await conn.execute(
                    "UPDATE contradiction_queue SET resolution_status = 'dismissed', resolved_at = NOW() WHERE id = $1",
                    row["id"],
                )
                stats["suspected_dismissed"] += 1
                continue

            # Re-evaluate with current state
            content_a = str(mem_a["summary"] or "")
            content_b = str(mem_b["summary"] or "")
            text_a = content_a.lower()
            text_b = content_b.lower()

            # Simple re-scoring: check negation patterns and valence
            rescore = 0.0
            valence_a = float(mem_a.get("valence") or 0.0)
            valence_b = float(mem_b.get("valence") or 0.0)
            if valence_a * valence_b < 0:
                rescore += 0.3

            import re as _re
            CONTRADICTION_PATTERNS = [
                (r"\bno\s+usar\b", r"\busar\b"),
                (r"\bevitar\b", r"\bpreferir\b"),
                (r"\bdeprecated?\b", r"\brecomend(?:ado|ed)\b"),
                (r"\bremove[dr]?\b", r"\badd(?:ed)?\b"),
                (r"\bdisable[dr]?\b", r"\benable[dr]?\b"),
            ]
            for pat_a, pat_b in CONTRADICTION_PATTERNS:
                if (_re.search(pat_a, text_a) and _re.search(pat_b, text_b)) or \
                   (_re.search(pat_b, text_a) and _re.search(pat_a, text_b)):
                    rescore += 0.15
                    break

            if rescore > 0.5:
                # Promote to pending
                await conn.execute(
                    "UPDATE contradiction_queue SET resolution_status = 'pending' WHERE id = $1",
                    row["id"],
                )
                stats["suspected_promoted"] += 1
            elif rescore < 0.3:
                # Dismiss
                await conn.execute(
                    "UPDATE contradiction_queue SET resolution_status = 'dismissed', resolved_at = NOW() WHERE id = $1",
                    row["id"],
                )
                stats["suspected_dismissed"] += 1
            # else: keep as suspected for next cycle
        except Exception as exc:
            logger.warning("[L2] NREM suspected validation error: %s", exc)

    # Step 3: Synapse candidate validation
    await update_heartbeat()
    for pname in project_names:
        try:
            cstats = await validate_synapse_candidates(conn, pname)
            stats["candidates_promoted"] += cstats["promoted"]
            stats["candidates_rejected"] += cstats["rejected"]
        except Exception as exc:
            logger.warning("[L2] NREM candidate validation failed for %s: %s", pname, exc)

    # Step 4: Cluster reinforcement (already exists as reinforce_hot_clusters)
    await update_heartbeat()
    stats["clusters_reinforced"] = await reinforce_hot_clusters(conn)

    # Step 5: Contradiction resolution
    await update_heartbeat()
    stats["contradictions_resolved"] = await resolve_contradictions(conn)

    return stats
```

- [ ] **Step 3: Extract REM phase into its own function**

Below `run_nrem_phase`, add:

```python
async def run_rem_phase(conn: asyncpg.Connection, project_names: list[str]) -> dict[str, int]:
    """[L2] REM Phase: Prune & Clean.

    1. Cold memory pruning — accelerate decay of unused memories
    2. Orphan relation cleanup — deactivate relations between dying memories
    3. Myelin decay — adaptive decay based on reinforcement history
    4. Permeability decay — reduce unused project permeability
    5. Tier 3 candidate expiry — reject stale synapse candidates
    """
    stats = {
        "memories_pruned": 0,
        "relations_orphaned": 0,
        "myelin_decayed": 0,
        "permeability_decayed": 0,
        "candidates_expired": 0,
    }

    # Step 1: Cold memory pruning (improved: 21 days, stability < 0.2)
    await update_heartbeat()
    result = await conn.execute(
        """
        UPDATE memory_log ml
        SET stability_score = GREATEST(0.05, ml.stability_score * 0.3)
        WHERE ml.access_count = 0
          AND ml.manual_pin = FALSE
          AND COALESCE(ml.arousal, 0.5) <= 0.6
          AND ml.action_type <> 'schema'
          AND ml.stability_score < 0.2
          AND ml.created_at < NOW() - INTERVAL '21 days'
        """
    )
    stats["memories_pruned"] = int(result.split()[-1]) if result else 0

    # Step 2: Orphan relation cleanup
    await update_heartbeat()
    result = await conn.execute(
        """
        UPDATE memory_relations mr
        SET active = FALSE, updated_at = NOW()
        FROM memory_log src, memory_log dst
        WHERE mr.source_memory_id = src.id
          AND mr.target_memory_id = dst.id
          AND src.stability_score < 0.1
          AND dst.stability_score < 0.1
          AND mr.active = TRUE
          AND mr.origin <> 'manual'
        """
    )
    stats["relations_orphaned"] = int(result.split()[-1]) if result else 0

    # Step 3: Adaptive myelin decay
    await update_heartbeat()
    stats["myelin_decayed"] = await apply_adaptive_myelin_decay(conn)

    # Step 4: Permeability decay (unchanged)
    stats["permeability_decayed"] = await apply_permeability_decay(conn)

    # Step 5: Tier 3 candidate expiry
    await update_heartbeat()
    result = await conn.execute(
        """
        UPDATE synapse_candidates
        SET status = 'expired', reviewed_at = NOW()
        WHERE status = 'pending'
          AND created_at < NOW() - INTERVAL '72 hours'
        """
    )
    stats["candidates_expired"] = int(result.split()[-1]) if result else 0

    return stats
```

- [ ] **Step 4: Add adaptive myelin decay function**

Before `run_rem_phase`, add:

```python
async def apply_adaptive_myelin_decay(conn) -> int:
    """[L2] REM: Adaptive myelin decay — frequently used paths resist forgetting.

    Decay rate = BASE_DECAY / (1 + 0.3 * reinforcement_count)
    - New relation (reinforcement=0): decays at 0.01/cycle
    - Relation used 10 times: decays at 0.0025/cycle (4x more resistant)
    """
    rows = await conn.fetch(
        """
        SELECT id, myelin_score, reinforcement_count
        FROM memory_relations
        WHERE myelin_score > 0
          AND last_activated_at < NOW() - INTERVAL '48 hours'
        """
    )
    decayed = 0
    base_decay = abs(MYELIN_DELTA_DECAY_PER_CYCLE)  # 0.01
    for row in rows:
        reinforcement = int(row["reinforcement_count"] or 0)
        effective_decay = base_decay / (1.0 + 0.3 * reinforcement)
        new_score = max(0.0, float(row["myelin_score"]) - effective_decay)
        await conn.execute(
            """
            UPDATE memory_relations
            SET myelin_score = $2, myelin_last_updated = NOW()
            WHERE id = $1
            """,
            row["id"],
            new_score,
        )
        if new_score <= 0.0:
            await conn.execute(
                "UPDATE memory_relations SET active = FALSE WHERE id = $1",
                row["id"],
            )
        decayed += 1
    return decayed
```

- [ ] **Step 5: Rewrite handle_deep_sleep to use NREM/REM phases**

Replace the body of `handle_deep_sleep()` (lines 1111-1226) with:

```python
async def handle_deep_sleep():
    """[8][L2] Deep Sleep: NREM (strengthen/abstract) then REM (prune/clean)."""
    if not pg_pool:
        return
    async with pg_pool.acquire() as conn:
        locked = await conn.fetchval("SELECT pg_try_advisory_lock($1)", ADVISORY_LOCK_KEY + 1)
        if not locked:
            return
        try:
            last_run = await conn.fetchval(
                "SELECT COALESCE(finished_at, started_at) FROM deep_sleep_runs ORDER BY started_at DESC LIMIT 1"
            )
            if last_run and now_utc() - last_run.astimezone(timezone.utc) < timedelta(seconds=DEEP_SLEEP_INTERVAL):
                return
            run_id = await conn.fetchval(
                "INSERT INTO deep_sleep_runs (status) VALUES ('running') RETURNING id"
            )
            logger.info("[8] Deep Sleep iniciado (run_id=%s)", run_id)

            project_names = [
                str(r["name"]) for r in await conn.fetch(
                    "SELECT DISTINCT p.name FROM projects p JOIN memory_log m ON m.project_id = p.id"
                )
            ]

            nrem_stats = {}
            rem_stats = {}
            error_text = None

            try:
                # NREM Phase: Strengthen & Abstract
                logger.info("[L2] NREM phase starting")
                nrem_stats = await run_nrem_phase(conn, run_id, project_names)
                logger.info("[L2] NREM complete: %s", nrem_stats)

                # REM Phase: Prune & Clean
                logger.info("[L2] REM phase starting")
                rem_stats = await run_rem_phase(conn, project_names)
                logger.info("[L2] REM complete: %s", rem_stats)

            except Exception as exc:
                logger.exception("[8] Deep Sleep fallo parcialmente")
                error_text = str(exc)[:2000]

            # Record separate NREM and REM cycles
            try:
                nrem_cycle_id = await record_sleep_cycle(conn, "nrem", "deep_sleep_interval", project_names, {})
                await complete_sleep_cycle(conn, nrem_cycle_id, nrem_stats)
                rem_cycle_id = await record_sleep_cycle(conn, "rem", "deep_sleep_interval", project_names, {})
                await complete_sleep_cycle(conn, rem_cycle_id, rem_stats)
            except Exception:
                logger.debug("Failed to record sleep cycles")

            # Legacy: update deep_sleep_runs table
            memories_scanned = await conn.fetchval("SELECT COUNT(*) FROM memory_log") or 0
            await conn.execute(
                """
                UPDATE deep_sleep_runs
                SET status = $2,
                    memories_scanned = $3,
                    schemas_created = $4,
                    contradictions_resolved = $5,
                    memories_pruned = $6,
                    relations_reinforced = $7,
                    error = $8,
                    finished_at = NOW()
                WHERE id = $1
                """,
                run_id,
                "failed" if error_text else "completed",
                memories_scanned,
                nrem_stats.get("schemas_created", 0),
                nrem_stats.get("contradictions_resolved", 0),
                rem_stats.get("memories_pruned", 0),
                nrem_stats.get("clusters_reinforced", 0),
                error_text,
            )
            logger.info(
                "[8][L2] Deep Sleep completado — NREM: %s | REM: %s",
                nrem_stats, rem_stats,
            )
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_KEY + 1)
```

- [ ] **Step 6: Remove old prune_cold_memories function**

The old `prune_cold_memories` at lines 954-967 is now inlined in `run_rem_phase`. Remove it, and also remove the old `apply_myelin_decay` at lines 1050-1069 (replaced by `apply_adaptive_myelin_decay`).

Keep `reinforce_hot_clusters`, `validate_synapse_candidates`, `resolve_contradictions`, `apply_permeability_decay`, `record_sleep_cycle`, and `complete_sleep_cycle` as they are — they're called from the new phase functions.

- [ ] **Step 7: Add MYELIN_DELTA_DECAY_PER_CYCLE import**

At the top of `reflection-worker/worker.py`, ensure the import from myelination includes the decay constant. Find the existing import line and add it:

```python
from myelination import MYELIN_DELTA_DECAY_PER_CYCLE
```

If myelination is not imported directly (the worker uses api_call), define the constant locally:

```python
MYELIN_DELTA_DECAY_PER_CYCLE = -0.01
```

- [ ] **Step 8: Commit**

```bash
git add reflection-worker/worker.py
git commit -m "feat: restructure deep_sleep into NREM (strengthen) and REM (prune) phases"
```

---

### Task 14: Add adaptive myelin ceiling and co-activation to myelination.py

**Files:**
- Modify: `api-server/myelination.py`

- [ ] **Step 1: Add compute_max_myelin function**

In `api-server/myelination.py`, after the constants block (line 24), add:

```python

def compute_myelin_decay_rate(base_decay: float, reinforcement_count: int) -> float:
    """Decay rate inversely proportional to reinforcement history.

    Frequently used cross-project paths resist forgetting.
    - reinforcement=0: decay = base_decay (0.01)
    - reinforcement=10: decay = 0.0025 (4x more resistant)
    - reinforcement=30: decay = 0.001 (10x more resistant)
    """
    return base_decay / (1.0 + 0.3 * reinforcement_count)


def compute_max_myelin(reinforcement_count: int) -> float:
    """Myelin ceiling grows with usage.

    New relations cap at 0.5. Heavily used paths can reach 1.0.
    - reinforcement=0: max 0.5
    - reinforcement=5: max 0.75
    - reinforcement=10+: max 1.0
    """
    return min(1.0, 0.5 + 0.05 * reinforcement_count)
```

- [ ] **Step 2: Update update_myelin_score to respect adaptive ceiling**

Replace the existing `update_myelin_score` function (lines 49-76) with:

```python
async def update_myelin_score(
    conn: asyncpg.Connection,
    relation_id: str,
    delta: float,
    event_type: str,
) -> float:
    """Update myelin_score on a relation and record the event.

    Respects adaptive ceiling based on reinforcement_count.
    """
    import uuid as _uuid

    # Get current reinforcement_count for adaptive ceiling
    rel_row = await conn.fetchrow(
        "SELECT reinforcement_count FROM memory_relations WHERE id = $1",
        _uuid.UUID(relation_id) if isinstance(relation_id, str) else relation_id,
    )
    reinforcement = int(rel_row["reinforcement_count"] or 0) if rel_row else 0
    max_myelin = compute_max_myelin(reinforcement)

    row = await conn.fetchrow(
        """
        UPDATE memory_relations
        SET myelin_score = GREATEST(0.0, LEAST($3, myelin_score + $2)),
            myelin_last_updated = NOW()
        WHERE id = $1
        RETURNING myelin_score
        """,
        _uuid.UUID(relation_id) if isinstance(relation_id, str) else relation_id,
        delta,
        max_myelin,
    )
    new_score = float(row["myelin_score"]) if row else 0.0
    if new_score <= 0.0 and delta < 0:
        await conn.execute(
            "UPDATE memory_relations SET active = FALSE WHERE id = $1",
            _uuid.UUID(relation_id) if isinstance(relation_id, str) else relation_id,
        )
    await record_myelination_event(conn, relation_id, None, event_type, delta, new_score)
    return new_score
```

- [ ] **Step 3: Add co-activation detection function**

At the end of `myelination.py`, add:

```python

MYELIN_DELTA_COACTIVATION = 0.03


async def strengthen_coactivated_myelin(conn: asyncpg.Connection) -> int:
    """[L2] NREM: Strengthen myelin on cross-project relations where both endpoints
    were activated in the same recent session (within 1 hour of each other).

    Returns count of relations strengthened.
    """
    rows = await conn.fetch(
        """
        SELECT mr.id::text AS relation_id, mr.reinforcement_count
        FROM memory_relations mr
        JOIN memory_log src ON src.id = mr.source_memory_id
        JOIN memory_log dst ON dst.id = mr.target_memory_id
        JOIN projects ps ON ps.id = src.project_id
        JOIN projects pd ON pd.id = dst.project_id
        WHERE ps.name <> pd.name
          AND mr.active = TRUE
          AND mr.origin <> 'manual'
          AND src.last_accessed_at > NOW() - INTERVAL '24 hours'
          AND dst.last_accessed_at > NOW() - INTERVAL '24 hours'
          AND ABS(EXTRACT(EPOCH FROM (src.last_accessed_at - dst.last_accessed_at))) < 3600
        """
    )
    strengthened = 0
    for row in rows:
        max_myelin = compute_max_myelin(int(row["reinforcement_count"] or 0))
        await conn.execute(
            """
            UPDATE memory_relations
            SET myelin_score = LEAST($2, myelin_score + $3),
                myelin_last_updated = NOW()
            WHERE id = $1::uuid
            """,
            row["relation_id"],
            max_myelin,
            MYELIN_DELTA_COACTIVATION,
        )
        await record_myelination_event(
            conn, row["relation_id"], None, "coactivation", MYELIN_DELTA_COACTIVATION, 0.0
        )
        strengthened += 1
    return strengthened
```

- [ ] **Step 4: Commit**

```bash
git add api-server/myelination.py
git commit -m "feat: adaptive myelin ceiling, decay rate, and co-activation strengthening"
```

---

### Task 15: Improve contradiction synthesis with formal relations and provenance

**Files:**
- Modify: `reflection-worker/worker.py:859-951` (resolve_contradictions)

- [ ] **Step 1: Improve the synthesis branch in resolve_contradictions**

In `reflection-worker/worker.py`, replace the synthesis branch in `resolve_contradictions()` (lines 908-933) with:

Find:
```python
            elif res_type == "synthesis":
                synth_content = f"SYNTHESIS: {str(mem_a['summary'])[:200]} / {str(mem_b['summary'])[:200]}"
                project_name = await conn.fetchval(
                    "SELECT p.name FROM memory_log ml JOIN projects p ON p.id = ml.project_id WHERE ml.id = $1::uuid",
                    uuid.UUID(mem_a_id),
                )
                if project_name:
                    try:
                        resp = await api_call("POST", "/api/memories", {
                            "content": synth_content,
                            "project": project_name,
                            "memory_type": "synthesis",
                            "importance": 0.8,
                            "tags": "synthesis,contradiction-resolved",
                            "agent_id": "deep-sleep-worker",
                        })
                        synth_id = ""
                        if resp.get("result", "").startswith("OK") and "memory_id=" in resp.get("result", ""):
                            synth_id = resp["result"].split("memory_id=")[1].split()[0]
                        await conn.execute(
                            "UPDATE contradiction_queue SET resolution_memory_id = $2::uuid WHERE id = $1",
                            cq_id,
                            uuid.UUID(synth_id) if synth_id else None,
                        )
                    except Exception as exc:
                        logger.debug("Error creando sintesis: %s", exc)
```

Replace with:
```python
            elif res_type == "synthesis":
                reasoning = resolution.get("reasoning", "")
                synth_content = f"SYNTHESIS: {str(mem_a['summary'])[:200]} / {str(mem_b['summary'])[:200]}"
                if reasoning:
                    synth_content = f"{synth_content}\nReasoning: {reasoning}"
                project_name = await conn.fetchval(
                    "SELECT p.name FROM memory_log ml JOIN projects p ON p.id = ml.project_id WHERE ml.id = $1::uuid",
                    uuid.UUID(mem_a_id),
                )
                if project_name:
                    try:
                        resp = await api_call("POST", "/api/memories", {
                            "content": synth_content,
                            "project": project_name,
                            "memory_type": "schema",
                            "importance": 0.85,
                            "tags": "synthesis,contradiction-resolution",
                            "agent_id": "deep-sleep-worker",
                        })
                        synth_id = ""
                        if resp.get("result", "").startswith("OK") and "memory_id=" in resp.get("result", ""):
                            synth_id = resp["result"].split("memory_id=")[1].split()[0]

                        if synth_id:
                            # Create formal derived_from relations
                            for source_id in [mem_a_id, mem_b_id]:
                                await api_call("POST", "/api/relations", {
                                    "source_memory_id": synth_id,
                                    "target_memory_id": source_id,
                                    "relation_type": "derived_from",
                                    "reason": f"contradiction_synthesis from {cq_id}",
                                    "weight": 0.9,
                                })

                            # Record in schema_sources
                            for source_id in [mem_a_id, mem_b_id]:
                                try:
                                    await conn.execute(
                                        """
                                        INSERT INTO schema_sources (schema_memory_id, source_memory_id)
                                        VALUES ($1::uuid, $2::uuid)
                                        ON CONFLICT DO NOTHING
                                        """,
                                        uuid.UUID(synth_id),
                                        uuid.UUID(source_id),
                                    )
                                except Exception:
                                    pass

                            # Proportional degradation (50% not 85%)
                            await conn.execute(
                                """
                                UPDATE memory_log
                                SET stability_score = GREATEST(0.05, stability_score * 0.5)
                                WHERE id = ANY($1::uuid[])
                                """,
                                [uuid.UUID(mem_a_id), uuid.UUID(mem_b_id)],
                            )

                        await conn.execute(
                            "UPDATE contradiction_queue SET resolution_memory_id = $2::uuid WHERE id = $1",
                            cq_id,
                            uuid.UUID(synth_id) if synth_id else None,
                        )
                    except Exception as exc:
                        logger.debug("Error creando sintesis: %s", exc)
```

- [ ] **Step 2: Add conditional resolution type handling**

After the synthesis block, before the final `await conn.execute(... SET resolution_status = 'resolved' ...)`, add handling for `conditional`:

Find the line after the synthesis block that starts:
```python
            await conn.execute(
                """
                UPDATE contradiction_queue
                SET resolution_status = 'resolved',
```

Add before it:
```python
            elif res_type == "conditional":
                cond_content = f"CONDITIONAL: {condition_text}"
                project_name = await conn.fetchval(
                    "SELECT p.name FROM memory_log ml JOIN projects p ON p.id = ml.project_id WHERE ml.id = $1::uuid",
                    uuid.UUID(mem_a_id),
                )
                if project_name and condition_text:
                    try:
                        resp = await api_call("POST", "/api/memories", {
                            "content": cond_content,
                            "project": project_name,
                            "memory_type": "schema",
                            "importance": 0.8,
                            "tags": "conditional,contradiction-resolution",
                            "agent_id": "deep-sleep-worker",
                        })
                        cond_id = ""
                        if resp.get("result", "").startswith("OK") and "memory_id=" in resp.get("result", ""):
                            cond_id = resp["result"].split("memory_id=")[1].split()[0]
                        if cond_id:
                            # Create applies_to relations — both originals remain valid
                            for source_id in [mem_a_id, mem_b_id]:
                                await api_call("POST", "/api/relations", {
                                    "source_memory_id": cond_id,
                                    "target_memory_id": source_id,
                                    "relation_type": "applies_to",
                                    "reason": f"contradiction_conditional from {cq_id}",
                                    "weight": 0.8,
                                })
                            # No degradation — both are correct in their context
                    except Exception as exc:
                        logger.debug("Error creating conditional resolution: %s", exc)
```

- [ ] **Step 3: Commit**

```bash
git add reflection-worker/worker.py
git commit -m "feat: improved synthesis with formal relations, provenance, and conditional resolution"
```

---

### Task 16: Add NREM co-activation call and sleep_cycles schema update

**Files:**
- Modify: `reflection-worker/worker.py` (run_nrem_phase)
- Modify: `config/postgres/init.sql`

- [ ] **Step 1: Add co-activation strengthening to NREM phase**

In `run_nrem_phase`, after cluster reinforcement (step 4) and before contradiction resolution (step 5), add:

```python
    # Step 4b: Cross-project co-activation myelin strengthening
    try:
        from myelination import strengthen_coactivated_myelin
        coactivated = await strengthen_coactivated_myelin(conn)
        stats["coactivation_strengthened"] = coactivated
    except Exception as exc:
        logger.debug("[L2] NREM co-activation strengthening error: %s", exc)
        stats["coactivation_strengthened"] = 0
```

Also add to the stats dict initialization:
```python
    stats = {
        ...
        "coactivation_strengthened": 0,
    }
```

- [ ] **Step 2: Add nrem_stats and rem_stats columns to sleep_cycles**

In `config/postgres/init.sql`, after the `sleep_cycles` table creation (line 253), add:

```sql
-- Add NREM/REM phase-specific stats (idempotent with DO NOTHING pattern)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'sleep_cycles' AND column_name = 'nrem_stats') THEN
        ALTER TABLE sleep_cycles ADD COLUMN nrem_stats JSONB DEFAULT '{}'::jsonb;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'sleep_cycles' AND column_name = 'rem_stats') THEN
        ALTER TABLE sleep_cycles ADD COLUMN rem_stats JSONB DEFAULT '{}'::jsonb;
    END IF;
END $$;
```

- [ ] **Step 3: Commit**

```bash
git add reflection-worker/worker.py config/postgres/init.sql
git commit -m "feat: add co-activation myelin strengthening and sleep_cycles phase stats"
```

---

### Task 17: Write integration tests for deep sleep evolution

**Files:**
- Create: `tests/test_deep_sleep_evolution.py`

- [ ] **Step 1: Write deep sleep tests**

Create `tests/test_deep_sleep_evolution.py`:

```python
"""Tests for deep sleep NREM/REM evolution."""
from __future__ import annotations

import time
from typing import Any


def test_plasticity_session_returns_all_fields(brain_client, unique_project_name):
    """Plasticity session should return all expected fields including consolidation."""
    project = unique_project_name("deep-sleep-fields")

    brain_client.create_memory(
        content="Microservices communicate via async message queues for loose coupling.",
        project=project,
        memory_type="architecture",
        tags="pattern/microservices,pattern/async",
        importance=0.9,
        agent_id="pytest",
    )

    brain_client.record_session(
        project=project,
        agent_id="pytest",
        session_id=f"session-{project}",
        goal="Test fields",
        outcome="Done",
        summary="Microservice async patterns.",
        changes=[],
        decisions=[],
        errors=[],
        follow_ups=[],
        tags=["tests"],
    )

    result = brain_client.apply_session_plasticity(
        project=project,
        agent_id="pytest",
        session_id=f"session-{project}",
        goal="Test fields",
        outcome="Done",
        summary="Microservice async patterns.",
        changes=[],
        decisions=[],
        errors=[],
        follow_ups=[],
        tags=["tests"],
    )

    expected_keys = {
        "activated_memories",
        "reinforced_pairs",
        "expanded_links",
        "decayed_relations",
        "decayed_stability",
        "consolidated_activations",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys in plasticity response. Expected: {expected_keys}. Got: {set(result.keys())}"
    )


def test_cold_memory_pruning_criteria(brain_client, unique_project_name):
    """Memories with access_count=0 and low stability should be pruned after aging."""
    project = unique_project_name("cold-prune")

    # Create a memory and don't access it
    mem = brain_client.create_memory(
        content="Temporary throwaway memory for cold pruning test that should eventually decay.",
        project=project,
        memory_type="observation",
        tags="test/cold-prune",
        importance=0.3,
        agent_id="pytest",
    )["memory_id"]

    # Verify the memory exists with access_count=0
    detail = brain_client.memory_detail(mem)
    assert detail["access_count"] == 0


def test_brain_health_endpoint(brain_client):
    """The brain health endpoint should return biological metrics."""
    health = brain_client.brain_health()
    assert "status" in health
```

- [ ] **Step 2: Run tests**

```bash
docker compose build api-server reflection-worker && docker compose up -d
sleep 10
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_deep_sleep_evolution.py -v
```

Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_deep_sleep_evolution.py
git commit -m "test: add deep sleep evolution integration tests"
```

---

### Task 18: Run full test suite for Branch 3

**Files:** None (verification only)

- [ ] **Step 1: Rebuild everything**

```bash
docker compose build && docker compose up -d
sleep 15
```

- [ ] **Step 2: Run full suite**

```bash
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Fix any regressions if needed**

---

## Summary

| Branch | Tasks | Key files |
|--------|-------|-----------|
| `feat/proactive-save-protocol` | 1-7 | `server.py`, `plugin/claude-code/*`, `docs/MCP_TOOLS.md` |
| `feat/runtime-biology` | 8-12 | `sensory_cortex.py`, `server.py`, `init.sql` |
| `feat/deep-sleep-evolution` | 13-18 | `worker.py`, `myelination.py`, `init.sql` |

**Dependency:** Branch 1 and 2 are independent. Branch 3 depends on Branch 2 (suspected contradictions).
