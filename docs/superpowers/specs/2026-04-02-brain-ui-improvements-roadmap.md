# Brain UI — Improvement Roadmap

> Reference spec for future implementation sessions. Each section is a self-contained feature that can be built independently.

**Current state:** React + TypeScript SPA using `react-force-graph-2d`. Multi-select project filtering, keyword search, bridge edges between projects, color-coded nodes by activation/stability. Located in `brain-ui/`.

**API surface used:** `POST /api/graph/subgraph` (nodes + edges), `GET /api/graph/facets` (project list), `GET /api/memories/{id}` (full detail).

---

## 1. Expanded Memory Detail Panel

**Problem:** Clicking a node shows a minimal preview. Users can't see the full content, relationships, or health metrics of a memory without going to the API directly.

**What to build:**

- Slide-in side panel (right side, ~350px) replacing the current compact `MemoryDetail` component
- Sections:
  - **Header:** memory type badge + project name with color dot
  - **Content:** full text from `GET /api/memories/{id}` (the `content` field, not just `content_preview`)
  - **Tags:** rendered as colored chips, clickable to set as keyword filter
  - **Metrics dashboard:** horizontal bars or gauges for `activation_score`, `stability_score`, `prominence`, `novelty_score`, `importance`
  - **Emotional axes:** valence (-1 to +1) and arousal (0 to 1) as a 2D scatter point or dual bars
  - **Relations list:** fetch relations from the edges already loaded, show linked memories as clickable items with relation type badge (supports, extends, contradicts)
  - **Metadata footer:** `access_count`, `review_count`, `stability_halflife_days`, `last_accessed_at`
- Panel should animate in/out (CSS transform, 200ms ease)
- Clicking a related memory in the list should navigate the graph (center + select that node)

**Files to modify:**
- `brain-ui/src/components/MemoryDetail.tsx` — full rewrite
- `brain-ui/src/components/MemoryDetail.module.css` — full rewrite
- `brain-ui/src/App.tsx` — pass edges to MemoryDetail for relation rendering
- `brain-ui/src/api/client.ts` — already has `fetchMemoryDetail`, just needs to be called

**API data available (MemoryDetailResponse):**
```typescript
memory: {
  memory_id, project, agent_id, memory_type, summary, content,
  content_preview, importance, tags, access_count, last_accessed_at,
  activation_score, stability_score, manual_pin, prominence,
  review_count, stability_halflife_days, valence, arousal,
  novelty_score, abstraction_level
}
relation_count: number
```

---

## 2. Semantic Zoom Levels

**Problem:** At low zoom, all nodes look the same — small colored circles. At high zoom, labels appear but are cramped. There's no progressive disclosure of information.

**What to build:**

Three zoom thresholds controlling what renders per node:

| Zoom level | What shows |
|---|---|
| < 1.0 (far) | Colored dot only, no label. Cluster shapes visible. |
| 1.0–2.5 (mid) | Dot + memory type icon inside (e.g. `D` for decision, `E` for error, `G` for general). Tags as tiny dots around the node perimeter. |
| > 2.5 (close) | Full current rendering: dot + content preview label + tag pills below node. |

- Read current zoom from `graphRef.current.zoom()` (already available)
- All rendering happens in `nodeCanvasObject` callback — just add zoom-based conditionals
- Memory type icons should be single characters drawn with `ctx.fillText` centered in the node circle
- Tag dots: small 2px circles arranged in a ring around the node, colored by tag hash

**Files to modify:**
- `brain-ui/src/components/BrainGraph.tsx` — modify `nodeCanvasObject` callback (currently at line ~103)

**Design notes:**
- Transitions between zoom levels should feel smooth — use opacity interpolation in the boundary zones (e.g., between zoom 0.8–1.2 fade in the type icon)
- Don't render text below zoom 1.0 — canvas text rendering at tiny sizes is expensive and illegible

---

## 3. Neighbor Highlight on Hover

**Problem:** With many nodes and edges, it's hard to trace which nodes are connected. Hovering should visually isolate a node's neighborhood.

**What to build:**

- On node hover: dim all non-connected nodes and edges to 10-15% opacity
- The hovered node + direct neighbors stay at full opacity
- Connected edges change color by relation type:
  - `supports` → `#4ecdc4` (teal)
  - `extends` → `#54a0ff` (blue)
  - `contradicts` → `#ff6b6b` (red)
  - bridge (cross-project) → `#a78bfa` (purple, dashed, already exists)
- On mouse leave: restore all opacities (with 150ms fade)

**Implementation approach:**

- Add state: `hoveredNodeId: string | null`
- Use `onNodeHover` prop of ForceGraph2D (fires on hover with node or null)
- Precompute adjacency map: `Map<string, Set<string>>` from edges (build once when edges change, via `useMemo`)
- In `nodeCanvasObject` and `linkCanvasObject`: check if `hoveredNodeId` is set. If so, check membership in the neighbor set to decide opacity.

**Files to modify:**
- `brain-ui/src/components/BrainGraph.tsx` — add hover state, adjacency map, modify render callbacks

