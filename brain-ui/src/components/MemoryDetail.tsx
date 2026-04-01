import { useState, useEffect } from "react";
import { fetchMemoryDetail } from "../api/client";
import type { MemoryDetailResponse, GraphNode } from "../types";
import { getNodeColor } from "../utils/nodeStyle";
import styles from "./MemoryDetail.module.css";

interface MemoryDetailProps {
  node: GraphNode;
  onClose: () => void;
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
  return d.toLocaleDateString("en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function valenceLabel(v: number): string {
  if (v > 0.2) return `+${v.toFixed(2)} (positive)`;
  if (v < -0.2) return `${v.toFixed(2)} (negative)`;
  return `${v.toFixed(2)} (neutral)`;
}

export default function MemoryDetail({ node, onClose }: MemoryDetailProps) {
  const [detail, setDetail] = useState<MemoryDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setDetail(null);
    fetchMemoryDetail(node.memory_id)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [node.memory_id]);

  const color = getNodeColor(node);

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

  return (
    <div className={styles.sidebar}>
      <div className={styles.header}>
        <div className={styles.colorDot} style={{ background: color }} />
        <div className={styles.title}>{m.summary}</div>
        <button className={styles.closeBtn} onClick={onClose}>
          &#x2715;
        </button>
      </div>

      <div className={styles.badges}>
        <span className={`${styles.badge} ${styles.badgeType}`}>
          {m.memory_type}
        </span>
        {m.tags.map((t) => (
          <span key={t} className={styles.badge}>
            {t}
          </span>
        ))}
      </div>

      <div className={styles.summary}>{m.content_preview}</div>

      <div className={styles.scoreGrid}>
        <div className={styles.scoreCard}>
          <div className={styles.scoreLabel}>Activation</div>
          <div className={styles.scoreValue} style={{ color: "#ff6b6b" }}>
            {m.activation_score.toFixed(2)}
          </div>
        </div>
        <div className={styles.scoreCard}>
          <div className={styles.scoreLabel}>Stability</div>
          <div className={styles.scoreValue} style={{ color: "#4ecdc4" }}>
            {m.stability_score.toFixed(2)}
          </div>
        </div>
        <div className={styles.scoreCard}>
          <div className={styles.scoreLabel}>Importance</div>
          <div className={styles.scoreValue} style={{ color: "#a78bfa" }}>
            {m.importance.toFixed(2)}
          </div>
        </div>
        <div className={styles.scoreCard}>
          <div className={styles.scoreLabel}>Arousal</div>
          <div className={styles.scoreValue} style={{ color: "#ffd93d" }}>
            {m.arousal.toFixed(2)}
          </div>
        </div>
      </div>

      <div className={styles.decaySection}>
        <div className={styles.decayLabel}>Ebbinghaus Decay</div>
        <div className={styles.decayBar}>
          <div
            className={styles.decayFill}
            style={{ width: `${m.stability_score * 100}%` }}
          />
        </div>
        <div className={styles.decayMeta}>
          <span>Halflife: {m.stability_halflife_days.toFixed(1)} days</span>
          <span>Reviews: {m.review_count}</span>
        </div>
      </div>

      <div className={styles.metaList}>
        <div className={styles.metaRow}>
          <span>Accesses</span>
          <span className={styles.metaValue}>{m.access_count}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Last accessed</span>
          <span className={styles.metaValue}>
            {formatDate(m.last_accessed_at)}
          </span>
        </div>
        <div className={styles.metaRow}>
          <span>Relations</span>
          <span className={styles.metaValue}>{detail.relation_count}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Abstraction</span>
          <span className={styles.metaValue}>Level {m.abstraction_level}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Valence</span>
          <span className={styles.metaValue}>{valenceLabel(m.valence)}</span>
        </div>
        <div className={styles.metaRow}>
          <span>Novelty</span>
          <span className={styles.metaValue}>
            {m.novelty_score.toFixed(2)}
          </span>
        </div>
        <div className={styles.metaRow}>
          <span>Pinned</span>
          <span
            className={
              m.manual_pin ? styles.metaHighlight : styles.metaValue
            }
          >
            {m.manual_pin ? "Yes" : "No"}
          </span>
        </div>
      </div>
    </div>
  );
}
