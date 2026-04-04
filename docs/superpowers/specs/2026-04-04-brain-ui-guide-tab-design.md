# Brain UI — Guide Tab Design Spec

**Date:** 2026-04-04
**Branch:** feat/brain-ui-improvements
**Status:** Approved

## Problem

The Brain UI displays neuroscience-inspired terminology (activation, stability, valence, arousal, Ebbinghaus decay, myelin, tiers, NREM/REM, etc.) without any explanation. Users without neuroscience background cannot understand what they're looking at.

## Solution

Add a new **Guide** tab (alongside Graph and Health) containing a complete reference of every concept, metric, visual cue, and health indicator in the UI.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Delivery mechanism | Dedicated Guide tab | User prefers a single reference page over inline tooltips |
| Internal navigation | Sidebar with section links | Large amount of content (~20 concepts across 13 sections) needs quick navigation |
| Tone | Direct and functional | No metaphors or analogies — state what it is, its range, and what values mean |
| Scope | Full coverage | Graph + node detail panel + health dashboard |

## Component: `GuideView.tsx`

New component rendered when `activeTab === "guide"` in `App.tsx`.

### Layout

```
+------------------+----------------------------------------+
| Sidebar          | Content                                |
| (200px fixed)    | (flex: 1, scrollable)                  |
|                  |                                        |
| [Sections]       | Section title                          |
| > The Graph      | Description text                       |
|   Node Colors    | Table: Visual | Condition | Meaning    |
|   Edges          |                                        |
|   Metrics        |                                        |
|   Emotions       |                                        |
|   Decay          |                                        |
|   Relations      |                                        |
|   Memory Types   |                                        |
|                  |                                        |
| [Health]         |                                        |
|   Overall Health |                                        |
|   Synapses       |                                        |
|   Regions        |                                        |
|   Connectivity   |                                        |
|   Sleep Cycles   |                                        |
+------------------+----------------------------------------+
```

- Sidebar: fixed 200px width, `position: sticky`, scrolls independently if needed
- Content: scrollable area, sections identified by `id` attributes for sidebar anchor links
- Active section highlighted in sidebar (scroll-spy or intersection observer)

### Sections and Content

#### 1. The Graph

How to read the main visualization:
- Each circle = a memory (stored information from the AI agent)
- Lines = relations (detected connections between memories)
- Radial layout: active memories near center, fading memories at edges
- Multiple projects occupy angular sectors
- Click a node to open detail panel, hover to highlight connections

#### 2. Node Colors & Effects

| Visual | Condition | Meaning |
|--------|-----------|---------|
| Red | activation > 0.7 | Very active, being used frequently |
| Cyan | stability > 0.5 | Well consolidated, resistant to forgetting |
| Yellow | stability 0.2 - 0.5 | Decaying, losing strength over time |
| Gray | stability < 0.2 | Nearly forgotten, low activity and stability |
| Pulsing ring | activation > 0.7 | Animated pulse indicates high current usage |
| Glow halo | prominence > 0.5 | Important memory that stands out |
| Larger size | high prominence | Node radius = 4px + prominence * 10px |
| Project ring | global view (no project filter) | Colored border indicating which project the memory belongs to |

#### 3. Edges & Connections

| Visual | Meaning |
|--------|---------|
| Solid line | Relation within same project |
| Dashed blue line | Bridge — connects memories across different projects |
| Glowing line | Myelinated connection (myelin > 0.5) — heavily reinforced pathway |
| Thicker line | Higher weight and/or myelin score |
| Red edge | Tier 1 — instant relation, detected immediately on ingestion |
| Yellow edge | Tier 2 — confirmed relation, validated by usage patterns |
| Purple edge | Tier 3 — reasoning relation, discovered by the reflection worker |

#### 4. Memory Metrics

Shown in the node detail panel when clicking a node.

| Metric | Range | Description |
|--------|-------|-------------|
| Activation | 0.0 — 1.0 | How much this memory is being used right now. High = frequently accessed recently. Low = idle. |
| Stability | 0.0 — 1.0 | Resistance to forgetting. High = well consolidated. Low = fragile, will fade if not accessed. |
| Importance | 0.0 — 1.0 | Assigned weight. Critical decisions and errors score high; routine observations score low. |
| Novelty | 0.0 — 1.0 | How unique compared to existing knowledge. High = new information. Low = redundant. |
| Prominence | 0.0 — 1.0 | Combined score of importance, connections, and recent usage. Determines node size in graph. |

#### 5. Emotional Axes

| Axis | Range | Description |
|------|-------|-------------|
| Valence | -1.0 to +1.0 | Positive or negative association. Errors and failures = negative. Successes and breakthroughs = positive. |
| Arousal | 0.0 — 1.0 | Emotional intensity. Critical production errors = high arousal. Routine notes = low arousal. |

#### 6. Ebbinghaus Decay

Models how memories are forgotten over time (based on the Ebbinghaus forgetting curve).

