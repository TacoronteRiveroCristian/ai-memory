# Proactive Save Protocol & Deep Biology Evolution

**Date:** 2026-04-11
**Status:** Approved
**Branches:** `feat/proactive-save-protocol`, `feat/runtime-biology`, `feat/deep-sleep-evolution`

---

## Context

Competitive analysis against Engram (Gentleman-Programming/engram) revealed two areas for improvement:

1. **No proactive save protocol** — agents only save memories when explicitly told. Engram's SKILL.md instructs agents to save automatically after decisions, bugs, discoveries. We have no equivalent.
2. **Biological features are shallow in places** — contradiction detection is manual-only, spreading activation is ephemeral (Redis TTL 15 min), NREM/REM are labels not behaviors, myelin decay is uniform, synthesis doesn't close the graph.

This spec addresses both: a behavioral layer for agents + 5 biological deepening features across 3 branches.

---

## Branch 1: `feat/proactive-save-protocol` — Behavioral Layer

### 1A. MCP Server Instructions

**File:** `api-server/server.py`

Add `serverInstructions` to the FastMCP initialization. Any MCP-compatible agent receives these instructions automatically on connection.

**Content of serverInstructions:**

```
PROACTIVE MEMORY PROTOCOL
=========================
You are connected to AI Memory Brain, a biological memory system. Save memories
IMMEDIATELY and WITHOUT BEING ASKED when any of the following occur:

TRIGGERS — Save automatically when:
- A decision is made (use store_decision)
- A bug is found or fixed (use store_error)
- A pattern or insight is discovered (use store_memory, type="observation")
- Architecture changes or is discussed (use store_memory, type="decision")
- A task is started, blocked, or completed (use update_task_state)
- An error is resolved with a solution (use store_error)
- A cross-project connection is noticed (use bridge_projects)
- Two memories relate to each other (use link_memories)

FORMAT — When saving memories:
- content: What happened + Why it matters + Context
- tags: Relevant hierarchical tags (e.g., "backend/auth", "bug/resolved")
- importance: 0.5 (routine) | 0.7 (notable) | 0.9 (critical decision or breakthrough)
- memory_type: observation | decision | error | schema

SESSION LIFECYCLE:
- On session start: call get_project_context to load current state
- During work: save continuously as triggers occur
- On session end: call record_session_summary with structured recap

QUALITY OVER QUANTITY:
- Save the WHY, not just the WHAT
- Include alternatives considered for decisions
- Tag errors with their signatures for dedup
- Don't save trivial or obvious information
```

### 1B. Claude Code Plugin

**Directory:** `plugin/claude-code/`

#### `plugin/claude-code/SKILL.md`

Detailed behavioral instructions for Claude Code specifically. Extends the MCP serverInstructions with Claude Code-specific patterns:

- Explicit examples of when to call each tool with sample payloads
- Integration with Claude Code's conversation flow (e.g., after tool calls that reveal bugs, after planning discussions)
- Importance calibration guide with concrete examples
- Tag vocabulary relevant to the project's domain
- Anti-patterns: don't save conversation summaries, don't save obvious code snippets, don't save temporary debug info

#### `plugin/claude-code/hooks/session-start.sh`

```bash
#!/bin/bash
# Auto-load project context at session start
# Outputs instruction for the agent to call get_project_context
echo "## Memory Brain: Session Started"
echo "Call get_project_context with your current project name to load context."
```

#### `plugin/claude-code/hooks/session-stop.sh`

```bash
#!/bin/bash
# Remind agent to record session summary
echo "## Memory Brain: Session Ending"
echo "Call record_session_summary before closing this session."
```

#### `plugin/claude-code/hooks/post-compaction.sh`

```bash
#!/bin/bash
# After context compaction, remind agent about memory
echo "## Memory Brain: Context Compacted"
echo "Context was compressed. Key memories should already be saved."
echo "Call get_project_context if you need to reload state."
```

#### `plugin/claude-code/settings.json`

Partial settings for hook registration:

```json
{
  "hooks": {
    "SessionStart": [{"command": "plugin/claude-code/hooks/session-start.sh"}],
    "SessionStop": [{"command": "plugin/claude-code/hooks/session-stop.sh"}],
    "PostCompaction": [{"command": "plugin/claude-code/hooks/post-compaction.sh"}]
  }
}
```

#### `plugin/claude-code/README.md`

One-liner setup instructions + what the plugin does.

### 1C. MCP Resource

