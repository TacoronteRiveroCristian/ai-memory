# Brain UI: Multi-Select Projects + Keyword Filter

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix "All Projects" to load every project (not just top 5), add multi-select project support, and add a keyword/tag filter that works across any scope.

**Architecture:** ProjectSelector becomes a multi-select with checkboxes. A new KeywordFilter component in the TopBar provides text search. App.tsx orchestrates both: multi-select drives which projects to load via parallel fetchSubgraph calls (using mergeSubgraphs), keyword filter switches to `mode: "search"` with `scope: "global"`. Both filters compose — keyword filter applies client-side on top of project selection.

**Tech Stack:** React, TypeScript, CSS Modules, existing API (`/api/graph/subgraph` with mode `search`/`project_hot`)

---

### Task 1: Convert ProjectSelector to multi-select

**Files:**
- Modify: `brain-ui/src/components/ProjectSelector.tsx`
- Modify: `brain-ui/src/components/ProjectSelector.module.css`

The selector currently uses `selected: string | null` and `onChange: (project: string | null) => void`. We change it to `selected: Set<string>` and `onChange: (projects: Set<string>) => void`. An empty set means "All".

- [ ] **Step 1: Update ProjectSelector props and state**

Replace the full component in `brain-ui/src/components/ProjectSelector.tsx`:

```tsx
import { useState, useRef, useEffect } from "react";
import type { FacetProject } from "../types";
import styles from "./ProjectSelector.module.css";

const PROJECT_COLORS = [
  "#ff6b6b",
  "#4ecdc4",
  "#ffd93d",
  "#a78bfa",
  "#ff9ff3",
  "#54a0ff",
  "#5f27cd",
  "#01a3a4",
];

interface ProjectSelectorProps {
  projects: FacetProject[];
  selected: Set<string>;
  onChange: (projects: Set<string>) => void;
}

export default function ProjectSelector({
  projects,
  selected,
  onChange,
}: ProjectSelectorProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  const filtered = search
    ? projects.filter((p) =>
        p.project.toLowerCase().includes(search.toLowerCase())
      )
    : projects;

  const totalMemories = projects.reduce((s, p) => s + p.memory_count, 0);
  const isAll = selected.size === 0;

  const toggleProject = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) {
      next.delete(name);
    } else {
      next.add(name);
    }
    onChange(next);
  };

  const selectAll = () => {
    onChange(new Set());
    setOpen(false);
    setSearch("");
  };

  // Display label
  let displayLabel: string;
  if (isAll) {
    displayLabel = "All Projects";
  } else if (selected.size === 1) {
    displayLabel = [...selected][0];
  } else {
    displayLabel = `${selected.size} Projects`;
  }

  return (
    <div className={styles.wrapper} ref={ref}>
      <div className={styles.trigger} onClick={() => setOpen(!open)}>
        <span className={styles.label}>Scope:</span>
        <span className={styles.value}>{displayLabel}</span>
        <span className={styles.arrow}>{open ? "\u25B2" : "\u25BC"}</span>
      </div>
      {open && (
        <div className={styles.dropdown}>
          <div className={styles.searchBox}>
            <input
              ref={inputRef}
              className={styles.searchInput}
              type="text"
              placeholder="Search projects..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className={styles.scrollArea}>
            <div
              className={`${styles.item} ${isAll ? styles.itemActive : ""}`}
              onClick={selectAll}
            >
              <span className={styles.itemIcon}>&#127760;</span>
              <div>
                <div className={styles.itemName}>All Projects</div>
                <div className={styles.itemMeta}>
                  {projects.length} projects &middot; {totalMemories} memories
                </div>
              </div>
            </div>
            <div className={styles.divider} />
            {filtered.map((p) => {
              const origIndex = projects.indexOf(p);
              const isSelected = selected.has(p.project);
              return (
                <div
                  key={p.project}
                  className={`${styles.item} ${isSelected ? styles.itemActive : ""}`}
                  onClick={() => toggleProject(p.project)}
                >
                  <div
                    className={`${styles.checkbox} ${isSelected ? styles.checkboxChecked : ""}`}
                    style={{
                      borderColor: PROJECT_COLORS[origIndex % PROJECT_COLORS.length],
                      background: isSelected
                        ? PROJECT_COLORS[origIndex % PROJECT_COLORS.length]
                        : "transparent",
                    }}
                  >
                    {isSelected && <span className={styles.checkmark}>✓</span>}
                  </div>
                  <div>
                    <div className={styles.itemName}>{p.project}</div>
                    <div className={styles.itemMeta}>
                      {p.memory_count} memories &middot; {p.pinned_memory_count} pinned
                    </div>
                  </div>
                </div>
              );
            })}
            {filtered.length === 0 && (
              <div className={styles.noResults}>No projects match</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export { PROJECT_COLORS };
```

