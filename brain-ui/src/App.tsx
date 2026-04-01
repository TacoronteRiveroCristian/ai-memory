import { useState, useEffect, useCallback } from "react";
import { fetchSubgraph, fetchFacets } from "./api/client";
import type { GraphNode, GraphEdge, FacetProject } from "./types";
import TopBar from "./components/TopBar";
import BrainGraph from "./components/BrainGraph";
import MemoryDetail from "./components/MemoryDetail";
import styles from "./App.module.css";

export default function App() {
  const [projects, setProjects] = useState<FacetProject[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadGraph = useCallback(async (project: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSubgraph({
        project: project ?? undefined,
        scope: project ? "local" : "global",
      });
      setNodes(data.nodes);
      setEdges(data.edges);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFacets = useCallback(async () => {
    try {
      const data = await fetchFacets();
      setProjects(data.projects);
    } catch {
      // Non-critical — project selector will be empty
    }
  }, []);

  useEffect(() => {
    loadFacets();
    loadGraph(null);
  }, [loadFacets, loadGraph]);

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
