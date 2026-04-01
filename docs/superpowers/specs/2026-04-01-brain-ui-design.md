# AI Memory Brain UI — Design Spec

## Overview

A web-based interactive visualization for the AI Memory Brain system. Displays memories as a living force-directed graph where visual properties (color, size, glow, pulse) encode memory state (activation, stability, arousal, decay). Clicking a node opens a detail sidebar with full memory metadata.

## MVP Scope

### What's in
1. **Force-directed graph** — nodes = memories, edges = relations, physics-based layout
2. **Detail sidebar** — opens on node click, shows all memory metadata
3. **Project selector with global view** — dropdown in top bar: "All Projects" (default), individual project, bridged scope

### What's out (future iterations)
- Text search with graph centering
- Advanced filters (by type, tags, stability range)
- Dashboard/metrics view
- Memory creation/editing from UI
- Timeline/history view

## Tech Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| Framework | React 18 + TypeScript | Ecosystem, scalability, type safety |
| Graph lib | react-force-graph-2d | Mature force-directed graph with zoom/pan/click, WebGL perf |
| HTTP | fetch / SWR | Lightweight data fetching with caching |
| Styling | CSS Modules or Tailwind | Scoped styles, dark theme |
| Build | Vite | Fast dev server, optimized builds |
| Deploy | Docker (nginx) | Fits existing docker-compose stack |

## Architecture

```
browser (React SPA)
  └─ GET/POST to api-server:8050
       ├─ POST /api/graph/subgraph   → graph data (nodes + edges)
       ├─ GET  /api/memories/{id}    → memory detail
       ├─ GET  /api/graph/facets     → project list, types, tags
       └─ GET  /api/graph/metrics    → system stats (for top bar health)
```

No BFF or proxy needed — the React app calls the existing API directly. CORS headers will need to be added to the FastAPI server.

## Visual Design: "Living Brain"

### Theme
- Background: `#0a0a12` (deep dark)
- Surface: `#12121f` (panels, cards)
- Border: `#1e1e3a`
- Text primary: `#ffffff`
- Text secondary: `#888888`
- Text muted: `#555555`

### Node Encoding

Nodes encode memory state through four visual channels:

| Visual property | Data source | Mapping |
|----------------|-------------|---------|
| **Color** | activation_score + stability_score + arousal | Red (#ff6b6b) = high activation/arousal. Cyan (#4ecdc4) = stable. Yellow (#ffd93d) = decaying (low stability, some activation). Gray (#666) = fading (low everything) |
| **Size** | prominence | Range 4px–14px radius, linear scale |
| **Glow** | importance | Radial gradient behind node, opacity 0–0.4 |
| **Pulse animation** | activation_score > 0.7 | Expanding ring animation on highly active nodes |

Color logic (pseudocode):
```
if arousal > 0.6 OR activation > 0.7 → red
else if stability > 0.5 → cyan
else if stability > 0.2 → yellow
else → gray
```

### Edge Encoding

| Visual property | Data source | Mapping |
|----------------|-------------|---------|
| **Opacity** | weight | 0.1–0.8 range |
| **Width** | weight | 0.5–3px |
| **Style** | origin | Solid = intra-project. Dashed = cross-project bridge |
| **Color** | relation context | Purple (#a78bfa) for bridges, inherits node color otherwise |

### Node Labels
- Show `content_preview` (truncated to ~30 chars) below each node
- Opacity tied to node opacity (fading nodes have fading labels)
- Only show labels above a zoom threshold to avoid clutter

## Layout: Three Zones

```
┌──────────────────────────────────────────────────┐
│  TOP BAR: Logo │ Project Selector │ System Health │
├────────────────────────────────┬─────────────────┤
│                                │  DETAIL SIDEBAR │
│                                │                 │
│         GRAPH CANVAS           │  (appears on    │
│    (force-directed, zoomable)  │   node click)   │
│                                │                 │
│                                │  280px width    │
│  [Legend: bottom-left]         │                 │
├────────────────────────────────┴─────────────────┤
```

### Top Bar
- Left: App name/logo "AI Memory Brain"
- Center/Right: Project scope selector dropdown
  - "All Projects" (default) → calls subgraph with `scope: "global"`
  - Individual project → calls with `scope: "local"`, `project: name`
  - Each project in dropdown shows: name, memory count, bridge count
  - Project colors are assigned from a palette and used consistently in the graph
- Far right: System health indicator (green dot + "healthy" or red + "unreachable")

### Graph Canvas
- Full remaining viewport height and width
- Force-directed physics (d3-force via react-force-graph)
- Interactions: zoom (scroll), pan (drag background), click node (open sidebar), hover node (highlight connections)
- Legend overlay bottom-left showing color meanings
- When in "All Projects" view, nodes naturally cluster by project due to intra-project edges being stronger

### Detail Sidebar
- Width: 280px, slides in from right on node click
- Close button (X) or click empty graph space to dismiss
- Content sections (top to bottom):
  1. **Header**: color dot + memory summary (title)
  2. **Type + Tags**: badges for action_type and tags
  3. **Content preview**: first ~200 chars of content
  4. **Score grid** (2x2): activation, stability, importance, arousal — each as labeled number with color
  5. **Ebbinghaus decay bar**: gradient bar showing stability_score, with halflife_days and review_count below
  6. **Metadata list**: access_count, last_accessed_at, created_at, relation count, abstraction_level, valence (with +/- label), novelty_score, manual_pin status

## API Integration

### Initial load
1. `GET /api/graph/facets?project=` → get project list for dropdown
2. `POST /api/graph/subgraph` with `{ mode: "project_hot", scope: "global", node_limit: 100, edge_limit: 300 }` → initial graph

### On project change
- Re-fetch subgraph with new `project` and `scope` params

### On node click
- `GET /api/memories/{memory_id}` → full detail for sidebar

### Polling (optional, low priority)
- Re-fetch subgraph every 60s to reflect activation changes (can be added post-MVP)

## Docker Integration

New service in `docker-compose.yaml`:

```yaml
brain-ui:
  build: ./brain-ui
  ports:
    - "3000:80"
  depends_on:
    - api-server
```

Dockerfile: multi-stage build (node:20 → nginx:alpine).

CORS: Add `CORSMiddleware` to FastAPI with `allow_origins=["http://localhost:3000"]`.

## File Structure

```
brain-ui/
├── Dockerfile
├── nginx.conf
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── client.ts          # API calls (subgraph, memory detail, facets)
│   ├── components/
│   │   ├── TopBar.tsx          # Logo, project selector, health
│   │   ├── BrainGraph.tsx      # Force graph canvas + legend
│   │   ├── MemoryDetail.tsx    # Sidebar panel
│   │   └── ProjectSelector.tsx # Dropdown with project list
│   ├── hooks/
│   │   └── useGraphData.ts    # Data fetching + transformation
│   ├── utils/
│   │   └── nodeStyle.ts       # Color/size/glow logic from scores
│   └── styles/
│       └── theme.ts           # Color constants, sizing
```

## Performance Considerations

- `node_limit: 100` default — adjustable, but keeps graph readable
- react-force-graph uses Canvas2D — handles hundreds of nodes smoothly
- Labels only rendered above zoom threshold
- Detail fetched on-demand (not preloaded for all nodes)
- SWR caching prevents redundant API calls