- [ ] **Step 2: Add checkbox styles to ProjectSelector.module.css**

Append these styles to the end of `brain-ui/src/components/ProjectSelector.module.css`:

```css
.checkbox {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1.5px solid #555;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.checkboxChecked {
  border-color: currentColor;
}

.checkmark {
  font-size: 9px;
  color: #0a0a12;
  font-weight: 700;
  line-height: 1;
}
```

- [ ] **Step 3: Commit**

```bash
git add brain-ui/src/components/ProjectSelector.tsx brain-ui/src/components/ProjectSelector.module.css
git commit -m "feat(ui): convert ProjectSelector to multi-select with checkboxes"
```

---

### Task 2: Add KeywordFilter component

**Files:**
- Create: `brain-ui/src/components/KeywordFilter.tsx`
- Create: `brain-ui/src/components/KeywordFilter.module.css`

A simple text input with debounced onChange. Submits on Enter or after 500ms idle. Shows a clear button when active.

- [ ] **Step 1: Create KeywordFilter.tsx**

```tsx
import { useState, useRef, useCallback, useEffect } from "react";
import styles from "./KeywordFilter.module.css";

interface KeywordFilterProps {
  value: string;
  onChange: (keyword: string) => void;
}

export default function KeywordFilter({ value, onChange }: KeywordFilterProps) {
  const [draft, setDraft] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const flush = useCallback(
    (text: string) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      onChange(text.trim());
    },
    [onChange]
  );

  const handleChange = (text: string) => {
    setDraft(text);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => flush(text), 500);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      flush(draft);
    }
  };

  const clear = () => {
    setDraft("");
    flush("");
  };

  return (
    <div className={styles.wrapper}>
      <input
        className={styles.input}
        type="text"
        placeholder="Filter by keyword or tag..."
        value={draft}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      {draft && (
        <button className={styles.clear} onClick={clear}>
          ✕
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create KeywordFilter.module.css**

```css
.wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  padding: 6px 28px 6px 10px;
  color: #ccc;
  font-size: 12px;
  font-family: inherit;
  width: 200px;
  outline: none;
  transition: border-color 0.15s, width 0.2s;
}

.input::placeholder {
  color: #555;
}

.input:focus {
  border-color: #a78bfa;
  width: 260px;
}

.clear {
  position: absolute;
  right: 6px;
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  font-size: 11px;
  padding: 2px 4px;
  line-height: 1;
}

.clear:hover {
  color: #ff6b6b;
}
```

- [ ] **Step 3: Commit**

```bash
git add brain-ui/src/components/KeywordFilter.tsx brain-ui/src/components/KeywordFilter.module.css
git commit -m "feat(ui): add KeywordFilter component with debounced search"
```

---

### Task 3: Update TopBar to include KeywordFilter

**Files:**
- Modify: `brain-ui/src/components/TopBar.tsx`
- Modify: `brain-ui/src/components/TopBar.module.css`

- [ ] **Step 1: Update TopBar.tsx**

Replace the full component in `brain-ui/src/components/TopBar.tsx`:

```tsx
import { useState, useEffect } from "react";
import { fetchHealth } from "../api/client";
import type { FacetProject } from "../types";
import ProjectSelector from "./ProjectSelector";
import KeywordFilter from "./KeywordFilter";
import styles from "./TopBar.module.css";