**File:** `api-server/server.py`

Expose a readable MCP resource at `memory://protocol` that returns the full proactive save protocol text. For agents that don't support serverInstructions but can read MCP resources.

```python
@mcp.resource("memory://protocol")
async def get_protocol():
    """Returns the proactive memory save protocol for agents."""
    return protocol_text
```

### Tests

- `test_server_instructions_served`: Connect to MCP, verify serverInstructions contains "PROACTIVE MEMORY PROTOCOL"
- `test_protocol_resource_accessible`: Read `memory://protocol` resource, verify it returns protocol text

### Files Changed

| File | Change |
|------|--------|
| `api-server/server.py` | Add serverInstructions to FastMCP init, add MCP resource |
| `plugin/claude-code/SKILL.md` | New — Claude Code behavioral instructions |
| `plugin/claude-code/hooks/session-start.sh` | New — session start hook |
| `plugin/claude-code/hooks/session-stop.sh` | New — session stop hook |
| `plugin/claude-code/hooks/post-compaction.sh` | New — post-compaction hook |
| `plugin/claude-code/settings.json` | New — hook registration |
| `plugin/claude-code/README.md` | New — setup instructions |
| `docs/MCP_TOOLS.md` | Update with protocol reference |

---

## Branch 2: `feat/runtime-biology` — Runtime Improvements

### 2A. Proactive Contradiction Detection

**Files:** `api-server/sensory_cortex.py`, `api-server/server.py`

#### New function: `compute_contradiction_score()`

**Location:** `api-server/sensory_cortex.py`

```python
def compute_contradiction_score(
    signals: dict,
    content_a: str,
    content_b: str
) -> float:
```

**Scoring (4 components, clamped to [0, 1]):**

| Component | Condition | Score |
|-----------|-----------|-------|
| `semantic_high_lexical_low` | semantic > 0.7 AND lexical < 0.3 | +0.30 |
| `valence_opposition` | valence_a * valence_b < 0 (opposite signs) | +0.25 |
| `negation_patterns` | Regex matches in content (see below) | +0.25 |
| `temporal_supersession` | Same keyphrases + >30 days apart | +0.20 |

**Negation patterns (regex):**

```python
CONTRADICTION_PATTERNS = [
    (r"no\s+usar\b.*\b(\w+)", r"\busar\b.*\b\1"),        # "no usar X" vs "usar X"
    (r"\bdeprecated?\b", r"\brecomend(?:ado|ed)\b"),       # deprecated vs recommended
    (r"\bevitar\b", r"\bpreferir\b"),                       # avoid vs prefer
    (r"\bremove[dr]?\b", r"\badd(?:ed)?\b"),               # removed vs added
    (r"\bdisable[dr]?\b", r"\benable[dr]?\b"),             # disabled vs enabled
    (r"\bnot?\s+recommend", r"\brecommend"),               # not recommend vs recommend
    (r"\banti[_-]?pattern\b", r"\bbest[_-]?practice\b"),   # antipattern vs best practice
]
```

For each pattern pair: if pattern_a matches content_a AND pattern_b matches content_b (or vice versa), add 0.25 / len(CONTRADICTION_PATTERNS) per match, capped at 0.25 total.

#### Integration in `auto_link_memory()`

**Location:** `api-server/server.py`, inside `auto_link_memory()`

After computing the 7-signal cascade for each candidate:

1. Call `compute_contradiction_score(signals, new_content, candidate_content)`
2. If score > 0.6: Create `contradicts` relation + enqueue in `contradiction_queue` with status `pending`
3. If score between 0.4-0.6: Enqueue in `contradiction_queue` with status `suspected`
4. Store `contradiction_score` in `evidence_json`

#### Schema change

**File:** `config/postgres/init.sql`

Add `suspected` as valid status for `contradiction_queue`:

```sql
-- contradiction_queue.resolution_status now accepts: pending, suspected, resolved, dismissed
```

### 2B. Activation Consolidation (Redis → DB)

**File:** `api-server/server.py`

#### New function: `consolidate_activation()`

```python
async def consolidate_activation(project_id: str, pool) -> int:
    """
    Reads spreading activation energy from Redis and consolidates
    significant activations into permanent DB state (LTP).

    Returns number of memories consolidated.
    """
```

**Algorithm:**

