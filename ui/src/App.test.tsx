import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import {
  fetchGraphFacets,
  fetchGraphMetrics,
  fetchGraphSubgraph,
  fetchMemoryDetail,
} from "./api";

vi.mock("cytoscape", () => {
  const run = vi.fn();
  const collection = {
    remove: vi.fn(),
    removeClass: vi.fn(),
    addClass: vi.fn(),
  };
  const node = {
    addClass: vi.fn(),
  };
  const cy = {
    elements: vi.fn(() => collection),
    add: vi.fn(),
    layout: vi.fn(() => ({ run })),
    batch: vi.fn((callback: () => void) => callback()),
    nodes: vi.fn(() => collection),
    $id: vi.fn(() => node),
    animate: vi.fn(),
    on: vi.fn(),
    destroy: vi.fn(),
  };
  const factory = Object.assign(vi.fn(() => cy), { use: vi.fn() });
  return { default: factory };
});

vi.mock("cytoscape-fcose", () => ({ default: {} }));

vi.mock("./api", () => ({
  fetchGraphFacets: vi.fn(),
  fetchGraphMetrics: vi.fn(),
  fetchGraphSubgraph: vi.fn(),
  fetchMemoryDetail: vi.fn(),
}));

const FACETS_FIXTURE = {
  project: "atlas",
  projects: [
    { project: "atlas", memory_count: 24, pinned_memory_count: 4 },
    { project: "iris", memory_count: 12, pinned_memory_count: 1 },
  ],
  memory_types: [
    { memory_type: "architecture", count: 10 },
    { memory_type: "decision", count: 8 },
  ],
  top_tags: [
    { tag: "incident/retry", count: 6 },
    { tag: "concept/event-sourcing", count: 5 },
  ],
  hot_memories: [
    {
      memory_id: "a",
      project: "atlas",
      memory_type: "architecture",
      content_preview: "Event sourcing blueprint",
      tags: ["concept/event-sourcing", "backend/event-log"],
      manual_pin: true,
      prominence: 0.89,
    },
    {
      memory_id: "b",
      project: "atlas",
      memory_type: "decision",
      content_preview: "Replayable projections",
      tags: ["incident/retry"],
      manual_pin: false,
      prominence: 0.71,
    },
  ],
  generated_at: "2030-01-01T00:00:00+00:00",
};

const METRICS_FIXTURE = {
  project: "atlas",
  memory_count: 24,
  relation_count: 40,
  active_relation_count: 34,
  pinned_memory_count: 4,
  hot_memory_count: 9,
  avg_activation_score: 0.62,
  avg_stability_score: 0.73,
  bridge_count: 2,
  top_memory_types: [
    { memory_type: "architecture", count: 10 },
    { memory_type: "decision", count: 8 },
  ],
  generated_at: "2030-01-01T00:00:00+00:00",
};

const SUBGRAPH_FIXTURE = {
  nodes: [
    {
      memory_id: "a",
      project: "atlas",
      memory_type: "architecture",
      content_preview: "Event sourcing blueprint",
      tags: ["concept/event-sourcing"],
      activation_score: 0.82,
      stability_score: 0.88,
      access_count: 4,
      manual_pin: true,
      prominence: 0.89,
    },
    {
      memory_id: "b",
      project: "atlas",
      memory_type: "decision",
      content_preview: "Replayable projections",
      tags: ["incident/retry"],
      activation_score: 0.64,
      stability_score: 0.74,
      access_count: 3,
      manual_pin: false,
      prominence: 0.71,
    },
  ],
  edges: [
    {
      source_memory_id: "a",
      target_memory_id: "b",
      relation_type: "same_concept",
      weight: 0.91,
      origin: "manual",
      active: true,
      reinforcement_count: 3,
      last_activated_at: "2030-01-01T00:00:00+00:00",
    },
  ],
  summary: {
    mode: "project_hot" as const,
    project: "atlas",
    scope: "project" as const,
    node_count: 2,
    edge_count: 1,
    seed_count: 2,
    requested_node_limit: 24,
    requested_edge_limit: 72,
    truncated_nodes: false,
    truncated_edges: false,
    allowed_projects: ["atlas"],
  },
};

const DETAIL_FIXTURE = {
  memory: {
    memory_id: "b",
    project: "atlas",
    agent_id: "agent-1",
    memory_type: "decision",
    summary: "Projection trade-offs",
    content: "Contenido del scheduler mental",
    content_preview: "Replayable projections",
    importance: 0.8,
    tags: ["incident/retry", "ops/recovery"],
    access_count: 7,
    last_accessed_at: "2030-01-02T00:00:00+00:00",
    activation_score: 0.64,
    stability_score: 0.74,
    manual_pin: false,
    prominence: 0.71,
  },
  relation_count: 1,
  relations: [
    {
      id: "rel-1",
      source_memory_id: "b",
      target_memory_id: "a",
      relation_type: "same_concept",
      weight: 0.91,
      origin: "manual",
      reinforcement_count: 3,
      last_activated_at: "2030-01-01T00:00:00+00:00",
      active: true,
      other_memory_id: "a",
      other_summary: "Event sourcing blueprint",
      other_project: "atlas",
    },
  ],
};

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchGraphFacets).mockImplementation(async () => FACETS_FIXTURE);
    vi.mocked(fetchGraphMetrics).mockImplementation(async () => METRICS_FIXTURE);
    vi.mocked(fetchGraphSubgraph).mockImplementation(async () => SUBGRAPH_FIXTURE);
    vi.mocked(fetchMemoryDetail).mockImplementation(async () => DETAIL_FIXTURE);
  });

  it("opens and closes the drawer from hot memory navigation", async () => {
    render(<App />);

    const memoryButton = await screen.findByRole("button", {
      name: /Replayable projections/i,
    });
    fireEvent.click(memoryButton);

    expect(await screen.findByRole("button", { name: /Cerrar/i })).toBeInTheDocument();
    expect(screen.getByText(/Contenido del scheduler mental/i)).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /Cerrar/i })).not.toBeInTheDocument();
    });
  });

  it("applies project filters from the dock and tag filters from the drawer", async () => {
    render(<App />);

    const projectSelect = await screen.findByLabelText(/Proyecto/i);
    fireEvent.change(projectSelect, { target: { value: "iris" } });

    await waitFor(() => {
      expect(fetchGraphSubgraph).toHaveBeenLastCalledWith(
        expect.objectContaining({ project: "iris" }),
      );
    });

    fireEvent.click(
      await screen.findByRole("button", { name: /Replayable projections/i }),
    );
    const drawer = await screen.findByRole("complementary", { name: /Detalle de neurona/i });
    fireEvent.click(await within(drawer).findByRole("button", { name: /incident\/retry/i }));

    await waitFor(() => {
      expect(fetchGraphSubgraph).toHaveBeenLastCalledWith(
        expect.objectContaining({ tags: ["incident/retry"] }),
      );
    });
  });

  it("recenters the graph from the drawer focus action", async () => {
    render(<App />);

    fireEvent.click(
      await screen.findByRole("button", { name: /Replayable projections/i }),
    );
    const drawer = await screen.findByRole("complementary", { name: /Detalle de neurona/i });
    fireEvent.click(await within(drawer).findByRole("button", { name: /Centrar neurona/i }));

    await waitFor(() => {
      expect(fetchGraphSubgraph).toHaveBeenLastCalledWith(
        expect.objectContaining({
          mode: "memory_focus",
          center_memory_id: "b",
        }),
      );
    });
  });
});
