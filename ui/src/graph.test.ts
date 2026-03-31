import { describe, expect, it } from "vitest";

import {
  buildCytoscapeElements,
  buildProjectRegions,
  buildSubgraphRequest,
  deriveEdgeVisualState,
  deriveNodeVisualState,
  sanitizeTagsInput,
  shouldShowNodeLabel,
} from "./graph";
import type { GraphControlsState, GraphSubgraphResponse, ProjectRegion } from "./types";

const GRAPH_FIXTURE: GraphSubgraphResponse = {
  nodes: [
    {
      memory_id: "a",
      project: "atlas",
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
      project: "atlas",
      memory_type: "decision",
      content_preview: "Replayable projections",
      tags: ["concept/event-sourcing"],
      activation_score: 0.7,
      stability_score: 0.85,
      access_count: 3,
      manual_pin: false,
      prominence: 0.72,
    },
    {
      memory_id: "c",
      project: "iris",
      memory_type: "error",
      content_preview: "Worker crash loop",
      tags: ["incident/retry"],
      activation_score: 0.35,
      stability_score: 0.42,
      access_count: 1,
      manual_pin: false,
      prominence: 0.24,
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
    {
      source_memory_id: "b",
      target_memory_id: "c",
      relation_type: "follow_up",
      weight: 0.21,
      origin: "system",
      active: false,
      reinforcement_count: 1,
      last_activated_at: null,
    },
  ],
  summary: {
    mode: "search",
    project: "atlas",
    scope: "project",
    node_count: 3,
    edge_count: 2,
    seed_count: 2,
    requested_node_limit: 4,
    requested_edge_limit: 4,
    truncated_nodes: false,
    truncated_edges: false,
    allowed_projects: ["atlas"],
  },
};

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

  it("assigns project regions deterministically and prioritizes the active project", () => {
    const regions = buildProjectRegions(GRAPH_FIXTURE, "iris");
    expect(regions.map((region) => region.project)).toEqual(["iris", "atlas"]);
    expect(regions[0]).toMatchObject({
      project: "iris",
      hemisphere: "left",
      color: "#6eb6ff",
      nodeCount: 1,
    });
    expect(regions[1]?.project).toBe("atlas");
  });

  it("computes label visibility and node visual intensity from scores", () => {
    const region: ProjectRegion = {
      project: "atlas",
      label: "atlas",
      hemisphere: "left",
      x: 0.28,
      y: 0.18,
      color: "#6eb6ff",
      nodeCount: 2,
    };

    expect(shouldShowNodeLabel(GRAPH_FIXTURE.nodes[0])).toBe(true);
    expect(
      shouldShowNodeLabel(GRAPH_FIXTURE.nodes[2], {
        hoveredMemoryId: "c",
      }),
    ).toBe(true);

    const visual = deriveNodeVisualState(GRAPH_FIXTURE.nodes[0], region, {
      selectedMemoryId: "a",
    });
    expect(visual.borderWidth).toBeGreaterThan(3);
    expect(visual.labelVisible).toBe(true);
    expect(visual.glowOpacity).toBeGreaterThan(0.7);
  });

  it("maps graph data into styled cytoscape elements", () => {
    const projectRegions = buildProjectRegions(GRAPH_FIXTURE, "atlas");
    const elements = buildCytoscapeElements(GRAPH_FIXTURE, { projectRegions });
    expect(elements).toHaveLength(5);
    expect(elements[0]?.classes).toContain("manual-pin");
    expect(elements[0]?.position).toBeDefined();
    expect(elements[0]?.data).toMatchObject({
      project: "atlas",
      projectColor: "#6eb6ff",
    });
    expect(elements[3]?.classes).toContain("manual-edge");
    expect(elements[4]?.classes).toContain("dashed-edge");
  });

  it("derives inactive edge visuals with reduced opacity", () => {
    const atlasRegion: ProjectRegion = {
      project: "atlas",
      label: "atlas",
      hemisphere: "left",
      x: 0.28,
      y: 0.18,
      color: "#6eb6ff",
      nodeCount: 2,
    };
    const irisRegion: ProjectRegion = {
      project: "iris",
      label: "iris",
      hemisphere: "right",
      x: 0.72,
      y: 0.18,
      color: "#49dfb5",
      nodeCount: 1,
    };

    const visual = deriveEdgeVisualState(GRAPH_FIXTURE.edges[1], atlasRegion, irisRegion);
    expect(visual.lineStyle).toBe("dashed");
    expect(visual.opacity).toBeLessThan(0.3);
  });
});
