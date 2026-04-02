# Neurogenesis Incremental: Cross-Project Brain Biology

**Date:** 2026-04-02
**Status:** Approved
**Approach:** Incremental layered construction (6 capas)

## Problem Statement

The current brain architecture has two fundamental problems:

**1. Project isolation during consolidation.** While project bridges enable cross-project search at query time, the "sleep" phases (schema extraction, relation reinforcement, contradiction resolution) operate exclusively within project boundaries. Schemas only abstract within-project patterns. Relation reinforcement explicitly requires `src.project_id = dst.project_id`. The brain can search across bridges but cannot synthesize knowledge from multiple projects during sleep.

**2. Fragile synapse formation.** The brain depends on exact tag string matching as a gate-keeper for creating relations between memories. `compute_tag_overlap()` uses set intersection after minimal normalization, so `grafana` vs `tech/grafana`, `retry-pattern` vs `retry-patterns`, `k8s` vs `kubernetes` all fail to match. The critical filter at `server.py:1534` discards candidates with `semantic_score < 0.88` if they share no tags — meaning a memory with 0.87 cosine similarity (very high) is rejected if tags don't match exactly. The brain has 1536-dimensional embeddings but relies on string comparison to decide if two neurons connect.

The brain has 10 senses but uses only 1 (tags) as a binary gate. Semantic embeddings, emotional metadata (valence/arousal), importance, temporal proximity, abstraction level, and memory type are all stored but underutilized in synapse formation.

## Design Philosophy