1. Scan Redis keys matching `activation_propagation:*`
2. Filter to memories belonging to `project_id` (lookup in Qdrant payload)
3. For each memory with energy > `ACTIVATION_CONSOLIDATION_THRESHOLD` (default 0.3):
   - Read current `activation_score` from DB
   - Update: `new_activation = old_activation + (redis_energy * CONSOLIDATION_FACTOR)`
   - `CONSOLIDATION_FACTOR = 0.15` (amortized to prevent inflation)
   - Cap at 1.0
   - Increment `access_count` by 1 (indirect activation counts as partial access)
   - Update `last_accessed_at` to now (resets Ebbinghaus decay clock)
4. For memories with energy < 0.1: skip (noise filter)
5. Return count of consolidated memories

#### Constants

```python
ACTIVATION_CONSOLIDATION_THRESHOLD = 0.3   # Min Redis energy to consolidate
CONSOLIDATION_FACTOR = 0.15                 # Amortization factor for LTP
```

#### Integration point

Called at the end of `apply_session_plasticity()`, after spreading activation completes:

```python
# ... existing plasticity code ...
# After spreading activation fire-and-forget tasks complete:
consolidated = await consolidate_activation(project_id, pool)
result["consolidated_activations"] = consolidated
```

### Tests

| Test | What it verifies |
|------|------------------|
| `test_contradiction_detected_automatically` | Store "usar Redis para cache" then "no usar Redis, usar Memcached" → contradiction_queue has entry with status pending |
| `test_no_false_contradiction` | Store two positive memories about same topic → no contradiction detected |
| `test_suspected_contradiction_threshold` | Score between 0.4-0.6 → status is `suspected` not `pending` |
| `test_contradiction_score_components` | Verify each component contributes correctly |
| `test_activation_consolidation_above_threshold` | Propagate activation > 0.3, run consolidate → DB activation_score increased |
| `test_activation_consolidation_noise_filter` | Propagate activation < 0.1, run consolidate → DB unchanged |
| `test_consolidation_amortization` | Multiple consolidations don't inflate activation_score past 1.0 |
| `test_plasticity_session_includes_consolidation` | Full plasticity session returns `consolidated_activations` in response |

### Files Changed

| File | Change |
|------|--------|
| `api-server/sensory_cortex.py` | Add `compute_contradiction_score()`, `CONTRADICTION_PATTERNS` |
| `api-server/server.py` | Integrate contradiction detection in `auto_link_memory()`, add `consolidate_activation()`, call from `apply_session_plasticity()` |
| `config/postgres/init.sql` | Allow `suspected` status in contradiction_queue |
| `tests/test_contradiction_detection.py` | New — contradiction detection tests |
| `tests/test_activation_consolidation.py` | New — consolidation tests |

---

## Branch 3: `feat/deep-sleep-evolution` — Offline Improvements

### 3A. NREM/REM Differentiated Phases

**File:** `reflection-worker/worker.py`

Restructure `run_deep_sleep()` into two distinct phases with clear separation of concerns.

#### NREM Phase: Strengthen & Abstract

Function: `run_nrem_phase(conn, run_id) -> dict`

**Steps (in order):**

1. **Schema extraction** (existing) — no changes
2. **Synapse candidate validation** (existing) — extend to also validate `suspected` contradictions:
   - Fetch `suspected` entries from `contradiction_queue`
   - For each: re-compute contradiction_score with current memory state
   - If score > 0.5: promote to `pending` (will be resolved in step 4)
   - If score < 0.3: dismiss (set status `dismissed`)
   - Otherwise: keep as `suspected` for next cycle
3. **Cluster reinforcement** (new):
   - Identify memory clusters: groups of 3+ memories connected by active relations with weight > 0.5
   - For each cluster: boost internal relation weights by +0.05 (cap at 1.0)
   - Log cluster IDs and sizes for metrics
4. **Contradiction resolution** (existing, improved):
   - Resolve all `pending` contradictions (including newly promoted from step 2)
   - Use improved synthesis (see 3C)

**Returns:**
```python
{
    "schemas_created": int,
    "candidates_validated": int,
    "candidates_rejected": int,
    "suspected_promoted": int,
    "suspected_dismissed": int,
    "clusters_reinforced": int,
    "contradictions_resolved": int
}
```

#### REM Phase: Prune & Clean

Function: `run_rem_phase(conn, run_id) -> dict`

**Steps (in order):**

