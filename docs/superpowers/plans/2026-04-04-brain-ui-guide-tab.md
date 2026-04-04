# Brain UI Guide Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Guide" tab to the Brain UI that explains every visual cue, metric, and concept in plain language for non-neuroscience users.

**Architecture:** A single new `GuideView.tsx` component (purely static/presentational, no API calls) renders a two-column layout: a sticky sidebar with section anchor links and a scrollable content area with 13 reference sections. Wired into `App.tsx` and `TabSwitcher.tsx` with minimal changes.

**Tech Stack:** React 18, TypeScript, CSS Modules, Vite dev server (`:5173`)

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `brain-ui/src/components/GuideView.tsx` | Full guide component — sidebar + all 13 sections |
| Create | `brain-ui/src/components/GuideView.module.css` | Layout and table styles matching existing dark theme |
| Modify | `brain-ui/src/components/TabSwitcher.tsx` | Add `"guide"` to `TabId` union type and `TABS` array |
| Modify | `brain-ui/src/App.tsx` | Import `GuideView` and render it for `activeTab === "guide"` |

---

## Task 1: Add "guide" to TabSwitcher

**Files:**
- Modify: `brain-ui/src/components/TabSwitcher.tsx`

- [ ] **Step 1: Open `TabSwitcher.tsx` and update `TabId` and `TABS`**

Replace the file content with:

```tsx
import styles from "./TabSwitcher.module.css";

export type TabId = "graph" | "health" | "guide";

interface TabSwitcherProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

const TABS: { id: TabId; label: string }[] = [
  { id: "graph", label: "🧠 Graph" },
  { id: "health", label: "❤ Health" },
  { id: "guide", label: "📖 Guide" },
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

- [ ] **Step 2: Verify TypeScript compiles with no errors**

```bash
cd brain-ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors (or only pre-existing errors unrelated to TabId).

- [ ] **Step 3: Commit**

```bash
cd brain-ui && git add src/components/TabSwitcher.tsx && git commit -m "feat(brain-ui): add Guide tab to TabSwitcher"
```

---

## Task 2: Create GuideView CSS

**Files:**
- Create: `brain-ui/src/components/GuideView.module.css`

- [ ] **Step 1: Create the CSS file**

```css
/* Layout */
.container {
  display: flex;
  flex: 1;
  overflow: hidden;
  font-size: 13px;
  color: #e0e0e0;
}

/* Sidebar */
.sidebar {
  width: 200px;
  flex-shrink: 0;
  background: #0f0f1a;
  border-right: 1px solid #ffffff11;
  overflow-y: auto;
  padding: 16px 0;
}

.sidebarGroup {
  margin-bottom: 8px;
}

.sidebarGroupLabel {
  padding: 4px 16px;
  font-size: 10px;
  text-transform: uppercase;
  color: #444;
  letter-spacing: 1px;
  margin-bottom: 2px;
}

.sidebarLink {
  display: block;
  width: 100%;
  padding: 7px 16px;
  font-size: 12px;
  color: #666;
  background: transparent;
  border: none;
  border-left: 2px solid transparent;
  text-align: left;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
  line-height: 1.3;
}

.sidebarLink:hover {
  color: #aaa;
  background: #ffffff08;
}

.sidebarLinkActive {
  color: #54a0ff;
  background: #54a0ff11;
  border-left-color: #54a0ff;
}

/* Content */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 28px 36px;
}

.section {
  margin-bottom: 40px;
  scroll-margin-top: 20px;
}

.sectionTitle {
  font-size: 19px;
  font-weight: 700;
  margin-bottom: 4px;
}

.sectionSubtitle {
  font-size: 11px;
  color: #555;
  margin-bottom: 16px;
}

.prose {
  color: #bbb;
  line-height: 1.7;
  margin-bottom: 14px;
}

.prose strong {
  color: #e0e0e0;
}

/* Tables */
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin-bottom: 8px;
}

.table th {
  text-align: left;
  padding: 7px 12px;
  color: #555;
  font-weight: 500;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #ffffff22;
}

.table td {
  padding: 8px 12px;
  border-bottom: 1px solid #ffffff08;
  vertical-align: top;
  color: #bbb;
  line-height: 1.5;
}

.table tr:last-child td {
  border-bottom: none;
}

/* Color swatch inline */
.swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  vertical-align: middle;
  margin-right: 5px;
  flex-shrink: 0;
}

/* Note block */
.note {
  background: #0d1a2e;
  border: 1px solid #54a0ff22;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12px;
  color: #888;
  line-height: 1.6;
  margin-top: 10px;
}
```