- **Multi-modal perception**: synapse formation uses ALL available signals, not just tags. Tags become one input among many, not a gate-keeper.
- **Evolutionary permeability**: starts fully isolated, connections emerge organically as shared patterns are detected and reinforced
- **Myelination model**: cross-project synapses start "mute" (no signal passes) and gain conductivity with repeated use — exactly like biological myelination
- **Adaptive sleep**: consolidation frequency responds to brain activity, not fixed timers
- **Emergent schemas with home**: cross-project abstractions live in the project where the pattern is strongest, with the ability to migrate
- **Dual-vector architecture**: each memory has a content vector (what it says) and a domain vector (what it's about), enabling Qdrant-native fusion search
- **Full observability**: biological health dashboard integrated into Brain UI

---

## Layer 0: Multi-Modal Sensory Cortex (Foundation)

### Why tags alone fail — and what replaces them

The current system treats synapse formation as: "do these two memories share tag strings?" This is like asking "do these two people have the same name?" to determine if they're related. The real question should be: "how much evidence, from any source, suggests these memories are related?"

Investigation of the codebase revealed 10 signals available but only 3 used (semantic score, tag overlap, lexical overlap), with tags acting as a hard gate. Investigation of Qdrant's capabilities revealed native multi-vector storage and RRF fusion search. Investigation of AI memory systems (Mem0, Zep, MemGPT, GraphRAG) revealed that the most effective systems use multi-signal fusion, not single-signal gating.

### Architecture: Dual-Vector + Multi-Signal Cascade

#### Part A: Automatic Concept Extraction (KeyBERT)

**Problem**: User-provided tags are inconsistent, sparse, and often missing. Two memories about the same concept may have completely different tags or no tags at all.

**Solution**: Extract keyphrases automatically from memory content using KeyBERT, which leverages the existing embedding model to find the most semantically representative phrases.

At write time (< 50ms overhead):
1. Memory content → KeyBERT extracts 5-8 keyphrases (uses cosine similarity between candidate phrases and document embedding)
2. User-provided tags are normalized and appended to keyphrases (not discarded)
3. Combined keyphrases stored in new field `memory_log.keyphrases TEXT[]`

```python
from keybert import KeyBERT

# Reuse existing embedding model for extraction
kw_model = KeyBERT(model=embedding_model)

def extract_keyphrases(content: str, user_tags: list[str]) -> list[str]:
    # Extract 5-8 keyphrases using existing embeddings
    keywords = kw_model.extract_keywords(
        content,
        keyphrase_ngram_range=(1, 2),
        stop_words="english",
        top_n=8,
        use_mmr=True,          # Maximal Marginal Relevance for diversity
        diversity=0.5,
    )
    keyphrases = [kw for kw, score in keywords if score > 0.25]
    
    # Append normalized user tags (complementary, not replacement)
    for tag in normalize_tags(user_tags):
        if tag not in keyphrases:
            keyphrases.append(tag)
    
    return keyphrases
```

**Why KeyBERT over alternatives:**
- **vs TF-IDF**: KeyBERT uses semantic similarity, not frequency. Finds concepts even if the exact word appears only once.
- **vs spaCy NER**: NER finds entities (people, places) but misses abstract concepts ("scalability", "error handling"). KeyBERT finds both.
- **vs LLM extraction**: LLM is 100-1000x more expensive and slower. KeyBERT runs in ~50ms with no API calls.
- **vs YAKE**: YAKE is purely statistical, no semantic understanding. KeyBERT leverages the embedding model we already have.

KeyBERT doesn't replace user tags — it supplements them. A memory tagged `k8s` by the user would get keyphrases like `["kubernetes deployment", "container orchestration", "pod scaling", "k8s"]`. The domain vector (see Part B) captures all of this semantically.

During NREM consolidation, batch LLM calls refine keyphrases for memories that have been accessed multiple times (worth the investment). This mimics biological memory: fast initial encoding, slow refinement during sleep.

#### Part B: Dual-Vector Qdrant Architecture

**Problem**: A single content embedding captures what a memory says but not the conceptual domain it belongs to. Two memories can discuss the same topic from different angles and have moderate content similarity but high domain similarity.

**Solution**: Store two named vectors per memory in Qdrant.

```python
# Collection creation (replaces current single-vector config)
await qdrant.create_collection(
    collection_name="memories",
    vectors_config={
        "content": models.VectorParams(
            size=1536,                          # OpenAI text-embedding-3-small
            distance=models.Distance.COSINE,
            on_disk=True,
        ),
        "domain": models.VectorParams(
            size=1536,                          # Same model, different input
            distance=models.Distance.COSINE,
            on_disk=True,
        ),
    },
)
```

**Content vector** (already exists): embedding of the full memory content.
**Domain vector** (new): embedding of the keyphrases concatenated as a phrase.

```python
# At write time
content_embedding = await get_embedding(memory_content)           # "Fixed retry logic in payment service after timeout errors"
domain_embedding = await get_embedding(" ".join(keyphrases))      # "retry logic payment service timeout error handling resilience"
```

**Why this works**: The content vector captures the specific narrative. The domain vector captures the conceptual fingerprint. Two memories — "Fixed retry logic in payment service" and "Added circuit breaker to order service" — might have only 0.75 content similarity but 0.90 domain similarity because their keyphrases overlap in the concepts of resilience and error handling.

**Cost**: One additional embedding API call per memory write. Cached in Redis like existing embeddings. At typical usage (hundreds of memories/day), cost is negligible (~$0.01/day).

#### Part C: Fusion Search (replaces current single-vector search)

Replace the current Qdrant query with a prefetch + RRF fusion query:

```python
# Current (single vector)
response = await qdrant.query_points(
    query=content_embedding,
    limit=limit,
)

# New (dual vector fusion with RRF)
response = await qdrant.query_points(
    collection_name="memories",
    prefetch=[
        models.Prefetch(query=content_embedding, using="content", limit=30),
        models.Prefetch(query=domain_embedding, using="domain", limit=30),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=limit,
    query_filter=query_filter,
    with_payload=True,
)
```

This means a search automatically considers BOTH what you said and what domain you're in. A query about "how to handle timeouts" matches memories about timeout handling (content) AND memories about resilience patterns (domain) even if they use different words.

**Fallback**: If domain embedding is missing (old memories not yet migrated), fall back to content-only search. Migration backfills domain vectors during first NREM cycle.

#### Part D: Multi-Signal Synapse Cascade (replaces heuristic gate)

The current `classify_relation_heuristic()` uses an if/elif chain with tags as a gate. Replace with a confidence cascade that uses ALL available signals:

**Signals available per memory pair:**

| Signal | Source | Range | What it captures |
|--------|--------|-------|-----------------|
| `semantic_score` | Qdrant content vector cosine | [0, 1] | Same narrative / facts |
| `domain_score` | Qdrant domain vector cosine | [0, 1] | Same conceptual area |
| `lexical_overlap` | Token Jaccard (already exists) | [0, 1] | Shared vocabulary |
| `emotional_proximity` | Euclidean in (valence, arousal) space | [0, 1] | Similar emotional charge |
| `importance_attraction` | Mean of both importances | [0, 1] | Important memories are "magnetic" |
| `temporal_proximity` | `exp(-hours_apart / 48)` | [0, 1] | Created near each other |
| `type_compatibility` | Lookup table | {0, 0.5, 1} | Compatible memory types |

**Emotional proximity** (new signal):
```python
def emotional_proximity(mem_a, mem_b) -> float:
    # Euclidean distance in 2D emotion space, normalized to [0, 1]
    dv = (mem_a["valence"] - mem_b["valence"]) ** 2
    da = (mem_a["arousal"] - mem_b["arousal"]) ** 2
    distance = math.sqrt(dv + da)
    max_distance = math.sqrt(4 + 1)  # valence [-1,1], arousal [0,1]
    return 1.0 - min(distance / max_distance, 1.0)
```

**Type compatibility matrix:**
```
              observation  decision  schema  insight  error  pattern
observation       1.0        0.5      0.5     0.7    0.7     0.5
decision          0.5        1.0      0.7     0.7    0.3     0.5
schema            0.5        0.7      1.0     0.8    0.3     0.9
insight           0.7        0.7      0.8     1.0    0.5     0.8
error             0.7        0.3      0.3     0.5    1.0     0.3
pattern           0.5        0.5      0.9     0.8    0.3     1.0
```

**The Cascade:**

```
Tier 1 — INSTINCT (dominant signal, no confirmation needed):
  semantic_score > 0.92
  → Immediate synapse: "same_concept", weight = semantic_score
  Rationale: extreme cosine similarity = same idea expressed differently.
  No tags, domain, or other signals needed.

Tier 2 — PERCEPTION (strong signal + one confirmation):
  semantic_score > 0.75 AND any ONE of:
    - domain_score > 0.70
    - lexical_overlap > 0.40
    - emotional_proximity > 0.80 AND temporal_proximity > 0.50
  → Confirmed synapse: type inferred from signal profile
  Rationale: good similarity + corroboration from another sense.

Tier 3 — REASONING (multiple weak signals converge):
  combined_score > 0.55 where:
    combined = 0.40 * semantic_score
             + 0.20 * domain_score
             + 0.12 * lexical_overlap
             + 0.10 * emotional_proximity
             + 0.08 * importance_attraction
             + 0.05 * temporal_proximity
             + 0.05 * type_compatibility
  → Candidate synapse: queued for validation during next sleep cycle
  → Stored in new `synapse_candidates` table with all signal values
  Rationale: individually weak signals that together suggest a relationship.
  Sleep validates with full context before committing.

Tier 4 — DISCOVERY (only during REM sleep):
  HDBSCAN cluster co-membership in embedding space
  + Qdrant Recommend API: "memories similar to these cluster members"
  → Discovered synapse: born with weight 0.30
  Rationale: statistical patterns invisible to individual pair comparison.
  Finds relationships that no combination of pairwise signals would catch.
```

**Relation type inference** (replaces the current if/elif chain):

Based on which signals are strongest:
- `semantic_score` dominant → `same_concept`
- `domain_score` dominant, different content → `supports` (same domain, different angle)
- `lexical_overlap` dominant → `extends` (builds on same vocabulary/ideas)
- Cross-project + high domain → `derived_from` (knowledge transfer)
- Emotional proximity dominant → `applies_to` (similar emotional context)
- LLM classification invoked only when cascade produces a synapse but type is ambiguous (semantic and domain scores within 0.05 of each other)

#### Part E: Tag Canonicalization (preserved from original, simplified)

Tags still matter as ONE signal. Improve their quality:

1. **Alias map**: `config/tag_aliases.json` — `k8s→kubernetes`, `pg→postgresql`, etc. Loaded at startup, applied during `canonicalize_tag()`.
2. **Leaf extraction**: `tech/grafana` → store both `tech/grafana` and `grafana`.
3. **Simple singularization**: strip trailing `s`/`es` with basic rules.

These improvements are still valuable because better tags → better keyphrases (user tags are appended to KeyBERT output) → better domain vectors. But tags are no longer a gate — they're a signal booster.

#### Part F: Synapse Candidates Table

Tier 3 candidates need a holding area until sleep validates them:

```sql
CREATE TABLE synapse_candidates (
    id SERIAL PRIMARY KEY,
    source_memory_id UUID NOT NULL REFERENCES memory_log(id),
    target_memory_id UUID NOT NULL REFERENCES memory_log(id),
    semantic_score FLOAT NOT NULL,
    domain_score FLOAT NOT NULL,
    lexical_overlap FLOAT NOT NULL,
    emotional_proximity FLOAT NOT NULL,
    importance_attraction FLOAT NOT NULL,
    temporal_proximity FLOAT NOT NULL,
    type_compatibility FLOAT NOT NULL,
    combined_score FLOAT NOT NULL,
    suggested_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',  -- pending, promoted, rejected
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    UNIQUE (source_memory_id, target_memory_id)
);

CREATE INDEX idx_synapse_candidates_status ON synapse_candidates(status);
CREATE INDEX idx_synapse_candidates_score ON synapse_candidates(combined_score DESC);
```

During NREM sleep, the worker reviews pending candidates:
- If both memories are still active (not decayed) AND the relation doesn't already exist → promote to `memory_relations`
- If one memory has decayed or the combined score has dropped (recalculated) → reject
- Keeps the graph clean while still allowing weak-signal discovery

#### Part G: HDBSCAN Cluster Discovery (during REM)

For finding relationships invisible to pairwise comparison:

```python
import hdbscan
from umap import UMAP

async def discover_clusters(project_memories: list[dict]) -> list[list[str]]:
    # 1. Extract content vectors from Qdrant
    vectors = [m["content_vector"] for m in project_memories]
    
    # 2. Dimensionality reduction (1536 → 50 dims, preserves local structure)
    reducer = UMAP(n_components=50, metric="cosine", random_state=42)
    reduced = reducer.fit_transform(vectors)
    
    # 3. Density-based clustering (no need to specify k)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=5,    # minimum 5 memories to form a cluster
        min_samples=3,         # noise tolerance
        metric="euclidean",    # on UMAP-reduced space
    )
    labels = clusterer.fit_predict(reduced)
    
    # 4. Group memories by cluster (label=-1 is noise, skip)
    clusters = {}
    for i, label in enumerate(labels):
        if label >= 0:
            clusters.setdefault(label, []).append(project_memories[i]["id"])
    
    return list(clusters.values())
```

Used in REM phase to:
1. Find clusters within each project → intra-project schema candidates
2. Find clusters across bridged projects → cross-project schema candidates
3. For each cluster, create weak synapses between members that aren't yet connected (born at weight 0.30)

**Why HDBSCAN over alternatives:**
- **vs DBSCAN**: HDBSCAN handles varying density (some topics have many memories, others few). DBSCAN needs a fixed epsilon that can't accommodate this.
- **vs k-means**: We don't know how many clusters exist. k-means requires k.
- **vs agglomerative**: O(n²) memory, problematic above 50k memories. HDBSCAN is O(n log n).

**Why UMAP before clustering:**
- 1536 dims is too sparse for distance-based clustering ("curse of dimensionality")
- UMAP preserves local neighborhood structure (critical for finding real clusters)
- Reduces noise from irrelevant embedding dimensions
- 50 dims is enough to capture meaningful structure, fast to cluster

### Impact on upper layers

Layer 0 transforms the foundation that all other layers build on:
- **Layer 1 (myelination)**: More synapses to myelinate. Cross-project synapses form organically via domain similarity, not just shared tag strings.
- **Layer 2 (sleep)**: NREM validates Tier 3 candidates. REM uses HDBSCAN for Tier 4 discovery. Sleep has real work to do.
- **Layer 3 (activation)**: Spreading activation traverses a richer graph with more cross-project paths.
- **Layer 4 (schemas)**: HDBSCAN clusters feed directly into schema extraction — schemas emerge from statistically significant groups, not just tag-matched pairs.
- **Layer 5 (observability)**: Signal breakdown visible in `/brain/health` — which signals drive the most synapses, which are underutilized.

### Migration strategy

1. Add `keyphrases` column to `memory_log` (nullable, backward compatible)
2. Add `domain` vector to Qdrant collection (named vectors config)
3. Create `synapse_candidates` table
4. First NREM cycle after deployment:
   - Backfill keyphrases for all existing memories (KeyBERT batch)
   - Backfill domain vectors in Qdrant
   - Re-run auto_link with new cascade for high-value memories (activation_score > 0.3)
5. New memories immediately get dual vectors + cascade scoring
6. Install Python dependencies: `keybert`, `hdbscan`, `umap-learn`

### Performance considerations

| Operation | Latency impact | Mitigation |
|-----------|---------------|------------|
| KeyBERT extraction | +50ms per write | Async, non-blocking |
| Domain embedding | +100ms per write (API call) | Redis cache, batch during quiet periods |
| Fusion search | ~same as single-vector | Qdrant handles fusion natively |
| Cascade scoring | +5ms per candidate pair | 7 signals, all cheap arithmetic |
| HDBSCAN clustering | 5-30s per project | Only during REM sleep, background |

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
  -> Qdrant fusion search finds memories from project-A (content match) AND project-B (domain match)
  -> Cascade: semantic=0.78, domain=0.91 → Tier 2 synapse (domain confirmed)
  -> Relation A<->B created with myelin_score = 0.0
  -> project_permeability(A,B) created or incremented += 0.01
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
- Phases:
  - Intra-project schema extraction (existing, unchanged)
  - Pruning cold memories (existing, unchanged)
  - Hot cluster reinforcement (existing, unchanged)
  - **NEW: Validate synapse candidates** — review Tier 3 candidates, promote or reject
  - **NEW: Refine keyphrases** — batch LLM call to improve keyphrases for frequently-accessed memories

**REM (deep sleep) — adaptive, cross-project:**
- Triggers based on `cross_project_activity_score`:
  - Count of cross-project searches + cross-project relations formed since last REM
  - If `cross_activity_score > 15` → trigger REM
  - Minimum: every 48h if there was any cross-project activity
  - Maximum: every 7 days regardless (maintenance cycle)

**REM phases (in order):**

1. **HDBSCAN cluster discovery**: Run UMAP + HDBSCAN on each project's memories. Then on merged memories of permeable project pairs. Find clusters that span project boundaries.

2. **Organic bridge discovery**: From HDBSCAN results, find project pairs with cross-project clusters that don't yet have `project_permeability` entries. Create initial permeability if cluster has >= 5 members from both projects.

3. **Cross-project schema extraction**: For project pairs with `permeability_score >= 0.15`, generate schemas from cross-project clusters. Schema lives in the project with highest `home_score = count * 0.6 + avg_activation * 0.4`.

4. **Cross-project synapse validation**: Evaluate existing cross-project relations. Recalculate cascade score with current data. Good support → `myelin_score += 0.08`. Degraded → `myelin_score -= 0.05`.

5. **Cross-project contradiction resolution**: Resolve contradictions between memories in connected projects.

6. **Tier 4 synapse formation**: From HDBSCAN clusters, create weak synapses between co-clustered memories that aren't yet connected. Use Qdrant Recommend API to find additional candidates: "memories similar to these cluster members but not yet linked".

7. **Myelin decay**: All cross-project relations unused since last cycle → `myelin_score -= 0.01`.

8. **Permeability decay**: Project pairs without recent cross-project activity → `permeability_score -= 0.005`.

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

`stats` JSONB contains: `schemas_created`, `relations_validated`, `relations_pruned`, `bridges_discovered`, `contradictions_resolved`, `myelin_decayed_count`, `candidates_promoted`, `candidates_rejected`, `clusters_found`, `tier4_synapses_created`, etc.

### Adaptive trigger logic (worker polling every 30 min)

```python
# NREM check (per project)
for project in projects_with_activity:
    pending = count_pending_memories(project)
    pending_candidates = count_pending_synapse_candidates(project)
    hours_since_nrem = hours_since_last_nrem(project)
    if pending > 20 or pending_candidates > 10 or hours_since_nrem > 6:
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

### Cross-project pattern discovery (during REM phases 1-3)

**Clustering (powered by Layer 0 HDBSCAN):**

1. REM phase 1 produces HDBSCAN clusters that may span project boundaries
2. For clusters spanning 2+ projects with `permeability_score >= 0.15`:
   - Filter to clusters with >= 3 members per project (significant cross-pollination)
   - These become cross-project schema candidates

3. **Determine schema home:**
   ```python
   home_score_per_project = count_source_memories * 0.6 + avg_activation_score * 0.4
   home_project = max(projects, key=lambda p: home_score[p])
   ```

4. **Generate schema via DeepSeek:**
   - Prompt includes memories from both projects, labeled by origin
   - Also includes keyphrases for each memory (richer context than raw content alone)
   - LLM extracts the unifying principle and notes which project has the strongest manifestation
   - Created as `memory_type = "schema"`, `abstraction_level` incremented, in the home project

5. **Link to secondary project:**
   - `derived_from` relations from schema to secondary project's memories
   - Born with `myelin_score = 0.08` (consolidation-validated)
   - Keyphrases include `cross_project_schema` + merged keyphrases from both project clusters

### Schema lifecycle

```
Discovery (REM) -> Schema born in home project
  |
  v
Usage: agents search and find the schema
  (fusion search finds it via domain vector even without exact tag match)
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
      "keyphrases_coverage": 0.94,
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
      "formation_reason": "shared retry/resilience patterns",
      "dominant_signals": ["domain_similarity", "semantic_score"]
    }
  },

  "synapse_formation": {
    "tier1_instant": 45,
    "tier2_confirmed": 128,
    "tier3_candidates_pending": 23,
    "tier3_promoted": 67,
    "tier3_rejected": 12,
    "tier4_discovered": 34,
    "signal_contribution": {
      "semantic_score": 0.41,
      "domain_score": 0.23,
      "lexical_overlap": 0.14,
      "emotional_proximity": 0.09,
      "importance_attraction": 0.06,
      "temporal_proximity": 0.04,
      "type_compatibility": 0.03
    }
  },

  "sleep": {
    "last_nrem": "2026-04-02T06:00:00Z",
    "last_rem": "2026-04-01T02:00:00Z",
    "cross_activity_score": 8,
    "rem_threshold": 15,
    "next_rem_estimate": "~24h or when cross_activity > 15",
    "clusters_last_rem": 12,
    "candidates_validated_last_nrem": 15
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
    },
    {
      "type": "signal_imbalance",
      "severity": "info",
      "message": "emotional_proximity contributing <5% to synapse formation — valence/arousal may be underutilized"
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
| `keyphrases_coverage` | % memories with keyphrases extracted | < 80% (migration incomplete) |
| `signal_contribution` | which signals drive synapse formation | any signal < 3% (underutilized) |
| `candidate_rejection_rate` | % Tier 3 candidates rejected in sleep | > 70% (threshold too low) |

### `overall_health` calculation

```python
overall_health = (
    (1 - avg_orphan_ratio) * 0.20 +          # connectivity
    avg_myelin_score * 0.15 +                  # cross-project maturity
    (1 - fragmentation_index / max_frag) * 0.15 +  # cohesion
    sleep_health * 0.15 +                      # consolidation recency
    schema_coverage * 0.15 +                   # abstraction quality
    keyphrases_coverage * 0.10 +               # sensory cortex health
    signal_balance * 0.10                      # multi-modal balance
)
```

### Brain UI integration

**Global view enhancements:**
- Cross-project edges colored by `myelin_score`: red (0.0-0.2) → yellow (0.2-0.5) → green (0.5-0.8) → bright blue (0.8-1.0)
- Edge thickness proportional to `permeability_score` between projects
- Schema nodes with star icon — cross-project schemas with gold border
- Pulsing/glow on recently activated nodes from spreading activation
- Tier 3 candidate synapses shown as dashed lines (not yet validated)

**New "Brain Vitals" side panel:**
- Overall health gauge (0-100%)
- Active alerts list
- Sleep cycle timeline (blue bars = NREM, purple bars = REM)
- Mini permeability graph between connected projects
- Signal contribution pie chart (which senses drive synapse formation)

**Live sleep view (v2, not critical for initial release):**
- When brain is in REM cycle, UI shows consolidation animation
- HDBSCAN clusters visualized as colored regions
- Relations being reinforced glow, pruned ones fade
- Tier 3 candidates being promoted flash green, rejected flash red
- Visual representation of what the brain does while "sleeping"

---

## Implementation Order

Each layer is independently testable and deployable:

| Layer | Dependencies | Estimated scope |
|-------|-------------|-----------------|
| 0. Multi-Modal Sensory Cortex | None — foundation | KeyBERT + dual-vector Qdrant + cascade scoring + HDBSCAN |
| 1. Myelination + Permeability | Layer 0 (richer synapse graph to myelinate) | SQL migration + Python model updates |
| 2. Adaptive Sleep | Layers 0+1 (candidates to validate, clusters to discover) | Refactor reflection-worker |
| 3. Spreading Activation | Layer 1 (reads myelin_score) | Modify propagate_activation in server.py |
| 4. Emergent Schemas | Layers 0+2 (HDBSCAN clusters + REM phase) | Extend schema extraction in worker.py |
| 5. Observability | All layers (reads all metrics) | New endpoint + Brain UI components |

## New Dependencies

```
# requirements.txt additions
keybert>=0.8.0          # Keyphrase extraction using embeddings
hdbscan>=0.8.33         # Density-based clustering for REM discovery
umap-learn>=0.5.0       # Dimensionality reduction before clustering
```

## Test Strategy

- All layers testable in deterministic mode (`AI_MEMORY_TEST_MODE=true`)
- KeyBERT uses deterministic embeddings in test mode (same `deterministic_embedding()` function)
- HDBSCAN gets fixed random seed for reproducibility
- Myelination deltas use fixed values → deterministic score progression
- Sleep triggers configurable via env vars for testing (lower thresholds)
- Cross-project test fixtures: two projects with known overlapping memories, different tags but similar content
- Cascade scoring tested with known signal combinations → verify correct tier assignment
- Performance targets: fusion search P95 <= 300ms, `/brain/health` endpoint P95 <= 500ms

## Backward Compatibility

- `project_bridges` table preserved during migration, queries redirected to `project_permeability`
- Existing `resolve_scope_projects()` API unchanged — "bridged" scope now uses `permeability_score >= 0.15` instead of `active = TRUE`
- Existing single-vector Qdrant search still works — fusion gracefully degrades if domain vector missing
- All existing endpoints maintain current behavior for single-project usage
- Memories without keyphrases still participate in Tier 1 and Tier 2 (semantic + lexical signals)
- New biology is additive — no existing behavior removed
