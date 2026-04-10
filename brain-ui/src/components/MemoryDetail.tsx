import { useState, useEffect } from "react";
import { fetchMemoryDetail } from "../api/client";
import type { MemoryDetailResponse, GraphNode, GraphEdge } from "../types";
import { getNodeColor } from "../utils/nodeStyle";
import styles from "./MemoryDetail.module.css";

interface MemoryDetailProps {
  node: GraphNode;
  edges: GraphEdge[];
  graphNodes: GraphNode[];
  onClose: () => void;
  onNodeNavigate: (memoryId: string) => void;
  onRelationHover: (memoryId: string | null) => void;
  onKeyphraseClick: (keyword: string) => void;
}

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffH = Math.floor(diffMs / 3_600_000);
  if (diffH < 1) return "< 1h ago";
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 30) return `${diffD}d ago`;
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" });
}

const TIER_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: "T1", color: "#ff6b6b" },
  2: { label: "T2", color: "#ffd93d" },
  3: { label: "T3", color: "#a78bfa" },
};

const RELATION_TYPE_COLORS: Record<string, string> = {
  same_concept: "#4ecdc4",
  supports: "#54a0ff",
  extends: "#a78bfa",
  derived_from: "#ffd93d",
  applies_to: "#ff9ff3",
};

