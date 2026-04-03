# Brain UI — Biological Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the brain-ui frontend in sync with the backend's biological brain features — edge dual encoding, semantic zoom, neighbor hover highlight, project cluster gravity, stats bar, expanded memory detail, and brain health dashboard.

**Architecture:** Hybrid approach — new components (TabSwitcher, StatsBar, HealthView) built from scratch; surgical refactors on BrainGraph, nodeStyle, types, and API client; full rewrite of MemoryDetail. Tab routing via React state (no router library).

**Tech Stack:** React 19, TypeScript, react-force-graph-2d, d3-force, CSS Modules, Vite

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `brain-ui/src/components/TabSwitcher.tsx` | Graph/Health tab toggle |
| `brain-ui/src/components/TabSwitcher.module.css` | Tab styling |
| `brain-ui/src/components/StatsBar.tsx` | Live graph counters bar |
| `brain-ui/src/components/StatsBar.module.css` | Stats bar styling |
| `brain-ui/src/components/HealthView.tsx` | Brain health dashboard |
| `brain-ui/src/components/HealthView.module.css` | Health dashboard styling |

### Modified Files
| File | Changes |
|------|---------|
| `api-server/server.py:2166-2217` | Add `myelin_score` to SQL SELECT, add `myelin_score` + `evidence_json` to `build_graph_edge()` |
| `api-server/server.py:986-999` | Add `keyphrases` to `build_graph_node()` |
| `brain-ui/src/types.ts` | Add `myelin_score`, `evidence_json` to GraphEdge; add `keyphrases` to GraphNode; add `BrainHealthResponse`; update `MemoryDetailResponse` |
| `brain-ui/src/api/client.ts` | Add `fetchBrainHealth()` |
| `brain-ui/src/utils/nodeStyle.ts` | Add tier color constants + edge functions for myelin/tier encoding |
| `brain-ui/src/components/BrainGraph.tsx` | Edge dual encoding, hover highlight, semantic zoom, cluster gravity, updated legend |
| `brain-ui/src/components/BrainGraph.module.css` | Legend updates for tier colors |
| `brain-ui/src/components/MemoryDetail.tsx` | Full rewrite with keyphrases, relations list, emotional axes, scores grid |
| `brain-ui/src/components/MemoryDetail.module.css` | Full rewrite |
| `brain-ui/src/components/TopBar.tsx` | Integrate TabSwitcher |
| `brain-ui/src/components/TopBar.module.css` | Minor tab styling adjustments |
| `brain-ui/src/App.tsx` | Tab state, pass edges to MemoryDetail, hover relay, StatsBar integration |
| `brain-ui/src/App.module.css` | Layout adjustment for stats bar |

---

## Task 1: Backend — Add biological fields to subgraph edge and node projections

**Files:**
- Modify: `api-server/server.py:2166-2217` (SQL query + `build_graph_edge`)
- Modify: `api-server/server.py:986-999` (`build_graph_node`)

- [ ] **Step 1: Add `myelin_score` to the SQL SELECT in `fetch_relation_rows_between`**

In `api-server/server.py`, at line 2166, the SELECT clause lists fields from `memory_relations`. Add `mr.myelin_score` after `mr.evidence_json`:

```python
            SELECT
                mr.id,
                mr.source_memory_id,
                mr.target_memory_id,
                mr.relation_type,
                mr.weight,
                mr.origin,
                mr.evidence_json,
                mr.myelin_score,
                mr.reinforcement_count,
                mr.last_activated_at,
                mr.active,
                mr.updated_at,
                src_p.name AS source_project,
                dst_p.name AS target_project
```

- [ ] **Step 2: Add `myelin_score` and `evidence_json` to `build_graph_edge`**

In `api-server/server.py`, replace the `build_graph_edge` function (lines 2207-2217):

```python
def build_graph_edge(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_memory_id": row["source_memory_id"],
        "target_memory_id": row["target_memory_id"],
        "relation_type": row["relation_type"],
        "weight": round(float(row.get("weight", 0.0) or 0.0), 4),
        "origin": row.get("origin"),
        "active": bool(row.get("active", False)),
        "reinforcement_count": int(row.get("reinforcement_count", 0) or 0),
        "last_activated_at": row.get("last_activated_at"),
        "myelin_score": round(float(row.get("myelin_score", 0.0) or 0.0), 4),
        "evidence_json": row.get("evidence_json") or None,
    }
```

- [ ] **Step 3: Add `keyphrases` to `build_graph_node`**

In `api-server/server.py`, in the `build_graph_node` function (line 986-999), add `keyphrases` after `prominence`:

```python
def build_graph_node(record: dict[str, Any]) -> dict[str, Any]:
    serialized = serialize_memory_record(record)
    return {
        "memory_id": serialized["id"],
        "project": serialized.get("project"),
        "memory_type": serialized.get("memory_type"),
        "content_preview": memory_content_preview(str(serialized.get("content") or serialized.get("summary") or "")),
        "tags": serialized.get("tags", []),
        "activation_score": round(float(serialized.get("activation_score", 0.0) or 0.0), 4),
        "stability_score": round(float(serialized.get("stability_score", 0.5) or 0.5), 4),
        "access_count": int(serialized.get("access_count", 0) or 0),
        "manual_pin": bool(serialized.get("manual_pin", False)),
        "prominence": compute_memory_prominence(record),
        "keyphrases": serialized.get("keyphrases", []) or [],
    }
```

- [ ] **Step 4: Commit**

```bash
git add api-server/server.py
git commit -m "feat(api): expose myelin_score, evidence_json, keyphrases in subgraph response"
```

---

## Task 2: Frontend types and API client updates

**Files:**
- Modify: `brain-ui/src/types.ts`
- Modify: `brain-ui/src/api/client.ts`

- [ ] **Step 1: Update `GraphNode` to include `keyphrases`**

In `brain-ui/src/types.ts`, add `keyphrases` to the `GraphNode` interface after `prominence` (line 11):

```typescript
export interface GraphNode {
  memory_id: string;
  project: string;
  memory_type: string;
  content_preview: string;
  tags: string[];
  activation_score: number;
  stability_score: number;
  access_count: number;
  manual_pin: boolean;
  prominence: number;
  keyphrases: string[];
}
```

- [ ] **Step 2: Update `GraphEdge` to include biological fields**

Replace the `GraphEdge` interface (lines 14-23):

```typescript
export interface GraphEdge {
  source_memory_id: string;
  target_memory_id: string;
  relation_type: string;
  weight: number;
  origin: "manual" | "vector_inference";
  active: boolean;
  reinforcement_count: number;
  last_activated_at: string | null;
  myelin_score: number;
  evidence_json?: {
    tier: 1 | 2 | 3;
    relation_type: string;
    reason: string;
    signals: Record<string, number>;
  } | null;
}
```

- [ ] **Step 3: Update `MemoryDetailResponse` to include `keyphrases`**

In the `MemoryDetailResponse` interface (line 62-87), add `keyphrases` after `abstraction_level` and add `relations` array:

```typescript
export interface MemoryDetailResponse {
  memory: {
    memory_id: string;
    project: string;
    agent_id: string;
    memory_type: string;
    summary: string;
    content: string;
    content_preview: string;
    importance: number;
    tags: string[];
    access_count: number;
    last_accessed_at: string | null;
    activation_score: number;
    stability_score: number;
    manual_pin: boolean;
    prominence: number;
    review_count: number;
    stability_halflife_days: number;
    valence: number;
    arousal: number;
    novelty_score: number;
    abstraction_level: number;
    keyphrases: string[];
  };
  relation_count: number;
  relations: Array<{
    relation_type: string;
    target_memory_id: string;
    weight: number;
    origin: string;
  }>;
}
```

- [ ] **Step 4: Replace `HealthResponse` with `BrainHealthResponse`**

Replace the `HealthResponse` interface (lines 89-93) with:

