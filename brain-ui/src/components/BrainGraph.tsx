import { useCallback, useRef, useEffect, useState, useMemo, forwardRef, useImperativeHandle } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphNode, GraphEdge } from "../types";
import {
  getNodeColor,
  getNodeSize,
  getNodeOpacity,
  getNodeVitality,
  shouldPulse,
  shouldGlow,
  getTypeChar,
  getEdgeWidth,
  getEdgeOpacity,
  getEdgeTierColor,
  shouldEdgeGlow,
  COLOR_BRIDGE,
} from "../utils/nodeStyle";
import { PROJECT_COLORS } from "./ProjectSelector";
import styles from "./BrainGraph.module.css";

interface BrainGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  projectList: string[];
  selectedProject: string | null;
  selectedProjects: Set<string>;
  onNodeClick: (node: GraphNode) => void;
  onBackgroundClick: () => void;
  focusNodeId?: string | null;
  externalHoveredNodeId?: string | null;
}

export interface BrainGraphHandle {
  centerView: () => void;
}

interface ForceNode extends GraphNode {
  id: string;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface ForceLink {
  source: string | ForceNode;
  target: string | ForceNode;
  weight: number;
  origin: string;
  isBridge: boolean;
  myelinScore: number;
  evidenceJson?: { tier: number } | null;
}

const BrainGraph = forwardRef<BrainGraphHandle, BrainGraphProps>(function BrainGraph({
  nodes,
  edges,
  projectList,
  selectedProject,
  selectedProjects,
  onNodeClick,
  onBackgroundClick,
  focusNodeId,
  externalHoveredNodeId,
}, ref) {
  const graphRef = useRef<any>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const pulsePhase = useRef(0);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const hoveredNodeIdRef = useRef<string | null>(null);
  const externalHoveredRef = useRef<string | null>(null);
  const selectedNodeIdRef = useRef<string | null>(null);

  useImperativeHandle(ref, () => ({
    centerView: () => {
      graphRef.current?.zoomToFit(600, 40);
    },
  }));

  // Keep external hover in sync via ref (no re-renders)
  useEffect(() => {
    externalHoveredRef.current = externalHoveredNodeId ?? null;
  }, [externalHoveredNodeId]);

  // Keep selected node in sync via ref (no re-renders)
  useEffect(() => {
    selectedNodeIdRef.current = focusNodeId ?? null;
  }, [focusNodeId]);

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

  const adjacencyRef = useRef(adjacencyMap);
  useEffect(() => { adjacencyRef.current = adjacencyMap; }, [adjacencyMap]);

  // Track container size so canvas always fills it
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const update = () => {
      setDimensions({ width: el.clientWidth, height: el.clientHeight });
    };
    update();

    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Stable graph data — only recreate when nodes/edges actually change
  const graphNodes = useMemo<ForceNode[]>(
    () => nodes.map((n) => ({ ...n, id: n.memory_id })),
    [nodes]
  );

  const nodeProjectMap = useMemo(() => {
    const map = new Map<string, string>();
    nodes.forEach((n) => map.set(n.memory_id, n.project));
    return map;
  }, [nodes]);

  const graphLinks = useMemo<ForceLink[]>(
    () =>
      edges.map((e) => {
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
      }),
    [edges, nodeProjectMap]
  );

  const graphData = useMemo(
    () => ({ nodes: graphNodes, links: graphLinks }),
    [graphNodes, graphLinks]
  );

  // Pulse animation — only updates ref, no state changes
  useEffect(() => {
    let animId: number;
    const tick = () => {
      pulsePhase.current = (Date.now() % 2500) / 2500;
      animId = requestAnimationFrame(tick);
    };
    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, []);

  // Auto zoom-to-fit after data loads
  const hasAutoFit = useRef(false);
  useEffect(() => {
    if (graphNodes.length > 0 && !hasAutoFit.current) {
      hasAutoFit.current = true;
      const timer = setTimeout(() => {
        graphRef.current?.zoomToFit(600, 40);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [graphNodes.length]);

  // Center graph on focused node, or zoom-to-fit smoothly when deselected
  const prevFocusNodeId = useRef<string | null>(null);
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) return;

    if (focusNodeId) {
      // Navigate to the selected node smoothly
      const node = graphNodes.find((n) => n.memory_id === focusNodeId);
      if (node?.x != null && node?.y != null) {
        fg.centerAt(node.x, node.y, 800);
      }
    } else if (prevFocusNodeId.current) {
      // Was selected, now deselected → smooth zoom back to full brain view
      fg.zoomToFit(1000, 40);
    }

    prevFocusNodeId.current = focusNodeId ?? null;
  }, [focusNodeId, graphNodes]);

  // Stable ref for graphNodes — used by custom forces
  const graphNodesRef = useRef(graphNodes);
  useEffect(() => { graphNodesRef.current = graphNodes; }, [graphNodes]);

  // Radial biological layout:
  // - Center = hot/active memories (high vitality)
  // - Periphery = decaying/fading memories (low vitality)
  // - Angle = project clusters
  // - Circular boundary instead of rectangular
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) return;

    const activeProjects = selectedProjects.size === 0
      ? projectList
      : projectList.filter((p) => selectedProjects.has(p));

    // Max radius of the brain circle
    const maxRadius = Math.min(dimensions.width, dimensions.height) * 0.38;

    // Project angle map — each project gets an angular sector
    const projectAngles = new Map<string, number>();
    activeProjects.forEach((p, i) => {
      projectAngles.set(p, (2 * Math.PI * i) / Math.max(activeProjects.length, 1) - Math.PI / 2);
    });

    const radialStrength = 0.006;
    const angularStrength = 0.004;
    const damping = 0.93;

    fg.d3Force("radialBiology", () => {
      for (const node of graphNodesRef.current) {
        if (node.x == null || node.y == null) continue;

        const vitality = getNodeVitality(node);
        // Invert: high vitality → small radius (center), low → large (periphery)
        // Add some spread so they don't all pile at exact center
        const targetR = maxRadius * (0.08 + 0.92 * (1 - vitality));

        // Current position in polar
        const dx = node.x;
        const dy = node.y;
        const currentR = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const currentAngle = Math.atan2(dy, dx);

        // Radial force: push toward target radius
        const radialDelta = (targetR - currentR) * radialStrength;
        node.vx = ((node.vx ?? 0) + (dx / currentR) * radialDelta) * damping;
        node.vy = ((node.vy ?? 0) + (dy / currentR) * radialDelta) * damping;

        // Angular force: nudge toward project's angle sector (only if multiple projects)
        const targetAngle = projectAngles.get(node.project);
        if (targetAngle != null && activeProjects.length > 1) {
          // Shortest angular difference
          let angleDiff = targetAngle - currentAngle;
          while (angleDiff > Math.PI) angleDiff -= 2 * Math.PI;
          while (angleDiff < -Math.PI) angleDiff += 2 * Math.PI;

          // Tangential push (perpendicular to radial direction)
          const tangentX = -Math.sin(currentAngle);
          const tangentY = Math.cos(currentAngle);
          const angularPush = angleDiff * angularStrength * currentR;
          node.vx = (node.vx ?? 0) + tangentX * angularPush;
          node.vy = (node.vy ?? 0) + tangentY * angularPush;
        }
      }
    });

    // Circular boundary — soft repulsion beyond maxRadius
    fg.d3Force("circularBoundary", () => {
      const limit = maxRadius * 1.15;
      for (const node of graphNodesRef.current) {
        if (node.x == null || node.y == null) continue;
        const r = Math.sqrt(node.x * node.x + node.y * node.y);
        if (r > limit) {
          const pushBack = (r - limit) * 0.08;
          node.vx = (node.vx ?? 0) - (node.x / r) * pushBack;
          node.vy = (node.vy ?? 0) - (node.y / r) * pushBack;
        }
      }
    });

    fg.d3ReheatSimulation();

    return () => {
      if (fg) {
        fg.d3Force("radialBiology", null);
        fg.d3Force("circularBoundary", null);
      }
    };
  }, [projectList, dimensions, selectedProjects]);

  const projectColorMap = useMemo(() => {
    const map = new Map<string, string>();
    projectList.forEach((p, i) => {
      map.set(p, PROJECT_COLORS[i % PROJECT_COLORS.length]);
    });
    return map;
  }, [projectList]);

  const selectedProjectRef = useRef(selectedProject);
  useEffect(() => { selectedProjectRef.current = selectedProject; }, [selectedProject]);

  const projectColorMapRef = useRef(projectColorMap);
  useEffect(() => { projectColorMapRef.current = projectColorMap; }, [projectColorMap]);

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D) => {
      const n = node as ForceNode;
      const x = n.x ?? 0;
      const y = n.y ?? 0;
      const color = getNodeColor(n);
      const size = getNodeSize(n);
      const opacity = getNodeOpacity(n);

      // Selection has priority over hover for highlighting
      const selected = selectedNodeIdRef.current;
      const hovered = hoveredNodeIdRef.current ?? externalHoveredRef.current;
      const activeId = hovered ?? selected;
      let highlighted = true;
      if (activeId) {
        const isSelected = selected && (
          n.memory_id === selected ||
          (adjacencyRef.current.get(selected)?.has(n.memory_id) ?? false)
        );
        const isHovered = hovered && (
          n.memory_id === hovered ||
          (adjacencyRef.current.get(hovered)?.has(n.memory_id) ?? false)
        );
        highlighted = !!(isSelected || isHovered);
      }
      const effectiveOpacity = highlighted ? opacity : 0.08;

      // Glow for prominent nodes
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

      // Pulse ring for highly active nodes
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
      if (!selectedProjectRef.current && highlighted) {
        const projColor = projectColorMapRef.current.get(n.project);
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

      // Semantic zoom levels
      const zoom = graphRef.current?.zoom?.() ?? 1;

      // Mid level (>=1.8): type letter inside node (only for larger nodes)
      if (zoom >= 1.8 && size > 5 && highlighted) {
        const typeChar = getTypeChar(n.memory_type);
        ctx.font = `bold ${Math.max(size * 0.9, 3)}px system-ui`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#fff";
        ctx.globalAlpha = effectiveOpacity * 0.85;
        ctx.fillText(typeChar, x, y);
        ctx.globalAlpha = 1;
        ctx.textBaseline = "alphabetic";
      }

      // Close level (>=3.5): content preview + keyphrases
      if (zoom >= 3.5 && highlighted) {
        const label =
          n.content_preview.length > 30
            ? n.content_preview.slice(0, 28) + "\u2026"
            : n.content_preview;
        ctx.font = "3px system-ui";
        ctx.textAlign = "center";
        ctx.fillStyle = color;
        ctx.globalAlpha = effectiveOpacity * 0.7;
        ctx.fillText(label, x, y + size + 5);

        const kps = n.keyphrases ?? [];
        if (kps.length > 0) {
          ctx.font = "2px system-ui";
          ctx.fillStyle = "#888";
          ctx.globalAlpha = effectiveOpacity * 0.5;
          const display = kps.length > 3
            ? kps.slice(0, 3).join(" \u00b7 ") + ` +${kps.length - 3}`
            : kps.join(" \u00b7 ");
          ctx.fillText(display, x, y + size + 9);
        }
        ctx.globalAlpha = 1;
      }
    },
    [] // No deps — reads everything from refs
  );

