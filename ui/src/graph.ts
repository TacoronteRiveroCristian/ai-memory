import type { ElementDefinition } from "cytoscape";

import type {
  EdgeVisualState,
  GraphControlsState,
  GraphEdge,
  GraphNode,
  GraphSubgraphRequestPayload,
  GraphSubgraphResponse,
  NodeVisualState,
  ProjectRegion,
} from "./types";

const BRAIN_WIDTH = 1000;
const BRAIN_HEIGHT = 760;

const REGION_ANCHORS: Array<{
  hemisphere: ProjectRegion["hemisphere"];
  x: number;
  y: number;
}> = [
  { hemisphere: "left", x: 0.28, y: 0.18 },
  { hemisphere: "left", x: 0.18, y: 0.34 },
  { hemisphere: "left", x: 0.34, y: 0.42 },
  { hemisphere: "left", x: 0.24, y: 0.58 },
  { hemisphere: "left", x: 0.17, y: 0.73 },
  { hemisphere: "center", x: 0.5, y: 0.5 },
  { hemisphere: "right", x: 0.72, y: 0.18 },
  { hemisphere: "right", x: 0.82, y: 0.34 },
  { hemisphere: "right", x: 0.66, y: 0.42 },
  { hemisphere: "right", x: 0.76, y: 0.58 },
  { hemisphere: "right", x: 0.83, y: 0.73 },
];

