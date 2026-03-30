import type {
  GraphMetrics,
  GraphSubgraphRequestPayload,
  GraphSubgraphResponse,
  MemoryDetailResponse,
} from "./types";

const API_BASE = "/brain-api";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchGraphMetrics(project: string): Promise<GraphMetrics> {
  const query = new URLSearchParams();
  if (project.trim()) {
    query.set("project", project.trim());
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return readJson<GraphMetrics>(await fetch(`${API_BASE}/api/graph/metrics${suffix}`));
}

export async function fetchGraphSubgraph(
  payload: GraphSubgraphRequestPayload,
): Promise<GraphSubgraphResponse> {
  return readJson<GraphSubgraphResponse>(
    await fetch(`${API_BASE}/api/graph/subgraph`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function fetchMemoryDetail(memoryId: string): Promise<MemoryDetailResponse> {
  return readJson<MemoryDetailResponse>(await fetch(`${API_BASE}/api/memories/${memoryId}`));
}
