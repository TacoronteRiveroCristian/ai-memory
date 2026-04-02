# Neurogenesis Incremental: Cross-Project Brain Biology

**Date:** 2026-04-02
**Status:** Approved
**Approach:** Incremental layered construction (5 capas)

## Problem Statement

The current brain architecture enforces strict project isolation during consolidation. While project bridges enable cross-project search at query time, the "sleep" phases (schema extraction, relation reinforcement, contradiction resolution) operate exclusively within project boundaries. This means:

- Schemas only abstract within-project patterns
- Relation reinforcement explicitly requires `src.project_id = dst.project_id`
- No organic discovery of cross-project connections
- Tags have no global ontology or cross-project discovery mechanism
- Projects that share patterns (retry strategies, error handling, architectural decisions) never develop biological connections

The brain can search across bridges but cannot synthesize knowledge from multiple projects during sleep — like a brain with regions that can hear each other but never form lasting connections.

## Design Philosophy

- **Evolutionary permeability**: starts fully isolated, connections emerge organically as shared patterns are detected and reinforced
- **Myelination model**: cross-project synapses start "mute" (no signal passes) and gain conductivity with repeated use — exactly like biological myelination
- **Adaptive sleep**: consolidation frequency responds to brain activity, not fixed timers
- **Emergent schemas with home**: cross-project abstractions live in the project where the pattern is strongest, with the ability to migrate
- **Full observability**: biological health dashboard integrated into Brain UI

---

## Layer 1: Myelination and Permeability (Data Model)

### Schema changes to `memory_relations`

Add two columns:

```sql
ALTER TABLE memory_relations
  ADD COLUMN myelin_score FLOAT DEFAULT 0.0,
  ADD COLUMN myelin_last_updated TIMESTAMPTZ DEFAULT NOW();
```

- `myelin_score` range: 0.0 (unmyelinated) to 1.0 (fully myelinated)
- Intra-project relations: `myelin_score` is ignored (always full conductivity)
- Cross-project relations: `myelin_score` modulates signal propagation

**Myelination deltas:**

| Event | Delta | Context |
|-------|-------|---------|
| Direct access (agent search returns cross-project result) | +0.05 | User found it useful |
| Co-activation (spreading activation crosses boundary) | +0.02 | Indirect reinforcement |
| Consolidation validation (REM validates semantic quality) | +0.08 | Brain confirms the link |
| Utility bonus (agent actually uses the cross-project result) | +0.03 | Real-world usefulness |
| Decay per sleep cycle without use | -0.01 | Ebbinghaus applied to myelin |
| REM prunes weak link | -0.05 | Active quality control |

If `myelin_score < 0.0` after decay → deactivate the relation (`active = FALSE`).

### `project_bridges` evolves to `project_permeability`

Replace the binary bridge model with a continuous permeability score:

```sql
CREATE TABLE project_permeability (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    related_project_id INTEGER NOT NULL REFERENCES projects(id),
    permeability_score FLOAT DEFAULT 0.0,
    organic_origin BOOLEAN DEFAULT TRUE,
    formation_reason TEXT,
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, related_project_id)
);
```

- Permeability grows organically: each reinforced cross-project synapse adds +0.01
- Manual bridge creation sets `permeability_score = 0.3, organic_origin = FALSE`
- Threshold for bridge discovery: `permeability_score >= 0.15`
- Decay without activity: -0.005 per REM cycle

**Backward compatibility**: `project_bridges` queries rewritten to use `project_permeability WHERE permeability_score >= 0.15` (or the existing threshold). `resolve_scope_projects()` updated accordingly.

### `myelination_events` (audit log)

```sql
CREATE TABLE myelination_events (
    id SERIAL PRIMARY KEY,
    relation_id INTEGER REFERENCES memory_relations(id),
    permeability_id INTEGER REFERENCES project_permeability(id),
    event_type VARCHAR(50) NOT NULL,  -- access, co_activation, consolidation_validation, decay, prune
    delta FLOAT NOT NULL,
    new_score FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_myelination_events_relation ON myelination_events(relation_id);
CREATE INDEX idx_myelination_events_created ON myelination_events(created_at);
```

### Data flow example

```
Agent searches "retry patterns" in project-A
  -> Results include memory from project-B (via scope bridged/global)
  -> Relation A<->B receives myelin_score += 0.05
  -> project_permeability(A,B) receives += 0.01
  -> Spreading activation reaches memory-C in project-B
  -> Relation B<->C receives myelin_score += 0.02 (co-activation)
  -> Events recorded in myelination_events
```

---

## Layer 2: Adaptive Sleep — NREM and REM Phases

### Sleep cycle model

**NREM (light sleep) — frequent, intra-project:**
- Triggers when `pending_consolidation_count > 20` for a project
- Or by time: minimum every 6h if there was activity
- Does what current deep sleep does: intra-project schema extraction, pruning, hot cluster reinforcement

**REM (deep sleep) — adaptive, cross-project:**
- Triggers based on `cross_project_activity_score`:
  - Count of cross-project searches + cross-project relations formed since last REM
  - If `cross_activity_score > 15` → trigger REM
  - Minimum: every 48h if there was any cross-project activity
  - Maximum: every 7 days regardless (maintenance cycle)

