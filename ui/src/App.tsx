import cytoscape, { type Core } from "cytoscape";
import fcose from "cytoscape-fcose";
import { AnimatePresence, motion } from "framer-motion";
import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from "react";

import {
  fetchGraphFacets,
  fetchGraphMetrics,
  fetchGraphSubgraph,
  fetchMemoryDetail,
} from "./api";
import {
  buildCytoscapeElements,
  buildProjectRegions,
  buildSubgraphRequest,
  shouldPauseAutoRefresh,
} from "./graph";
import type {
  BrainViewState,
  GraphControlsState,
  GraphFacets,
  GraphMetrics,
  GraphSubgraphResponse,
  MemoryDetailResponse,
} from "./types";

cytoscape.use(fcose);

const DEFAULT_CONTROLS: GraphControlsState = {
  project: "",
  mode: "project_hot",
  query: "",
  scope: "project",
  memoryType: "",
  tagsInput: "",
  nodeLimit: 24,
  edgeLimit: 72,
  includeInactive: false,
  centerMemoryId: "",
};

const DEFAULT_VIEW_STATE: BrainViewState = {
  dockOpen: true,
  hudOpen: true,
  railOpen: true,
  drawerOpen: false,
};

const INTERACTION_COOLDOWN_MS = 8000;

type HoveredNodeState = {
  memoryId: string;
  label: string;
  project: string;
  memoryType: string;
  x: number;
  y: number;
};

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "sin actividad reciente";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function formatRatio(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(2);
}