```typescript
export interface HealthResponse {
  status: string;
  timestamp: string;
  test_mode: boolean;
}

export interface BrainHealthResponse {
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

- [ ] **Step 5: Add `fetchBrainHealth` to API client**

In `brain-ui/src/api/client.ts`, add the import of `BrainHealthResponse` and the new function after `fetchHealth` (after line 57):

Update the import at line 1-6:
```typescript
import type {
  SubgraphResponse,
  FacetsResponse,
  MemoryDetailResponse,
  HealthResponse,
  BrainHealthResponse,
} from "../types";
```

Add the function at the end of the file:
```typescript
export async function fetchBrainHealth(): Promise<BrainHealthResponse> {
  const res = await fetch(`${API_URL}/brain/health`, { headers });
  if (!res.ok) throw new Error(`brain health failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd brain-ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: may show errors from components that need updating (BrainGraph, MemoryDetail) — that's expected since we changed the types they consume. No errors in types.ts or client.ts themselves.

- [ ] **Step 7: Commit**

```bash
git add brain-ui/src/types.ts brain-ui/src/api/client.ts
git commit -m "feat(brain-ui): add biological types and brain health API client"
```

---

## Task 3: nodeStyle — Add tier colors and myelin-based edge functions

**Files:**
- Modify: `brain-ui/src/utils/nodeStyle.ts`

- [ ] **Step 1: Add tier color constants and myelin-aware edge functions**

Replace the full content of `brain-ui/src/utils/nodeStyle.ts`:

```typescript
import type { GraphNode, GraphEdge } from "../types";

// Node colors
const COLOR_RED = "#ff6b6b";
const COLOR_CYAN = "#4ecdc4";
const COLOR_YELLOW = "#ffd93d";
const COLOR_GRAY = "#666666";

// Edge colors
const COLOR_BRIDGE = "#54a0ff";
const COLOR_TIER1 = "#ff6b6b";   // Instinct
const COLOR_TIER2 = "#ffd93d";   // Perception
const COLOR_TIER3 = "#a78bfa";   // Reasoning

export function getNodeColor(node: GraphNode): string {
  if (node.activation_score > 0.7) return COLOR_RED;
  if (node.stability_score > 0.5) return COLOR_CYAN;
  if (node.stability_score > 0.2) return COLOR_YELLOW;
  return COLOR_GRAY;
}

export function getNodeSize(node: GraphNode): number {
  return 4 + node.prominence * 10;
}

export function getNodeOpacity(node: GraphNode): number {
  const aliveness = Math.max(node.activation_score, node.stability_score);
  return 0.2 + aliveness * 0.7;
}

export function shouldPulse(node: GraphNode): boolean {
  return node.activation_score > 0.7;
}

export function shouldGlow(node: GraphNode): boolean {
  return node.prominence > 0.5;
}

/** Memory type → single character for semantic zoom mid-level */
export function getTypeChar(memoryType: string): string {
  const map: Record<string, string> = {
    decision: "D",
    error: "E",
    observation: "O",
    schema: "S",
    insight: "I",
    pattern: "P",
  };
  return map[memoryType] ?? memoryType.charAt(0).toUpperCase();
}

// --- Edge style functions ---

export function getEdgeTierColor(edge: { evidence_json?: { tier: number } | null }): string | null {
  const tier = edge.evidence_json?.tier;
  if (tier === 1) return COLOR_TIER1;
  if (tier === 2) return COLOR_TIER2;
  if (tier === 3) return COLOR_TIER3;
  return null;
}

export function getEdgeWidth(weight: number, myelinScore: number = 0): number {
  return 0.5 + myelinScore * 3 + weight * 0.5;
}

export function getEdgeOpacity(weight: number, myelinScore: number = 0): number {
  return 0.15 + Math.max(myelinScore, weight) * 0.7;
}

export function shouldEdgeGlow(myelinScore: number): boolean {
  return myelinScore > 0.5;
}

export {
  COLOR_RED, COLOR_CYAN, COLOR_YELLOW, COLOR_GRAY,
  COLOR_BRIDGE, COLOR_TIER1, COLOR_TIER2, COLOR_TIER3,
};
```

- [ ] **Step 2: Commit**

```bash
git add brain-ui/src/utils/nodeStyle.ts
git commit -m "feat(brain-ui): add tier colors and myelin-aware edge styling functions"
```

---

## Task 4: TabSwitcher component

**Files:**
- Create: `brain-ui/src/components/TabSwitcher.tsx`
- Create: `brain-ui/src/components/TabSwitcher.module.css`

- [ ] **Step 1: Create TabSwitcher component**

Create `brain-ui/src/components/TabSwitcher.tsx`:

```typescript
import styles from "./TabSwitcher.module.css";

export type TabId = "graph" | "health";

interface TabSwitcherProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

const TABS: { id: TabId; label: string }[] = [
  { id: "graph", label: "\u{1f9e0} Graph" },
  { id: "health", label: "\u2764 Health" },
];

export default function TabSwitcher({ activeTab, onTabChange }: TabSwitcherProps) {
  return (
    <div className={styles.tabs}>
      {TABS.map((tab) => (
        <button
          key={tab.id}
          className={`${styles.tab} ${activeTab === tab.id ? styles.active : ""}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create TabSwitcher styles**

Create `brain-ui/src/components/TabSwitcher.module.css`:

```css
.tabs {
  display: flex;
  gap: 2px;
}

.tab {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 6px 14px;
  color: #666;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.tab:hover {
  color: #aaa;
}

.active {
  color: #4ecdc4;
  border-bottom-color: #4ecdc4;
}
```

- [ ] **Step 3: Commit**

```bash
git add brain-ui/src/components/TabSwitcher.tsx brain-ui/src/components/TabSwitcher.module.css
git commit -m "feat(brain-ui): add TabSwitcher component"
```

---

## Task 5: StatsBar component

**Files:**
- Create: `brain-ui/src/components/StatsBar.tsx`
- Create: `brain-ui/src/components/StatsBar.module.css`

- [ ] **Step 1: Create StatsBar component**

Create `brain-ui/src/components/StatsBar.tsx`:

```typescript
import type { GraphNode, GraphEdge } from "../types";
import styles from "./StatsBar.module.css";

interface StatsBarProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  totalNodes: number;
  totalEdges: number;
  keyword: string;
}

export default function StatsBar({ nodes, edges, totalNodes, totalEdges, keyword }: StatsBarProps) {
  const decaying = nodes.filter((n) => n.stability_score < 0.3).length;
  const hot = nodes.filter((n) => n.activation_score > 0.7).length;
  const pinned = nodes.filter((n) => n.manual_pin).length;

  return (
    <div className={styles.bar}>
      <span className={styles.stat}>
        <span className={styles.num}>{nodes.length}</span> nodes
        <span className={styles.sep}>&middot;</span>
        <span className={styles.num}>{edges.length}</span> edges
      </span>

      <span className={styles.divider}>|</span>

      {decaying > 0 && (
        <span className={`${styles.stat} ${styles.decaying}`}>
          <span className={styles.num}>{decaying}</span> decaying
        </span>
      )}
      {hot > 0 && (
        <span className={`${styles.stat} ${styles.hot}`}>
          <span className={styles.hotDot} />
          <span className={styles.num}>{hot}</span> hot
        </span>
      )}
      {pinned > 0 && (
        <span className={`${styles.stat} ${styles.pinned}`}>
          <span className={styles.num}>{pinned}</span> pinned
        </span>
      )}

      {keyword && (
        <>
          <span className={styles.divider}>|</span>
          <span className={styles.stat}>
            Showing <span className={styles.num}>{nodes.length}</span> of{" "}
            <span className={styles.num}>{totalNodes}</span>
          </span>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create StatsBar styles**

Create `brain-ui/src/components/StatsBar.module.css`:

```css
.bar {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #0d0d1a;
  border-bottom: 1px solid #1a1a2e;
  padding: 0 20px;
  height: 36px;
  font-family: "SF Mono", "Fira Code", monospace;
  font-size: 12px;
  color: #888;
  flex-shrink: 0;
}

.stat {
  display: flex;
  align-items: center;
  gap: 4px;
}

.num {
  color: #ccc;
  font-weight: 600;
}

.divider {
  color: #333;
}

.sep {
  color: #555;
  margin: 0 2px;
}

.decaying {
  color: #ffa94d;
}
.decaying .num {
  color: #ffa94d;
}

.hot {
  color: #ff6b6b;
}
.hot .num {
  color: #ff6b6b;
}

.hotDot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ff6b6b;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.pinned {
  color: #4ecdc4;
}
.pinned .num {
  color: #4ecdc4;
}
```

- [ ] **Step 3: Commit**

```bash
git add brain-ui/src/components/StatsBar.tsx brain-ui/src/components/StatsBar.module.css
git commit -m "feat(brain-ui): add StatsBar component with live counters"
```

---

## Task 6: BrainGraph — Edge dual encoding (tier color + myelin glow)

**Files:**
- Modify: `brain-ui/src/components/BrainGraph.tsx:26-38,76-86,178-207`
- Modify: `brain-ui/src/components/BrainGraph.module.css:30-49`

- [ ] **Step 1: Update ForceLink interface and graphLinks mapping**

In `brain-ui/src/components/BrainGraph.tsx`, replace the `ForceLink` interface (lines 32-38) and the `graphLinks` mapping (lines 76-86):

Replace `ForceLink` interface:
```typescript
interface ForceLink {
  source: string | ForceNode;
  target: string | ForceNode;
  weight: number;
  origin: string;
  isBridge: boolean;
  myelinScore: number;
  evidenceJson?: { tier: number } | null;
}
```

Replace `graphLinks` mapping:
```typescript
  const graphLinks: ForceLink[] = edges.map((e) => {
    const sourceProject = nodeProjectMap.get(e.source_memory_id);
    const targetProject = nodeProjectMap.get(e.target_memory_id);
    return {
      source: e.source_memory_id,
      target: e.target_memory_id,
      weight: e.weight,
      origin: e.origin,
      isBridge: sourceProject !== targetProject,
      myelinScore: e.myelin_score ?? 0,
      evidenceJson: e.evidence_json ?? null,
    };
  });
```

- [ ] **Step 2: Replace `linkCanvasObject` callback with tier + myelin rendering**

Replace the `linkCanvasObject` callback (lines 178-207):

```typescript
  const linkCanvasObject = useCallback(
    (link: any, ctx: CanvasRenderingContext2D) => {
      const start = link.source;
      const end = link.target;
      if (typeof start === "string" || typeof end === "string") return;
      if (!start.x || !end.x) return;

      // Color priority: bridge > tier > source node
      let color: string;
      if (link.isBridge) {
        color = COLOR_BRIDGE;
      } else {
        const tierColor = getEdgeTierColor(link);
        color = tierColor ?? getNodeColor(start);
      }

      const myelin = link.myelinScore ?? 0;
      const width = getEdgeWidth(link.weight, myelin);
      const opacity = getEdgeOpacity(link.weight, myelin);

      // Myelin glow (drawn behind the main line)
      if (shouldEdgeGlow(myelin)) {
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.strokeStyle = color;
        ctx.globalAlpha = 0.15;
        ctx.lineWidth = width * 2.5;
        ctx.setLineDash([]);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // Main line
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.setLineDash(link.isBridge ? [5, 4] : []);
      ctx.lineTo(end.x, end.y);
      ctx.strokeStyle = color;
      ctx.globalAlpha = opacity;
      ctx.lineWidth = width;
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.setLineDash([]);
    },
    []
  );
```

- [ ] **Step 3: Update imports in BrainGraph.tsx**

Replace the import from `nodeStyle` (lines 4-13):

```typescript
import {
  getNodeColor,
  getNodeSize,
  getNodeOpacity,
  shouldPulse,
  shouldGlow,
  getEdgeWidth,
  getEdgeOpacity,
  getEdgeTierColor,
  shouldEdgeGlow,
  COLOR_BRIDGE,
  COLOR_TIER1,
  COLOR_TIER2,
  COLOR_TIER3,
} from "../utils/nodeStyle";
```

- [ ] **Step 4: Update the legend to include tier colors**

Replace the legend JSX (lines 246-267):

```typescript
      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: "#ff6b6b" }} />
          High activation / T1
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: "#4ecdc4" }} />
          Stable
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: "#ffd93d" }} />
          Decaying / T2
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: "#a78bfa" }} />
          T3 Reasoning
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: "#666" }} />
          Fading
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendLine} />
          Bridge
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendGlow} />
          Myelinated
        </span>
      </div>
```

- [ ] **Step 5: Add `.legendGlow` style**

In `brain-ui/src/components/BrainGraph.module.css`, add after `.legendLine` (after line 49):

```css
.legendGlow {
  width: 16px;
  height: 4px;
  border-radius: 2px;
  background: #4ecdc4;
  box-shadow: 0 0 6px rgba(78, 205, 196, 0.6);
  display: inline-block;
  vertical-align: middle;
}
```

- [ ] **Step 6: Commit**

```bash
git add brain-ui/src/components/BrainGraph.tsx brain-ui/src/components/BrainGraph.module.css
git commit -m "feat(brain-ui): edge dual encoding — tier color + myelin glow"
```

---

## Task 7: BrainGraph — Neighbor highlight on hover

**Files:**
- Modify: `brain-ui/src/components/BrainGraph.tsx`

- [ ] **Step 1: Add hover state and adjacency map**

In `brain-ui/src/components/BrainGraph.tsx`, add imports and state after the existing refs (after line 51). Add `useMemo` to the React import at line 1:

Update import line 1:
```typescript
import { useCallback, useRef, useEffect, useState, useMemo } from "react";
```

Add after line 51 (`const [dimensions, setDimensions] = ...`):
```typescript
  const hoveredNodeIdRef = useRef<string | null>(null);
  const [, forceRender] = useState(0);

  // Adjacency map for hover highlight
  const adjacencyMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const e of edges) {
      if (!map.has(e.source_memory_id)) map.set(e.source_memory_id, new Set());
      if (!map.has(e.target_memory_id)) map.set(e.target_memory_id, new Set());
      map.get(e.source_memory_id)!.add(e.target_memory_id);
      map.get(e.target_memory_id)!.add(e.source_memory_id);
    }
    return map;
  }, [edges]);
```

- [ ] **Step 2: Add hover check helpers inside the component**

Add after the adjacencyMap useMemo:

```typescript
  const isHighlighted = (nodeId: string): boolean => {
    const hovered = hoveredNodeIdRef.current;
    if (!hovered) return true; // no hover active → everything visible
    if (nodeId === hovered) return true;
    return adjacencyMap.get(hovered)?.has(nodeId) ?? false;
  };

  const isEdgeHighlighted = (sourceId: string, targetId: string): boolean => {
    const hovered = hoveredNodeIdRef.current;
    if (!hovered) return true;
    return sourceId === hovered || targetId === hovered;
  };
```

- [ ] **Step 3: Apply hover dimming in `nodeCanvasObject`**

At the beginning of the `nodeCanvasObject` callback (right after `const opacity = getNodeOpacity(n);` at line ~110), add:

```typescript
      const highlighted = isHighlighted(n.memory_id);
      const effectiveOpacity = highlighted ? opacity : 0.08;
```

Then replace all occurrences of `opacity` in the node rendering with `effectiveOpacity`. Specifically:
- Line where node circle is filled: use `ctx.globalAlpha = effectiveOpacity;`
- The glow check: wrap with `if (shouldGlow(n) && highlighted)`
- The pulse check: wrap with `if (shouldPulse(n) && highlighted)`
- The label rendering: use `ctx.globalAlpha = effectiveOpacity * 0.7;`

Here's the full updated `nodeCanvasObject`:

```typescript
  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D) => {
      const n = node as ForceNode;
      const x = n.x ?? 0;
      const y = n.y ?? 0;
      const color = getNodeColor(n);
      const size = getNodeSize(n);
      const opacity = getNodeOpacity(n);
      const highlighted = isHighlighted(n.memory_id);
      const effectiveOpacity = highlighted ? opacity : 0.08;

      // Glow for prominent nodes (only when highlighted)
      if (shouldGlow(n) && highlighted) {
        const glowRadius = size * 3;
        const gradient = ctx.createRadialGradient(x, y, size, x, y, glowRadius);
        gradient.addColorStop(0, color + "66");
        gradient.addColorStop(1, color + "00");
        ctx.beginPath();
        ctx.arc(x, y, glowRadius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
      }

      // Pulse ring for highly active nodes (only when highlighted)
      if (shouldPulse(n) && highlighted) {
        const phase = pulsePhase.current;
        const pulseRadius = size + phase * 10;
        const pulseOpacity = (1 - phase) * 0.4;
        ctx.beginPath();
        ctx.arc(x, y, pulseRadius, 0, Math.PI * 2);
        ctx.strokeStyle = color;
        ctx.globalAlpha = pulseOpacity;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // Project ring in global view
      if (!selectedProject && highlighted) {
        const projColor = projectColorMap.get(n.project);
        if (projColor) {
          ctx.beginPath();
          ctx.arc(x, y, size + 2, 0, Math.PI * 2);
          ctx.strokeStyle = projColor;
          ctx.globalAlpha = 0.3;
          ctx.lineWidth = 1.5;
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = effectiveOpacity;
      ctx.fill();
      ctx.globalAlpha = 1;

      // Label
      const zoom = graphRef.current?.zoom?.() ?? 1;
      if (zoom > 1.5 && highlighted) {
        const label =
          n.content_preview.length > 30
            ? n.content_preview.slice(0, 28) + "\u2026"
            : n.content_preview;
        ctx.font = "3px system-ui";
        ctx.textAlign = "center";
        ctx.fillStyle = color;
        ctx.globalAlpha = effectiveOpacity * 0.7;
        ctx.fillText(label, x, y + size + 5);
        ctx.globalAlpha = 1;
      }
    },
    [selectedProject, projectColorMap, adjacencyMap]
  );
```

- [ ] **Step 4: Apply hover dimming in `linkCanvasObject`**

Add at the top of the `linkCanvasObject` callback (after the `if (!start.x || !end.x) return;` check):

```typescript
      const sourceId = typeof start === "object" ? start.memory_id : "";
      const targetId = typeof end === "object" ? end.memory_id : "";
      const edgeHighlighted = isEdgeHighlighted(sourceId, targetId);
```

Then in the main line drawing section, multiply opacity by highlight:
```typescript
      ctx.globalAlpha = edgeHighlighted ? opacity : 0.05;
```

And for the glow, only draw when highlighted:
```typescript
      if (shouldEdgeGlow(myelin) && edgeHighlighted) {
```

- [ ] **Step 5: Add `onNodeHover` to ForceGraph2D props**

In the ForceGraph2D JSX props (around line 237), add after `onBackgroundClick`:

```typescript
        onNodeHover={(node: any) => {
          hoveredNodeIdRef.current = node ? (node as ForceNode).memory_id : null;
          forceRender((c) => c + 1);
        }}
```

- [ ] **Step 6: Add `hoveredNodeId` prop for external control (MemoryDetail relay)**

Update the `BrainGraphProps` interface to include an optional external hover:

```typescript
interface BrainGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  projectList: string[];
  selectedProject: string | null;
  onNodeClick: (node: GraphNode) => void;
  onBackgroundClick: () => void;
  externalHoveredNodeId?: string | null;
}
```

Add destructuring of `externalHoveredNodeId` in the component params. Update `isHighlighted` to also consider the external hover:

```typescript
  const isHighlighted = (nodeId: string): boolean => {
    const hovered = hoveredNodeIdRef.current ?? externalHoveredNodeId ?? null;
    if (!hovered) return true;
    if (nodeId === hovered) return true;
    return adjacencyMap.get(hovered)?.has(nodeId) ?? false;
  };

  const isEdgeHighlighted = (sourceId: string, targetId: string): boolean => {
    const hovered = hoveredNodeIdRef.current ?? externalHoveredNodeId ?? null;
    if (!hovered) return true;
    return sourceId === hovered || targetId === hovered;
  };
```

- [ ] **Step 7: Commit**

```bash
git add brain-ui/src/components/BrainGraph.tsx
git commit -m "feat(brain-ui): neighbor highlight on hover with external relay support"
```

---

## Task 8: BrainGraph — Semantic zoom (3 levels)

**Files:**
- Modify: `brain-ui/src/components/BrainGraph.tsx` (nodeCanvasObject)

- [ ] **Step 1: Replace the label section of `nodeCanvasObject` with 3-level zoom**

In the `nodeCanvasObject` callback, replace the label section (the block starting with `const zoom = graphRef.current?.zoom?.() ?? 1;` through the end of the label if-block) with:

```typescript
      // Semantic zoom levels
      const zoom = graphRef.current?.zoom?.() ?? 1;

      // Mid level (1.0-2.5): type letter inside node
      if (zoom >= 0.8 && highlighted) {
        const midAlpha = zoom < 1.2 ? (zoom - 0.8) / 0.4 : 1; // fade in 0.8-1.2
        if (zoom >= 1.0) {
          const typeChar = getTypeChar(n.memory_type);
          ctx.font = `bold ${Math.max(size * 0.9, 3)}px system-ui`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillStyle = "#fff";
          ctx.globalAlpha = effectiveOpacity * midAlpha * 0.85;
          ctx.fillText(typeChar, x, y);
          ctx.globalAlpha = 1;
          ctx.textBaseline = "alphabetic";
        }
      }

      // Close level (>2.5): content preview + keyphrases
      if (zoom >= 2.0 && highlighted) {
        const closeAlpha = zoom < 2.8 ? (zoom - 2.0) / 0.8 : 1; // fade in 2.0-2.8
        if (zoom >= 2.5) {
          // Content preview label
          const label =
            n.content_preview.length > 30
              ? n.content_preview.slice(0, 28) + "\u2026"
              : n.content_preview;
          ctx.font = "3px system-ui";
          ctx.textAlign = "center";
          ctx.fillStyle = color;
          ctx.globalAlpha = effectiveOpacity * closeAlpha * 0.7;
          ctx.fillText(label, x, y + size + 5);

          // Keyphrases (max 3)
          const kps = n.keyphrases ?? [];
          if (kps.length > 0) {
            ctx.font = "2px system-ui";
            ctx.fillStyle = "#888";
            ctx.globalAlpha = effectiveOpacity * closeAlpha * 0.5;
            const display = kps.length > 3
              ? kps.slice(0, 3).join(" \u00b7 ") + ` +${kps.length - 3}`
              : kps.join(" \u00b7 ");
            ctx.fillText(display, x, y + size + 9);
          }
          ctx.globalAlpha = 1;
        }
      }
```

- [ ] **Step 2: Add `getTypeChar` to imports**

Update the import from nodeStyle to include `getTypeChar`:

```typescript
import {
  getNodeColor,
  getNodeSize,
  getNodeOpacity,
  shouldPulse,
  shouldGlow,
  getTypeChar,
  getEdgeWidth,
  getEdgeOpacity,
  getEdgeTierColor,
  shouldEdgeGlow,
  COLOR_BRIDGE,
  COLOR_TIER1,
  COLOR_TIER2,
  COLOR_TIER3,
} from "../utils/nodeStyle";
```

- [ ] **Step 3: Commit**

```bash
git add brain-ui/src/components/BrainGraph.tsx
git commit -m "feat(brain-ui): semantic zoom with 3 progressive detail levels"
```

---

## Task 9: BrainGraph — Project cluster gravity

**Files:**
- Modify: `brain-ui/src/components/BrainGraph.tsx`

- [ ] **Step 1: Add cluster gravity force after graph mount**

Add a new `useEffect` after the pulse animation effect (after line ~96). This effect sets up the custom d3 force:

```typescript
  // Project cluster gravity
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg || projectList.length < 2) {
      // Remove force if only 1 project
      if (fg) fg.d3Force("projectCluster", null);
      return;
    }

    const centerX = dimensions.width / 2;
    const centerY = dimensions.height / 2;
    const radius = Math.min(dimensions.width, dimensions.height) * 0.25;

    // Compute project centers in a circle
    const projectCenters = new Map<string, { x: number; y: number }>();
    const activeProjects = selectedProjects.size === 0
      ? projectList
      : projectList.filter((p) => selectedProjects.has(p));

    activeProjects.forEach((p, i) => {
      const angle = (2 * Math.PI * i) / activeProjects.length - Math.PI / 2;
      projectCenters.set(p, {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      });
    });

    fg.d3Force("projectCluster", () => {
      for (const node of graphNodes) {
        const center = projectCenters.get(node.project);
        if (!center || node.x == null || node.y == null) continue;
        const strength = 0.03;
        node.vx = (node.vx ?? 0) + (center.x - node.x) * strength;
        node.vy = (node.vy ?? 0) + (center.y - node.y) * strength;
      }
    });

    fg.d3ReheatSimulation();

    return () => {
      if (fg) fg.d3Force("projectCluster", null);
    };
  }, [projectList, dimensions, selectedProjects, graphNodes]);
```

Note: This requires `selectedProjects` to be passed as a prop. Update the props interface:

```typescript
interface BrainGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  projectList: string[];
  selectedProject: string | null;
  selectedProjects: Set<string>;
  onNodeClick: (node: GraphNode) => void;
  onBackgroundClick: () => void;
  externalHoveredNodeId?: string | null;
}
```

Add `selectedProjects` to the destructured props.

- [ ] **Step 2: Add floating project labels in a post-render callback**

Add a `frameCounter` ref and project label rendering inside `nodeCanvasObject`. Add before the glow section:

```typescript
      // Floating project label (rendered once per project per frame)
```

Actually, a simpler approach: use `onRenderFramePost` prop. Add after the ForceGraph2D closing tag but this prop goes on the component. Add to ForceGraph2D props:

```typescript
        onRenderFramePost={(ctx: CanvasRenderingContext2D, globalScale: number) => {
          if (projectList.length < 2) return;
          // Compute centroids per project
          const centroids = new Map<string, { sx: number; sy: number; count: number }>();
          for (const node of graphNodes) {
            if (node.x == null || node.y == null) continue;
            const entry = centroids.get(node.project) ?? { sx: 0, sy: 0, count: 0 };
            entry.sx += node.x;
            entry.sy += node.y;
            entry.count += 1;
            centroids.set(node.project, entry);
          }
          for (const [project, data] of centroids) {
            if (data.count === 0) continue;
            const cx = data.sx / data.count;
            const cy = data.sy / data.count;
            const projColor = projectColorMap.get(project) ?? "#666";
            ctx.font = `${14 / globalScale}px system-ui`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = projColor;
            ctx.globalAlpha = 0.15;
            ctx.fillText(project, cx, cy);
            ctx.globalAlpha = 1;
          }
        }}
```

- [ ] **Step 3: Commit**

```bash
git add brain-ui/src/components/BrainGraph.tsx
git commit -m "feat(brain-ui): project cluster gravity with floating labels"
```

---

## Task 10: MemoryDetail — Full rewrite

**Files:**
- Rewrite: `brain-ui/src/components/MemoryDetail.tsx`
- Rewrite: `brain-ui/src/components/MemoryDetail.module.css`

- [ ] **Step 1: Write the new MemoryDetail component**

Replace the entire content of `brain-ui/src/components/MemoryDetail.tsx`:

```typescript
import { useState, useEffect } from "react";
import { fetchMemoryDetail } from "../api/client";
import type { MemoryDetailResponse, GraphNode, GraphEdge } from "../types";
import { getNodeColor } from "../utils/nodeStyle";
import styles from "./MemoryDetail.module.css";

interface MemoryDetailProps {
  node: GraphNode;
  edges: GraphEdge[];
  graphNodes: GraphNode[];
  onClose: () => void;
  onNodeNavigate: (memoryId: string) => void;
  onRelationHover: (memoryId: string | null) => void;
  onKeyphraseClick: (keyword: string) => void;
}

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffH = Math.floor(diffMs / 3_600_000);
  if (diffH < 1) return "< 1h ago";
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 30) return `${diffD}d ago`;
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" });
}

const TIER_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: "T1", color: "#ff6b6b" },
  2: { label: "T2", color: "#ffd93d" },
  3: { label: "T3", color: "#a78bfa" },
};

const RELATION_TYPE_COLORS: Record<string, string> = {
  same_concept: "#4ecdc4",
  supports: "#54a0ff",
  extends: "#a78bfa",
  derived_from: "#ffd93d",
  applies_to: "#ff9ff3",
};

export default function MemoryDetail({
  node,
  edges,
  graphNodes,
  onClose,
  onNodeNavigate,
  onRelationHover,
  onKeyphraseClick,
}: MemoryDetailProps) {
  const [detail, setDetail] = useState<MemoryDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoveredRelation, setHoveredRelation] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setDetail(null);
    fetchMemoryDetail(node.memory_id)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [node.memory_id]);

  const color = getNodeColor(node);

  // Build relations from graph edges
  const relations = edges
    .filter((e) => e.source_memory_id === node.memory_id || e.target_memory_id === node.memory_id)
    .map((e) => {
      const targetId = e.source_memory_id === node.memory_id ? e.target_memory_id : e.source_memory_id;
      const targetNode = graphNodes.find((n) => n.memory_id === targetId);
      return { edge: e, targetId, targetNode };
    })
    .filter((r) => r.targetNode);

  if (loading) {
    return (
      <div className={styles.sidebar}>
        <div className={styles.loading}>Loading...</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className={styles.sidebar}>
        <div className={styles.loading}>Failed to load</div>
      </div>
    );
  }

  const m = detail.memory;

  return (
    <div className={styles.sidebar}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.colorDot} style={{ background: color }} />
        <div className={styles.headerText}>
          <div className={styles.title}>{m.summary || m.content_preview}</div>
          <div className={styles.projectLabel}>{m.project}</div>
        </div>
        <button className={styles.closeBtn} onClick={onClose}>{"\u2715"}</button>
      </div>

      {/* Memory type badge */}
      <div className={styles.badges}>
        <span className={`${styles.badge} ${styles.badgeType}`}>{m.memory_type}</span>
        {m.tags.map((t) => (
          <span key={t} className={`${styles.badge} ${styles.badgeTag}`}>{t}</span>
        ))}
      </div>

      {/* Full content */}
      <div className={styles.content}>{m.content || m.content_preview}</div>

      {/* Keyphrases */}
      {m.keyphrases && m.keyphrases.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionLabel}>Keyphrases</div>
          <div className={styles.keyphrases}>
            {m.keyphrases.map((kp) => (
              <button
                key={kp}
                className={styles.keyphrase}
                onClick={() => onKeyphraseClick(kp)}
              >
                {kp}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Scores Grid */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>Metrics</div>
        <div className={styles.scoreGrid}>
          <ScoreBar label="Activation" value={m.activation_score} color="#ff6b6b" />
          <ScoreBar label="Stability" value={m.stability_score} color="#4ecdc4" />
          <ScoreBar label="Importance" value={m.importance} color="#a78bfa" />
          <ScoreBar label="Novelty" value={m.novelty_score} color="#54a0ff" />
          <ScoreBar label="Prominence" value={m.prominence} color="#ffd93d" />
        </div>
      </div>

      {/* Emotional Axes */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>Emotional Axes</div>
        <div className={styles.emotionRow}>
          <span className={styles.emotionLabel}>Valence</span>
          <div className={styles.valenceBar}>
            <div
              className={styles.valenceMarker}
              style={{ left: `${((m.valence + 1) / 2) * 100}%` }}
            />
          </div>
          <span className={styles.emotionValue}>{m.valence > 0 ? "+" : ""}{m.valence.toFixed(2)}</span>
        </div>
        <div className={styles.emotionRow}>
          <span className={styles.emotionLabel}>Arousal</span>
          <div className={styles.arousalBar}>
            <div
              className={styles.arousalFill}
              style={{ width: `${m.arousal * 100}%` }}
            />
          </div>
          <span className={styles.emotionValue}>{m.arousal.toFixed(2)}</span>
        </div>
      </div>

      {/* Ebbinghaus Decay */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>Ebbinghaus Decay</div>
        <div className={styles.decayBar}>
          <div className={styles.decayFill} style={{ width: `${m.stability_score * 100}%` }} />
        </div>
        <div className={styles.decayMeta}>
          <span>Halflife: {m.stability_halflife_days.toFixed(1)}d</span>
          <span>Reviews: {m.review_count}</span>
        </div>
      </div>

      {/* Relations */}
      {relations.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionLabel}>Relations ({relations.length})</div>
          <div className={styles.relationList}>
            {relations.map(({ edge, targetId, targetNode }) => {
              const tier = edge.evidence_json?.tier;
              const tierInfo = tier ? TIER_LABELS[tier] : null;
              const relColor = RELATION_TYPE_COLORS[edge.relation_type] ?? "#666";
              const isHovered = hoveredRelation === targetId;

              return (
                <div
                  key={targetId}
                  className={`${styles.relationItem} ${isHovered ? styles.relationHovered : ""}`}
                  onMouseEnter={() => {
                    setHoveredRelation(targetId);
                    onRelationHover(targetId);
                  }}
                  onMouseLeave={() => {
                    setHoveredRelation(null);
                    onRelationHover(null);
                  }}
                  onClick={() => onNodeNavigate(targetId)}
                >
                  <div className={styles.relationBadges}>
                    <span className={styles.relationTypeBadge} style={{ borderColor: relColor, color: relColor }}>
                      {edge.relation_type}
                    </span>
                    {tierInfo && (
                      <span className={styles.tierBadge} style={{ background: tierInfo.color }}>
                        {tierInfo.label}
                      </span>
                    )}
                  </div>
                  <div className={styles.relationPreview}>
                    {targetNode!.content_preview}
                  </div>
                  {/* Hover tooltip with extra info */}
                  {isHovered && (
                    <div className={styles.relationTooltip}>
                      <div>Weight: {edge.weight.toFixed(3)}</div>
                      {edge.myelin_score > 0 && <div>Myelin: {edge.myelin_score.toFixed(3)}</div>}
                      <div>Reinforced: {edge.reinforcement_count}x</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Metadata footer */}
      <div className={styles.metaList}>
        <div className={styles.metaRow}>
          <span>Accesses</span><span className={styles.metaValue}>{m.access_count}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Last accessed</span><span className={styles.metaValue}>{formatDate(m.last_accessed_at)}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Abstraction</span><span className={styles.metaValue}>Level {m.abstraction_level}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Pinned</span>
          <span className={m.manual_pin ? styles.metaHighlight : styles.metaValue}>
            {m.manual_pin ? "Yes" : "No"}
          </span>
        </div>
      </div>
    </div>
  );
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={styles.scoreItem}>
      <div className={styles.scoreHeader}>
        <span className={styles.scoreLabel}>{label}</span>
        <span className={styles.scoreNum} style={{ color }}>{value.toFixed(2)}</span>
      </div>
      <div className={styles.scoreBarTrack}>
        <div className={styles.scoreBarFill} style={{ width: `${value * 100}%`, background: color }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write the new MemoryDetail styles**

Replace the entire content of `brain-ui/src/components/MemoryDetail.module.css`:

```css
.sidebar {
  width: 380px;
  background: #0f0f1a;
  border-left: 1px solid #1e1e3a;
  padding: 16px;
  overflow-y: auto;
  font-size: 12px;
  color: #ccc;
  flex-shrink: 0;
  animation: slideIn 0.2s ease;
}

@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 14px;
}

.colorDot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 4px;
}

.headerText {
  flex: 1;
  min-width: 0;
}

.title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  line-height: 1.3;
}

.projectLabel {
  font-size: 10px;
  color: #666;
  margin-top: 2px;
}

.closeBtn {
  margin-left: auto;
  background: none;
  border: none;
  color: #555;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
  flex-shrink: 0;
}
.closeBtn:hover { color: #ccc; }

.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
}

.badge {
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 10px;
}

.badgeType {
  background: #1a1a2e;
  color: #a78bfa;
  border: 1px solid #a78bfa44;
}

.badgeTag {
  background: transparent;
  color: #888;
  border: 1px solid #2a2a4a;
}

.content {
  color: #aaa;
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #1a1a2e;
  max-height: 150px;
  overflow-y: auto;
}

.section {
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #1a1a2e;
}

.sectionLabel {
  font-size: 9px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

/* Keyphrases */
.keyphrases {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.keyphrase {
  background: #162030;
  border: 1px solid #1e3a5f;
  border-radius: 12px;
  padding: 2px 10px;
  font-size: 10px;
  color: #54a0ff;
  cursor: pointer;
  transition: background 0.15s;
}
.keyphrase:hover {
  background: #1e3a5f;
}

/* Score Grid */
.scoreGrid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.scoreItem {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.scoreHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.scoreLabel {
  font-size: 10px;
  color: #666;
}

.scoreNum {
  font-size: 11px;
  font-weight: 600;
  font-family: "SF Mono", "Fira Code", monospace;
}

.scoreBarTrack {
  background: #12121f;
  border-radius: 2px;
  height: 4px;
  overflow: hidden;
}

.scoreBarFill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* Emotional Axes */
.emotionRow {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.emotionLabel {
  font-size: 10px;
  color: #666;
  width: 50px;
  flex-shrink: 0;
}

.emotionValue {
  font-size: 10px;
  color: #888;
  font-family: "SF Mono", "Fira Code", monospace;
  width: 40px;
  text-align: right;
  flex-shrink: 0;
}

.valenceBar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(90deg, #ff6b6b, #444 50%, #4ecdc4);
  position: relative;
}

.valenceMarker {
  position: absolute;
  top: -2px;
  width: 4px;
  height: 10px;
  border-radius: 2px;
  background: #fff;
  transform: translateX(-50%);
}

.arousalBar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: #12121f;
  overflow: hidden;
}

.arousalFill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #666, #ffa94d);
  transition: width 0.3s ease;
}

/* Decay */
.decayBar {
  background: #12121f;
  border-radius: 4px;
  height: 6px;
  overflow: hidden;
  margin-bottom: 4px;
}

.decayFill {
  background: linear-gradient(90deg, #4ecdc4, #ffd93d, #ff6b6b);
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.decayMeta {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: #555;
}

/* Relations */
.relationList {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 250px;
  overflow-y: auto;
}

.relationItem {
  background: #12121f;
  border-radius: 6px;
  padding: 8px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}
.relationItem:hover {
  background: #1a1a30;
}
.relationHovered {
  background: #1a1a30;
}

.relationBadges {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
}

.relationTypeBadge {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 3px;
  border: 1px solid;
  background: transparent;
}

.tierBadge {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  color: #000;
  font-weight: 700;
}

.relationPreview {
  font-size: 11px;
  color: #999;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.relationTooltip {
  position: absolute;
  right: 8px;
  top: -4px;
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 10px;
  color: #aaa;
  z-index: 10;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

/* Meta footer */
.metaList {
  font-size: 11px;
  color: #555;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 12px;
  border-top: 1px solid #1a1a2e;
}

.metaRow {
  display: flex;
  justify-content: space-between;
}

.metaValue { color: #888; }
.metaHighlight { color: #4ecdc4; }

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #555;
}
```

- [ ] **Step 3: Commit**

```bash
git add brain-ui/src/components/MemoryDetail.tsx brain-ui/src/components/MemoryDetail.module.css
git commit -m "feat(brain-ui): rewrite MemoryDetail with keyphrases, relations, emotional axes"
```

---

## Task 11: HealthView — Brain health dashboard

**Files:**
- Create: `brain-ui/src/components/HealthView.tsx`
- Create: `brain-ui/src/components/HealthView.module.css`

- [ ] **Step 1: Create HealthView component**

Create `brain-ui/src/components/HealthView.tsx`:

```typescript
import { useState, useEffect } from "react";
import { fetchBrainHealth } from "../api/client";
import type { BrainHealthResponse } from "../types";
import styles from "./HealthView.module.css";

function formatRelative(iso: string | null): string {
  if (!iso) return "\u2014";
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffH = Math.floor(diffMs / 3_600_000);
  if (diffH < 1) return "< 1h ago";
  if (diffH < 24) return `${diffH}h ago`;
  return `${Math.floor(diffH / 24)}d ago`;
}

function healthColor(score: number): string {
  if (score >= 0.7) return "#4ecdc4";
  if (score >= 0.4) return "#ffd93d";
  return "#ff6b6b";
}

export default function HealthView() {
  const [data, setData] = useState<BrainHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = () =>
      fetchBrainHealth()
        .then((d) => mounted && setData(d))
        .catch((e) => mounted && setError(e instanceof Error ? e.message : "Failed"));

    load();
    const id = setInterval(load, 60_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  if (error) {
    return <div className={styles.container}><div className={styles.error}>{error}</div></div>;
  }
  if (!data) {
    return <div className={styles.container}><div className={styles.loading}>Loading brain health...</div></div>;
  }

  const syn = data.synapse_formation;
  const sleep = data.sleep;

  return (
    <div className={styles.container}>
      {/* Overall Health */}
      <div className={`${styles.card} ${styles.healthCard}`}>
        <div className={styles.cardTitle}>Overall Brain Health</div>
        <div className={styles.healthScore} style={{ color: healthColor(data.overall_health) }}>
          {Math.round(data.overall_health * 100)}%
        </div>
        <div className={styles.healthBar}>
          <div
            className={styles.healthFill}
            style={{ width: `${data.overall_health * 100}%`, background: healthColor(data.overall_health) }}
          />
        </div>
        <div className={styles.cardMeta}>Updated {formatRelative(data.timestamp)}</div>
      </div>

      {/* Synapse Formation */}
      <div className={styles.card}>
        <div className={styles.cardTitle}>Synapse Formation</div>
        <div className={styles.synapseGrid}>
          <div className={styles.synapseTier}>
            <div className={styles.synapseNum} style={{ color: "#ff6b6b" }}>{syn.tier1_instant}</div>
            <div className={styles.synapseLabel}>T1 Instinct</div>
          </div>
          <div className={styles.synapseTier}>
            <div className={styles.synapseNum} style={{ color: "#ffd93d" }}>{syn.tier2_confirmed}</div>
            <div className={styles.synapseLabel}>T2 Perception</div>
          </div>
          <div className={styles.synapseTier}>
            <div className={styles.synapseNum} style={{ color: "#a78bfa" }}>
              {syn.tier3_promoted + syn.tier3_candidates_pending}
            </div>
            <div className={styles.synapseLabel}>T3 Reasoning</div>
            <div className={styles.t3Detail}>
              <span className={styles.t3Promoted}>{syn.tier3_promoted} promoted</span>
              <span className={styles.t3Pending}>{syn.tier3_candidates_pending} pending</span>
              <span className={styles.t3Rejected}>{syn.tier3_rejected} rejected</span>
            </div>
          </div>
        </div>
      </div>

      {/* Regions */}
      <div className={styles.card}>
        <div className={styles.cardTitle}>Regions</div>
        <div className={styles.regionList}>
          {Object.entries(data.regions).map(([name, region]) => (
            <div key={name} className={styles.regionItem}>
              <div className={styles.regionName}>{name}</div>
              <div className={styles.regionStats}>
                <span>{region.memory_count} memories</span>
                <span>{region.active_synapses} synapses</span>
                <span>Activation: {region.avg_activation.toFixed(2)}</span>
              </div>
              <div className={styles.regionBars}>
                <div className={styles.miniBarGroup}>
                  <span className={styles.miniBarLabel}>Orphans</span>
                  <div className={styles.miniBarTrack}>
                    <div
                      className={styles.miniBarFill}
                      style={{
                        width: `${region.orphan_ratio * 100}%`,
                        background: region.orphan_ratio > 0.2 ? "#ff6b6b" : "#4ecdc4",
                      }}
                    />
                  </div>
                  <span className={styles.miniBarValue}>{(region.orphan_ratio * 100).toFixed(0)}%</span>
                </div>
                <div className={styles.miniBarGroup}>
                  <span className={styles.miniBarLabel}>Keyphrases</span>
                  <div className={styles.miniBarTrack}>
                    <div
                      className={styles.miniBarFill}
                      style={{ width: `${region.keyphrases_coverage * 100}%`, background: "#54a0ff" }}
                    />
                  </div>
                  <span className={styles.miniBarValue}>{(region.keyphrases_coverage * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div className={styles.regionMeta}>NREM: {formatRelative(region.last_nrem)}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Connectivity */}
      {Object.keys(data.connectivity).length > 0 && (
        <div className={styles.card}>
          <div className={styles.cardTitle}>Connectivity</div>
          <div className={styles.connectList}>
            {Object.entries(data.connectivity).map(([pair, conn]) => (
              <div key={pair} className={styles.connectItem}>
                <div className={styles.connectPair}>{pair}</div>
                <div className={styles.connectStats}>
                  <div className={styles.miniBarGroup}>
                    <span className={styles.miniBarLabel}>Permeability</span>
                    <div className={styles.miniBarTrack}>
                      <div className={styles.miniBarFill} style={{ width: `${conn.permeability_score * 100}%`, background: "#a78bfa" }} />
                    </div>
                    <span className={styles.miniBarValue}>{conn.permeability_score.toFixed(2)}</span>
                  </div>
                  <span className={styles.connectMeta}>
                    {conn.myelinated_relations} myelinated &middot; avg {conn.avg_myelin_score.toFixed(2)}
                    {" "}&middot;{" "}
                    <span className={conn.organic_origin ? styles.organic : styles.manual}>
                      {conn.organic_origin ? "organic" : "manual"}
                    </span>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sleep Cycles */}
      <div className={styles.card}>
        <div className={styles.cardTitle}>Sleep Cycles</div>
        <div className={styles.sleepGrid}>
          <div className={styles.sleepItem}>
            <span className={styles.sleepLabel}>Last NREM</span>
            <span className={styles.sleepValue}>{formatRelative(sleep.last_nrem)}</span>
          </div>
          <div className={styles.sleepItem}>
            <span className={styles.sleepLabel}>Last REM</span>
            <span className={styles.sleepValue}>{formatRelative(sleep.last_rem)}</span>
          </div>
        </div>
        <div className={styles.miniBarGroup}>
          <span className={styles.miniBarLabel}>
            Cross-activity {sleep.cross_activity_score} / {sleep.rem_threshold}
          </span>
          <div className={styles.miniBarTrack}>
            <div
              className={styles.miniBarFill}
              style={{
                width: `${Math.min((sleep.cross_activity_score / Math.max(sleep.rem_threshold, 1)) * 100, 100)}%`,
                background: sleep.cross_activity_score >= sleep.rem_threshold ? "#ff6b6b" : "#4ecdc4",
              }}
            />
          </div>
        </div>
        {sleep.cross_activity_score >= sleep.rem_threshold && (
          <div className={styles.remNeeded}>REM cycle needed</div>
        )}
      </div>

      {/* Alerts */}
      <div className={styles.card}>
        <div className={styles.cardTitle}>Alerts</div>
        {data.alerts.length === 0 ? (
          <div className={styles.allClear}>All clear</div>
        ) : (
          <div className={styles.alertList}>
            {data.alerts.map((alert, i) => (
              <div key={i} className={`${styles.alert} ${styles[`alert_${alert.severity}`]}`}>
                <span className={styles.alertSeverity}>{alert.severity}</span>
                <span>{alert.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create HealthView styles**

Create `brain-ui/src/components/HealthView.module.css`:

```css
.container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
  align-content: start;
}

.loading, .error {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: #555;
  font-size: 14px;
}
.error { color: #ff6b6b; }

.card {
  background: #0d0d1a;
  border: 1px solid #1e1e3a;
  border-radius: 10px;
  padding: 18px;
}

.healthCard {
  grid-column: 1 / -1;
  text-align: center;
}

.cardTitle {
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.cardMeta {
  font-size: 10px;
  color: #444;
  margin-top: 8px;
}

/* Overall Health */
.healthScore {
  font-size: 48px;
  font-weight: 700;
  font-family: "SF Mono", "Fira Code", monospace;
  margin-bottom: 10px;
}

.healthBar {
  background: #12121f;
  border-radius: 6px;
  height: 10px;
  overflow: hidden;
  max-width: 400px;
  margin: 0 auto;
}

.healthFill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.5s ease;
}

/* Synapse Formation */
.synapseGrid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  text-align: center;
}

.synapseTier {
  background: #12121f;
  border-radius: 8px;
  padding: 12px 8px;
}

.synapseNum {
  font-size: 28px;
  font-weight: 700;
  font-family: "SF Mono", "Fira Code", monospace;
}

.synapseLabel {
  font-size: 10px;
  color: #666;
  margin-top: 4px;
}

.t3Detail {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 6px;
  font-size: 9px;
}

.t3Promoted { color: #4ecdc4; }
.t3Pending { color: #ffd93d; }
.t3Rejected { color: #ff6b6b; }

/* Regions */
.regionList {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
}

.regionItem {
  background: #12121f;
  border-radius: 8px;
  padding: 10px 12px;
}

.regionName {
  font-size: 12px;
  font-weight: 600;
  color: #ccc;
  margin-bottom: 4px;
}

.regionStats {
  display: flex;
  gap: 12px;
  font-size: 10px;
  color: #666;
  margin-bottom: 6px;
}

.regionBars {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.regionMeta {
  font-size: 9px;
  color: #555;
  margin-top: 4px;
}

/* Connectivity */
.connectList {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.connectItem {
  background: #12121f;
  border-radius: 8px;
  padding: 10px 12px;
}

.connectPair {
  font-size: 11px;
  color: #ccc;
  font-weight: 600;
  margin-bottom: 6px;
}

.connectStats {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.connectMeta {
  font-size: 9px;
  color: #666;
}

.organic { color: #4ecdc4; }
.manual { color: #ffd93d; }

/* Shared Mini Bar */
.miniBarGroup {
  display: flex;
  align-items: center;
  gap: 6px;
}

.miniBarLabel {
  font-size: 9px;
  color: #666;
  width: 65px;
  flex-shrink: 0;
}

.miniBarTrack {
  flex: 1;
  background: #1a1a2e;
  border-radius: 2px;
  height: 4px;
  overflow: hidden;
}

.miniBarFill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.miniBarValue {
  font-size: 9px;
  color: #888;
  font-family: "SF Mono", "Fira Code", monospace;
  width: 30px;
  text-align: right;
  flex-shrink: 0;
}

/* Sleep */
.sleepGrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 10px;
}

.sleepItem {
  background: #12121f;
  border-radius: 6px;
  padding: 8px;
  text-align: center;
}

.sleepLabel {
  display: block;
  font-size: 9px;
  color: #666;
  margin-bottom: 4px;
}

.sleepValue {
  font-size: 13px;
  color: #ccc;
  font-weight: 600;
}

.remNeeded {
  margin-top: 8px;
  padding: 6px;
  background: #2a1515;
  border: 1px solid #ff6b6b44;
  border-radius: 6px;
  color: #ff6b6b;
  font-size: 11px;
  text-align: center;
}

/* Alerts */
.alertList {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.alert {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px;
  border-radius: 6px;
  font-size: 11px;
  color: #ccc;
}

.alertSeverity {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 3px;
}

.alert_info {
  background: #0d1a2e;
  border: 1px solid #54a0ff33;
}
.alert_info .alertSeverity {
  background: #54a0ff22;
  color: #54a0ff;
}

.alert_warning {
  background: #1a1a0d;
  border: 1px solid #ffd93d33;
}
.alert_warning .alertSeverity {
  background: #ffd93d22;
  color: #ffd93d;
}

.alert_critical {
  background: #1a0d0d;
  border: 1px solid #ff6b6b33;
}
.alert_critical .alertSeverity {
  background: #ff6b6b22;
  color: #ff6b6b;
}

.allClear {
  color: #4ecdc4;
  font-size: 13px;
  text-align: center;
  padding: 16px;
}
```

- [ ] **Step 3: Commit**

```bash
git add brain-ui/src/components/HealthView.tsx brain-ui/src/components/HealthView.module.css
git commit -m "feat(brain-ui): add Brain Health dashboard with all biological metrics"
```

---

## Task 12: App.tsx — Wire everything together

**Files:**
- Modify: `brain-ui/src/App.tsx`
- Modify: `brain-ui/src/App.module.css`
- Modify: `brain-ui/src/components/TopBar.tsx`
- Modify: `brain-ui/src/components/TopBar.module.css`

- [ ] **Step 1: Update App.tsx with tab routing, StatsBar, and MemoryDetail wiring**

Replace the entire content of `brain-ui/src/App.tsx`:

```typescript
import { useState, useEffect, useCallback, useRef } from "react";
import { fetchSubgraph, fetchFacets } from "./api/client";
import type { GraphNode, GraphEdge, FacetProject, SubgraphResponse } from "./types";
import type { TabId } from "./components/TabSwitcher";
import TopBar from "./components/TopBar";
import StatsBar from "./components/StatsBar";
import BrainGraph from "./components/BrainGraph";
import MemoryDetail from "./components/MemoryDetail";
import HealthView from "./components/HealthView";
import styles from "./App.module.css";

function mergeSubgraphs(responses: SubgraphResponse[]): {
  nodes: GraphNode[];
  edges: GraphEdge[];
} {
  const nodeMap = new Map<string, GraphNode>();
  const edgeSet = new Set<string>();
  const edges: GraphEdge[] = [];

  for (const r of responses) {
    for (const n of r.nodes) {
      if (!nodeMap.has(n.memory_id)) nodeMap.set(n.memory_id, n);
    }
    for (const e of r.edges) {
      const key = `${e.source_memory_id}-${e.target_memory_id}`;
      if (!edgeSet.has(key)) {
        edgeSet.add(key);
        edges.push(e);
      }
    }
  }

  return { nodes: Array.from(nodeMap.values()), edges };
}

function filterByKeyword(
  nodes: GraphNode[],
  edges: GraphEdge[],
  keyword: string
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  if (!keyword) return { nodes, edges };
  const lower = keyword.toLowerCase();
  const matchingNodes = nodes.filter(
    (n) =>
      n.content_preview.toLowerCase().includes(lower) ||
      n.tags.some((t) => t.toLowerCase().includes(lower)) ||
      n.memory_type.toLowerCase().includes(lower) ||
      n.project.toLowerCase().includes(lower) ||
      (n.keyphrases ?? []).some((kp) => kp.toLowerCase().includes(lower))
  );
  const nodeIds = new Set(matchingNodes.map((n) => n.memory_id));
  const matchingEdges = edges.filter(
    (e) => nodeIds.has(e.source_memory_id) && nodeIds.has(e.target_memory_id)
  );
  return { nodes: matchingNodes, edges: matchingEdges };
}

export default function App() {
  const [projects, setProjects] = useState<FacetProject[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<Set<string>>(new Set());
  const [allNodes, setAllNodes] = useState<GraphNode[]>([]);
  const [allEdges, setAllEdges] = useState<GraphEdge[]>([]);
  const [keyword, setKeyword] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("graph");
  const [externalHoveredNodeId, setExternalHoveredNodeId] = useState<string | null>(null);
  const projectsRef = useRef<FacetProject[]>([]);

  const loadGraph = useCallback(
    async (selected: Set<string>, projectList?: FacetProject[]) => {
      const available = projectList || projectsRef.current;
      setLoading(true);
      setError(null);
      try {
        const targetProjects =
          selected.size === 0
            ? available.map((p) => p.project)
            : [...selected];

        if (targetProjects.length === 0) {
          setAllNodes([]);
          setAllEdges([]);
          return;
        }

        const results = await Promise.all(
          targetProjects.map((p) =>
            fetchSubgraph({ project: p, scope: "bridged" })
          )
        );
        const merged = mergeSubgraphs(results);
        setAllNodes(merged.nodes);
        setAllEdges(merged.edges);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load graph");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchFacets();
        setProjects(data.projects);
        projectsRef.current = data.projects;
        await loadGraph(new Set(), data.projects);
      } catch {
        setError("Failed to connect to API");
        setLoading(false);
      }
    })();
  }, [loadGraph]);

  const handleProjectChange = (next: Set<string>) => {
    setSelectedProjects(next);
    setSelectedNode(null);
    loadGraph(next);
  };

  const handleKeywordChange = (kw: string) => {
    setKeyword(kw);
  };

  const handleNodeNavigate = (memoryId: string) => {
    const node = allNodes.find((n) => n.memory_id === memoryId);
    if (node) setSelectedNode(node);
  };

  const { nodes, edges } = filterByKeyword(allNodes, allEdges, keyword);
  const projectList = projects.map((p) => p.project);

  return (
    <div className={styles.app}>
      <TopBar
        projects={projects}
        selectedProjects={selectedProjects}
        onProjectChange={handleProjectChange}
        keyword={keyword}
        onKeywordChange={handleKeywordChange}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {activeTab === "graph" && (
        <>
          <StatsBar
            nodes={nodes}
            edges={edges}
            totalNodes={allNodes.length}
            totalEdges={allEdges.length}
            keyword={keyword}
          />
          <div className={styles.main}>
            {loading ? (
              <div className={styles.loading}>Loading brain...</div>
            ) : error ? (
              <div className={styles.error}>
                <span>{error}</span>
                <button className={styles.retryBtn} onClick={() => loadGraph(selectedProjects)}>
                  Retry
                </button>
              </div>
            ) : (
              <BrainGraph
                nodes={nodes}
                edges={edges}
                projectList={projectList}
                selectedProject={selectedProjects.size === 1 ? [...selectedProjects][0] : null}
                selectedProjects={selectedProjects}
                onNodeClick={setSelectedNode}
                onBackgroundClick={() => setSelectedNode(null)}
                externalHoveredNodeId={externalHoveredNodeId}
              />
            )}
            {selectedNode && (
              <MemoryDetail
                node={selectedNode}
                edges={edges}
                graphNodes={nodes}
                onClose={() => setSelectedNode(null)}
                onNodeNavigate={handleNodeNavigate}
                onRelationHover={setExternalHoveredNodeId}
                onKeyphraseClick={(kp) => handleKeywordChange(kp)}
              />
            )}
          </div>
        </>
      )}

      {activeTab === "health" && (
        <div className={styles.main}>
          <HealthView />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Update TopBar to include TabSwitcher**

Replace the entire content of `brain-ui/src/components/TopBar.tsx`:

```typescript
import { useState, useEffect } from "react";
import { fetchHealth } from "../api/client";
import type { FacetProject } from "../types";
import type { TabId } from "./TabSwitcher";
import TabSwitcher from "./TabSwitcher";
import ProjectSelector from "./ProjectSelector";
import KeywordFilter from "./KeywordFilter";
import styles from "./TopBar.module.css";

interface TopBarProps {
  projects: FacetProject[];
  selectedProjects: Set<string>;
  onProjectChange: (projects: Set<string>) => void;
  keyword: string;
  onKeywordChange: (keyword: string) => void;
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export default function TopBar({
  projects,
  selectedProjects,
  onProjectChange,
  keyword,
  onKeywordChange,
  activeTab,
  onTabChange,
}: TopBarProps) {
  const [healthy, setHealthy] = useState(true);

  useEffect(() => {
    let mounted = true;
    const check = () =>
      fetchHealth()
        .then(() => mounted && setHealthy(true))
        .catch(() => mounted && setHealthy(false));
    check();
    const id = setInterval(check, 30_000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className={styles.topbar}>
      <div className={styles.left}>
        <div className={styles.logo}>{"\u{1f9e0}"} AI Memory Brain</div>
        <TabSwitcher activeTab={activeTab} onTabChange={onTabChange} />
      </div>
      <div className={styles.right}>
        <KeywordFilter value={keyword} onChange={onKeywordChange} />
        <ProjectSelector
          projects={projects}
          selected={selectedProjects}
          onChange={onProjectChange}
        />
        <div className={styles.health}>
          <div
            className={`${styles.healthDot} ${
              healthy ? styles.healthy : styles.unhealthy
            }`}
          />
          {healthy ? "System healthy" : "Unreachable"}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update TopBar styles to accommodate tabs**

Replace the entire content of `brain-ui/src/components/TopBar.module.css`:

```css
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #12121f;
  border-bottom: 1px solid #1e1e3a;
  padding: 0 20px;
  height: 52px;
  flex-shrink: 0;
}

.left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.logo {
  font-size: 17px;
  font-weight: 700;
  color: #a78bfa;
  letter-spacing: -0.3px;
}

.right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.health {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #666;
}

.healthDot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.healthy {
  background: #4ecdc4;
  box-shadow: 0 0 6px rgba(78, 205, 196, 0.4);
}

.unhealthy {
  background: #ff6b6b;
  box-shadow: 0 0 6px rgba(255, 107, 107, 0.4);
}
```

- [ ] **Step 4: Commit**

```bash
git add brain-ui/src/App.tsx brain-ui/src/App.module.css brain-ui/src/components/TopBar.tsx brain-ui/src/components/TopBar.module.css
git commit -m "feat(brain-ui): wire tab routing, StatsBar, and MemoryDetail with biological data"
```

---

## Task 13: Build verification and fixes

**Files:**
- All modified files

- [ ] **Step 1: Run TypeScript compilation check**

```bash
cd brain-ui && npx tsc --noEmit 2>&1
```

Expected: clean compilation with no errors. If there are errors, fix them.

- [ ] **Step 2: Run the Vite dev build**

```bash
cd brain-ui && npx vite build 2>&1 | tail -20
```

Expected: successful build with no errors.

- [ ] **Step 3: Fix any compilation errors found**

Address any TypeScript or build errors discovered in steps 1-2.

- [ ] **Step 4: Commit fixes if any**

```bash
git add -A brain-ui/src/
git commit -m "fix(brain-ui): resolve build errors from biological update"
```

---

## Task 14: Final commit — update .gitignore for superpowers brainstorm directory

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add .superpowers/ to gitignore if not already present**

Check if `.superpowers/` is in `.gitignore`. If not, add it.

```bash
grep -q '.superpowers/' .gitignore || echo '.superpowers/' >> .gitignore
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .superpowers/ to gitignore"
```
