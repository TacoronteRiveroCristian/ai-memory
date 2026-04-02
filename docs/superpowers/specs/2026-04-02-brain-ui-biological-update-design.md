# Brain UI — Biological Update Design

> Sprint to bring the frontend in sync with the backend's biological brain features. Covers data visualization, new components, and UX improvements.

**Date:** 2026-04-02
**Approach:** Hybrid — new components from scratch, surgical refactors on existing ones, full rewrite of MemoryDetail only.
**Excluded:** Timeline slider (deferred to a future iteration).

---

## 1. Architecture & Component Structure

### Tab Routing

State `activeTab: "graph" | "health"` in App.tsx. No react-router — simple conditional rendering.

```
App
├── TopBar (existing, minor: add TabSwitcher)
│   ├── KeywordFilter (unchanged)
│   └── ProjectSelector (unchanged)
├── StatsBar ← NEW (graph tab only)
├── [activeTab === "graph"]
│   ├── BrainGraph (existing, refactor render callbacks)
│   └── MemoryDetail ← REWRITE (expanded sidebar)
└── [activeTab === "health"]
    └── HealthView ← NEW (full dashboard)
```

### New Files

| File | Purpose |
|------|---------|
| `components/TabSwitcher.tsx` + `.module.css` | Graph / Health tab toggle |
| `components/StatsBar.tsx` + `.module.css` | Live graph counters |
| `components/HealthView.tsx` + `.module.css` | Brain health dashboard |

### Modified Files

| File | Change |
|------|--------|
| `types.ts` | Add biological fields to GraphEdge, new BrainHealthResponse type |
| `api/client.ts` | Add `fetchBrainHealth()` |
| `App.tsx` | Tab state, pass edges to MemoryDetail, hover relay |
| `components/BrainGraph.tsx` | Hover highlight, edge dual encoding, semantic zoom, cluster gravity |
| `components/MemoryDetail.tsx` + `.module.css` | Full rewrite |
| `components/nodeStyle.ts` | Update for semantic zoom levels |

---

## 2. Types & API Changes

### GraphEdge — New Fields

```typescript
interface GraphEdge {
  // existing: source_memory_id, target_memory_id, relation_type, weight, origin, active, reinforcement_count, last_activated_at
  myelin_score: number;           // [0, 1] conductivity
  evidence_json?: {
    tier: 1 | 2 | 3;
    relation_type: string;
    reason: string;
    signals: Record<string, number>;
  };
}
```

### BrainHealthResponse — New Type

```typescript
interface BrainHealthResponse {
  overall_health: number;
  timestamp: string;
  regions: Record<string, {
    memory_count: number;
    active_synapses: number;
    avg_activation: number;
    schemas_count: number;
    orphan_memories: number;
    orphan_ratio: number;
    keyphrases_coverage: number;
    last_nrem: string | null;
  }>;
  connectivity: Record<string, {
    permeability_score: number;
    myelinated_relations: number;
    avg_myelin_score: number;
    organic_origin: boolean;
    formation_reason: string;
  }>;
  synapse_formation: {
    tier1_instant: number;
    tier2_confirmed: number;
    tier3_candidates_pending: number;
    tier3_promoted: number;
    tier3_rejected: number;
  };
  sleep: {
    last_nrem: string | null;
    last_rem: string | null;
    cross_activity_score: number;
    rem_threshold: number;
  };
  alerts: Array<{
    type: string;
    severity: "info" | "warning" | "critical";
    message: string;
  }>;
}
```

### New API Function

```typescript
fetchBrainHealth(): Promise<BrainHealthResponse>
// GET /brain/health (with API key header)
```

### MemoryDetailResponse — Keyphrases

The `keyphrases: string[]` field already exists in the backend response. The UI type needs to declare it.

---

## 3. Edge Dual Encoding

**Color by tier:**