function MetricBadge(props: {
  label: string;
  value: string | number;
  accent?: "teal" | "gold" | "blue" | "rose";
}) {
  return (
    <div className={`metric-badge metric-badge--${props.accent ?? "teal"}`}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function App() {
  const [controls, setControls] = useState<GraphControlsState>(DEFAULT_CONTROLS);
  const [viewState, setViewState] = useState<BrainViewState>(DEFAULT_VIEW_STATE);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);

  const [graphData, setGraphData] = useState<GraphSubgraphResponse | null>(null);
  const [graphError, setGraphError] = useState("");
  const [graphLoading, setGraphLoading] = useState(false);

  const [metrics, setMetrics] = useState<GraphMetrics | null>(null);
  const [metricsError, setMetricsError] = useState("");

  const [facets, setFacets] = useState<GraphFacets | null>(null);
  const [facetsError, setFacetsError] = useState("");

  const [selectedMemoryId, setSelectedMemoryId] = useState("");
  const [detail, setDetail] = useState<MemoryDetailResponse | null>(null);
  const [detailError, setDetailError] = useState("");

  const [hoveredMemoryId, setHoveredMemoryId] = useState("");
  const [hoveredNode, setHoveredNode] = useState<HoveredNodeState | null>(null);

  const [isInteracting, setIsInteracting] = useState(false);
  const [lastInteractionAt, setLastInteractionAt] = useState<number | null>(null);

  const graphRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const interactionTimeoutRef = useRef<number | null>(null);
  const lastNodeTapRef = useRef<{ memoryId: string; at: number } | null>(null);

  const activeProject = controls.project.trim();
  const deferredQuery = useDeferredValue(controls.query);
  const selectedTag = controls.tagsInput.split(",")[0]?.trim() || "";
  const graphRefreshPaused = shouldPauseAutoRefresh(
    isInteracting,
    lastInteractionAt,
    Date.now(),
    INTERACTION_COOLDOWN_MS,
  );
  const projectRegions = useMemo(
    () => buildProjectRegions(graphData, activeProject),
    [graphData, activeProject],
  );

  function patchControls<K extends keyof GraphControlsState>(
    key: K,
    value: GraphControlsState[K],
  ) {
    setControls((current) => ({ ...current, [key]: value }));
  }

  function patchViewState<K extends keyof BrainViewState>(key: K, value: BrainViewState[K]) {
    setViewState((current) => ({ ...current, [key]: value }));
  }

  function refreshNow() {
    setReloadToken((value) => value + 1);
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

  function closeDrawer() {
    patchViewState("drawerOpen", false);
  }

  function selectMemory(memoryId: string, openDrawer = true) {
    if (!memoryId) {
      return;
    }
    markInteraction();
    startTransition(() => {
      setSelectedMemoryId(memoryId);
    });
    if (openDrawer) {
      patchViewState("drawerOpen", true);
    }
  }

  function focusMemory(memoryId: string, project = "") {
    if (!memoryId) {
      return;
    }
    markInteraction();
    if (project) {
      patchControls("project", project);
    }
    patchControls("mode", "memory_focus");
    patchControls("centerMemoryId", memoryId);
    startTransition(() => {
      setSelectedMemoryId(memoryId);
    });
    patchViewState("drawerOpen", true);
    refreshNow();
  }

  function applyProjectFilter(project: string) {
    setControls((current) => ({
      ...current,
      project,
      mode: current.mode === "memory_focus" ? "project_hot" : current.mode,
      centerMemoryId: "",
    }));
    refreshNow();
  }

  function clearFilters() {
    setControls((current) => ({
      ...current,
      mode: "project_hot",
      scope: "project",
      memoryType: "",
      tagsInput: "",
      centerMemoryId: "",
      query: "",
    }));
    setSelectedMemoryId("");
    setHoveredMemoryId("");
    setHoveredNode(null);
    patchViewState("drawerOpen", false);
    refreshNow();
  }

  useEffect(() => {
    return () => {
      if (interactionTimeoutRef.current !== null) {
        window.clearTimeout(interactionTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        patchViewState("drawerOpen", false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
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
            "text-opacity": "data(labelOpacity)",
            "font-size": 11,
            "font-family": "Space Grotesk, Segoe UI, sans-serif",
            color: "#f4f7ff",
            "text-wrap": "wrap",
            "text-max-width": 150,
            "text-valign": "center",
            "text-halign": "center",
            width: "mapData(size, 0.08, 1, 18, 76)",
            height: "mapData(size, 0.08, 1, 18, 76)",
            "border-width": "data(borderWidth)",
            "border-color": "data(borderColor)",
            "background-color": "data(fillColor)",
            "background-opacity": "data(nodeOpacity)",
            "overlay-opacity": 0,
            "shadow-color": "data(projectColor)",
            "shadow-opacity": "data(glowOpacity)",
            "shadow-blur": "data(glowBlur)",
          },
        },
        {
          selector: "node.hovered-node",
          style: {
            "text-opacity": 1,
            "border-width": 3.6,
            "shadow-opacity": 0.9,
            "shadow-blur": 42,
          },
        },
        {
          selector: "node.selected-node",
          style: {
            "text-opacity": 1,
            "border-width": 4.4,
            "shadow-opacity": 0.95,
            "shadow-blur": 52,
          },
        },
        {
          selector: "node.manual-pin",
          style: {
            "border-color": "#ffd38b",
          },
        },
        {
          selector: "edge",
          style: {
            width: "data(edgeWidth)",
            "line-color": "data(edgeColor)",
            "target-arrow-color": "data(edgeColor)",
            "curve-style": "bezier",
            opacity: "data(edgeOpacity)",
          },
        },
        {
          selector: "edge.manual-edge",
          style: {
            width: "data(edgeWidth)",
          },
        },
        {
          selector: "edge.dashed-edge",
          style: {
            "line-style": "dashed",
          },
        },
        {
          selector: "edge.inactive-edge",
          style: {
            opacity: "data(edgeOpacity)",
          },
        },
      ] as never,
    });

    const onNodeTap = (event: cytoscape.EventObject) => {
      const memoryId = String(event.target.data("memoryId") ?? "");
      const project = String(event.target.data("project") ?? "");
      if (!memoryId) {
        return;
      }
      const now = Date.now();
      const isDoubleTap =
        lastNodeTapRef.current?.memoryId === memoryId &&
        now - lastNodeTapRef.current.at < 300;
      lastNodeTapRef.current = { memoryId, at: now };

      if (isDoubleTap) {
        focusMemory(memoryId, project);
        return;
      }
      selectMemory(memoryId, true);
    };

    const onNodeOver = (event: cytoscape.EventObject) => {
      const memoryId = String(event.target.data("memoryId") ?? "");
      if (!memoryId) {
        return;
      }
      const renderedPosition =
        "renderedPosition" in event && event.renderedPosition
          ? event.renderedPosition
          : { x: 0, y: 0 };
      setHoveredMemoryId(memoryId);
      setHoveredNode({
        memoryId,
        label: String(event.target.data("label") ?? ""),
        project: String(event.target.data("project") ?? ""),
        memoryType: String(event.target.data("memoryType") ?? "general"),
        x: renderedPosition.x,
        y: renderedPosition.y,
      });
    };

    const onNodeOut = () => {
      setHoveredMemoryId("");
      setHoveredNode(null);
    };

    const onCanvasInteraction = () => {
      markInteraction();
      setHoveredNode(null);
    };

    cy.on("tap", "node", onNodeTap);
    cy.on("mouseover", "node", onNodeOver);
    cy.on("mouseout", "node", onNodeOut);
    cy.on("dragfree", onCanvasInteraction);
    cy.on("grab", onCanvasInteraction);
    cy.on("pan", onCanvasInteraction);
    cy.on("zoom", onCanvasInteraction);
    cy.on("layoutstart", onCanvasInteraction);

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
    const elements = buildCytoscapeElements(graphData, { projectRegions });
    cy.batch(() => {
      cy.elements().remove();
      if (elements.length) {
        cy.add(elements);
      }
    });

    if (!elements.length) {
      return;
    }

    cy.layout({
      name: "preset",
      fit: false,
    } as never).run();

    cy.layout({
      name: "fcose",
      animate: true,
      animationDuration: 420,
      fit: true,
      randomize: false,
      padding: 70,
      idealEdgeLength: 136,
      nodeRepulsion: 9800,
      gravity: 0.08,
      quality: "default",
    } as never).run();
  }, [graphData, projectRegions]);

  useEffect(() => {
    if (!cyRef.current) {
      return;
    }
    const cy = cyRef.current;
    cy.nodes().removeClass("selected-node");
    if (!selectedMemoryId) {
      return;
    }
    const node = cy.$id(selectedMemoryId);
    if (typeof node.addClass === "function") {
      node.addClass("selected-node");
      if (typeof cy.animate === "function") {
        cy.animate({ center: { eles: node }, duration: 260 });
      }
    }
  }, [selectedMemoryId]);

  useEffect(() => {
    if (!cyRef.current) {
      return;
    }
    const cy = cyRef.current;
    cy.nodes().removeClass("hovered-node");
    if (!hoveredMemoryId) {
      return;
    }
    const node = cy.$id(hoveredMemoryId);
    if (typeof node.addClass === "function") {
      node.addClass("hovered-node");
    }
  }, [hoveredMemoryId]);

  useEffect(() => {
    let active = true;
    const loadFacets = async () => {
      try {
        const response = await fetchGraphFacets(activeProject || undefined);
        if (!active) {
          return;
        }
        setFacets(response);
        setFacetsError("");
      } catch (error) {
        if (!active) {
          return;
        }
        setFacetsError(
          error instanceof Error ? error.message : "No pude leer las claves del cerebro",
        );
      }
    };

    void loadFacets();
    if (!autoRefresh) {
      return () => {
        active = false;
      };
    }
    const intervalId = window.setInterval(loadFacets, 15000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [activeProject, autoRefresh, reloadToken]);

  useEffect(() => {
    if (controls.project.trim() || !facets?.projects.length) {
      return;
    }
    patchControls("project", facets.projects[0].project);
  }, [controls.project, facets]);

  useEffect(() => {
    if (controls.mode !== "memory_focus" || controls.centerMemoryId.trim() || selectedMemoryId) {
      return;
    }
    const fallbackMemory = facets?.hot_memories[0]?.memory_id;
    if (fallbackMemory) {
      patchControls("centerMemoryId", fallbackMemory);
    }
  }, [controls.mode, controls.centerMemoryId, selectedMemoryId, facets]);

  useEffect(() => {
    let active = true;
    const loadMetrics = async () => {
      try {
        const response = await fetchGraphMetrics(activeProject);
        if (!active) {
          return;
        }
        setMetrics(response);
        setMetricsError("");
      } catch (error) {
        if (!active) {
          return;
        }
        setMetricsError(error instanceof Error ? error.message : "No pude calcular métricas");
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
  }, [activeProject, autoRefresh, reloadToken]);

  useEffect(() => {
    const focusMemoryId = controls.centerMemoryId.trim() || selectedMemoryId.trim();
    const canLoadSearch = controls.mode !== "search" || Boolean(deferredQuery.trim());
    const canLoadFocus = controls.mode !== "memory_focus" || Boolean(focusMemoryId);
    const canLoadGraph =
      (controls.mode === "memory_focus" && canLoadFocus) ||
      (controls.mode !== "memory_focus" && Boolean(activeProject) && canLoadSearch);

    if (!canLoadGraph) {
      setGraphData(null);
      setGraphError("");
      return undefined;
    }

    let active = true;
    const loadGraph = async () => {
      setGraphLoading(true);
      try {
        const response = await fetchGraphSubgraph(
          buildSubgraphRequest({ ...controls, query: deferredQuery }, selectedMemoryId),
        );
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
        if (!response.nodes.length) {
          patchViewState("drawerOpen", false);
        }
        setGraphError("");
      } catch (error) {
        if (!active) {
          return;
        }
        setGraphError(error instanceof Error ? error.message : "No pude cargar el subgrafo");
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
      if (
        !shouldPauseAutoRefresh(
          isInteracting,
          lastInteractionAt,
          Date.now(),
          INTERACTION_COOLDOWN_MS,
        )
      ) {
        void loadGraph();
      }
    }, 10000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [
    controls,
    activeProject,
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
      setDetailError("");
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
        setDetailError(error instanceof Error ? error.message : "No pude abrir esta memoria");
      }
    };
    void loadDetail();
    return () => {
      active = false;
    };
  }, [selectedMemoryId]);

  function onNumberInput(key: "nodeLimit" | "edgeLimit", event: ChangeEvent<HTMLInputElement>) {
    patchControls(key, Number(event.target.value));
  }

  const projects = facets?.projects ?? [];
  const memoryTypes = facets?.memory_types ?? [];
  const topTags = facets?.top_tags ?? [];
  const hotMemories = facets?.hot_memories ?? [];
  const graphHasNodes = Boolean(graphData?.nodes.length);
  const compactRegionLabels = projectRegions.length > 7;

  return (
    <div className="brain-app">
      <div className="brain-shell">
        <div className="brain-panel-switches">
          <button
            className="panel-toggle"
            onClick={() => patchViewState("dockOpen", !viewState.dockOpen)}
            type="button"
          >
            Filtros
          </button>
          <button
            className="panel-toggle"
            onClick={() => patchViewState("hudOpen", !viewState.hudOpen)}
            type="button"
          >
            HUD
          </button>
          <button
            className="panel-toggle"
            onClick={() => patchViewState("railOpen", !viewState.railOpen)}
            type="button"
          >
            Rail
          </button>
        </div>

        <motion.section
          animate={{ opacity: 1, y: 0 }}
          className="brain-stage"
          initial={{ opacity: 0, y: 20 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="brain-stage__glow brain-stage__glow--left" />
          <div className="brain-stage__glow brain-stage__glow--right" />
          <div className="brain-silhouette" />

          <div className="brain-regions">
            {projectRegions.map((region, index) => {
              const shouldShowLabel =
                !compactRegionLabels || region.project === activeProject || index < 6;
              const diameter = Math.min(220, 120 + region.nodeCount * 14);
              return (
                <div
                  className={`brain-region ${region.project === activeProject ? "brain-region--active" : ""}`}
                  key={region.project}
                  style={{
                    left: `${region.x * 100}%`,
                    top: `${region.y * 100}%`,
                    width: `${diameter}px`,
                    height: `${diameter}px`,
                    background: `radial-gradient(circle, ${region.color}22 0%, ${region.color}0f 44%, transparent 74%)`,
                    boxShadow: `0 0 56px ${region.color}22`,
                  }}
                >
                  {shouldShowLabel ? (
                    <button
                      className="brain-region__label"
                      onClick={() => applyProjectFilter(region.project)}
                      type="button"
                    >
                      <span>{region.label}</span>
                      <small>{region.nodeCount} neuronas</small>
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>

          <div className="brain-canvas-shell">
            <div className="brain-stage__meta">
              <div>
                <p className="brain-kicker">AI MEMORY BRAIN</p>
                <h1>Cerebro navegable</h1>
                <p className="brain-copy">
                  El workspace prioriza recorrido visual, foco rápido y lectura del estado vivo de
                  tus memorias.
                </p>
              </div>
              <div className="brain-status">
                <span>{graphHasNodes ? `${graphData?.summary.node_count ?? 0} neuronas` : "sin neuronas visibles"}</span>
                <span>
                  {graphRefreshPaused
                    ? "refresco pausado mientras navegas"
                    : autoRefresh
                      ? "auto-refresh cada 10s"
                      : "refresco manual"}
                </span>
              </div>
            </div>

            {graphLoading ? <div className="brain-loading" /> : null}
            {graphError ? <p className="brain-notice brain-notice--danger">{graphError}</p> : null}
            {metricsError ? <p className="brain-notice brain-notice--warning">{metricsError}</p> : null}
            {facetsError ? <p className="brain-notice brain-notice--warning">{facetsError}</p> : null}

            {graphHasNodes ? (
              <div className="brain-canvas" ref={graphRef} />
            ) : (
              <div className="brain-empty">
                <strong>No hay neuronas para esta combinación.</strong>
                <p>
                  Cambia de proyecto, amplía el alcance o limpia filtros para reabrir el cerebro.
                </p>
                <div className="brain-empty__actions">
                  <button className="ghost-button" onClick={clearFilters} type="button">
                    Reiniciar lectura
                  </button>
                  {projects.slice(0, 3).map((item) => (
                    <button
                      className="ghost-button"
                      key={item.project}
                      onClick={() => applyProjectFilter(item.project)}
                      type="button"
                    >
                      Abrir {item.project}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="brain-legend">
              <span><i className="legend-dot legend-dot--warm" /> activación</span>
              <span><i className="legend-dot legend-dot--stable" /> estabilidad</span>
              <span><i className="legend-dot legend-dot--pin" /> neurona fijada</span>
              <span><i className="legend-dot legend-dot--inactive" /> enlace inactivo</span>
            </div>

            {hoveredNode ? (
              <div
                className="brain-tooltip"
                style={{
                  left: `clamp(16px, ${hoveredNode.x}px, calc(100% - 220px))`,
                  top: `clamp(16px, ${hoveredNode.y - 18}px, calc(100% - 120px))`,
                }}
              >
                <strong>{hoveredNode.label}</strong>
                <span>{hoveredNode.project}</span>
                <small>{hoveredNode.memoryType.replace(/_/g, " ")}</small>
              </div>
            ) : null}
          </div>

          <AnimatePresence>
            {viewState.dockOpen ? (
              <motion.section
                animate={{ opacity: 1, x: 0 }}
                aria-label="Dock de filtros"
                className="brain-dock"
                exit={{ opacity: 0, x: -20 }}
                initial={{ opacity: 0, x: -28 }}
                transition={{ duration: 0.28 }}
              >
                <div className="panel-header">
                  <div>
                    <p className="panel-kicker">Dock</p>
                    <h2>Filtros neuronales</h2>
                  </div>
                  <button
                    className="ghost-button ghost-button--small"
                    onClick={() => patchViewState("dockOpen", false)}
                    type="button"
                  >
                    Ocultar
                  </button>
                </div>

                <div className="dock-grid">
                  <label className="brain-field">
                    <span>Proyecto</span>
                    <select
                      value={controls.project}
                      onChange={(event) => applyProjectFilter(event.target.value)}
                    >
                      <option value="">Selecciona un proyecto</option>
                      {projects.map((item) => (
                        <option key={item.project} value={item.project}>
                          {item.project} · {item.memory_count}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="brain-field">
                    <span>Vista</span>
                    <select
                      value={controls.mode}
                      onChange={(event) =>
                        patchControls("mode", event.target.value as GraphControlsState["mode"])
                      }
                    >
                      <option value="project_hot">Proyecto activo</option>
                      <option value="search">Buscar ideas</option>
                      <option value="memory_focus">Memoria en foco</option>
                    </select>
                  </label>

                  <label className="brain-field">
                    <span>Alcance</span>
                    <select
                      value={controls.scope}
                      onChange={(event) =>
                        patchControls("scope", event.target.value as GraphControlsState["scope"])
                      }
                    >
                      <option value="project">Solo proyecto</option>
                      <option value="bridged">Proyectos conectados</option>
                      <option value="global">Global</option>
                    </select>
                  </label>

                  <label className="brain-field">
                    <span>Tipo</span>
                    <select
                      value={controls.memoryType}
                      onChange={(event) => patchControls("memoryType", event.target.value)}
                    >
                      <option value="">Todos</option>
                      {memoryTypes.map((item) => (
                        <option key={item.memory_type} value={item.memory_type}>
                          {item.memory_type} · {item.count}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="brain-field brain-field--wide">
                    <span>Búsqueda</span>
                    <input
                      placeholder={
                        controls.mode === "search"
                          ? "Describe la idea que quieres recuperar"
                          : "Disponible en modo Buscar ideas"
                      }
                      value={controls.query}
                      onChange={(event) => patchControls("query", event.target.value)}
                    />
                  </label>

                  <label className="brain-field">
                    <span>Etiqueta</span>
                    <select
                      value={selectedTag}
                      onChange={(event) => patchControls("tagsInput", event.target.value)}
                    >
                      <option value="">Sin etiqueta</option>
                      {topTags.map((item) => (
                        <option key={item.tag} value={item.tag}>
                          {item.tag} · {item.count}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="brain-field">
                    <span>Memoria focal</span>
                    <select
                      value={controls.centerMemoryId}
                      onChange={(event) => patchControls("centerMemoryId", event.target.value)}
                    >
                      <option value="">Elegir memoria caliente</option>
                      {hotMemories.map((item) => (
                        <option key={item.memory_id} value={item.memory_id}>
                          {item.content_preview}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="brain-field">
                    <span>Nodos</span>
                    <input
                      max={80}
                      min={1}
                      type="number"
                      value={controls.nodeLimit}
                      onChange={(event) => onNumberInput("nodeLimit", event)}
                    />
                  </label>

                  <label className="brain-field">
                    <span>Enlaces</span>
                    <input
                      max={200}
                      min={1}
                      type="number"
                      value={controls.edgeLimit}
                      onChange={(event) => onNumberInput("edgeLimit", event)}
                    />
                  </label>
                </div>

                <div className="dock-switches">
                  <label className="brain-toggle">
                    <input
                      checked={controls.includeInactive}
                      onChange={(event) => patchControls("includeInactive", event.target.checked)}
                      type="checkbox"
                    />
                    <span>Incluir enlaces inactivos</span>
                  </label>
                  <label className="brain-toggle">
                    <input
                      checked={autoRefresh}
                      onChange={(event) => setAutoRefresh(event.target.checked)}
                      type="checkbox"
                    />
                    <span>Auto-refresh</span>
                  </label>
                </div>

                <div className="dock-actions">
                  <button className="primary-button" onClick={refreshNow} type="button">
                    Actualizar ahora
                  </button>
                  <button
                    className="ghost-button"
                    onClick={() => focusMemory(controls.centerMemoryId || selectedMemoryId)}
                    type="button"
                  >
                    Centrar selección
                  </button>
                  <button className="ghost-button" onClick={clearFilters} type="button">
                    Limpiar
                  </button>
                </div>

                <div className="dock-clusters">
                  <div>
                    <span className="dock-label">Proyectos vivos</span>
                    <div className="chip-row">
                      {projects.slice(0, 6).map((item) => (
                        <button
                          className={`brain-chip ${controls.project === item.project ? "brain-chip--active" : ""}`}
                          key={item.project}
                          onClick={() => applyProjectFilter(item.project)}
                          type="button"
                        >
                          {item.project}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="dock-label">Etiquetas densas</span>
                    <div className="chip-row">
                      {topTags.slice(0, 8).map((item) => (
                        <button
                          className={`brain-chip ${selectedTag === item.tag ? "brain-chip--active" : ""}`}
                          key={item.tag}
                          onClick={() => patchControls("tagsInput", item.tag)}
                          type="button"
                        >
                          {item.tag}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.section>
            ) : null}
          </AnimatePresence>

          <AnimatePresence>
            {viewState.hudOpen ? (
              <motion.aside
                animate={{ opacity: 1, x: 0 }}
                aria-label="HUD del cerebro"
                className="brain-hud"
                exit={{ opacity: 0, x: 20 }}
                initial={{ opacity: 0, x: 26 }}
                transition={{ duration: 0.28 }}
              >
                <div className="panel-header panel-header--tight">
                  <div>
                    <p className="panel-kicker">HUD</p>
                    <h2>Lectura rápida</h2>
                  </div>
                  <button
                    className="ghost-button ghost-button--small"
                    onClick={() => patchViewState("hudOpen", false)}
                    type="button"
                  >
                    Ocultar
                  </button>
                </div>

                <div className="hud-metrics">
                  <MetricBadge accent="teal" label="Memorias" value={metrics?.memory_count ?? "—"} />
                  <MetricBadge
                    accent="blue"
                    label="Relaciones activas"
                    value={metrics?.active_relation_count ?? "—"}
                  />
                  <MetricBadge accent="gold" label="Fijadas" value={metrics?.pinned_memory_count ?? "—"} />
                  <MetricBadge accent="rose" label="Cluster caliente" value={metrics?.hot_memory_count ?? "—"} />
                </div>

                <div className="hud-stack">
                  <div className="hud-card">
                    <span>Proyecto visible</span>
                    <strong>{activeProject || "sin fijar"}</strong>
                    <small>
                      {controls.scope === "global"
                        ? "visión global"
                        : controls.scope === "bridged"
                          ? "con puentes"
                          : "aislado por proyecto"}
                    </small>
                  </div>
                  <div className="hud-card">
                    <span>Actividad media</span>
                    <strong>{formatRatio(metrics?.avg_activation_score)}</strong>
                    <small>{metrics?.bridge_count ?? 0} puentes entre proyectos</small>
                  </div>
                  <div className="hud-card">
                    <span>Refresco</span>
                    <strong>{graphLoading ? "cargando" : "estable"}</strong>
                    <small>
                      {metrics?.generated_at
                        ? `métricas ${formatTimestamp(metrics.generated_at)}`
                        : "sin métrica reciente"}
                    </small>
                  </div>
                </div>
              </motion.aside>
            ) : null}
          </AnimatePresence>

          <AnimatePresence>
            {viewState.railOpen ? (
              <motion.section
                animate={{ opacity: 1, y: 0 }}
                aria-label="Rail de memorias calientes"
                className="brain-rail"
                exit={{ opacity: 0, y: 26 }}
                initial={{ opacity: 0, y: 28 }}
                transition={{ duration: 0.32 }}
              >
                <div className="panel-header panel-header--tight">
                  <div>
                    <p className="panel-kicker">Rail</p>
                    <h2>Memorias calientes</h2>
                  </div>
                  <button
                    className="ghost-button ghost-button--small"
                    onClick={() => patchViewState("railOpen", false)}
                    type="button"
                  >
                    Ocultar
                  </button>
                </div>

                <div className="rail-scroll">
                  {hotMemories.map((item) => (
                    <motion.button
                      className={`memory-card ${selectedMemoryId === item.memory_id ? "memory-card--active" : ""}`}
                      key={item.memory_id}
                      layout
                      onClick={() => selectMemory(item.memory_id)}
                      type="button"
                      whileHover={{ y: -4 }}
                    >
                      <span className="memory-card__project">{item.project || "Sin proyecto"}</span>
                      <strong>{item.content_preview}</strong>
                      <small>
                        {(item.memory_type || "general").replace(/_/g, " ")} ·{" "}
                        {item.prominence.toFixed(2)}
                      </small>
                      <span className="memory-card__tags">
                        {item.tags.slice(0, 2).map((tag) => (
                          <i key={tag}>{tag}</i>
                        ))}
                      </span>
                      <span className="memory-card__actions">
                        <span>abrir</span>
                        <span>centrar</span>
                      </span>
                    </motion.button>
                  ))}
                </div>
              </motion.section>
            ) : null}
          </AnimatePresence>

          <AnimatePresence>
            {viewState.drawerOpen ? (
              <motion.aside
                animate={{ opacity: 1, x: 0 }}
                aria-label="Detalle de neurona"
                className="brain-drawer"
                exit={{ opacity: 0, x: 36 }}
                initial={{ opacity: 0, x: 44 }}
                transition={{ duration: 0.3 }}
              >
                <div className="panel-header">
                  <div>
                    <p className="panel-kicker">Neurona</p>
                    <h2>
                      {detail?.memory.memory_type
                        ? detail.memory.memory_type.replace(/_/g, " ")
                        : "Sin selección"}
                    </h2>
                  </div>
                  <div className="drawer-actions">
                    <button
                      className="ghost-button ghost-button--small"
                      onClick={() => focusMemory(selectedMemoryId, detail?.memory.project ?? "")}
                      type="button"
                    >
                      Centrar neurona
                    </button>
                    <button
                      className="ghost-button ghost-button--small"
                      onClick={closeDrawer}
                      type="button"
                    >
                      Cerrar
                    </button>
                  </div>
                </div>

                {detail ? (
                  <>
                    <div className="drawer-summary">
                      <span className="drawer-pill">{detail.memory.project || "sin proyecto"}</span>
                      <span className="drawer-pill drawer-pill--muted">
                        {detail.memory.prominence.toFixed(2)} prominencia
                      </span>
                    </div>

                    <p className="drawer-title">{detail.memory.content_preview}</p>
                    <div className="drawer-body">
                      {detail.memory.content || detail.memory.summary || "Sin contenido ampliado."}
                    </div>

                    <div className="signal-grid">
                      <div className="signal-card">
                        <span>Accesos</span>
                        <strong>{detail.memory.access_count}</strong>
                        <small>frecuencia de consulta</small>
                      </div>
                      <div className="signal-card">
                        <span>Activación</span>
                        <strong>{detail.memory.activation_score.toFixed(3)}</strong>
                        <small>calor actual</small>
                      </div>
                      <div className="signal-card">
                        <span>Estabilidad</span>
                        <strong>{detail.memory.stability_score.toFixed(3)}</strong>
                        <small>persistencia</small>
                      </div>
                      <div className="signal-card">
                        <span>Último acceso</span>
                        <strong>{formatTimestamp(detail.memory.last_accessed_at)}</strong>
                        <small>fecha exacta en detalle</small>
                      </div>
                    </div>

                    <div className="drawer-section">
                      <div className="drawer-section__header">
                        <span>Filtros rápidos</span>
                      </div>
                      <div className="chip-row">
                        {detail.memory.project ? (
                          <button
                            className="brain-chip"
                            onClick={() => applyProjectFilter(detail.memory.project || "")}
                            type="button"
                          >
                            {detail.memory.project}
                          </button>
                        ) : null}
                        {detail.memory.memory_type ? (
                          <button
                            className="brain-chip"
                            onClick={() => patchControls("memoryType", detail.memory.memory_type || "")}
                            type="button"
                          >
                            {detail.memory.memory_type.replace(/_/g, " ")}
                          </button>
                        ) : null}
                        {detail.memory.tags.map((tag) => (
                          <button
                            className="brain-chip"
                            key={tag}
                            onClick={() => patchControls("tagsInput", tag)}
                            type="button"
                          >
                            {tag}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="drawer-section">
                      <div className="drawer-section__header">
                        <span>{detail.relation_count} conexiones cercanas</span>
                      </div>
                      <div className="relation-stack">
                        {detail.relations.length ? (
                          detail.relations.map((relation) => (
                            <button
                              className="relation-row"
                              key={relation.id}
                              onClick={() =>
                                focusMemory(relation.other_memory_id, relation.other_project ?? "")
                              }
                              type="button"
                            >
                              <span className="relation-row__headline">
                                {relation.relation_type.replace(/_/g, " ")} ·{" "}
                                {relation.weight.toFixed(2)}
                              </span>
                              <span className="relation-row__body">
                                {relation.other_summary || relation.other_memory_id}
                              </span>
                              <small>{relation.other_project || "sin proyecto"}</small>
                            </button>
                          ))
                        ) : (
                          <div className="drawer-empty">
                            Aquí aparecerán las conexiones más cercanas de la neurona actual.
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="drawer-empty">
                    Selecciona una neurona del canvas o del rail para abrir su lectura completa.
                  </div>
                )}
                {detailError ? <p className="brain-notice brain-notice--warning">{detailError}</p> : null}
              </motion.aside>
            ) : null}
          </AnimatePresence>
        </motion.section>
      </div>
    </div>
  );
}

export default App;
