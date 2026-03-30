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

import {
  fetchGraphFacets,
  fetchGraphMetrics,
  fetchGraphSubgraph,
  fetchMemoryDetail,
} from "./api";
import {
  buildCytoscapeElements,
  buildSubgraphRequest,
  shouldPauseAutoRefresh,
} from "./graph";
import type {
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

const INTERACTION_COOLDOWN_MS = 8000;

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

function MetricCard(props: {
  label: string;
  value: string | number;
  helper: string;
}) {
  return (
    <article className="metric-card">
      <span className="metric-card__label">{props.label}</span>
      <strong className="metric-card__value">{props.value}</strong>
      <span className="metric-card__helper">{props.helper}</span>
    </article>
  );
}

function App() {
  const [controls, setControls] = useState<GraphControlsState>(DEFAULT_CONTROLS);
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

  const [isInteracting, setIsInteracting] = useState(false);
  const [lastInteractionAt, setLastInteractionAt] = useState<number | null>(null);

  const graphRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const interactionTimeoutRef = useRef<number | null>(null);

  const activeProject = controls.project.trim();
  const deferredQuery = useDeferredValue(controls.query);
  const selectedTag = controls.tagsInput.split(",")[0]?.trim() || "";
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

  function focusMemory(memoryId: string) {
    if (!memoryId) {
      return;
    }
    markInteraction();
    patchControls("mode", "memory_focus");
    patchControls("centerMemoryId", memoryId);
    startTransition(() => {
      setSelectedMemoryId(memoryId);
    });
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
            color: "#1b2925",
            "text-wrap": "wrap",
            "text-max-width": 130,
            "text-valign": "center",
            "text-halign": "center",
            width: "mapData(size, 0.05, 1, 36, 82)",
            height: "mapData(size, 0.05, 1, 36, 82)",
            "border-width": 1.6,
            "border-color": "#b7cbc7",
            "background-color": "#edf4f2",
            "overlay-opacity": 0,
          },
        },
        {
          selector: "node.manual-pin",
          style: {
            shape: "round-rectangle",
            "border-color": "#c59d64",
            "border-width": 2.6,
            "background-color": "#f5ede2",
          },
        },
        {
          selector: "node.selected-node",
          style: {
            "border-color": "#2f7d76",
            "border-width": "3.4",
            "shadow-color": "#7db8b1",
            "shadow-opacity": "0.25",
            "shadow-blur": "24",
          },
        },
        {
          selector: "node.type-decision",
          style: { "background-color": "#e9f1f9" },
        },
        {
          selector: "node.type-error",
          style: { "background-color": "#f9ece8" },
        },
        {
          selector: "node.type-architecture",
          style: { "background-color": "#e7f3ef" },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(weight, 0, 1, 1, 4.8)",
            "line-color": "#c8d4d1",
            "target-arrow-color": "#c8d4d1",
            "curve-style": "bezier",
            opacity: "mapData(weight, 0, 1, 0.12, 0.9)",
          },
        },
        {
          selector: "edge.manual-edge",
          style: {
            "line-color": "#c59d64",
            "target-arrow-color": "#c59d64",
          },
        },
        {
          selector: "edge.inactive-edge",
          style: {
            "line-style": "dashed",
            opacity: "0.18",
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
      animationDuration: 320,
      fit: true,
      padding: 40,
      idealEdgeLength: 136,
      nodeRepulsion: 3900,
      gravity: 0.16,
    } as any).run();
  }, [graphData, selectedMemoryId]);

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
        setFacetsError(error instanceof Error ? error.message : "No pude leer las claves del cerebro");
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
  const graphTitle =
    controls.mode === "memory_focus"
      ? "Memoria en foco"
      : activeProject || "Exploración del cerebro";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="kicker">AI MEMORY BRAIN</p>
          <h1>Mapa limpio del cerebro</h1>
          <p className="lede">
            Explora tus memorias con una vista clara, filtros guiados y claves reales sacadas del
            propio cerebro: proyectos, tipos, etiquetas y memorias calientes.
          </p>
        </div>
        <div className="topbar__meta">
          <span className="soft-pill">
            {graphRefreshPaused ? "Auto-refresh en pausa" : autoRefresh ? "Auto-refresh activo" : "Refresco manual"}
          </span>
          <span className="soft-pill soft-pill--muted">
            {graphLoading ? "cargando mapa" : "mapa listo"}
          </span>
          <button className="primary-button" onClick={refreshNow} type="button">
            Actualizar ahora
          </button>
        </div>
      </header>

      <section className="toolbar-card">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Explorar</p>
            <h2>Controles principales</h2>
          </div>
          <button className="ghost-button" onClick={clearFilters} type="button">
            Limpiar filtros
          </button>
        </div>

        <div className="toolbar-grid">
          <label className="field">
            <span>Proyecto</span>
            <select
              value={controls.project}
              onChange={(event) => patchControls("project", event.target.value)}
            >
              <option value="">Selecciona un proyecto</option>
              {projects.map((item) => (
                <option key={item.project} value={item.project}>
                  {item.project} · {item.memory_count}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Vista</span>
            <select
              value={controls.mode}
              onChange={(event) => patchControls("mode", event.target.value as GraphControlsState["mode"])}
            >
              <option value="project_hot">Proyecto activo</option>
              <option value="search">Buscar ideas</option>
              <option value="memory_focus">Memoria en foco</option>
            </select>
          </label>

          <label className="field">
            <span>Alcance</span>
            <select
              value={controls.scope}
              onChange={(event) => patchControls("scope", event.target.value as GraphControlsState["scope"])}
            >
              <option value="project">Solo proyecto</option>
              <option value="bridged">Proyectos conectados</option>
              <option value="global">Global</option>
            </select>
          </label>

          <label className="field">
            <span>Tipo de memoria</span>
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

          <label className="field">
            <span>Etiqueta clave</span>
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

          <label className="field field--wide">
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

          <label className="field field--wide">
            <span>Búsqueda</span>
            <input
              value={controls.query}
              onChange={(event) => patchControls("query", event.target.value)}
              placeholder={
                controls.mode === "search"
                  ? "Describe lo que quieres recuperar"
                  : "Solo se usa en la vista Buscar ideas"
              }
            />
          </label>

          <label className="field">
            <span>Nodos</span>
            <input
              type="number"
              min={1}
              max={80}
              value={controls.nodeLimit}
              onChange={(event) => onNumberInput("nodeLimit", event)}
            />
          </label>

          <label className="field">
            <span>Aristas</span>
            <input
              type="number"
              min={1}
              max={200}
              value={controls.edgeLimit}
              onChange={(event) => onNumberInput("edgeLimit", event)}
            />
          </label>
        </div>

        <div className="toolbar-actions">
          <label className="toggle">
            <input
              checked={controls.includeInactive}
              onChange={(event) => patchControls("includeInactive", event.target.checked)}
              type="checkbox"
            />
            <span>Incluir enlaces inactivos</span>
          </label>
          <label className="toggle">
            <input
              checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)}
              type="checkbox"
            />
            <span>Auto-refresh</span>
          </label>
          <button
            className="ghost-button"
            onClick={() => focusMemory(controls.centerMemoryId || selectedMemoryId)}
            type="button"
          >
            Enfocar memoria elegida
          </button>
        </div>
      </section>

      <section className="brain-keys-card">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Claves del cerebro</p>
            <h2>Atajos y sugerencias reales</h2>
          </div>
          <span className="section-meta">
            {facets?.generated_at ? `actualizado ${formatTimestamp(facets.generated_at)}` : "leyendo cerebro…"}
          </span>
        </div>

        <div className="brain-keys-grid">
          <details className="brain-key" open>
            <summary>
              <span>Proyectos</span>
              <strong>{projects.length}</strong>
            </summary>
            <div className="brain-key__content">
              {projects.map((item) => (
                <button
                  className="chip-button"
                  key={item.project}
                  onClick={() => patchControls("project", item.project)}
                  type="button"
                >
                  {item.project}
                  <small>{item.memory_count}</small>
                </button>
              ))}
            </div>
          </details>

          <details className="brain-key" open>
            <summary>
              <span>Tipos</span>
              <strong>{memoryTypes.length}</strong>
            </summary>
            <div className="brain-key__content">
              {memoryTypes.map((item) => (
                <button
                  className="chip-button"
                  key={item.memory_type}
                  onClick={() => patchControls("memoryType", item.memory_type)}
                  type="button"
                >
                  {item.memory_type}
                  <small>{item.count}</small>
                </button>
              ))}
            </div>
          </details>

          <details className="brain-key" open>
            <summary>
              <span>Etiquetas</span>
              <strong>{topTags.length}</strong>
            </summary>
            <div className="brain-key__content">
              {topTags.map((item) => (
                <button
                  className="chip-button"
                  key={item.tag}
                  onClick={() => patchControls("tagsInput", item.tag)}
                  type="button"
                >
                  {item.tag}
                  <small>{item.count}</small>
                </button>
              ))}
            </div>
          </details>

          <details className="brain-key" open>
            <summary>
              <span>Memorias calientes</span>
              <strong>{hotMemories.length}</strong>
            </summary>
            <div className="memory-picks">
              {hotMemories.map((item) => (
                <button
                  className="memory-pick"
                  key={item.memory_id}
                  onClick={() => focusMemory(item.memory_id)}
                  type="button"
                >
                  <span className="memory-pick__title">{item.content_preview}</span>
                  <span className="memory-pick__meta">
                    {(item.memory_type || "general").replace(/_/g, " ")} · {item.prominence.toFixed(2)}
                  </span>
                </button>
              ))}
            </div>
          </details>
        </div>

        {facetsError ? <p className="notice notice--warning">{facetsError}</p> : null}
      </section>

      <section className="metrics-strip">
        <MetricCard
          label="Memorias"
          value={metrics?.memory_count ?? "—"}
          helper="volumen visible del cerebro"
        />
        <MetricCard
          label="Relaciones activas"
          value={metrics?.active_relation_count ?? "—"}
          helper="enlaces actualmente vivos"
        />
        <MetricCard
          label="Fijadas"
          value={metrics?.pinned_memory_count ?? "—"}
          helper="anclas manuales estables"
        />
        <MetricCard
          label="Cluster caliente"
          value={metrics?.hot_memory_count ?? "—"}
          helper="memorias más presentes"
        />
      </section>

      <section className="workspace">
        <article className="graph-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Subgrafo</p>
              <h2>{graphTitle}</h2>
            </div>
            <div className="panel-badges">
              <span className="soft-pill">{graphData?.summary.node_count ?? 0} nodos</span>
              <span className="soft-pill">{graphData?.summary.edge_count ?? 0} enlaces</span>
              <span className="soft-pill soft-pill--muted">
                {controls.mode === "project_hot"
                  ? "proyecto activo"
                  : controls.mode === "search"
                    ? "búsqueda"
                    : "foco"}
              </span>
            </div>
          </div>

          <div className="subtle-row">
            <span>
              {controls.scope === "global"
                ? "alcance global"
                : controls.scope === "bridged"
                  ? "incluye proyectos conectados"
                  : "solo este proyecto"}
            </span>
            <span>
              {graphRefreshPaused
                ? "pauso el refresco mientras mueves el mapa"
                : autoRefresh
                  ? "refresco automático cada 10s"
                  : "refresco manual"}
            </span>
          </div>

          {graphLoading ? <div className="loading-line" /> : null}
          {graphError ? <p className="notice notice--danger">{graphError}</p> : null}
          {metricsError ? <p className="notice notice--warning">{metricsError}</p> : null}

          {graphHasNodes ? (
            <div className="graph-surface">
              <div className="graph-canvas" ref={graphRef} />
            </div>
          ) : (
            <div className="empty-state">
              <strong>No hay nodos para esta vista todavía.</strong>
              <p>
                Prueba con otro proyecto, quita filtros o usa una de las claves del cerebro para
                arrancar desde una memoria caliente.
              </p>
              <div className="empty-state__actions">
                {projects.slice(0, 3).map((item) => (
                  <button
                    className="ghost-button"
                    key={item.project}
                    onClick={() => patchControls("project", item.project)}
                    type="button"
                  >
                    Abrir {item.project}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="legend-row">
            <span><i className="legend-dot legend-dot--architecture" /> arquitectura</span>
            <span><i className="legend-dot legend-dot--decision" /> decisión</span>
            <span><i className="legend-dot legend-dot--error" /> error</span>
            <span><i className="legend-dot legend-dot--pin" /> fijada</span>
          </div>
        </article>

        <aside className="inspector">
          <section className="info-card">
            <div className="section-heading">
              <div>
                <p className="section-kicker">Detalle</p>
                <h2>{detail?.memory.memory_type ? detail.memory.memory_type.replace(/_/g, " ") : "Sin selección"}</h2>
              </div>
              <span className="soft-pill">
                {detail ? `${detail.memory.prominence.toFixed(2)} prominencia` : "elige un nodo"}
              </span>
            </div>

            {detail ? (
              <>
                <p className="lead-copy">{detail.memory.content_preview}</p>
                <details className="fold-card" open>
                  <summary>Contenido completo</summary>
                  <p>{detail.memory.content || detail.memory.summary}</p>
                </details>
                <details className="fold-card" open>
                  <summary>Etiquetas y señales</summary>
                  <div className="tag-cloud">
                    {detail.memory.tags.map((tag) => (
                      <button
                        className="tag-pill"
                        key={tag}
                        onClick={() => patchControls("tagsInput", tag)}
                        type="button"
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                  <dl className="detail-list">
                    <div>
                      <dt>Proyecto</dt>
                      <dd>{detail.memory.project || "sin proyecto"}</dd>
                    </div>
                    <div>
                      <dt>Accesos</dt>
                      <dd>{detail.memory.access_count}</dd>
                    </div>
                    <div>
                      <dt>Activación</dt>
                      <dd>{detail.memory.activation_score.toFixed(3)}</dd>
                    </div>
                    <div>
                      <dt>Estabilidad</dt>
                      <dd>{detail.memory.stability_score.toFixed(3)}</dd>
                    </div>
                    <div>
                      <dt>Fijada</dt>
                      <dd>{detail.memory.manual_pin ? "sí" : "no"}</dd>
                    </div>
                    <div>
                      <dt>Último acceso</dt>
                      <dd>{formatTimestamp(detail.memory.last_accessed_at)}</dd>
                    </div>
                  </dl>
                </details>
              </>
            ) : (
              <div className="empty-mini">
                Selecciona una memoria del mapa o una memoria caliente del acordeón para ver su
                contenido y sus señales internas.
              </div>
            )}
            {detailError ? <p className="notice notice--warning">{detailError}</p> : null}
          </section>

          <section className="info-card">
            <div className="section-heading">
              <div>
                <p className="section-kicker">Enlaces</p>
                <h2>{detail?.relation_count ?? 0} conexiones</h2>
              </div>
              <span className="soft-pill soft-pill--muted">
                {metrics ? `${metrics.avg_activation_score.toFixed(2)} media` : "sin media"}
              </span>
            </div>

            <div className="relation-stack">
              {detail?.relations.length ? (
                detail.relations.map((relation) => (
                  <button
                    className="relation-row"
                    key={relation.id}
                    onClick={() => focusMemory(relation.other_memory_id)}
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
                <div className="empty-mini">
                  Aquí aparecerán las relaciones más cercanas cuando selecciones una memoria.
                </div>
              )}
            </div>
          </section>

          <section className="info-card">
            <div className="section-heading">
              <div>
                <p className="section-kicker">Resumen</p>
                <h2>Lectura rápida del cerebro</h2>
              </div>
              <span className="soft-pill soft-pill--muted">
                {metrics?.bridge_count ?? 0} puentes
              </span>
            </div>

            <details className="fold-card" open>
              <summary>Tipos dominantes</summary>
              <div className="summary-list">
                {metrics?.top_memory_types.length ? (
                  metrics.top_memory_types.map((item) => (
                    <div className="summary-row" key={item.memory_type}>
                      <span>{item.memory_type}</span>
                      <strong>{item.count}</strong>
                    </div>
                  ))
                ) : (
                  <p>Sin tipos destacados todavía.</p>
                )}
              </div>
            </details>

            <details className="fold-card" open>
              <summary>Etiquetas más repetidas</summary>
              <div className="tag-cloud">
                {topTags.length ? (
                  topTags.map((item) => (
                    <button
                      className="tag-pill"
                      key={item.tag}
                      onClick={() => patchControls("tagsInput", item.tag)}
                      type="button"
                    >
                      {item.tag}
                    </button>
                  ))
                ) : (
                  <p>No hay etiquetas disponibles.</p>
                )}
              </div>
            </details>
          </section>
        </aside>
      </section>
    </div>
  );
}

export default App;
