import cytoscape, { type Core } from "cytoscape";
import fcose from "cytoscape-fcose";
import {
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
} from "react";

import { fetchGraphMetrics, fetchGraphSubgraph, fetchMemoryDetail } from "./api";
import {
  buildCytoscapeElements,
  buildSubgraphRequest,
  shouldPauseAutoRefresh,
} from "./graph";
import type {
  GraphControlsState,
  GraphMetrics,
  GraphSubgraphResponse,
  MemoryDetailResponse,
} from "./types";

cytoscape.use(fcose);

const DEFAULT_CONTROLS: GraphControlsState = {
  project: "ai-memory",
  mode: "project_hot",
  query: "event sourcing replay audit trail rebuild projections",
  scope: "project",
  memoryType: "",
  tagsInput: "",
  nodeLimit: 32,
  edgeLimit: 96,
  includeInactive: false,
  centerMemoryId: "",
};

const INTERACTION_COOLDOWN_MS = 8000;

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "never";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function MetricCard(props: {
  label: string;
  value: string | number;
  accent: "teal" | "sun" | "ember" | "slate";
}) {
  return (
    <div className={`metric-card metric-card--${props.accent}`}>
      <span className="metric-card__label">{props.label}</span>
      <strong className="metric-card__value">{props.value}</strong>
    </div>
  );
}

