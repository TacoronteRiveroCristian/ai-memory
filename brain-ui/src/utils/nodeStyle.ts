import type { GraphNode } from "../types";

const COLOR_RED = "#ff6b6b";
const COLOR_CYAN = "#4ecdc4";
const COLOR_YELLOW = "#ffd93d";
const COLOR_GRAY = "#666666";
const COLOR_BRIDGE = "#a78bfa";

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

export function getEdgeWidth(weight: number): number {
  return 0.5 + weight * 2.5;
}

export function getEdgeOpacity(weight: number): number {
  return 0.1 + weight * 0.7;
}

export { COLOR_RED, COLOR_CYAN, COLOR_YELLOW, COLOR_GRAY, COLOR_BRIDGE };