| Tier | Color | Hex |
|------|-------|-----|
| T1 Instinct | Red | `#ff6b6b` |
| T2 Perception | Yellow | `#ffd93d` |
| T3 Reasoning | Purple | `#a78bfa` |
| Bridge (cross-project) | Blue, dashed | `#54a0ff` |
| No tier / fallback | Source node color | (current behavior) |

**Myelin encoding (width + glow):**
- Width: `0.5 + myelin_score * 3`
- Glow: if `myelin_score > 0.5`, draw a second line behind at `opacity: 0.15`, `width * 2.5`
- Base opacity: `0.15 + myelin_score * 0.7`

**Logic in `linkCanvasObject`:**
1. Check bridge (source.project !== target.project) → blue dashed
2. Else read `evidence_json.tier` → tier color
3. Fallback if no tier → source node color
4. Apply width and glow from `myelin_score` (default 0)

**Legend:** Expand existing legend with tier colors + "thickness = myelination" indicator.

---

## 4. Neighbor Highlight on Hover

**State:** `hoveredNodeIdRef = useRef<string | null>(null)` — avoids React re-renders, canvas reads ref directly.

**Adjacency map:** `useMemo` over edges → `Map<string, Set<string>>`.

**Visual behavior on hover:**
- Non-connected nodes → `globalAlpha = 0.08`
- Hovered node + direct neighbors → full opacity
- Non-connected edges → `globalAlpha = 0.05`
- Connected edges → full opacity with tier color

**MemoryDetail integration:**
- `onRelationHover(memoryId | null)` callback from App → MemoryDetail
- Hovering a relation in the sidebar list highlights the corresponding edge in the graph

**Performance:** Adjacency map recalculated only when edges change. Hover uses ref, not state — no React render cycle on mouse move.

---

## 5. Semantic Zoom (3 Levels)

| Zoom | Level | Renders |
|------|-------|---------|
| < 1.0 | Far | Colored circle only. No text. |
| 1.0 – 2.5 | Mid | Circle + type letter inside (`D`, `E`, `O`, `S`, `I`, `P`). Project color border in global view. |
| > 2.5 | Close | All above + content_preview label (30 chars) + keyphrases below (max 3, `+N` overflow). |

**Smooth transitions:**
- Zoom 0.8–1.2: fade-in type letter via `globalAlpha` interpolation
- Zoom 2.0–2.8: fade-in label and keyphrases

**Keyphrases at Close level:**
- Max 3 displayed as small text below the label
- Color: `#888`, font size ~8px
- Overflow: `+N` suffix

**Zoom reading:** `graphRef.current.zoom()` in canvas callbacks — no React state needed.

---

## 6. Project Cluster Gravity

**Custom d3-force** via `graphRef.current.d3Force('projectCluster', forceFn)` after mount.

**Center calculation:**
- N projects → distributed in circle, radius = `min(width, height) * 0.25`
- 1 project → viewport center (no force)
- 2 projects → left/right
- 3+ → uniform circular distribution
- Recalculate on project selection change or window resize

**Force strength:** `0.03` — gentle clustering, allows cross-project connected nodes to remain close.

**Floating project labels:**
- Position: real centroid of project's nodes (recalculated every ~30 frames)
- Style: project name in project color, large font, `globalAlpha = 0.15` (watermark behind nodes)
- Only shown when 2+ projects active

---

## 7. StatsBar

**Location:** Between TopBar and graph, graph tab only. Height: ~36px.

**Content (left to right):**
- `{N} nodes · {M} edges`
- `|`
- `{X} decaying` (stability_score < 0.3, orange)
- `{Y} hot` (activation_score > 0.7, red + pulsing dot)
- `{Z} pinned` (manual_pin === true, pin icon)
- `|`
- When keyword active: `Showing {filtered} of {total}`

**Data:** Computed from node/edge arrays already in App.tsx. No additional API calls.

**Style:** Background `#0d0d1a`, monospace 12px, base color `#888`, highlights in respective colors.

---