const REGION_COLORS = [
  "#6eb6ff",
  "#49dfb5",
  "#f8b66a",
  "#ff7d92",
  "#a592ff",
  "#58d9ff",
  "#c7ff75",
  "#ff9a5b",
  "#84a2ff",
  "#63f1da",
  "#f6c7ff",
];

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function alphaColor(hex: string, alpha: number): string {
  const normalized = hex.replace("#", "");
  const base = normalized.length === 3
    ? normalized
        .split("")
        .map((char) => char + char)
        .join("")
    : normalized;
  const value = Number.parseInt(base, 16);
  const red = (value >> 16) & 255;
  const green = (value >> 8) & 255;
  const blue = value & 255;
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function getProjectKey(project: string | null | undefined): string {
  return project?.trim() || "Sin proyecto";
}

function clampToBrainSilhouette(x: number, y: number): { x: number; y: number } {
  const centerX = BRAIN_WIDTH / 2;
  const centerY = BRAIN_HEIGHT / 2;
  const radiusX = 390;
  const radiusY = 325;
  const normalizedX = (x - centerX) / radiusX;
  const normalizedY = (y - centerY) / radiusY;
  const distance = normalizedX * normalizedX + normalizedY * normalizedY;

  if (distance <= 1) {
    return { x, y };
  }

  const factor = 0.96 / Math.sqrt(distance);
  return {
    x: centerX + (x - centerX) * factor,
    y: centerY + (y - centerY) * factor,
  };
}

function buildNodePosition(
  region: ProjectRegion,
  node: GraphNode,
  index: number,
  total: number,
): { x: number; y: number } {
  const angle = index * 2.399963229728653 + (region.hemisphere === "left" ? Math.PI * 0.12 : 0);
  const spread = 26 + Math.max(12, Math.sqrt(total) * 15);
  const radius = spread + Math.sqrt(index + 1) * (18 + total * 1.8) * (1.08 - node.prominence * 0.25);
  const stretchX = region.hemisphere === "center" ? 1.04 : 1.18;
  const stretchY = 0.92;
  const originX = region.x * BRAIN_WIDTH;
  const originY = region.y * BRAIN_HEIGHT;
  const rawX = originX + Math.cos(angle) * radius * stretchX;
  const rawY = originY + Math.sin(angle) * radius * stretchY;
  return clampToBrainSilhouette(rawX, rawY);
}

function findRegionForProject(project: string | null | undefined, projectRegions: ProjectRegion[]): ProjectRegion {
  const projectKey = getProjectKey(project);
  return (
    projectRegions.find((item) => item.project === projectKey) ?? {
      project: projectKey,
      label: projectKey,
      hemisphere: "center",
      x: 0.5,
      y: 0.5,
      color: "#8fb7ff",
      nodeCount: 0,
    }
  );
}

export function sanitizeTagsInput(rawValue: string): string[] {
  return rawValue
    .split(",")
    .map((tag) => tag.trim().toLowerCase())
    .filter(Boolean);
}

export function buildSubgraphRequest(
  controls: GraphControlsState,
  selectedMemoryId: string,
): GraphSubgraphRequestPayload {
  const centerMemoryId = controls.centerMemoryId.trim() || selectedMemoryId.trim();
  const payload: GraphSubgraphRequestPayload = {
    project: controls.project.trim(),
    mode: controls.mode,
    scope: controls.scope,
    tags: sanitizeTagsInput(controls.tagsInput),
    depth: controls.mode === "memory_focus" ? 1 : 1,
    node_limit: Math.max(1, Math.min(80, controls.nodeLimit)),
    edge_limit: Math.max(1, Math.min(200, controls.edgeLimit)),
    min_weight: 0.18,
    include_inactive: controls.includeInactive,
  };

  if (controls.query.trim() && controls.mode === "search") {
    payload.query = controls.query.trim();
  }
  if (controls.memoryType.trim()) {
    payload.memory_type = controls.memoryType.trim();
  }
  if (centerMemoryId && controls.mode === "memory_focus") {
    payload.center_memory_id = centerMemoryId;
  }
  return payload;
}

export function buildProjectRegions(
  graph: GraphSubgraphResponse | GraphNode[] | null,
  activeProject = "",
): ProjectRegion[] {
  const nodes = Array.isArray(graph) ? graph : graph?.nodes ?? [];
  const counts = new Map<string, number>();

  for (const node of nodes) {
    const project = getProjectKey(node.project);
    counts.set(project, (counts.get(project) ?? 0) + 1);
  }

  const projects = Array.from(counts.entries()).sort((left, right) => {
    const activeLeft = left[0] === activeProject ? 1 : 0;
    const activeRight = right[0] === activeProject ? 1 : 0;
    return activeRight - activeLeft || right[1] - left[1] || left[0].localeCompare(right[0]);
  });

  return projects.map(([project, nodeCount], index) => {
    const anchor = REGION_ANCHORS[index % REGION_ANCHORS.length] ?? REGION_ANCHORS[0];
    const band = Math.floor(index / REGION_ANCHORS.length);
    const lateralOffset =
      band === 0
        ? 0
        : (anchor.hemisphere === "left" ? -1 : anchor.hemisphere === "right" ? 1 : 0) *
          band *
          0.028;
    const verticalOffset = band === 0 ? 0 : ((band % 3) - 1) * 0.04;
    return {
      project,
      label: project,
      hemisphere: anchor.hemisphere,
      x: clamp(anchor.x + lateralOffset, 0.14, 0.86),
      y: clamp(anchor.y + verticalOffset, 0.14, 0.82),
      color: REGION_COLORS[index % REGION_COLORS.length] ?? "#8fb7ff",
      nodeCount,
    };
  });
}

export function shouldShowNodeLabel(
  node: Pick<GraphNode, "memory_id" | "manual_pin" | "prominence">,
  state: { selectedMemoryId?: string; hoveredMemoryId?: string } = {},
): boolean {
  return Boolean(
    node.manual_pin ||
      node.prominence >= 0.76 ||
      node.memory_id === state.selectedMemoryId ||
      node.memory_id === state.hoveredMemoryId,
  );
}

export function deriveNodeVisualState(
  node: GraphNode,
  region: ProjectRegion,
  state: { selectedMemoryId?: string; hoveredMemoryId?: string } = {},
): NodeVisualState {
  const isSelected = node.memory_id === state.selectedMemoryId;
  const isHovered = node.memory_id === state.hoveredMemoryId;
  const activation = clamp(node.activation_score, 0, 1);
  const stability = clamp(node.stability_score, 0, 1);
  const emphasis = isSelected ? 0.3 : isHovered ? 0.18 : 0;
  return {
    fillColor: alphaColor(region.color, 0.26 + stability * 0.42 + emphasis),
    borderColor: node.manual_pin ? "#ffd38b" : alphaColor(region.color, 0.65 + emphasis),
    borderWidth: node.manual_pin ? (isSelected ? 4 : 3) : isSelected ? 3.2 : 1.45,
    glowOpacity: clamp(0.18 + activation * 0.56 + emphasis, 0.18, 0.94),
    glowBlur: 18 + activation * 28 + (isSelected ? 12 : 0),
    opacity: clamp(0.54 + stability * 0.38 + (isHovered ? 0.08 : 0), 0.42, 1),
    labelVisible: shouldShowNodeLabel(node, state),
  };
}

export function deriveEdgeVisualState(
  edge: GraphEdge,
  sourceRegion: ProjectRegion,
  targetRegion: ProjectRegion,
): EdgeVisualState {
  const sameRegion = sourceRegion.project === targetRegion.project;
  const baseColor = sameRegion ? sourceRegion.color : "#90a2d4";
  return {
    color: alphaColor(baseColor, edge.active ? 0.62 : 0.24),
    width: clamp(1.2 + edge.weight * 4.4, 1.2, 6),
    opacity: clamp(edge.active ? 0.18 + edge.weight * 0.58 : 0.08 + edge.weight * 0.2, 0.08, 0.92),
    lineStyle: edge.active ? "solid" : "dashed",
  };
}

export function buildCytoscapeElements(
  graph: GraphSubgraphResponse | null,
  options: {
    projectRegions: ProjectRegion[];
  },
): ElementDefinition[] {
  if (!graph) {
    return [];
  }

  const projectRegions = options.projectRegions;
  const projectGroups = new Map<string, GraphNode[]>();

  for (const node of graph.nodes) {
    const project = getProjectKey(node.project);
    const currentGroup = projectGroups.get(project) ?? [];
    currentGroup.push(node);
    projectGroups.set(project, currentGroup);
  }

  const nodeElements = graph.nodes.map((node) => {
    const project = getProjectKey(node.project);
    const group = projectGroups.get(project) ?? [node];
    const index = group.findIndex((candidate) => candidate.memory_id === node.memory_id);
    const region = findRegionForProject(project, projectRegions);
    const visual = deriveNodeVisualState(node, region);
    const position = buildNodePosition(region, node, index, group.length);
    return {
      data: {
        id: node.memory_id,
        memoryId: node.memory_id,
        label: node.content_preview,
        project,
        projectColor: region.color,
        memoryType: node.memory_type ?? "general",
        size: Math.max(0.08, node.prominence),
        activation: node.activation_score,
        stability: node.stability_score,
        accessCount: node.access_count,
        manualPin: node.manual_pin ? 1 : 0,
        fillColor: visual.fillColor,
        borderColor: visual.borderColor,
        borderWidth: visual.borderWidth,
        glowOpacity: visual.glowOpacity,
        glowBlur: visual.glowBlur,
        nodeOpacity: visual.opacity,
        labelOpacity: visual.labelVisible ? 1 : 0,
      },
      position,
      classes: [
        `type-${(node.memory_type ?? "general").replace(/[^a-z0-9_-]+/gi, "-")}`,
        node.manual_pin ? "manual-pin" : "",
        visual.labelVisible ? "label-node" : "",
      ]
        .filter(Boolean)
        .join(" "),
    };
  });

  const edgeElements = graph.edges.map((edge) => {
    const sourceRegion = findRegionForProject(
      graph.nodes.find((node) => node.memory_id === edge.source_memory_id)?.project,
      projectRegions,
    );
    const targetRegion = findRegionForProject(
      graph.nodes.find((node) => node.memory_id === edge.target_memory_id)?.project,
      projectRegions,
    );
    const visual = deriveEdgeVisualState(edge, sourceRegion, targetRegion);
    return {
      data: {
        id: `${edge.source_memory_id}::${edge.target_memory_id}::${edge.relation_type}`,
        source: edge.source_memory_id,
        target: edge.target_memory_id,
        weight: edge.weight,
        relationType: edge.relation_type,
        reinforcementCount: edge.reinforcement_count,
        activeFlag: edge.active ? 1 : 0,
        label: edge.relation_type.replace(/_/g, " "),
        edgeColor: visual.color,
        edgeWidth: visual.width,
        edgeOpacity: visual.opacity,
      },
      classes: [
        edge.origin === "manual" ? "manual-edge" : "",
        edge.active ? "active-edge" : "inactive-edge",
        visual.lineStyle === "dashed" ? "dashed-edge" : "",
      ]
        .filter(Boolean)
        .join(" "),
    };
  });

  return [...nodeElements, ...edgeElements];
}

export function shouldPauseAutoRefresh(
  isInteracting: boolean,
  lastInteractionAt: number | null,
  now: number,
  cooldownMs = 8000,
): boolean {
  if (!isInteracting || lastInteractionAt === null) {
    return false;
  }
  return now - lastInteractionAt < cooldownMs;
}
