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

/** Memory type -> single character for semantic zoom mid-level */
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

/**
 * Node vitality: how "alive" a memory is.
 * 1.0 = hot core of the brain, 0.0 = fading periphery.
 */
export function getNodeVitality(node: GraphNode): number {
  const aliveness = Math.max(node.activation_score, node.stability_score);
  // Boost pinned and high-prominence nodes toward center
  const pinBoost = node.manual_pin ? 0.15 : 0;
  const prominenceBoost = node.prominence * 0.2;
  return Math.min(1, aliveness + pinBoost + prominenceBoost);
}

export {
  COLOR_RED, COLOR_CYAN, COLOR_YELLOW, COLOR_GRAY,
  COLOR_BRIDGE, COLOR_TIER1, COLOR_TIER2, COLOR_TIER3,
};