- [ ] **Step 2: Commit**

```bash
cd brain-ui && git add src/components/GuideView.module.css && git commit -m "feat(brain-ui): add GuideView CSS module"
```

---

## Task 3: Create GuideView component

**Files:**
- Create: `brain-ui/src/components/GuideView.tsx`

- [ ] **Step 1: Create `GuideView.tsx`**

```tsx
import { useState, useEffect, useRef } from "react";
import styles from "./GuideView.module.css";

interface Section {
  id: string;
  label: string;
}

const GRAPH_SECTIONS: Section[] = [
  { id: "the-graph", label: "The Graph" },
  { id: "node-colors", label: "Node Colors & Effects" },
  { id: "edges", label: "Edges & Connections" },
  { id: "metrics", label: "Memory Metrics" },
  { id: "emotions", label: "Emotional Axes" },
  { id: "decay", label: "Ebbinghaus Decay" },
  { id: "relations", label: "Relations & Tiers" },
  { id: "memory-types", label: "Memory Types" },
];

const HEALTH_SECTIONS: Section[] = [
  { id: "overall-health", label: "Overall Health" },
  { id: "synapse-formation", label: "Synapse Formation" },
  { id: "regions", label: "Regions" },
  { id: "connectivity", label: "Connectivity" },
  { id: "sleep-cycles", label: "Sleep Cycles" },
];

export default function GuideView() {
  const [activeId, setActiveId] = useState("the-graph");
  const contentRef = useRef<HTMLDivElement>(null);

  // Scroll-spy: update active section based on scroll position
  useEffect(() => {
    const container = contentRef.current;
    if (!container) return;

    const allIds = [...GRAPH_SECTIONS, ...HEALTH_SECTIONS].map((s) => s.id);

    const onScroll = () => {
      for (let i = allIds.length - 1; i >= 0; i--) {
        const el = container.querySelector(`#${allIds[i]}`);
        if (el && (el as HTMLElement).getBoundingClientRect().top <= 80) {
          setActiveId(allIds[i]);
          return;
        }
      }
      setActiveId(allIds[0]);
    };

    container.addEventListener("scroll", onScroll, { passive: true });
    return () => container.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (id: string) => {
    const container = contentRef.current;
    if (!container) return;
    const el = container.querySelector(`#${id}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveId(id);
  };

  return (
    <div className={styles.container}>
      {/* Sidebar */}
      <nav className={styles.sidebar}>
        <div className={styles.sidebarGroup}>
          <div className={styles.sidebarGroupLabel}>Graph View</div>
          {GRAPH_SECTIONS.map((s) => (
            <button
              key={s.id}
              className={`${styles.sidebarLink} ${activeId === s.id ? styles.sidebarLinkActive : ""}`}
              onClick={() => scrollTo(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className={styles.sidebarGroup}>
          <div className={styles.sidebarGroupLabel}>Health Dashboard</div>
          {HEALTH_SECTIONS.map((s) => (
            <button
              key={s.id}
              className={`${styles.sidebarLink} ${activeId === s.id ? styles.sidebarLinkActive : ""}`}
              onClick={() => scrollTo(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <div className={styles.content} ref={contentRef}>

        {/* 1. The Graph */}
        <div className={styles.section} id="the-graph">
          <div className={styles.sectionTitle}>The Graph</div>
          <div className={styles.sectionSubtitle}>How to read the main visualization</div>
          <p className={styles.prose}>
            Each <strong>circle</strong> is a memory — a piece of information stored by the AI agent
            (a decision, an error, an observation, etc.). <strong>Lines</strong> between circles are
            relations — connections the system detected between memories.
          </p>
          <p className={styles.prose}>
            The layout is <strong>radial</strong>: memories with high activation cluster near the
            center, fading memories drift toward the edges. When multiple projects are loaded, each
            project occupies its own angular sector of the circle.
          </p>
          <p className={styles.prose}>
            <strong>Click</strong> any node to open its detail panel.{" "}
            <strong>Hover</strong> to highlight only that node and its direct connections.
            Use the keyword filter bar to search by content, tags, or keyphrases.
          </p>
        </div>

        {/* 2. Node Colors & Effects */}
        <div className={styles.section} id="node-colors">
          <div className={styles.sectionTitle}>Node Colors & Effects</div>
          <div className={styles.sectionSubtitle}>What the visual appearance of each node means</div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Visual</th>
                <th>Condition</th>
                <th>Meaning</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><span className={styles.swatch} style={{ background: "#ff6b6b" }} />Red</td>
                <td>activation &gt; 0.7</td>
                <td>Very active right now — being used frequently</td>
              </tr>
              <tr>
                <td><span className={styles.swatch} style={{ background: "#4ecdc4" }} />Cyan</td>
                <td>stability &gt; 0.5</td>
                <td>Well consolidated — resistant to forgetting</td>
              </tr>
              <tr>
                <td><span className={styles.swatch} style={{ background: "#ffd93d" }} />Yellow</td>
                <td>stability 0.2 – 0.5</td>
                <td>Decaying — losing strength over time</td>
              </tr>
              <tr>
                <td><span className={styles.swatch} style={{ background: "#666" }} />Gray</td>
                <td>stability &lt; 0.2</td>
                <td>Nearly forgotten — low activity and stability</td>
              </tr>
              <tr>
                <td>Pulsing ring</td>
                <td>activation &gt; 0.7</td>
                <td>Animated pulse indicates high current usage</td>
              </tr>
              <tr>
                <td>Glow halo</td>
                <td>prominence &gt; 0.5</td>
                <td>Memory that stands out in the system</td>
              </tr>
              <tr>
                <td>Larger size</td>
                <td>high prominence</td>
                <td>Node radius scales with prominence (4px base + prominence × 10px)</td>
              </tr>
              <tr>
                <td>Project ring</td>
                <td>No project filter active</td>
                <td>Colored border showing which project this memory belongs to</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 3. Edges */}
        <div className={styles.section} id="edges">
          <div className={styles.sectionTitle}>Edges & Connections</div>
          <div className={styles.sectionSubtitle}>What the lines between nodes mean</div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Visual</th>
                <th>Meaning</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Solid line</td>
                <td>Relation within the same project</td>
              </tr>
              <tr>
                <td style={{ color: "#54a0ff" }}>Dashed blue line</td>
                <td>Bridge — connects memories across different projects</td>
              </tr>
              <tr>
                <td>Glowing line</td>
                <td>Myelinated connection (myelin &gt; 0.5) — heavily reinforced pathway</td>
              </tr>
              <tr>
                <td>Thicker line</td>
                <td>Higher weight and/or myelin score — stronger connection</td>
              </tr>
              <tr>
                <td style={{ color: "#ff6b6b" }}>Red edge</td>
                <td>Tier 1 — instant relation, created immediately when the memory was stored</td>
              </tr>
              <tr>
                <td style={{ color: "#ffd93d" }}>Yellow edge</td>
                <td>Tier 2 — confirmed relation, validated by usage patterns over time</td>
              </tr>
              <tr>
                <td style={{ color: "#a78bfa" }}>Purple edge</td>
                <td>Tier 3 — reasoning relation, discovered by the offline reflection worker</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 4. Memory Metrics */}
        <div className={styles.section} id="metrics">
          <div className={styles.sectionTitle}>Memory Metrics</div>
          <div className={styles.sectionSubtitle}>Scores shown in the detail panel when you click a node</div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Range</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ color: "#ff6b6b" }}>Activation</td>
                <td>0.0 – 1.0</td>
                <td>How much this memory is being used right now. High = frequently accessed recently. Low = idle.</td>
              </tr>
              <tr>
                <td style={{ color: "#4ecdc4" }}>Stability</td>
                <td>0.0 – 1.0</td>
                <td>Resistance to forgetting. High = well consolidated, won't decay soon. Low = fragile, will fade if not accessed.</td>
              </tr>
              <tr>
                <td style={{ color: "#a78bfa" }}>Importance</td>
                <td>0.0 – 1.0</td>
                <td>Assigned weight of this memory. Critical decisions and errors score high; routine observations score low.</td>
              </tr>
              <tr>
                <td style={{ color: "#54a0ff" }}>Novelty</td>
                <td>0.0 – 1.0</td>
                <td>How unique this memory is compared to existing knowledge. High = new information. Low = redundant.</td>
              </tr>
              <tr>
                <td style={{ color: "#ffd93d" }}>Prominence</td>
                <td>0.0 – 1.0</td>
                <td>Combined score of importance, connections, and recent usage. Determines node size in the graph.</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 5. Emotional Axes */}
        <div className={styles.section} id="emotions">
          <div className={styles.sectionTitle}>Emotional Axes</div>
          <div className={styles.sectionSubtitle}>Emotional tagging applied to each memory</div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Axis</th>
                <th>Range</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Valence</td>
                <td>-1.0 to +1.0</td>
                <td>
                  Positive or negative association. Errors and failures score negative.
                  Successes and breakthroughs score positive. Neutral observations near 0.
                </td>
              </tr>
              <tr>
                <td>Arousal</td>
                <td>0.0 – 1.0</td>
                <td>
                  Emotional intensity. A critical production error = high arousal.
                  A routine note or observation = low arousal.
                </td>
              </tr>
            </tbody>
          </table>
          <div className={styles.note}>
            The valence bar in the detail panel goes from red (left = negative) to cyan (right = positive).
            The marker position shows the exact value.
          </div>
        </div>

        {/* 6. Ebbinghaus Decay */}
        <div className={styles.section} id="decay">
          <div className={styles.sectionTitle}>Ebbinghaus Decay</div>
          <div className={styles.sectionSubtitle}>How the system models forgetting over time</div>
          <p className={styles.prose}>
            Memories lose <strong>stability</strong> over time if not accessed — modeled after the
            Ebbinghaus forgetting curve. Each access or review doubles the memory's halflife,
            making it more resistant to future decay.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Field</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Stability bar</td>
                <td>Visual representation of current stability score — how resistant the memory is to forgetting right now</td>
              </tr>
              <tr>
                <td>Halflife</td>
                <td>Days until stability drops by half. Doubles with each review or access. A high halflife = memory will persist a long time.</td>
              </tr>
              <tr>
                <td>Reviews</td>
                <td>Number of times the offline consolidation process has reviewed this memory. More reviews = longer halflife.</td>
              </tr>
            </tbody>
          </table>
          <div className={styles.note}>
            A memory with halflife 14d and 3 reviews is far more resistant to forgetting than one
            with halflife 1d and 0 reviews, even if both currently show the same stability score.
          </div>
        </div>

        {/* 7. Relations & Tiers */}
        <div className={styles.section} id="relations">
          <div className={styles.sectionTitle}>Relations & Tiers</div>
          <div className={styles.sectionSubtitle}>The connections shown in the node detail panel</div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Field</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Relation type</td>
                <td>
                  Kind of connection:{" "}
                  <code>same_concept</code>, <code>supports</code>, <code>extends</code>,{" "}
                  <code>derived_from</code>, <code>applies_to</code>
                </td>
              </tr>
              <tr>
                <td>Tier (T1 / T2 / T3)</td>
                <td>Confidence level — T1 = instant/instinct, T2 = confirmed/perception, T3 = deep reasoning</td>
              </tr>
              <tr>
                <td>Weight</td>
                <td>Connection strength (0.0 – 1.0). Higher = stronger semantic association.</td>
              </tr>
              <tr>
                <td>Myelin</td>
                <td>Reinforcement score (0.0 – 1.0). Increases each time both memories are accessed together. High myelin = well-established pathway, shown as a glowing edge in the graph.</td>
              </tr>
              <tr>
                <td>Reinforced</td>
                <td>Number of times this connection has been activated together.</td>
              </tr>
              <tr>
                <td>Origin</td>
                <td><code>manual</code> = user-created relation. <code>vector_inference</code> = detected automatically by semantic similarity.</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 8. Memory Types */}
        <div className={styles.section} id="memory-types">
          <div className={styles.sectionTitle}>Memory Types</div>
          <div className={styles.sectionSubtitle}>Categories of stored memories — the letter shown inside nodes at mid-zoom</div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Type</th>
                <th>Letter</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>decision</td>
                <td style={{ fontFamily: "monospace", color: "#4ecdc4" }}>D</td>
                <td>A choice or decision made during work</td>
              </tr>
              <tr>
                <td>error</td>
                <td style={{ fontFamily: "monospace", color: "#ff6b6b" }}>E</td>
                <td>An error, bug, or failure encountered</td>
              </tr>
              <tr>
                <td>observation</td>
                <td style={{ fontFamily: "monospace", color: "#ffd93d" }}>O</td>
                <td>A general observation or note</td>
              </tr>
              <tr>
                <td>schema</td>
                <td style={{ fontFamily: "monospace", color: "#a78bfa" }}>S</td>
                <td>An abstract pattern detected across multiple memories</td>
              </tr>
              <tr>
                <td>insight</td>
                <td style={{ fontFamily: "monospace", color: "#54a0ff" }}>I</td>
                <td>A conclusion or realization derived from other memories</td>
              </tr>
              <tr>
                <td>pattern</td>
                <td style={{ fontFamily: "monospace", color: "#ff9ff3" }}>P</td>
                <td>A recurring pattern identified in data or behavior</td>
              </tr>
            </tbody>
          </table>
          <div className={styles.note}>
            The letter appears inside the node when zoomed in (zoom ≥ 1.8). Zoom in with the scroll
            wheel to see type labels, and further to zoom ≥ 3.5 to see the content preview text.
          </div>
        </div>

        {/* 9. Overall Health */}
        <div className={styles.section} id="overall-health">
          <div className={styles.sectionTitle}>Overall Health</div>
          <div className={styles.sectionSubtitle}>Top-level score in the Health dashboard</div>
          <p className={styles.prose}>
            A single percentage (0–100%) representing the overall state of the memory system.
            Calculated from region health, connectivity between regions, orphan ratios, and synapse quality.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Color</th>
                <th>Range</th>
                <th>Meaning</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><span className={styles.swatch} style={{ background: "#4ecdc4" }} />Cyan</td>
                <td>≥ 70%</td>
                <td>Healthy system</td>
              </tr>
              <tr>
                <td><span className={styles.swatch} style={{ background: "#ffd93d" }} />Yellow</td>
                <td>40 – 69%</td>
                <td>Needs attention</td>
              </tr>
              <tr>
                <td><span className={styles.swatch} style={{ background: "#ff6b6b" }} />Red</td>
                <td>&lt; 40%</td>
                <td>Critical issues — check Alerts section</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 10. Synapse Formation */}
        <div className={styles.section} id="synapse-formation">
          <div className={styles.sectionTitle}>Synapse Formation</div>
          <div className={styles.sectionSubtitle}>How connections between memories are created and promoted</div>
          <p className={styles.prose}>
            The system creates relations between memories in three tiers of confidence, modeled after
            neural pathway formation:
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Tier</th>
                <th>Name</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ color: "#ff6b6b" }}>T1</td>
                <td>Instinct</td>
                <td>Instant relations created when a memory is stored. Based on direct semantic similarity. Count = active T1 relations.</td>
              </tr>
              <tr>
                <td style={{ color: "#ffd93d" }}>T2</td>
                <td>Perception</td>
                <td>Confirmed relations — initially T1, promoted after usage patterns validate the connection over time.</td>
              </tr>
              <tr>
                <td style={{ color: "#a78bfa" }}>T3</td>
                <td>Reasoning</td>
                <td>Deep relations discovered by the offline reflection worker. Shows promoted / pending / rejected breakdown.</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 11. Regions */}
        <div className={styles.section} id="regions">
          <div className={styles.sectionTitle}>Regions</div>
          <div className={styles.sectionSubtitle}>Each project is a "region" — an isolated area of the brain</div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Field</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Memory count</td>
                <td>Total memories stored in this project/region</td>
              </tr>
              <tr>
                <td>Active synapses</td>
                <td>Number of active relations currently in this region</td>
              </tr>
              <tr>
                <td>Orphan ratio</td>
                <td>
                  Percentage of memories with no relations. Above 20% (shown in red) means many
                  memories are isolated — they haven't been connected to other knowledge yet.
                </td>
              </tr>
              <tr>
                <td>Schemas count</td>
                <td>Number of abstract patterns the system detected across memories in this region</td>
              </tr>
              <tr>
                <td>Keyphrases coverage</td>
                <td>How well keyphrases cover the content — higher is better for search quality</td>
              </tr>
              <tr>
                <td>Last NREM</td>
                <td>When the last consolidation cycle ran for this region</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 12. Connectivity */}
        <div className={styles.section} id="connectivity">
          <div className={styles.sectionTitle}>Connectivity</div>
          <div className={styles.sectionSubtitle}>How well different regions (projects) communicate with each other</div>
          <p className={styles.prose}>
            Each entry is a pair of projects. Connectivity measures the strength of cross-project pathways —
            bridges in the graph visualization.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Field</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Permeability score</td>
                <td>0.0 – 1.0. How easily information flows between the two regions. High = well connected.</td>
              </tr>
              <tr>
                <td>Myelinated relations</td>
                <td>Number of strong, reinforced connections between the two regions (myelin &gt; threshold)</td>
              </tr>
              <tr>
                <td>Avg myelin score</td>
                <td>Average reinforcement level of cross-region connections</td>
              </tr>
              <tr>
                <td>Organic origin</td>
                <td>Whether this cross-region pathway formed naturally (vs manually created)</td>
              </tr>
              <tr>
                <td>Formation reason</td>
                <td>Why this inter-region pathway exists — the triggering pattern or event</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 13. Sleep Cycles */}
        <div className={styles.section} id="sleep-cycles">
          <div className={styles.sectionTitle}>Sleep Cycles</div>
          <div className={styles.sectionSubtitle}>Periodic offline consolidation processes modeled after biological sleep</div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Field</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Last NREM</td>
                <td>
                  Last time the consolidation worker ran. It promotes memories, updates relation weights,
                  applies Ebbinghaus decay, and detects contradictions. Runs automatically every ~6 hours.
                </td>
              </tr>
              <tr>
                <td>Last REM</td>
                <td>
                  Last time the cross-project analysis ran. It finds patterns across different projects
                  and creates inter-region connections.
                </td>
              </tr>
              <tr>
                <td>Cross-activity score</td>
                <td>Current level of cross-project activity. When this exceeds the REM threshold, a REM cycle is triggered.</td>
              </tr>
              <tr>
                <td>REM threshold</td>
                <td>The threshold value that triggers a REM cycle. Shown as the denominator in the progress bar.</td>
              </tr>
              <tr>
                <td>"REM cycle needed"</td>
                <td>Alert shown when cross-activity ≥ threshold — the system should run cross-project consolidation soon.</td>
              </tr>
            </tbody>
          </table>
          <div className={styles.note}>
            NREM = consolidation within regions (like slow-wave sleep processing individual memories).
            REM = cross-region synthesis (like dream-state pattern finding across different knowledge areas).
          </div>
        </div>

      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd brain-ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
cd brain-ui && git add src/components/GuideView.tsx && git commit -m "feat(brain-ui): add GuideView component with 13 reference sections"
```

---

## Task 4: Wire GuideView into App.tsx

**Files:**
- Modify: `brain-ui/src/App.tsx`

- [ ] **Step 1: Add GuideView import and render it for the "guide" tab**

In `brain-ui/src/App.tsx`:

1. Add import after the existing imports:
```tsx
import GuideView from "./components/GuideView";
```

2. Add the guide tab render block after the `activeTab === "health"` block (around line 196):
```tsx
      {activeTab === "guide" && (
        <div className={styles.main}>
          <GuideView />
        </div>
      )}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd brain-ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd brain-ui && git add src/App.tsx && git commit -m "feat(brain-ui): wire GuideView into App — Guide tab now renders"
```

---

## Task 5: Smoke test in browser

**Files:** none (verification only)

- [ ] **Step 1: Start the dev server**

```bash
cd brain-ui && npm run dev
```

Expected output contains: `Local: http://localhost:5173/`

- [ ] **Step 2: Verify Guide tab appears**

Open `http://localhost:5173` in the browser. Confirm:
- Three tabs visible: 🧠 Graph | ❤ Health | 📖 Guide
- Clicking Guide tab shows the GuideView layout
- Sidebar shows two groups: "Graph View" (8 items) and "Health Dashboard" (5 items)
- Clicking any sidebar item scrolls the content to that section and highlights the active link
- All 13 sections render with their tables

- [ ] **Step 3: Verify Graph and Health tabs still work**

Click Graph → brain visualization renders as before.
Click Health → health dashboard renders as before.

- [ ] **Step 4: Final commit**

```bash
cd brain-ui && git add -p && git commit -m "feat(brain-ui): Guide tab — reference for all brain UI concepts"
```

---

## Self-Review

**Spec coverage:**
- ✅ New Guide tab alongside Graph and Health → Task 1 (TabSwitcher) + Task 4 (App.tsx)
- ✅ Sidebar with 13 section links → Task 3 sidebar nav
- ✅ Direct/functional tone, no metaphors → all table descriptions
- ✅ Node colors with thresholds → Task 3 section 2
- ✅ Edge types including bridges, myelin, tiers → Task 3 section 3
- ✅ All 5 metrics with ranges → Task 3 section 4
- ✅ Emotional axes (valence/arousal) → Task 3 section 5
- ✅ Ebbinghaus decay (halflife, reviews) → Task 3 section 6
- ✅ Relations and tier confidence levels → Task 3 section 7
- ✅ Memory types with letters → Task 3 section 8
- ✅ Overall health score with color thresholds → Task 3 section 9
- ✅ Synapse formation T1/T2/T3 → Task 3 section 10
- ✅ Regions (orphan ratio, schemas, etc.) → Task 3 section 11
- ✅ Connectivity (permeability, myelin) → Task 3 section 12
- ✅ Sleep cycles (NREM/REM, cross-activity) → Task 3 section 13
- ✅ Dark theme matching existing UI → Task 2 CSS uses `#0f0f1a`, `#0a0a12`, existing palette
- ✅ Scroll-spy active section highlighting → Task 3 useEffect

**Placeholder scan:** No TBDs, TODOs, or vague steps found.

**Type consistency:** `TabId` extended in Task 1 and consumed consistently in App.tsx Task 4. `GuideView` has no props — clean interface. No cross-task type mismatches.
