import type { GraphNode, GraphEdge } from "../types";
import styles from "./StatsBar.module.css";

interface StatsBarProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  totalNodes: number;
  totalEdges: number;
  filtered: boolean;
}

export default function StatsBar({ nodes, edges, totalNodes, totalEdges: _totalEdges, filtered }: StatsBarProps) {
  const decaying = nodes.filter((n) => n.stability_score < 0.3).length;
  const hot = nodes.filter((n) => n.activation_score > 0.7).length;
  const pinned = nodes.filter((n) => n.manual_pin).length;

  return (
    <div className={styles.bar}>
      <span className={styles.stat}>
        <span className={styles.num}>{nodes.length}</span> nodes
        <span className={styles.sep}>&middot;</span>
        <span className={styles.num}>{edges.length}</span> edges
      </span>

      <span className={styles.divider}>|</span>

      {decaying > 0 && (
        <span className={`${styles.stat} ${styles.decaying}`}>
          <span className={styles.num}>{decaying}</span> decaying
        </span>
      )}
      {hot > 0 && (
        <span className={`${styles.stat} ${styles.hot}`}>
          <span className={styles.hotDot} />
          <span className={styles.num}>{hot}</span> hot
        </span>
      )}
      {pinned > 0 && (
        <span className={`${styles.stat} ${styles.pinned}`}>
          <span className={styles.num}>{pinned}</span> pinned
        </span>
      )}

      {filtered && (
        <>
          <span className={styles.divider}>|</span>
          <span className={styles.stat}>
            Showing <span className={styles.num}>{nodes.length}</span> of{" "}
            <span className={styles.num}>{totalNodes}</span>
          </span>
        </>
      )}
    </div>
  );
}