1. **Cold memory pruning** (existing, improved):
   - Criteria: `access_count = 0 AND stability_score < 0.2 AND age > 21 days AND manual_pin = FALSE AND arousal < 0.7`
   - Reduced from 30 to 21 days (more aggressive, biologically accurate — unused memories fade faster)
   - Action: `stability_score *= 0.3` (not delete, just accelerate decay)
2. **Orphan relation cleanup** (new):
   - Find relations where BOTH endpoints have `stability_score < 0.1`
   - Set `active = FALSE` on these relations
   - These are connections between dying memories — no value in keeping them active
3. **Myelin decay** (existing, replaced by adaptive — see 3B)
4. **Permeability decay** (existing) — no changes
5. **Tier 3 candidate expiry** (new):
   - Find `synapse_candidates` with status `pending` created more than 3 deep sleep cycles ago
   - Set status to `expired`
   - Rationale: if a weak-signal connection hasn't been validated in 3 cycles, it's noise

**Returns:**
```python
{
    "memories_pruned": int,
    "relations_orphaned": int,
    "myelin_decayed": int,
    "permeability_decayed": int,
    "candidates_expired": int
}
```

#### Sleep Cycles Metrics

**File:** `config/postgres/init.sql`

Add columns to `sleep_cycles` table:

```sql
ALTER TABLE sleep_cycles ADD COLUMN nrem_stats JSONB DEFAULT '{}';
ALTER TABLE sleep_cycles ADD COLUMN rem_stats JSONB DEFAULT '{}';
```

Each phase writes its return dict as the stats JSON. The existing columns remain for backwards compatibility.

### 3B. Adaptive Myelin

**Files:** `reflection-worker/worker.py`, `api-server/myelination.py`

#### Adaptive Decay Rate

Replace fixed decay (0.01 per cycle) with history-aware decay:

```python
def compute_myelin_decay(base_decay: float, reinforcement_count: int) -> float:
    """
    Decay rate inversely proportional to reinforcement history.
    Frequently used cross-project paths resist forgetting.
    """
    return base_decay / (1.0 + 0.3 * reinforcement_count)
```

| reinforcement_count | effective_decay | Resistance vs baseline |
|--------------------:|----------------:|-----------------------:|
| 0 | 0.0100 | 1x |
| 5 | 0.0040 | 2.5x |
| 10 | 0.0025 | 4x |
| 20 | 0.0014 | 7x |
| 30 | 0.0010 | 10x |

#### Adaptive Ceiling

Myelin score maximum grows with usage:

```python
def compute_max_myelin(reinforcement_count: int) -> float:
    """
    New relations cap at 0.5 myelin. Heavily used paths can reach 1.0.
    """
    return min(1.0, 0.5 + 0.05 * reinforcement_count)
```

| reinforcement_count | max_myelin |
|--------------------:|-----------:|
| 0 | 0.50 |
| 5 | 0.75 |
| 10 | 1.00 |

Applied during myelin increment operations (in `update_myelin_score` or equivalent).

#### Co-activation Strengthening

During NREM phase, detect cross-project memory pairs that were both activated in the same plasticity session:

1. Query `memory_relations` where `origin != 'manual'` and both endpoints have `last_activated_at` within same 1-hour window
2. For matching pairs: `myelin_score += MYELIN_DELTA_COACTIVATION` (0.03)
3. Log event in `myelination_events` with `event_type = 'coactivation'`

### 3C. Improved Synthesis

**File:** `reflection-worker/worker.py`

#### Resolution type: `synthesis`

When DeepSeek resolves a contradiction as synthesis:

1. Create synthesis memory (existing):
   - `memory_type = 'schema'`
   - `abstraction_level = 2`
   - `importance = 0.85`
   - `tags` include `'synthesis'`, `'contradiction_resolution'`

2. **Create formal relations** (new):
   - `synthesis → mem_a`: relation_type `derived_from`, weight 0.9, origin `manual`
   - `synthesis → mem_b`: relation_type `derived_from`, weight 0.9, origin `manual`
   - Insert both into `schema_sources` table

3. **Proportional degradation** (new):
   - `mem_a.stability_score *= 0.5`
   - `mem_b.stability_score *= 0.5`
   - Neither is deleted — they lose prominence but retain history

4. **Provenance tracking** (new):
   Store in synthesis memory's `details` JSONB:
   ```json
   {
     "provenance": "contradiction_synthesis",
     "source_memories": ["<mem_a_id>", "<mem_b_id>"],
     "resolution_reasoning": "<DeepSeek output>",
     "original_contradiction_id": "<queue_id>"
   }
   ```