interface TopBarProps {
  projects: FacetProject[];
  selectedProjects: Set<string>;
  onProjectChange: (projects: Set<string>) => void;
  keyword: string;
  onKeywordChange: (keyword: string) => void;
}

export default function TopBar({
  projects,
  selectedProjects,
  onProjectChange,
  keyword,
  onKeywordChange,
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
      <div className={styles.logo}>&#x1f9e0; AI Memory Brain</div>
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

- [ ] **Step 2: Commit**

```bash
git add brain-ui/src/components/TopBar.tsx
git commit -m "feat(ui): integrate KeywordFilter into TopBar"
```

---

### Task 4: Update App.tsx — load all projects, multi-select, keyword filter

**Files:**
- Modify: `brain-ui/src/App.tsx`

This is the core logic change. Three key behaviors:
1. **"All" (empty set):** fetch ALL projects in parallel with `scope: "bridged"`, merge
2. **Multi-select (N projects):** fetch those N projects in parallel with `scope: "bridged"`, merge
3. **Keyword filter active:** use `mode: "search"` with `scope: "global"` for each target project, merge. Client-side: filter nodes whose `content_preview` or `tags` match the keyword.

- [ ] **Step 1: Replace App.tsx**

```tsx
import { useState, useEffect, useCallback, useRef } from "react";
import { fetchSubgraph, fetchFacets } from "./api/client";
import type { GraphNode, GraphEdge, FacetProject, SubgraphResponse } from "./types";
import TopBar from "./components/TopBar";
import BrainGraph from "./components/BrainGraph";
import MemoryDetail from "./components/MemoryDetail";
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
      n.project.toLowerCase().includes(lower)
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
  const projectsRef = useRef<FacetProject[]>([]);

  const loadGraph = useCallback(
    async (selected: Set<string>, projectList?: FacetProject[]) => {
      const available = projectList || projectsRef.current;
      setLoading(true);
      setError(null);
      try {
        // Determine which projects to fetch
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

  // Apply client-side keyword filter on top of loaded data
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
      />
      <div className={styles.main}>
        {loading ? (
          <div className={styles.loading}>Loading brain...</div>
        ) : error ? (
          <div className={styles.error}>
            <span>{error}</span>
            <button
              className={styles.retryBtn}
              onClick={() => loadGraph(selectedProjects)}
            >
              Retry
            </button>
          </div>
        ) : (
          <BrainGraph
            nodes={nodes}
            edges={edges}
            projectList={projectList}
            selectedProject={selectedProjects.size === 1 ? [...selectedProjects][0] : null}
            onNodeClick={setSelectedNode}
            onBackgroundClick={() => setSelectedNode(null)}
          />
        )}
        {selectedNode && (
          <MemoryDetail
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add brain-ui/src/App.tsx
git commit -m "feat(ui): load all projects in global view, multi-select support, keyword filter"
```

---

### Task 5: Verify in browser

- [ ] **Step 1: Start dev server**

```bash
cd brain-ui && npm run dev
```

- [ ] **Step 2: Manual verification checklist**

Open http://localhost:5173 and verify:

1. **All Projects view:** Should show ALL nodes from every project with cross-project bridge edges (dashed lines)
2. **Multi-select:** Click CLIMARISK → shows only CLIMARISK nodes. Click REFFECT too → shows both with bridges. Click "All Projects" → back to all.
3. **Keyword filter:** Type "influxdb" → only nodes with influxdb in content/tags remain. Type "docker" → filters to docker-related nodes. Clear → all nodes return.
4. **Combined:** Select REFFECT + type "mqtt" → only REFFECT nodes mentioning mqtt.
5. **Project ring colors** still show in multi-project views.

- [ ] **Step 3: Commit any fixes if needed**