  const linkCanvasObject = useCallback(
    (link: any, ctx: CanvasRenderingContext2D) => {
      const start = link.source;
      const end = link.target;
      if (typeof start === "string" || typeof end === "string") return;
      if (!start.x || !end.x) return;

      const sourceId = typeof start === "object" ? start.memory_id : "";
      const targetId = typeof end === "object" ? end.memory_id : "";

      // Selection has priority over hover for edge highlighting
      const selected = selectedNodeIdRef.current;
      const hovered = hoveredNodeIdRef.current ?? externalHoveredRef.current;
      const activeId = hovered ?? selected;
      const edgeHighlighted = !activeId ||
        sourceId === activeId || targetId === activeId ||
        (selected && (sourceId === selected || targetId === selected));

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

      if (shouldEdgeGlow(myelin) && edgeHighlighted) {
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

      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.setLineDash(link.isBridge ? [5, 4] : []);
      ctx.lineTo(end.x, end.y);
      ctx.strokeStyle = color;
      ctx.globalAlpha = edgeHighlighted ? opacity : 0.05;
      ctx.lineWidth = width;
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.setLineDash([]);
    },
    []
  );

  // Stable callback refs for ForceGraph props
  const handleNodeClick = useCallback((node: any) => {
    const n = node as ForceNode;
    if (graphRef.current) {
      graphRef.current.centerAt(n.x, n.y, 800);
    }
    onNodeClick(n);
  }, [onNodeClick]);

  const handleNodeHover = useCallback((node: any) => {
    hoveredNodeIdRef.current = node ? (node as ForceNode).memory_id : null;
    // No forceRender — canvas repaints on its own tick
  }, []);

  const handleRenderFramePost = useCallback(
    (ctx: CanvasRenderingContext2D, globalScale: number) => {
      if (projectList.length < 2) return;
      if (globalScale < 0.3 || globalScale > 4) return;
      const currentNodes = graphNodesRef.current;
      const centroids = new Map<string, { sx: number; sy: number; count: number }>();
      for (const node of currentNodes) {
        if (node.x == null || node.y == null) continue;
        const entry = centroids.get(node.project) ?? { sx: 0, sy: 0, count: 0 };
        entry.sx += node.x;
        entry.sy += node.y;
        entry.count += 1;
        centroids.set(node.project, entry);
      }
      const fontSize = Math.min(14 / globalScale, 40);
      for (const [project, data] of centroids) {
        if (data.count === 0) continue;
        const cx = data.sx / data.count;
        const cy = data.sy / data.count;
        const projColor = projectColorMapRef.current.get(project) ?? "#666";
        ctx.font = `${fontSize}px system-ui`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = projColor;
        ctx.globalAlpha = 0.15;
        ctx.fillText(project, cx, cy);
        ctx.globalAlpha = 1;
      }
    },
    [projectList.length]
  );

  return (
    <div className={styles.container} ref={containerRef}>
      <ForceGraph2D
        ref={graphRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={graphData}
        nodeId="id"
        linkSource="source"
        linkTarget="target"
        nodeCanvasObject={nodeCanvasObject}
        linkCanvasObject={linkCanvasObject}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          const size = getNodeSize(node as ForceNode);
          const hitRadius = Math.max(size + 4, 8);
          ctx.beginPath();
          ctx.arc(node.x ?? 0, node.y ?? 0, hitRadius, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        onBackgroundClick={onBackgroundClick}
        onRenderFramePost={handleRenderFramePost}
        backgroundColor="#0a0a12"
        linkDirectionalParticles={0}
        enableNodeDrag={false}
        d3AlphaDecay={0.05}
        d3VelocityDecay={0.4}
        warmupTicks={100}
        cooldownTicks={0}
      />
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
    </div>
  );
});

export default BrainGraph;