**REM phases (in order):**

1. **Organic bridge discovery**: Find project pairs with semantically similar memories that don't yet have `project_permeability` entries. Create initial permeability if >= 3 memory pairs with similarity > 0.85.

2. **Cross-project schema extraction**: For project pairs with `permeability_score >= 0.15`, find shared patterns. Schema lives in the project with highest `home_score = count * 0.6 + avg_activation * 0.4`.

3. **Cross-project synapse validation**: Evaluate existing cross-project relations. Good semantic support → `myelin_score += 0.08`. Noise → `myelin_score -= 0.05`.

4. **Cross-project contradiction resolution**: Resolve contradictions between memories in connected projects.

5. **Myelin decay**: All cross-project relations unused since last cycle → `myelin_score -= 0.01`.

6. **Permeability decay**: Project pairs without recent cross-project activity → `permeability_score -= 0.005`.

### `sleep_cycles` table

```sql
CREATE TABLE sleep_cycles (
    id SERIAL PRIMARY KEY,
    cycle_type VARCHAR(10) NOT NULL,  -- nrem, rem
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    trigger_reason TEXT,
    projects_processed TEXT[],
    stats JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_sleep_cycles_type ON sleep_cycles(cycle_type);
CREATE INDEX idx_sleep_cycles_started ON sleep_cycles(started_at DESC);
```

`stats` JSONB contains: `schemas_created`, `relations_validated`, `relations_pruned`, `bridges_discovered`, `contradictions_resolved`, `myelin_decayed_count`, etc.

### Adaptive trigger logic (worker polling every 30 min)

```python
# NREM check (per project)
for project in projects_with_activity:
    pending = count_pending_memories(project)
    hours_since_nrem = hours_since_last_nrem(project)
    if pending > 20 or hours_since_nrem > 6:
        trigger_nrem(project)

# REM check (global)
cross_score = count_cross_project_events_since_last_rem()
days_since_rem = days_since_last_rem()
had_cross_activity = cross_score > 0

if cross_score > 15:
    trigger_rem("cross_activity_threshold")
elif days_since_rem > 2 and had_cross_activity:
    trigger_rem("time_with_activity")
elif days_since_rem > 7:
    trigger_rem("maintenance")
```

---

## Layer 3: Spreading Activation with Myelinic Resistance

### Current model (unchanged for intra-project)

```python
propagated_energy = source_energy * 0.4 * weight
```

Depth: 2 hops. Decay factor: 0.4. Min threshold: 0.05. Redis TTL: 900s.

### New model for cross-project propagation

When a relation crosses a project boundary, the decay factor is modulated by myelin:

```python
if is_cross_project(source_memory, target_memory):
    effective_decay = 0.4 * relation.myelin_score
    # myelin=0.0 -> energy=0 (no signal passes)
    # myelin=0.5 -> half signal
    # myelin=1.0 -> full signal (same as intra-project)
else:
    effective_decay = 0.4  # unchanged

propagated_energy = source_energy * effective_decay * weight
```

### Cross-project depth limiting

- Intra-project: 2 hops (unchanged)
- After crossing a project boundary: 1 additional hop max
- Exception: if `permeability_score >= 0.7` between two projects → allow 2 hops cross-project (highly connected projects behave almost as one)

### Co-activation reinforcement events

When propagation crosses a project boundary and resulting energy > 0.05:

1. Record `co_activation` event in `myelination_events`
2. `myelin_score += 0.02` for that relation
3. `project_permeability += 0.005` for that project pair
4. If the target memory appears in the agent's search results → additional `myelin_score += 0.03` (utility reinforcement)

### Performance impact

- The `memory_relations` query already exists — only adds reading `myelin_score` and checking `project_id` of target
- Extra computation is one multiplication — negligible
- Myelination events written async (fire-and-forget) to avoid search latency impact

---

## Layer 4: Emergent Schemas with Home

### Cross-project pattern discovery (during REM phase 2)

**Clustering:**

1. For each project pair with `permeability_score >= 0.15`:
   - Fetch "hot" memories (activation_score > 0.3) from both projects
   - Compute semantic similarity between clusters
   - If >= 3 memory pairs with similarity > 0.85 → schema candidate

2. **Determine schema home:**
   ```python
   home_score_per_project = count_source_memories * 0.6 + avg_activation_score * 0.4
   home_project = max(projects, key=lambda p: home_score[p])
   ```

3. **Generate schema via DeepSeek:**
   - Prompt includes memories from both projects, labeled by origin
   - LLM extracts the unifying principle and notes which project has the strongest manifestation
   - Created as `memory_type = "schema"`, `abstraction_level` incremented, in the home project

4. **Link to secondary project:**
   - `derived_from` relations from schema to secondary project's memories
   - Born with `myelin_score = 0.08` (consolidation-validated)
   - Tag: `cross_project_schema`

### Schema lifecycle

