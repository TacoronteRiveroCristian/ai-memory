import type { ElementDefinition } from "cytoscape";

import type {
  GraphControlsState,
  GraphSubgraphRequestPayload,
  GraphSubgraphResponse,
} from "./types";

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

export function buildCytoscapeElements(
  graph: GraphSubgraphResponse | null,
  selectedMemoryId: string,
): ElementDefinition[] {
  if (!graph) {
    return [];
  }

  const nodeElements = graph.nodes.map((node) => ({
    data: {
      id: node.memory_id,
      memoryId: node.memory_id,
      label: node.content_preview,
      project: node.project ?? "unknown",
      memoryType: node.memory_type ?? "general",
      size: Math.max(0.05, node.prominence),
      activation: node.activation_score,
      stability: node.stability_score,
      accessCount: node.access_count,
      manualPin: node.manual_pin ? 1 : 0,
    },
    classes: [
      `type-${(node.memory_type ?? "general").replace(/[^a-z0-9_-]+/gi, "-")}`,
      node.manual_pin ? "manual-pin" : "",
      node.memory_id === selectedMemoryId ? "selected-node" : "",
    ]
      .filter(Boolean)
      .join(" "),
  }));

  const edgeElements = graph.edges.map((edge) => ({
    data: {
      id: `${edge.source_memory_id}::${edge.target_memory_id}::${edge.relation_type}`,
      source: edge.source_memory_id,
      target: edge.target_memory_id,
      weight: edge.weight,
      relationType: edge.relation_type,
      reinforcementCount: edge.reinforcement_count,
      activeFlag: edge.active ? 1 : 0,
      label: edge.relation_type.replace(/_/g, " "),
    },
    classes: [
      edge.origin === "manual" ? "manual-edge" : "",
      edge.active ? "active-edge" : "inactive-edge",
    ]
      .filter(Boolean)
      .join(" "),
  }));

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