function App() {
  const [controls, setControls] = useState<GraphControlsState>(DEFAULT_CONTROLS);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);

  const [graphData, setGraphData] = useState<GraphSubgraphResponse | null>(null);
  const [graphError, setGraphError] = useState<string>("");
  const [graphLoading, setGraphLoading] = useState(false);

  const [metrics, setMetrics] = useState<GraphMetrics | null>(null);
  const [metricsError, setMetricsError] = useState<string>("");

  const [selectedMemoryId, setSelectedMemoryId] = useState("");
  const [detail, setDetail] = useState<MemoryDetailResponse | null>(null);
  const [detailError, setDetailError] = useState<string>("");

  const [isInteracting, setIsInteracting] = useState(false);
  const [lastInteractionAt, setLastInteractionAt] = useState<number | null>(null);

  const graphRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const interactionTimeoutRef = useRef<number | null>(null);

  const deferredQuery = useDeferredValue(controls.query);
  const graphRefreshPaused = shouldPauseAutoRefresh(
    isInteracting,
    lastInteractionAt,
    Date.now(),
    INTERACTION_COOLDOWN_MS,
  );

  function patchControls<K extends keyof GraphControlsState>(
    key: K,
    value: GraphControlsState[K],
  ) {
    setControls((current) => ({ ...current, [key]: value }));
  }

  function markInteraction() {
    const now = Date.now();
    setLastInteractionAt(now);
    setIsInteracting(true);
    if (interactionTimeoutRef.current !== null) {
      window.clearTimeout(interactionTimeoutRef.current);
    }
    interactionTimeoutRef.current = window.setTimeout(() => {
      setIsInteracting(false);
    }, INTERACTION_COOLDOWN_MS);
  }

  function refreshNow() {
    setReloadToken((value) => value + 1);
  }

  useEffect(() => {
    return () => {
      if (interactionTimeoutRef.current !== null) {
        window.clearTimeout(interactionTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!graphRef.current) {
      return undefined;
    }

    const cy = cytoscape({
      container: graphRef.current,
      elements: [],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 11,
            "font-family": "Space Grotesk, Segoe UI, sans-serif",
            color: "#f8f5ec",
            "text-wrap": "wrap",
            "text-max-width": 120,
            "text-valign": "center",
            "text-halign": "center",
            width: "mapData(size, 0.05, 1, 24, 78)",
            height: "mapData(size, 0.05, 1, 24, 78)",
            "border-width": 1.5,
            "border-color": "#f6f2e8",
            "background-color": "#2b6d7f",
            "overlay-opacity": 0,
            "text-outline-width": "2",
            "text-outline-color": "#0f1f26",
          },
        },
        {
          selector: "node.manual-pin",
          style: {
            shape: "round-rectangle",
            "background-color": "#c96f2d",
            "border-width": 2.2,
          },
        },
        {
          selector: "node.selected-node",
          style: {
            "border-color": "#ffe57a",
            "border-width": "3.5",
            "shadow-color": "#ffe57a",
            "shadow-opacity": "0.38",
            "shadow-blur": "16",
          },
        },
        {
          selector: "node.type-decision",
          style: { "background-color": "#406e8e" },
        },
        {
          selector: "node.type-error",
          style: { "background-color": "#8d3f2f" },
        },
        {
          selector: "node.type-architecture",
          style: { "background-color": "#1f6f64" },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(weight, 0, 1, 1.2, 6.5)",
            "line-color": "#f2d0a4",
            "target-arrow-color": "#f2d0a4",
            "curve-style": "bezier",
            opacity: "mapData(weight, 0, 1, 0.18, 0.95)",
            label: "data(label)",
            "font-size": 8,
            color: "#d9d0c0",
            "text-background-opacity": 1,
            "text-background-color": "#111d22",
            "text-background-padding": 2,
          },
        },
        {
          selector: "edge.manual-edge",
          style: {
            "line-style": "solid",
            "line-color": "#ffd166",
            "target-arrow-color": "#ffd166",
          },
        },
        {
          selector: "edge.inactive-edge",
          style: {
            "line-style": "dashed",
            opacity: "0.22",
          },
        },
      ] as any,
    });

    const onNodeTap = (event: cytoscape.EventObject) => {
      const memoryId = String(event.target.data("memoryId") ?? "");
      if (!memoryId) {
        return;
      }
      markInteraction();
      startTransition(() => {
        setSelectedMemoryId(memoryId);
      });
    };

    cy.on("tap", "node", onNodeTap);
    cy.on("dragfree", markInteraction);
    cy.on("grab", markInteraction);
    cy.on("pan", markInteraction);
    cy.on("zoom", markInteraction);
    cy.on("layoutstart", markInteraction);

    const currentContainer = graphRef.current;
    const onPointerDown = () => markInteraction();
    const onWheel = () => markInteraction();
    currentContainer.addEventListener("pointerdown", onPointerDown);
    currentContainer.addEventListener("wheel", onWheel, { passive: true });

    cyRef.current = cy;

    return () => {
      currentContainer.removeEventListener("pointerdown", onPointerDown);
      currentContainer.removeEventListener("wheel", onWheel);
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!cyRef.current) {
      return;
    }
    const cy = cyRef.current;
    const elements = buildCytoscapeElements(graphData, selectedMemoryId);
    cy.elements().remove();
    if (!elements.length) {
      return;
    }
    cy.add(elements);
    cy.layout({
      name: "fcose",
      animate: true,
      animationDuration: 380,
      fit: true,
      padding: 42,
      idealEdgeLength: 150,
      nodeRepulsion: 4200,
      gravity: 0.18,
    } as any).run();
  }, [graphData, selectedMemoryId]);

  useEffect(() => {
    const project = controls.project.trim();
    if (!project) {
      setMetrics(null);
      return undefined;
    }

    let active = true;
    const loadMetrics = async () => {
      try {
        const response = await fetchGraphMetrics(project);
        if (!active) {
          return;
        }
        setMetrics(response);
        setMetricsError("");
      } catch (error) {
        if (!active) {
          return;
        }
        setMetricsError(error instanceof Error ? error.message : "Could not load metrics");
      }
    };

    void loadMetrics();
    if (!autoRefresh) {
      return () => {
        active = false;
      };
    }
    const intervalId = window.setInterval(loadMetrics, 5000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [controls.project, autoRefresh, reloadToken]);

  useEffect(() => {
    const canLoadSearch = controls.mode !== "search" || Boolean(deferredQuery.trim());
    const centerMemoryId = controls.centerMemoryId.trim() || selectedMemoryId.trim();
    const canLoadFocus = controls.mode !== "memory_focus" || Boolean(centerMemoryId);
    const canLoadProjectScoped =
      controls.mode === "memory_focus" || Boolean(controls.project.trim());

    if (!canLoadSearch || !canLoadFocus || !canLoadProjectScoped) {
      setGraphData(null);
      return undefined;
    }

    let active = true;
    const loadGraph = async () => {
      setGraphLoading(true);
      const payload = buildSubgraphRequest(
        { ...controls, query: deferredQuery },
        selectedMemoryId,
      );
      try {
        const response = await fetchGraphSubgraph(payload);
        if (!active) {
          return;
        }
        startTransition(() => {
          setGraphData(response);
          setSelectedMemoryId((current) => {
            if (current && response.nodes.some((node) => node.memory_id === current)) {
              return current;
            }
            return response.nodes[0]?.memory_id ?? "";
          });
        });
        setGraphError("");
      } catch (error) {
        if (!active) {
          return;
        }
        setGraphError(error instanceof Error ? error.message : "Could not load subgraph");
      } finally {
        if (active) {
          setGraphLoading(false);
        }
      }
    };

    void loadGraph();
    if (!autoRefresh) {
      return () => {
        active = false;
      };
    }
    const intervalId = window.setInterval(() => {
      if (!shouldPauseAutoRefresh(isInteracting, lastInteractionAt, Date.now(), INTERACTION_COOLDOWN_MS)) {
        void loadGraph();
      }
    }, 10000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [
    controls,
    deferredQuery,
    autoRefresh,
    isInteracting,
    lastInteractionAt,
    reloadToken,
    selectedMemoryId,
  ]);

  useEffect(() => {
    if (!selectedMemoryId) {
      setDetail(null);
      return undefined;
    }
    let active = true;
    const loadDetail = async () => {
      try {
        const response = await fetchMemoryDetail(selectedMemoryId);
        if (!active) {
          return;
        }
        setDetail(response);
        setDetailError("");
      } catch (error) {
        if (!active) {
          return;
        }
        setDetailError(error instanceof Error ? error.message : "Could not load memory detail");
      }
    };
    void loadDetail();
    return () => {
      active = false;
    };
  }, [selectedMemoryId]);

  const activeProject = controls.project.trim();

  function onNumberInput(
    key: "nodeLimit" | "edgeLimit",
    event: ChangeEvent<HTMLInputElement>,
  ) {
    patchControls(key, Number(event.target.value));
  }

  return (
    <div className="app-shell">
      <header className="hero-panel">
        <div>
          <p className="eyebrow">AI Memory Brain</p>
          <h1>Observable plastic graph</h1>
          <p className="hero-copy">
            Watch the brain as a bounded graph of memories and relations. The UI never loads the
            whole universe, only the active subgraph that matters right now.
          </p>
        </div>
        <div className="hero-panel__status">
          <span className={`status-pill ${graphRefreshPaused ? "status-pill--paused" : ""}`}>
            {graphRefreshPaused ? "graph refresh paused" : "graph refresh live"}
          </span>
          <span className="status-pill status-pill--quiet">
            {graphLoading ? "loading graph" : "graph ready"}
          </span>
          <button className="ghost-button" onClick={refreshNow} type="button">
            refresh now
          </button>
        </div>
      </header>

      <section className="control-panel">
        <div className="control-grid">
          <label className="control-field">
            <span>Project</span>
            <input
              value={controls.project}
              onChange={(event) => patchControls("project", event.target.value)}
              placeholder="ai-memory"
            />
          </label>

          <label className="control-field">
            <span>Mode</span>
            <select
              value={controls.mode}
              onChange={(event) => patchControls("mode", event.target.value as GraphControlsState["mode"])}
            >
              <option value="project_hot">project_hot</option>
              <option value="search">search</option>
              <option value="memory_focus">memory_focus</option>
            </select>
          </label>

          <label className="control-field">
            <span>Scope</span>
            <select
              value={controls.scope}
              onChange={(event) => patchControls("scope", event.target.value as GraphControlsState["scope"])}
            >
              <option value="project">project</option>
              <option value="bridged">bridged</option>
              <option value="global">global</option>
            </select>
          </label>

          <label className="control-field">
            <span>Memory type</span>
            <input
              value={controls.memoryType}
              onChange={(event) => patchControls("memoryType", event.target.value)}
              placeholder="architecture"
            />
          </label>

          <label className="control-field control-field--wide">
            <span>Tags</span>
            <input
              value={controls.tagsInput}
              onChange={(event) => patchControls("tagsInput", event.target.value)}
              placeholder="concept/event-sourcing,pattern/replay"
            />
          </label>

          <label className="control-field control-field--wide">
            <span>Search query</span>
            <input
              value={controls.query}
              onChange={(event) => patchControls("query", event.target.value)}
              placeholder="event sourcing replay audit trail rebuild projections"
            />
          </label>

          <label className="control-field control-field--wide">
            <span>Center memory</span>
            <input
              value={controls.centerMemoryId}
              onChange={(event) => patchControls("centerMemoryId", event.target.value)}
              placeholder={selectedMemoryId || "click a node to focus it"}
            />
          </label>

          <label className="control-field">
            <span>Node limit</span>
            <input
              type="number"
              min={1}
              max={80}
              value={controls.nodeLimit}
              onChange={(event) => onNumberInput("nodeLimit", event)}
            />
          </label>

          <label className="control-field">
            <span>Edge limit</span>
            <input
              type="number"
              min={1}
              max={200}
              value={controls.edgeLimit}
              onChange={(event) => onNumberInput("edgeLimit", event)}
            />
          </label>
        </div>

        <div className="control-panel__actions">
          <label className="toggle">
            <input
              checked={controls.includeInactive}
              onChange={(event) => patchControls("includeInactive", event.target.checked)}
              type="checkbox"
            />
            <span>include inactive edges</span>
          </label>
          <label className="toggle">
            <input
              checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)}
              type="checkbox"
            />
            <span>auto refresh</span>
          </label>
          <button
            className="focus-button"
            onClick={() => {
              if (!selectedMemoryId) {
                return;
              }
              patchControls("mode", "memory_focus");
              patchControls("centerMemoryId", selectedMemoryId);
              refreshNow();
            }}
            type="button"
          >
            focus selected memory
          </button>
        </div>
      </section>

      <section className="metrics-strip">
        <MetricCard
          label="memories"
          value={metrics?.memory_count ?? "—"}
          accent="teal"
        />
        <MetricCard
          label="active relations"
          value={metrics?.active_relation_count ?? "—"}
          accent="sun"
        />
        <MetricCard
          label="pinned"
          value={metrics?.pinned_memory_count ?? "—"}
          accent="ember"
        />
        <MetricCard
          label="hot cluster"
          value={metrics?.hot_memory_count ?? "—"}
          accent="slate"
        />
      </section>

      <section className="workspace">
        <article className="graph-card">
          <div className="card-header">
            <div>
              <p className="eyebrow">Subgraph</p>
              <h2>{activeProject || "Select a project"}</h2>
            </div>
            <div className="summary-meta">
              <span>{graphData?.summary.node_count ?? 0} nodes</span>
              <span>{graphData?.summary.edge_count ?? 0} edges</span>
              <span>{graphData?.summary.mode ?? controls.mode}</span>
            </div>
          </div>

          <div className="card-banner">
            <span>
              allowed projects: {graphData?.summary.allowed_projects.join(", ") || "none"}
            </span>
            <span>
              {graphRefreshPaused
                ? "interaction freeze active"
                : autoRefresh
                  ? "polling every 10s"
                  : "manual refresh"}
            </span>
          </div>

          <div className="graph-canvas" ref={graphRef} />

          {graphError ? <p className="error-line">{graphError}</p> : null}
          {metricsError ? <p className="error-line">{metricsError}</p> : null}
        </article>

        <aside className="side-panel">
          <section className="detail-card">
            <div className="card-header">
              <div>
                <p className="eyebrow">Memory detail</p>
                <h2>{detail?.memory.memory_type ?? "No selection"}</h2>
              </div>
              <span className="mono-chip">
                {detail?.memory.prominence?.toFixed(2) ?? "0.00"} prominence
              </span>
            </div>

            {detail ? (
              <>
                <p className="detail-copy">{detail.memory.content || detail.memory.summary}</p>
                <div className="tag-row">
                  {detail.memory.tags.map((tag) => (
                    <span className="tag-chip" key={tag}>
                      {tag}
                    </span>
                  ))}
                </div>
                <dl className="detail-grid">
                  <div>
                    <dt>project</dt>
                    <dd>{detail.memory.project || "unknown"}</dd>
                  </div>
                  <div>
                    <dt>accesses</dt>
                    <dd>{detail.memory.access_count}</dd>
                  </div>
                  <div>
                    <dt>activation</dt>
                    <dd>{detail.memory.activation_score.toFixed(3)}</dd>
                  </div>
                  <div>
                    <dt>stability</dt>
                    <dd>{detail.memory.stability_score.toFixed(3)}</dd>
                  </div>
                  <div>
                    <dt>manual pin</dt>
                    <dd>{detail.memory.manual_pin ? "yes" : "no"}</dd>
                  </div>
                  <div>
                    <dt>last seen</dt>
                    <dd>{formatTimestamp(detail.memory.last_accessed_at)}</dd>
                  </div>
                </dl>
              </>
            ) : (
              <p className="detail-copy">
                Click any node to inspect its content, relation list and plasticity markers.
              </p>
            )}
            {detailError ? <p className="error-line">{detailError}</p> : null}
          </section>

          <section className="detail-card">
            <div className="card-header">
              <div>
                <p className="eyebrow">Relations</p>
                <h2>{detail?.relation_count ?? 0} known links</h2>
              </div>
              <span className="mono-chip">
                {metrics?.avg_activation_score?.toFixed(2) ?? "0.00"} avg activation
              </span>
            </div>
            <div className="relation-list">
              {detail?.relations.length ? (
                detail.relations.map((relation) => (
                  <button
                    className="relation-row"
                    key={relation.id}
                    onClick={() => {
                      patchControls("mode", "memory_focus");
                      patchControls("centerMemoryId", relation.other_memory_id);
                      startTransition(() => {
                        setSelectedMemoryId(relation.other_memory_id);
                      });
                      refreshNow();
                    }}
                    type="button"
                  >
                    <span className="relation-row__headline">
                      {relation.relation_type.replace(/_/g, " ")} · {relation.weight.toFixed(2)}
                    </span>
                    <span className="relation-row__body">
                      {relation.other_summary || relation.other_memory_id}
                    </span>
                  </button>
                ))
              ) : (
                <p className="detail-copy">
                  No relations available for the current selection yet.
                </p>
              )}
            </div>
          </section>

          <section className="detail-card">
            <div className="card-header">
              <div>
                <p className="eyebrow">Type mix</p>
                <h2>Project pulse</h2>
              </div>
              <span className="mono-chip">{metrics?.bridge_count ?? 0} bridges</span>
            </div>
            <div className="type-list">
              {metrics?.top_memory_types.map((item) => (
                <div className="type-row" key={item.memory_type}>
                  <span>{item.memory_type}</span>
                  <strong>{item.count}</strong>
                </div>
              )) || <p className="detail-copy">Metrics will appear after the first successful load.</p>}
            </div>
          </section>
        </aside>
      </section>
    </div>
  );
}

export default App;