export default function MemoryDetail({
  node,
  edges,
  graphNodes,
  onClose,
  onNodeNavigate,
  onRelationHover,
  onKeyphraseClick,
}: MemoryDetailProps) {
  const [detail, setDetail] = useState<MemoryDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoveredRelation, setHoveredRelation] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setDetail(null);
    fetchMemoryDetail(node.memory_id)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [node.memory_id]);

  const color = getNodeColor(node);

  // Build relations from graph edges
  const relations = edges
    .filter((e) => e.source_memory_id === node.memory_id || e.target_memory_id === node.memory_id)
    .map((e) => {
      const targetId = e.source_memory_id === node.memory_id ? e.target_memory_id : e.source_memory_id;
      const targetNode = graphNodes.find((n) => n.memory_id === targetId);
      return { edge: e, targetId, targetNode };
    })
    .filter((r) => r.targetNode);

  if (loading) {
    return (
      <div className={styles.sidebar}>
        <div className={styles.loading}>Loading...</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className={styles.sidebar}>
        <div className={styles.loading}>Failed to load</div>
      </div>
    );
  }

  const m = detail.memory;
  const headerText = m.summary || m.content_preview;
  const fullContent = m.content || m.content_preview;
  const showContent = fullContent !== headerText;

  return (
    <div className={styles.sidebar}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.colorDot} style={{ background: color }} />
        <div className={styles.headerText}>
          <div className={styles.title}>{headerText}</div>
          <div className={styles.projectLabel}>{m.project}</div>
        </div>
        <button className={styles.closeBtn} onClick={onClose}>{"\u2715"}</button>
      </div>

      {/* Memory type badge */}
      <div className={styles.badges}>
        <span className={`${styles.badge} ${styles.badgeType}`}>{m.memory_type}</span>
        {m.tags.map((t) => (
          <span key={t} className={`${styles.badge} ${styles.badgeTag}`}>{t}</span>
        ))}
      </div>

      {/* Full content (only if different from header) */}
      {showContent && (
        <div className={styles.content}>{fullContent}</div>
      )}

      {/* Keyphrases */}
      {m.keyphrases && m.keyphrases.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionLabel}>Keyphrases</div>
          <div className={styles.keyphrases}>
            {m.keyphrases.map((kp) => (
              <button
                key={kp}
                className={styles.keyphrase}
                onClick={() => onKeyphraseClick(kp)}
              >
                {kp}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Scores Grid */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>Metrics</div>
        <div className={styles.scoreGrid}>
          <ScoreBar label="Activation" value={m.activation_score} color="#ff6b6b" />
          <ScoreBar label="Stability" value={m.stability_score} color="#4ecdc4" />
          <ScoreBar label="Importance" value={m.importance} color="#a78bfa" />
          <ScoreBar label="Novelty" value={m.novelty_score} color="#54a0ff" />
          <ScoreBar label="Prominence" value={m.prominence} color="#ffd93d" />
        </div>
      </div>

      {/* Emotional Axes */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>Emotional Axes</div>
        <div className={styles.emotionRow}>
          <span className={styles.emotionLabel}>Valence</span>
          <div className={styles.valenceBar}>
            <div
              className={styles.valenceMarker}
              style={{ left: `${((m.valence + 1) / 2) * 100}%` }}
            />
          </div>
          <span className={styles.emotionValue}>{m.valence > 0 ? "+" : ""}{m.valence.toFixed(2)}</span>
        </div>
        <div className={styles.emotionRow}>
          <span className={styles.emotionLabel}>Arousal</span>
          <div className={styles.arousalBar}>
            <div
              className={styles.arousalFill}
              style={{ width: `${m.arousal * 100}%` }}
            />
          </div>
          <span className={styles.emotionValue}>{m.arousal.toFixed(2)}</span>
        </div>
      </div>

      {/* Ebbinghaus Decay */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>Ebbinghaus Decay</div>
        <div className={styles.decayBar}>
          <div className={styles.decayFill} style={{ width: `${m.stability_score * 100}%` }} />
        </div>
        <div className={styles.decayMeta}>
          <span>Halflife: {m.stability_halflife_days.toFixed(1)}d</span>
          <span>Reviews: {m.review_count}</span>
        </div>
      </div>

      {/* Relations */}
      {relations.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionLabel}>Relations ({relations.length})</div>
          <div className={styles.relationList}>
            {relations.map(({ edge, targetId, targetNode }) => {
              const tier = edge.evidence_json?.tier;
              const tierInfo = tier ? TIER_LABELS[tier] : null;
              const relColor = RELATION_TYPE_COLORS[edge.relation_type] ?? "#666";
              const isHovered = hoveredRelation === targetId;

              return (
                <div
                  key={targetId}
                  className={`${styles.relationItem} ${isHovered ? styles.relationHovered : ""}`}
                  onMouseEnter={() => {
                    setHoveredRelation(targetId);
                    onRelationHover(targetId);
                  }}
                  onMouseLeave={() => {
                    setHoveredRelation(null);
                    onRelationHover(null);
                  }}
                  onClick={() => onNodeNavigate(targetId)}
                >
                  <div className={styles.relationBadges}>
                    <span className={styles.relationTypeBadge} style={{ borderColor: relColor, color: relColor }}>
                      {edge.relation_type}
                    </span>
                    {tierInfo && (
                      <span className={styles.tierBadge} style={{ background: tierInfo.color }}>
                        {tierInfo.label}
                      </span>
                    )}
                  </div>
                  <div className={styles.relationPreview}>
                    {targetNode!.content_preview}
                  </div>
                  <div className={`${styles.relationTooltip} ${isHovered ? styles.relationTooltipVisible : ""}`}>
                    <div>Weight: {edge.weight.toFixed(3)}</div>
                    {edge.myelin_score > 0 && <div>Myelin: {edge.myelin_score.toFixed(3)}</div>}
                    <div>Reinforced: {edge.reinforcement_count}x</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Metadata footer */}
      <div className={styles.metaList}>
        <div className={styles.metaRow}>
          <span>Accesses</span><span className={styles.metaValue}>{m.access_count}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Last accessed</span><span className={styles.metaValue}>{formatDate(m.last_accessed_at)}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Abstraction</span><span className={styles.metaValue}>Level {m.abstraction_level}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Pinned</span>
          <span className={m.manual_pin ? styles.metaHighlight : styles.metaValue}>
            {m.manual_pin ? "Yes" : "No"}
          </span>
        </div>
      </div>
    </div>
  );
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={styles.scoreItem}>
      <div className={styles.scoreHeader}>
        <span className={styles.scoreLabel}>{label}</span>
        <span className={styles.scoreNum} style={{ color }}>{value.toFixed(2)}</span>
      </div>
      <div className={styles.scoreBarTrack}>
        <div className={styles.scoreBarFill} style={{ width: `${value * 100}%`, background: color }} />
      </div>
    </div>
  );
}