| Field | Description |
|-------|-------------|
| Stability bar | Visual representation of current stability score (how resistant to forgetting) |
| Halflife | Number of days until stability drops by half. Doubles with each review/access. |
| Reviews | Number of times the memory has been reviewed by the consolidation process. More reviews = longer halflife. |

How it works: memories lose stability over time. Each time a memory is accessed or reviewed, its halflife doubles. A memory with halflife 14d and 3 reviews is much more resistant to forgetting than one with halflife 1d and 0 reviews.

#### 7. Relations & Tiers

When clicking a node, the detail panel shows its relations to other memories.

| Field | Description |
|-------|-------------|
| Relation type | The kind of connection: `same_concept`, `supports`, `extends`, `derived_from`, `applies_to` |
| Tier (T1/T2/T3) | Confidence level of the relation (see Edges section above) |
| Weight | Connection strength (0.0 — 1.0). Higher = stronger association. |
| Myelin | Reinforcement score (0.0 — 1.0). Increases each time both memories are accessed together. High myelin = well-established pathway. |
| Reinforcement count | Number of times this connection has been activated. |
| Origin | `manual` (user-created) or `vector_inference` (detected by similarity). |

#### 8. Memory Types

| Type | Letter | Description |
|------|--------|-------------|
| decision | D | A choice or decision made during work |
| error | E | An error, bug, or failure encountered |
| observation | O | A general observation or note |
| schema | S | An abstract pattern detected across multiple memories |
| insight | I | A conclusion or realization derived from other memories |
| pattern | P | A recurring pattern identified in the data |

The letter is displayed inside the node at mid-zoom level (zoom >= 1.8).

#### 9. Overall Health

Single percentage score (0-100%) representing the overall state of the memory system. Calculated from region health, connectivity, orphan ratios, and synapse quality.

| Color | Range | Meaning |
|-------|-------|---------|
| Cyan/green | >= 70% | Healthy system |
| Yellow | 40-69% | Needs attention |
| Red | < 40% | Critical issues |

#### 10. Synapse Formation

How the system creates connections between memories, organized in three tiers:

| Tier | Name | Description |
|------|------|-------------|
| T1 | Instinct | Instant relations created when a memory is stored. Based on direct similarity. |
| T2 | Perception | Confirmed relations. Initially T1, promoted after usage patterns validate the connection. |
| T3 | Reasoning | Deep relations discovered by the reflection worker (offline consolidation). Shows promoted/pending/rejected counts. |

#### 11. Regions

Each project is a "region" of the brain. Region stats:

| Field | Description |
|-------|-------------|
| Memory count | Total memories in this project/region |
| Active synapses | Number of active relations in this region |
| Orphan ratio | Percentage of memories with no relations. High orphan ratio (> 20%) = memories are isolated, not well connected. |
| Schemas count | Number of abstract patterns detected in this region |
| Keyphrases coverage | How well keyphrases cover the content in this region |
| Last NREM | When the last consolidation cycle ran for this region |

#### 12. Connectivity

Measures how well regions communicate with each other. Each entry is a pair of projects.

| Field | Description |
|-------|-------------|
| Permeability score | 0.0 — 1.0. How easily information flows between two regions. High = well connected. |
| Myelinated relations | Number of strong, reinforced connections between the two regions |
| Avg myelin score | Average reinforcement level of cross-region connections |
| Organic origin | Whether the connection formed naturally (vs manually created) |
| Formation reason | Why this inter-region pathway exists |

#### 13. Sleep Cycles

The system runs periodic consolidation processes modeled after biological sleep:

| Field | Description |
|-------|-------------|
| Last NREM | Last time the consolidation worker ran (promotes memories, updates relation weights, applies Ebbinghaus decay, detects contradictions). Runs every ~6 hours. |
| Last REM | Last time the cross-project analysis ran (finds patterns across different projects). |
| Cross-activity score | Current level of cross-project activity. When this exceeds the threshold, a REM cycle is triggered. |
| REM threshold | The threshold value that triggers a REM cycle. |
| "REM cycle needed" | Alert shown when cross-activity >= threshold, meaning the system should run cross-project consolidation. |

## Integration

### Files to create
- `brain-ui/src/components/GuideView.tsx` — main component
- `brain-ui/src/components/GuideView.module.css` — styles

### Files to modify
- `brain-ui/src/App.tsx` — add Guide tab rendering (`activeTab === "guide"`)
- `brain-ui/src/components/TabSwitcher.tsx` — add "Guide" option to tab list

### No new dependencies required

The component is purely presentational (static content + scroll-spy). No API calls, no new libraries.

## Styling

- Match existing dark theme (`background: #0a0a12`, `#12121f` for cards)
- Use existing color palette from `nodeStyle.ts` for consistency
- Tables with subtle row borders (`#ffffff0a`)
- Sidebar: `#0f0f1a` background, active item highlighted with left border + blue tint
- Content: readable line-height (1.7), 13px body text
- Section headers: 20px bold, with subtle description text below in `#666`