#### Resolution type: `conditional`

When both memories are valid under different conditions:

1. Create conditional memory:
   - `memory_type = 'schema'`
   - `abstraction_level = 1`
   - `importance = 0.8`
   - `details` includes `condition_text`

2. **Create context relations** (new):
   - `conditional → mem_a`: relation_type `applies_to`, weight 0.8
   - `conditional → mem_b`: relation_type `applies_to`, weight 0.8

3. **No degradation** — both originals remain at full stability (both are correct in their context)

4. **Provenance tracking**:
   ```json
   {
     "provenance": "contradiction_conditional",
     "source_memories": ["<mem_a_id>", "<mem_b_id>"],
     "condition": "<condition_text>",
     "original_contradiction_id": "<queue_id>"
   }
   ```

### Tests

| Test | What it verifies |
|------|------------------|
| `test_nrem_validates_suspected_contradictions` | Suspected contradiction with score > 0.5 gets promoted to pending |
| `test_nrem_dismisses_weak_suspected` | Suspected contradiction with score < 0.3 gets dismissed |
| `test_nrem_cluster_reinforcement` | Cluster of 3+ connected memories gets +0.05 weight boost |
| `test_rem_prunes_cold_memories` | access_count=0, stability<0.2, age>21d → stability reduced |
| `test_rem_orphan_relation_cleanup` | Relation between two stability<0.1 memories → active=FALSE |
| `test_rem_tier3_candidate_expiry` | Pending candidate older than 3 cycles → status expired |
| `test_myelin_adaptive_decay` | reinforcement=10 decays 4x slower than reinforcement=0 |
| `test_myelin_adaptive_ceiling` | reinforcement=0 caps at 0.5, reinforcement=10 caps at 1.0 |
| `test_myelin_coactivation` | Two cross-project memories activated same session → myelin +0.03 |
| `test_synthesis_creates_bidirectional_relations` | Synthesis → mem_a and synthesis → mem_b relations exist |
| `test_synthesis_degrades_originals` | Both original memories stability *= 0.5 |
| `test_synthesis_provenance_tracking` | Synthesis memory details contain provenance JSON |
| `test_conditional_no_degradation` | Both originals keep full stability |
| `test_conditional_applies_to_relations` | Conditional → both originals with applies_to |
| `test_sleep_cycle_separate_metrics` | sleep_cycles row has nrem_stats and rem_stats JSONB |

### Files Changed

| File | Change |
|------|--------|
| `reflection-worker/worker.py` | Restructure deep_sleep into `run_nrem_phase()` + `run_rem_phase()`, improved synthesis, contradiction validation |
| `api-server/myelination.py` | `compute_myelin_decay()`, `compute_max_myelin()`, co-activation detection |
| `config/postgres/init.sql` | Add `nrem_stats`, `rem_stats` to sleep_cycles; allow `suspected`/`dismissed`/`expired` statuses |
| `tests/test_deep_sleep_nrem.py` | New — NREM phase tests |
| `tests/test_deep_sleep_rem.py` | New — REM phase tests |
| `tests/test_myelin_adaptive.py` | New — adaptive myelin tests |
| `tests/test_synthesis_improved.py` | New — improved synthesis tests |

---

## Dependency Order

```
Branch 1 (proactive-save-protocol)  ──── independent, can merge first
Branch 2 (runtime-biology)          ──── independent of Branch 1
Branch 3 (deep-sleep-evolution)     ──── depends on Branch 2 (suspected contradictions)
```

Branch 1 and 2 can be developed in parallel. Branch 3 should start after Branch 2's contradiction detection is merged (it validates `suspected` entries created by Branch 2).

## Performance Considerations

- `compute_contradiction_score()` adds ~1ms per candidate in `auto_link_memory()` (regex + arithmetic, no API calls)
- `consolidate_activation()` scans Redis keys — bounded by number of memories in project, typically <100ms
- NREM cluster detection is O(relations) — bounded by `AUTO_LINK_CANDIDATE_LIMIT`
- Adaptive myelin is arithmetic only — negligible overhead
- All new DB writes use existing connection pools

## Deterministic Test Mode

All new features respect `AI_MEMORY_TEST_MODE=true`:
- Contradiction detection uses same deterministic embeddings
- Consolidation thresholds unchanged (deterministic Redis values)
- NREM/REM use heuristic reasoning instead of DeepSeek calls
- Myelin arithmetic is deterministic by nature