```
Discovery (REM) -> Schema born in home project
  |
  v
Usage: agents search and find the schema
  |
  v
Accessed from secondary project:
  -> myelin on cross-project relations grows
  -> Schema becomes more "visible" from other project
  |
  v
Never accessed:
  -> myelin decays -> cross-project relations deactivate
  -> Schema survives as intra-project schema in home
  -> Not deleted, just loses cross-project connections
```

### Home migration

During REM, recalculate `home_score` based on recent access (last 30 days):
- If another project exceeds current home by > 20% → migrate: update schema's `project_id`
- Record migration in `sleep_cycles.stats`
- Relations rebalanced (former home now has `derived_from` instead)

This allows knowledge to flow toward where it's most needed — like real cortical plasticity.

---

## Layer 5: Observability — `/brain/health` and Brain UI

### Endpoint: `GET /brain/health`

Returns complete biological state:

```json
{
  "overall_health": 0.72,
  "timestamp": "2026-04-02T14:30:00Z",

  "regions": {
    "project-A": {
      "memory_count": 342,
      "active_synapses": 128,
      "avg_activation": 0.45,
      "schemas_count": 12,
      "orphan_memories": 23,
      "orphan_ratio": 0.067,
      "last_nrem": "2026-04-02T03:00:00Z"
    }
  },

  "connectivity": {
    "project-A<->project-B": {
      "permeability_score": 0.34,
      "myelinated_relations": 15,
      "avg_myelin_score": 0.42,
      "cross_schemas": 3,
      "organic_origin": true,
      "formation_reason": "shared retry/resilience patterns"
    }
  },

  "sleep": {
    "last_nrem": "2026-04-02T06:00:00Z",
    "last_rem": "2026-04-01T02:00:00Z",
    "cross_activity_score": 8,
    "rem_threshold": 15,
    "next_rem_estimate": "~24h or when cross_activity > 15"
  },

  "alerts": [
    {
      "type": "fragmentation",
      "severity": "warning",
      "message": "project-C has 45 orphan memories (>30%), consider seeding relations"
    },
    {
      "type": "sleep_needed",
      "severity": "info",
      "message": "cross_activity_score approaching REM threshold (8/15)"
    }
  ]
}
```

### Health metrics

| Metric | Description | Alert threshold |
|--------|------------|-----------------|
| `orphan_ratio` | % memories with no relations | > 30% |
| `avg_myelin_score` | maturity of cross-project connections | < 0.1 after 30 days with bridge |
| `permeability_score` | connection strength between projects | decaying to 0 (bridge dying) |
| `fragmentation_index` | disconnected components in graph | > 5 islands per project |
| `sleep_debt` | accumulated activity without consolidation | cross_score > 2x threshold |

### `overall_health` calculation

```python
overall_health = (
    (1 - avg_orphan_ratio) * 0.25 +          # connectivity
    avg_myelin_score * 0.20 +                  # cross-project maturity
    (1 - fragmentation_index / max_frag) * 0.20 +  # cohesion
    sleep_health * 0.15 +                      # consolidation recency
    schema_coverage * 0.20                     # abstraction quality
)
```

### Brain UI integration

**Global view enhancements:**
- Cross-project edges colored by `myelin_score`: red (0.0-0.2) -> yellow (0.2-0.5) -> green (0.5-0.8) -> bright blue (0.8-1.0)
- Edge thickness proportional to `permeability_score` between projects
- Schema nodes with star icon — cross-project schemas with gold border
- Pulsing/glow on recently activated nodes from spreading activation

**New "Brain Vitals" side panel:**
- Overall health gauge (0-100%)
- Active alerts list
- Sleep cycle timeline (blue bars = NREM, purple bars = REM)
- Mini permeability graph between connected projects

**Live sleep view (v2, not critical for initial release):**
- When brain is in REM cycle, UI shows consolidation animation
- Relations being reinforced glow, pruned ones fade
- Visual representation of what the brain does while "sleeping"

---

## Implementation Order

Each layer is independently testable and deployable:

| Layer | Dependencies | Estimated scope |
|-------|-------------|-----------------|
| 1. Myelination + Permeability | None — data model only | SQL migration + Python model updates |
| 2. Adaptive Sleep | Layer 1 (reads myelin/permeability) | Refactor reflection-worker |
| 3. Spreading Activation | Layer 1 (reads myelin_score) | Modify propagate_activation in server.py |
| 4. Emergent Schemas | Layers 1+2 (REM phase + permeability) | Extend schema extraction in worker.py |
| 5. Observability | All layers (reads all metrics) | New endpoint + Brain UI components |

## Test Strategy

- All layers testable in deterministic mode (`AI_MEMORY_TEST_MODE=true`)
- Myelination deltas use fixed values → deterministic score progression
- Sleep triggers configurable via env vars for testing (lower thresholds)
- Cross-project test fixtures: two projects with known overlapping memories
- Performance targets: `/brain/health` endpoint P95 <= 500ms

## Backward Compatibility

- `project_bridges` table preserved during migration, queries redirected to `project_permeability`
- Existing `resolve_scope_projects()` API unchanged — "bridged" scope now uses `permeability_score >= 0.15` instead of `active = TRUE`
- All existing endpoints maintain current behavior for single-project usage
- New biology is additive — no existing behavior removed
