import { useState, useEffect, useCallback, useRef } from "react";
import { fetchSubgraph, fetchFacets } from "./api/client";
import type { GraphNode, GraphEdge, FacetProject, SubgraphResponse } from "./types";
import type { TabId } from "./components/TabSwitcher";
import TopBar from "./components/TopBar";
import StatsBar from "./components/StatsBar";
import BrainGraph from "./components/BrainGraph";
import MemoryDetail from "./components/MemoryDetail";
import HealthView from "./components/HealthView";
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

function filterByKeyword(
  nodes: GraphNode[],
  edges: GraphEdge[],
  keyword: string
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  if (!keyword) return { nodes, edges };
  const lower = keyword.toLowerCase();
  const matchingNodes = nodes.filter(
    (n) =>
      n.content_preview.toLowerCase().includes(lower) ||
      n.tags.some((t) => t.toLowerCase().includes(lower)) ||
      n.memory_type.toLowerCase().includes(lower) ||
      n.project.toLowerCase().includes(lower) ||
      (n.keyphrases ?? []).some((kp) => kp.toLowerCase().includes(lower))
  );
  const nodeIds = new Set(matchingNodes.map((n) => n.memory_id));
  const matchingEdges = edges.filter(
    (e) => nodeIds.has(e.source_memory_id) && nodeIds.has(e.target_memory_id)
  );
  return { nodes: matchingNodes, edges: matchingEdges };
}

export default function App() {
  const [projects, setProjects] = useState<FacetProject[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<Set<string>>(new Set());
  const [allNodes, setAllNodes] = useState<GraphNode[]>([]);
  const [allEdges, setAllEdges] = useState<GraphEdge[]>([]);
  const [keyword, setKeyword] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("graph");
  const [externalHoveredNodeId, setExternalHoveredNodeId] = useState<string | null>(null);
  const projectsRef = useRef<FacetProject[]>([]);

  const loadGraph = useCallback(
    async (selected: Set<string>, projectList?: FacetProject[]) => {
      const available = projectList || projectsRef.current;
      setLoading(true);
      setError(null);
      try {
        const targetProjects =
          selected.size === 0
            ? available.map((p) => p.project)
            : [...selected];

        if (targetProjects.length === 0) {
          setAllNodes([]);
          setAllEdges([]);
          return;
        }

        const results = await Promise.all(
          targetProjects.map((p) =>
            fetchSubgraph({ project: p, scope: "bridged" })
          )
        );
        const merged = mergeSubgraphs(results);
        setAllNodes(merged.nodes);
        setAllEdges(merged.edges);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load graph");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchFacets();
        setProjects(data.projects);
        projectsRef.current = data.projects;
        await loadGraph(new Set(), data.projects);
      } catch {
        setError("Failed to connect to API");
        setLoading(false);
      }
    })();
  }, [loadGraph]);

  const handleProjectChange = (next: Set<string>) => {
    setSelectedProjects(next);
    setSelectedNode(null);
    loadGraph(next);
  };

  const handleKeywordChange = (kw: string) => {
    setKeyword(kw);
  };

  const handleNodeNavigate = (memoryId: string) => {
    const node = allNodes.find((n) => n.memory_id === memoryId);
    if (node) setSelectedNode(node);
  };

  const { nodes, edges } = filterByKeyword(allNodes, allEdges, keyword);
  const projectList = projects.map((p) => p.project);

  return (
    <div className={styles.app}>
      <TopBar
        projects={projects}
        selectedProjects={selectedProjects}
        onProjectChange={handleProjectChange}
        keyword={keyword}
        onKeywordChange={handleKeywordChange}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {activeTab === "graph" && (
        <>
          <StatsBar
            nodes={nodes}
            edges={edges}
            totalNodes={allNodes.length}
            totalEdges={allEdges.length}
            keyword={keyword}
          />
          <div className={styles.main}>
            {loading ? (
              <div className={styles.loading}>Loading brain...</div>
            ) : error ? (
              <div className={styles.error}>
                <span>{error}</span>
                <button className={styles.retryBtn} onClick={() => loadGraph(selectedProjects)}>
                  Retry
                </button>
              </div>
            ) : (
              <BrainGraph
                nodes={nodes}
                edges={edges}
                projectList={projectList}
                selectedProject={selectedProjects.size === 1 ? [...selectedProjects][0] : null}
                selectedProjects={selectedProjects}
                onNodeClick={setSelectedNode}
                onBackgroundClick={() => setSelectedNode(null)}
                externalHoveredNodeId={externalHoveredNodeId}
              />
            )}
            {selectedNode && (
              <MemoryDetail
                node={selectedNode}
                edges={edges}
                graphNodes={nodes}
                onClose={() => setSelectedNode(null)}
                onNodeNavigate={handleNodeNavigate}
                onRelationHover={setExternalHoveredNodeId}
                onKeyphraseClick={(kp) => handleKeywordChange(kp)}
              />
            )}
          </div>
        </>
      )}

      {activeTab === "health" && (
        <div className={styles.main}>
          <HealthView />
        </div>
      )}
    </div>
  );
}
