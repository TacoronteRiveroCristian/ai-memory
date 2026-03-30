import { describe, expect, it } from "vitest";

import { buildCytoscapeElements, buildSubgraphRequest, sanitizeTagsInput } from "./graph";
import type { GraphControlsState, GraphSubgraphResponse } from "./types";

describe("graph helpers", () => {
  it("normalizes tag input and builds filtered payloads", () => {
    const controls: GraphControlsState = {
      project: "demo",
      mode: "memory_focus",
      query: "ignored here",
      scope: "bridged",
      memoryType: "architecture",
      tagsInput: "concept/event-sourcing, tech/postgres , ",
      nodeLimit: 99,
      edgeLimit: 320,
      includeInactive: true,
      centerMemoryId: "",
    };

    expect(sanitizeTagsInput(controls.tagsInput)).toEqual([
      "concept/event-sourcing",
      "tech/postgres",
    ]);
    expect(buildSubgraphRequest(controls, "memory-123")).toEqual({
      project: "demo",
      mode: "memory_focus",
      scope: "bridged",
      memory_type: "architecture",
      tags: ["concept/event-sourcing", "tech/postgres"],
      depth: 1,
      node_limit: 80,
      edge_limit: 200,
      min_weight: 0.18,
      include_inactive: true,
      center_memory_id: "memory-123",
    });
  });

  it("maps graph data into cytoscape elements", () => {
    const graph: GraphSubgraphResponse = {
      nodes: [
        {
          memory_id: "a",
          project: "demo",
          memory_type: "architecture",
          content_preview: "Event sourcing",
          tags: ["concept/event-sourcing"],
          activation_score: 0.8,
          stability_score: 0.9,
          access_count: 4,
          manual_pin: true,
          prominence: 0.88,
        },
        {
          memory_id: "b",
          project: "demo",
          memory_type: "architecture",
          content_preview: "Replayable projections",
          tags: ["concept/event-sourcing"],
          activation_score: 0.7,
          stability_score: 0.85,
          access_count: 3,
          manual_pin: false,
          prominence: 0.72,
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
        mode: "search",
        project: "demo",
        scope: "project",
        node_count: 2,
        edge_count: 1,
        seed_count: 2,
        requested_node_limit: 4,
        requested_edge_limit: 4,
        truncated_nodes: false,
        truncated_edges: false,
        allowed_projects: ["demo"],
      },
    };

    const elements = buildCytoscapeElements(graph, "a");
    expect(elements).toHaveLength(3);
    expect(elements[0]?.classes).toContain("selected-node");
    expect(elements[0]?.classes).toContain("manual-pin");
    expect(elements[2]?.classes).toContain("manual-edge");
  });
});
