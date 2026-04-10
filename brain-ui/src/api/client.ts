import type {
  SubgraphResponse,
  FacetsResponse,
  MemoryDetailResponse,
  HealthResponse,
  BrainHealthResponse,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8050";
const API_KEY = import.meta.env.VITE_API_KEY || "";

const headers: HeadersInit = {
  "Content-Type": "application/json",
  "X-API-Key": API_KEY,
};

export async function fetchSubgraph(params: {
  project?: string;
  scope?: string;
  mode?: string;
  node_limit?: number;
  edge_limit?: number;
}): Promise<SubgraphResponse> {
  const body = {
    mode: params.mode || "project_hot",
    scope: params.scope || "global",
    project: params.project || null,
    node_limit: params.node_limit || 80,
    edge_limit: params.edge_limit || 200,
  };
  const res = await fetch(`${API_URL}/api/graph/subgraph`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`subgraph failed: ${res.status}`);
  return res.json();
}

export async function fetchFacets(): Promise<FacetsResponse> {
  const res = await fetch(`${API_URL}/api/graph/facets`, { headers });
  if (!res.ok) throw new Error(`facets failed: ${res.status}`);
  return res.json();
}

export async function fetchMemoryDetail(
  memoryId: string
): Promise<MemoryDetailResponse> {
  const res = await fetch(`${API_URL}/api/memories/${memoryId}`, { headers });
  if (!res.ok) throw new Error(`memory detail failed: ${res.status}`);
  return res.json();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error(`health failed: ${res.status}`);
  return res.json();
}

export async function fetchBrainHealth(): Promise<BrainHealthResponse> {
  const res = await fetch(`${API_URL}/brain/health`, { headers });
  if (!res.ok) throw new Error(`brain health failed: ${res.status}`);
  return res.json();
}

export async function deleteProject(name: string): Promise<{ result: string; project: string; memories_deleted: number }> {
  const res = await fetch(`${API_URL}/api/projects/${encodeURIComponent(name)}`, {
    method: "DELETE",
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: `Delete failed: ${res.status}` }));
    throw new Error(body.detail || `Delete failed: ${res.status}`);
  }
  return res.json();
}
