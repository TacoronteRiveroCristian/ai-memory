import { useCallback, useRef, useEffect, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphNode, GraphEdge } from "../types";
import {
  getNodeColor,
  getNodeSize,
  getNodeOpacity,
  shouldPulse,
  shouldGlow,
  getEdgeWidth,
  getEdgeOpacity,
  COLOR_BRIDGE,
} from "../utils/nodeStyle";
import { PROJECT_COLORS } from "./ProjectSelector";
import styles from "./BrainGraph.module.css";

interface BrainGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  projectList: string[];
  selectedProject: string | null;
  onNodeClick: (node: GraphNode) => void;
  onBackgroundClick: () => void;
}

interface ForceNode extends GraphNode {
  id: string;
  x?: number;
  y?: number;
}

interface ForceLink {
  source: string | ForceNode;
  target: string | ForceNode;
  weight: number;
  origin: string;
  isBridge: boolean;
}

export default function BrainGraph({
  nodes,
  edges,
  projectList,
  selectedProject,
  onNodeClick,
  onBackgroundClick,
}: BrainGraphProps) {
  const graphRef = useRef<any>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const pulsePhase = useRef(0);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

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

  const graphNodes: ForceNode[] = nodes.map((n) => ({
    ...n,
    id: n.memory_id,
  }));

  const nodeProjectMap = new Map<string, string>();
  nodes.forEach((n) => nodeProjectMap.set(n.memory_id, n.project));

  const graphLinks: ForceLink[] = edges.map((e) => {
    const sourceProject = nodeProjectMap.get(e.source_memory_id);
    const targetProject = nodeProjectMap.get(e.target_memory_id);
    return {
      source: e.source_memory_id,
      target: e.target_memory_id,
      weight: e.weight,
      origin: e.origin,
      isBridge: sourceProject !== targetProject,
    };
  });

  useEffect(() => {
    let animId: number;
    const tick = () => {
      pulsePhase.current = (Date.now() % 2500) / 2500;
      animId = requestAnimationFrame(tick);
    };
    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, []);

  const projectColorMap = new Map<string, string>();
  projectList.forEach((p, i) => {
    projectColorMap.set(p, PROJECT_COLORS[i % PROJECT_COLORS.length]);
  });

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D) => {
      const n = node as ForceNode;
      const x = n.x ?? 0;
      const y = n.y ?? 0;
      const color = getNodeColor(n);
      const size = getNodeSize(n);
      const opacity = getNodeOpacity(n);

      // Glow for prominent nodes
      if (shouldGlow(n)) {
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
      if (shouldPulse(n)) {
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
      if (!selectedProject) {
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
      ctx.globalAlpha = opacity;
      ctx.fill();
      ctx.globalAlpha = 1;

      // Label
      const zoom = graphRef.current?.zoom?.() ?? 1;
      if (zoom > 1.5) {
        const label =
          n.content_preview.length > 30
            ? n.content_preview.slice(0, 28) + "\u2026"
            : n.content_preview;
        ctx.font = "3px system-ui";
        ctx.textAlign = "center";
        ctx.fillStyle = color;
        ctx.globalAlpha = opacity * 0.7;
        ctx.fillText(label, x, y + size + 5);
        ctx.globalAlpha = 1;
      }
    },
    [selectedProject, projectColorMap]
  );

  const linkCanvasObject = useCallback(
    (link: any, ctx: CanvasRenderingContext2D) => {
      const start = link.source;
      const end = link.target;
      if (typeof start === "string" || typeof end === "string") return;
      if (!start.x || !end.x) return;

      const color = link.isBridge ? COLOR_BRIDGE : getNodeColor(start);
      const width = getEdgeWidth(link.weight);
      const opacity = getEdgeOpacity(link.weight);

      ctx.beginPath();
      ctx.moveTo(start.x, start.y);

      if (link.isBridge) {
        ctx.setLineDash([5, 4]);
      } else {
        ctx.setLineDash([]);
      }

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

  return (
    <div className={styles.container} ref={containerRef}>
      <ForceGraph2D
        ref={graphRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={{ nodes: graphNodes, links: graphLinks }}
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
        onNodeClick={(node: any) => {
          const n = node as ForceNode;
          // Smooth center on clicked node
          if (graphRef.current) {
            graphRef.current.centerAt(n.x, n.y, 600);
          }
          onNodeClick(n);
        }}
        onBackgroundClick={onBackgroundClick}
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
          High activation
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: "#4ecdc4" }} />
          Stable
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: "#ffd93d" }} />
          Decaying
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: "#666" }} />
          Fading
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendLine} />
          Bridge
        </span>
      </div>
    </div>
  );
}