## 8. MemoryDetail (Rewrite)

**Sidebar: right side, ~380px, slide-in via CSS transform (200ms ease).**

**Sections top to bottom:**

1. **Header** — Memory type badge (colored) + project name with color dot + close button

2. **Content** — Full `content` text (not just preview). Scrollable, max-height ~150px

3. **Keyphrases** — Colored pills/chips. Click → sets keyword filter in App. Hidden if empty.

4. **Tags** — Existing pills, visually differentiated from keyphrases (outline vs filled)

5. **Scores Grid** — 2x3 grid with horizontal mini-bars:
   - Activation, Stability, Importance, Novelty, Prominence
   - Bar color matches score range (red=high activation, cyan=stable, etc.)

6. **Emotional Axes** — Valence and Arousal as horizontal bars with position marker:
   - Valence: red (negative) → gray (neutral) → green (positive)
   - Arousal: gray (low) → orange (high)

7. **Ebbinghaus Decay** — Stability progress bar, halflife in days, review count

8. **Relations** — Scrollable list:
   - Each: `relation_type` badge + tier badge (T1/T2/T3 colored) + target content_preview (truncated)
   - Hover → expanded preview tooltip with full content + myelin score
   - Hover → triggers `onRelationHover` to highlight edge in graph
   - Click → navigates to node in graph (center + select)

9. **Metadata footer** — access_count, last_accessed_at (relative), abstraction_level, manual_pin

**Data:** Relations built by cross-referencing graph edges with selected memory_id. Target content_preview from loaded nodes. No additional fetch needed for hover preview.

---

## 9. HealthView (Dashboard)

**Full viewport when Health tab active. Calls `GET /brain/health` on mount and every 60 seconds.**

**Layout: card grid on dark background.**

### Card 1 — Overall Health (top, prominent)
- Large number: `overall_health` as percentage
- Wide colored bar: red (<0.4) → yellow (0.4–0.7) → green (>0.7)
- Update timestamp

### Card 2 — Synapse Formation
- 3 columns: T1 Instinct | T2 Perception | T3 Reasoning
- Large number + label each
- T3 subdivided: pending / promoted / rejected with proportional mini-bars

### Card 3 — Regions (per project)
- Grid of projects with compact metrics:
  - Memory count, active synapses, avg activation (mini-bar)
  - Orphan ratio (warning badge if > 0.2)
  - Keyphrases coverage (mini-bar)
  - Last NREM (relative date)
- Scrollable if many projects

### Card 4 — Connectivity (permeability)
- List of connected project pairs
- Each: permeability_score bar + myelinated relations count + avg myelin
- "organic" or "manual" badge from `organic_origin`
- formation_reason as tooltip

### Card 5 — Sleep Cycles
- Last NREM and Last REM with relative dates
- Cross activity score vs REM threshold as progress bar
- Visual indicator: "REM needed" if `cross_activity_score >= rem_threshold`

### Card 6 — Alerts
- Alert list with severity-colored badges: info (blue), warning (yellow), critical (red)
- Empty state: "All clear" in green

**Style:** Same palette as graph (#0a0a12 background, cards #0d0d1a, subtle borders). Vivid colors for data (cyan, yellow, red). Monospace for numbers.

---

## 10. Backend Adjustments

**Scope: projection-only changes, no new logic.**

### `api-server/server.py` — Subgraph Edge Projection

The `POST /api/graph/subgraph` endpoint needs to include `myelin_score` and `evidence_json` in its edge response. Currently these fields exist in the `memory_relations` table but may not be projected in the subgraph builder.

**Change:** Add `myelin_score` and `evidence_json` to the edge SELECT/projection in the subgraph query.

### Verify Existing Endpoints

- `GET /api/memories/{id}` — confirm `keyphrases` is included in the response
- `GET /brain/health` — confirm it exists and matches the documented response structure

**Not touched:** No business logic, no schema changes, no new endpoints.
