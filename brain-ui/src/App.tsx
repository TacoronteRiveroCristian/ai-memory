import { useState, useEffect, useCallback, useRef } from "react";
import { fetchSubgraph, fetchFacets } from "./api/client";
import type { GraphNode, GraphEdge, FacetProject, SubgraphResponse } from "./types";
import TopBar from "./components/TopBar";
import BrainGraph from "./components/BrainGraph";
import MemoryDetail from "./components/MemoryDetail";
import styles from "./App.module.css";

function mergeSubgraphs(responses: SubgraphResponse[]): {
  nodes: GraphNode[];
  edges: GraphEdge[];
} {
  const nodeMap = new Map<string, GraphNode>();
  const edgeSet = new Set<string>();
  const edges: GraphEdge[] = [];

  for (const r of responses) {
    for (const n of r.nodes) {
      if (!nodeMap.has(n.memory_id)) nodeMap.set(n.memory_id, n);
    }
    for (const e of r.edges) {
      const key = `${e.source_memory_id}-${e.target_memory_id}`;
      if (!edgeSet.has(key)) {
        edgeSet.add(key);
        edges.push(e);
      }
    }
  }

  return { nodes: Array.from(nodeMap.values()), edges };
}

export default function App() {
  const [projects, setProjects] = useState<FacetProject[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const projectsRef = useRef<FacetProject[]>([]);

  const loadGraph = useCallback(async (project: string | null, projectList?: FacetProject[]) => {
    const available = projectList || projectsRef.current;
    setLoading(true);
    setError(null);
    try {
      if (project) {
        // Single project
        const data = await fetchSubgraph({ project, scope: "bridged" });
        setNodes(data.nodes);
        setEdges(data.edges);
      } else if (available.length > 0) {
        // All projects: top 5 by memory count, bridged scope, then merge
        const top = [...available]
          .sort((a, b) => b.memory_count - a.memory_count)
          .slice(0, 5);
        const results = await Promise.all(
          top.map((p) =>
            fetchSubgraph({ project: p.project, scope: "bridged" })
          )
        );
        const merged = mergeSubgraphs(results);
        setNodes(merged.nodes);
        setEdges(merged.edges);
      } else {
        setNodes([]);
        setEdges([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchFacets();
        setProjects(data.projects);
        projectsRef.current = data.projects;
        await loadGraph(null, data.projects);
      } catch {
        setError("Failed to connect to API");
        setLoading(false);
      }
    })();
  }, [loadGraph]);

  const handleProjectChange = (project: string | null) => {
    setSelectedProject(project);
    setSelectedNode(null);
    loadGraph(project);
  };

  const projectList = projects.map((p) => p.project);

  return (
    <div className={styles.app}>
      <TopBar
        projects={projects}
        selectedProject={selectedProject}
        onProjectChange={handleProjectChange}
      />
      <div className={styles.main}>
        {loading ? (
          <div className={styles.loading}>Loading brain...</div>
        ) : error ? (
          <div className={styles.error}>
            <span>{error}</span>
            <button
              className={styles.retryBtn}
              onClick={() => loadGraph(selectedProject)}
            >
              Retry
            </button>
          </div>
        ) : (
          <BrainGraph
            nodes={nodes}
            edges={edges}
            projectList={projectList}
            selectedProject={selectedProject}
            onNodeClick={setSelectedNode}
            onBackgroundClick={() => setSelectedNode(null)}
          />
        )}
        {selectedNode && (
          <MemoryDetail
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
}