**Performance note:** The adjacency map should be memoized with `useMemo` on the edges array. With 80 nodes / 200 edges this is trivial, but avoid rebuilding on every frame.

---

## 4. Timeline Slider

**Problem:** No temporal dimension. Users can't see how the brain grew over time or when specific knowledge clusters formed.

**What to build:**

- Horizontal slider at the bottom of the graph area (above the legend)
- Range: earliest memory creation date → now
- Dragging the slider filters nodes to only show those created before the slider's date
- Edges are filtered accordingly (both endpoints must be visible)
- A small label above the thumb shows the current date
- Play button: auto-advances the slider at ~1 day/second, animating the brain growing

**Data requirement:** `GraphNode` currently does NOT have a `created_at` field. This needs to be added:
- Backend: `build_graph_subgraph` in `api-server/server.py` already fetches memory records — add `created_at` to the node projection
- Frontend type: add `created_at: string` to `GraphNode` in `types.ts`

**Files to create/modify:**
- Create: `brain-ui/src/components/TimelineSlider.tsx`
- Create: `brain-ui/src/components/TimelineSlider.module.css`
- Modify: `brain-ui/src/types.ts` — add `created_at` to GraphNode
- Modify: `brain-ui/src/App.tsx` — add timeline state, filter logic
- Modify: `brain-ui/src/components/BrainGraph.tsx` — render slider below graph
- Modify: `api-server/server.py` — include `created_at` in subgraph node response

**Design notes:**
- Slider track should show a mini histogram of memory creation density (how many memories per day/week)
- When in play mode, new nodes should appear with a brief scale-in animation (CSS transition won't work on canvas — use a `birthTime` field and scale factor in `nodeCanvasObject`)

---

## 5. Project Cluster Gravity

**Problem:** In multi-project views, nodes from different projects mix randomly. There's no spatial grouping by project, making it hard to see project boundaries.

**What to build:**

- Add a custom force that pulls nodes toward a project-specific center point
- Project centers arranged in a circle layout (2 projects = left/right, 3 = triangle, N = circle)
- Gravity strength: moderate — nodes cluster by project but connected cross-project nodes still gravitate toward each other
- Floating project label rendered at each cluster centroid (recalculated every ~30 frames)
- Label style: project name in the project's color, semi-transparent, large font, rendered behind nodes

**Implementation approach:**

Using `d3-force` custom force (ForceGraph2D exposes d3 forces via `graphRef.current.d3Force()`):

```typescript
// After graph mounts:
const fg = graphRef.current;
fg.d3Force('projectCluster', () => {
  // custom force that pulls nodes toward their project center
  // strength ~0.03 to keep it gentle
});
```

- Compute project centers based on viewport size and number of active projects
- In the force tick: each node gets a small velocity nudge toward its project center
- Project labels: render in a separate canvas overlay or in `nodeCanvasObject` (check if any node in that project is the "first" one rendered, then draw the label at the centroid)

**Files to modify:**
- `brain-ui/src/components/BrainGraph.tsx` — add custom d3 force after mount, compute centroids, render labels

**Tuning parameters:**
- `clusterStrength`: 0.02–0.05 (too high = projects don't interact, too low = no visible clustering)
- `centerDistance`: based on viewport — projects should be ~200-300px apart at default zoom
- Recompute centers when project selection or window size changes

---

## 6. Stats Bar

**Problem:** No quantitative feedback about what's visible. When filtering by keyword or project, users don't know how many nodes/edges they're seeing or the health distribution.

**What to build:**

- Compact bar below the TopBar (or integrated into it), showing:
  - `{N} nodes · {M} edges` — updates live with filters
  - `{X} decaying` — count of nodes with `stability_score < 0.3` (orange text)
  - `{Y} high activation` — count of nodes with `activation_score > 0.7` (red pulse dot)
  - `{Z} pinned` — count of nodes with `manual_pin === true` (pin icon)
- When keyword filter is active, show: `Showing {filtered} of {total} nodes`
- All counters should animate number changes (simple CSS transition on opacity + transform)

**Files to create/modify:**
- Create: `brain-ui/src/components/StatsBar.tsx`
- Create: `brain-ui/src/components/StatsBar.module.css`
- Modify: `brain-ui/src/App.tsx` — render StatsBar, pass node/edge arrays and totals

**Data available:** All fields needed (`stability_score`, `activation_score`, `manual_pin`) are already in `GraphNode`.

---

## Implementation Priority

Recommended order based on effort vs. impact:

| Priority | Feature | Effort | Impact | Dependencies |
|---|---|---|---|---|
| 1 | Neighbor Highlight on Hover | Low | High | None |
| 2 | Stats Bar | Low | Medium | None |
| 3 | Expanded Detail Panel | Medium | High | None |
| 4 | Project Cluster Gravity | Medium | High | None |
| 5 | Semantic Zoom | Medium | Medium | None |
| 6 | Timeline Slider | High | High | Backend change (created_at) |

Features 1 and 2 can be implemented in parallel. Feature 6 requires a backend change and is the most complex — save for last.
