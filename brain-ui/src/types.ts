export interface GraphNode {
  memory_id: string;
  project: string;
  memory_type: string;
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
  origin: "manual" | "vector_inference";
  active: boolean;
  reinforcement_count: number;
  last_activated_at: string | null;
}

export interface GraphSummary {
  mode: string;
  project: string | null;
  scope: string;
  query: string | null;
  center_memory_id: string | null;
  node_count: number;
  edge_count: number;
  seed_count: number;
  requested_node_limit: number;
  requested_edge_limit: number;
  truncated_nodes: boolean;
  truncated_edges: boolean;
  allowed_projects: string[];
}

export interface SubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: GraphSummary;
}

export interface FacetProject {
  project: string;
  memory_count: number;
  pinned_memory_count: number;
}

export interface FacetsResponse {
  project: string | null;
  projects: FacetProject[];
  memory_types: { memory_type: string; count: number }[];
  top_tags: { tag: string; count: number }[];
  hot_memories: GraphNode[];
  generated_at: string;
}

export interface MemoryDetailResponse {
  memory: {
    memory_id: string;
    project: string;
    agent_id: string;
    memory_type: string;
    summary: string;
    content: string;
    content_preview: string;
    importance: number;
    tags: string[];
    access_count: number;
    last_accessed_at: string | null;
    activation_score: number;
    stability_score: number;
    manual_pin: boolean;
    prominence: number;
    review_count: number;
    stability_halflife_days: number;
    valence: number;
    arousal: number;
    novelty_score: number;
    abstraction_level: number;
  };
  relation_count: number;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  test_mode: boolean;
}
