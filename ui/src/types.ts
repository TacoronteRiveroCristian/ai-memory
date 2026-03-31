export type GraphMode = "project_hot" | "search" | "memory_focus";
export type GraphScope = "project" | "bridged" | "global";

export interface GraphNode {
  memory_id: string;
  project: string | null;
  memory_type: string | null;
  content_preview: string;
  tags: string[];
  activation_score: number;
  stability_score: number;
  access_count: number;
  manual_pin: boolean;
  prominence: number;
}

export interface GraphEdge {
  source_memory_id: string;
  target_memory_id: string;
  relation_type: string;
  weight: number;
  origin: string;
  active: boolean;
  reinforcement_count: number;
  last_activated_at: string | null;
}

export interface GraphSummary {
  mode: GraphMode;
  project: string | null;
  scope: GraphScope;
  query?: string | null;
  center_memory_id?: string | null;
  node_count: number;
  edge_count: number;
  seed_count: number;
  requested_node_limit: number;
  requested_edge_limit: number;
  truncated_nodes: boolean;
  truncated_edges: boolean;
  allowed_projects: string[];
}

export interface GraphSubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: GraphSummary;
}

export interface MemoryDetail {
  memory_id: string;
  project: string | null;
  agent_id: string | null;
  memory_type: string | null;
  summary: string | null;
  content: string | null;
  content_preview: string;
  importance: number;
  tags: string[];
  access_count: number;
  last_accessed_at: string | null;
  activation_score: number;
  stability_score: number;
  manual_pin: boolean;
  prominence: number;
}

export interface MemoryDetailResponse {
  memory: MemoryDetail;
  relation_count: number;
  relations: Array<{
    id: string;
    source_memory_id: string;
    target_memory_id: string;
    relation_type: string;
    weight: number;
    origin: string;
    reinforcement_count: number;
    last_activated_at: string | null;
    active: boolean;
    other_memory_id: string;
    other_summary: string | null;
    other_project: string | null;
  }>;
}

export interface GraphMetrics {
  project: string | null;
  memory_count: number;
  relation_count: number;
  active_relation_count: number;
  pinned_memory_count: number;
  hot_memory_count: number;
  avg_activation_score: number;
  avg_stability_score: number;
  bridge_count: number;
  top_memory_types: Array<{ memory_type: string; count: number }>;
  generated_at: string;
}

export interface GraphFacets {
  project: string | null;
  projects: Array<{
    project: string;
    memory_count: number;
    pinned_memory_count: number;
  }>;
  memory_types: Array<{
    memory_type: string;
    count: number;
  }>;
  top_tags: Array<{
    tag: string;
    count: number;
  }>;
  hot_memories: Array<{
    memory_id: string;
    project: string | null;
    memory_type: string | null;
    content_preview: string;
    tags: string[];
    manual_pin: boolean;
    prominence: number;
  }>;
  generated_at: string;
}

export interface GraphControlsState {
  project: string;
  mode: GraphMode;
  query: string;
  scope: GraphScope;
  memoryType: string;
  tagsInput: string;
  nodeLimit: number;
  edgeLimit: number;
  includeInactive: boolean;
  centerMemoryId: string;
}

export interface BrainViewState {
  dockOpen: boolean;
  hudOpen: boolean;
  railOpen: boolean;
  drawerOpen: boolean;
}

export interface ProjectRegion {
  project: string;
  label: string;
  hemisphere: "left" | "right" | "center";
  x: number;
  y: number;
  color: string;
  nodeCount: number;
}

export interface NodeVisualState {
  fillColor: string;
  borderColor: string;
  borderWidth: number;
  glowOpacity: number;
  glowBlur: number;
  opacity: number;
  labelVisible: boolean;
}

export interface EdgeVisualState {
  color: string;
  width: number;
  opacity: number;
  lineStyle: "solid" | "dashed";
}

export interface GraphSubgraphRequestPayload {
  project: string;
  mode: GraphMode;
  query?: string;
  center_memory_id?: string;
  scope: GraphScope;
  memory_type?: string;
  tags: string[];
  depth: number;
  node_limit: number;
  edge_limit: number;
  min_weight: number;
  include_inactive: boolean;
}
