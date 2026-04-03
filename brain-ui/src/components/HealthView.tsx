import { useState, useEffect } from "react";
import { fetchBrainHealth } from "../api/client";
import type { BrainHealthResponse } from "../types";
import styles from "./HealthView.module.css";

function formatRelative(iso: string | null): string {
  if (!iso) return "\u2014";
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffH = Math.floor(diffMs / 3_600_000);
  if (diffH < 1) return "< 1h ago";
  if (diffH < 24) return `${diffH}h ago`;
  return `${Math.floor(diffH / 24)}d ago`;
}

function healthColor(score: number): string {
  if (score >= 0.7) return "#4ecdc4";
  if (score >= 0.4) return "#ffd93d";
  return "#ff6b6b";
}

export default function HealthView() {
  const [data, setData] = useState<BrainHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAllRegions, setShowAllRegions] = useState(false);
  const [showAllConnectivity, setShowAllConnectivity] = useState(false);
  const [showAllAlerts, setShowAllAlerts] = useState(false);

  useEffect(() => {
    let mounted = true;
    const load = () =>
      fetchBrainHealth()
        .then((d) => mounted && setData(d))
        .catch((e) => mounted && setError(e instanceof Error ? e.message : "Failed"));

    load();
    const id = setInterval(load, 60_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  if (error) {
    return <div className={styles.container}><div className={styles.error}>{error}</div></div>;
  }
  if (!data) {
    return <div className={styles.container}><div className={styles.loading}>Loading brain health...</div></div>;
  }

  const syn = data.synapse_formation;
  const sleep = data.sleep;

  return (
    <div className={styles.container}>
      {/* Overall Health */}
      <div className={`${styles.card} ${styles.healthCard}`}>
        <div className={styles.cardTitle}>Overall Brain Health</div>
        <div className={styles.healthScore} style={{ color: healthColor(data.overall_health) }}>
          {Math.round(data.overall_health * 100)}%
        </div>
        <div className={styles.healthBar}>
          <div
            className={styles.healthFill}
            style={{ width: `${data.overall_health * 100}%`, background: healthColor(data.overall_health) }}
          />
        </div>
        <div className={styles.cardMeta}>Updated {formatRelative(data.timestamp)}</div>
      </div>

      {/* Synapse Formation */}
      <div className={styles.card}>
        <div className={styles.cardTitle}>Synapse Formation</div>
        <div className={styles.synapseGrid}>
          <div className={styles.synapseTier}>
            <div className={styles.synapseNum} style={{ color: "#ff6b6b" }}>{syn.tier1_instant}</div>
            <div className={styles.synapseLabel}>T1 Instinct</div>
          </div>
          <div className={styles.synapseTier}>
            <div className={styles.synapseNum} style={{ color: "#ffd93d" }}>{syn.tier2_confirmed}</div>
            <div className={styles.synapseLabel}>T2 Perception</div>
          </div>
          <div className={styles.synapseTier}>
            <div className={styles.synapseNum} style={{ color: "#a78bfa" }}>
              {syn.tier3_promoted + syn.tier3_candidates_pending}
            </div>
            <div className={styles.synapseLabel}>T3 Reasoning</div>
            <div className={styles.t3Detail}>
              <span className={styles.t3Promoted}>{syn.tier3_promoted} promoted</span>
              <span className={styles.t3Pending}>{syn.tier3_candidates_pending} pending</span>
              <span className={styles.t3Rejected}>{syn.tier3_rejected} rejected</span>
            </div>
          </div>
        </div>
      </div>

      {/* Regions */}
      {(() => {
        const regionEntries = Object.entries(data.regions);
        const totalMemories = regionEntries.reduce((s, [, r]) => s + r.memory_count, 0);
        const avgOrphan = regionEntries.length > 0
          ? regionEntries.reduce((s, [, r]) => s + r.orphan_ratio, 0) / regionEntries.length
          : 0;
        const visibleRegions = showAllRegions ? regionEntries : regionEntries.slice(0, 6);

        return (
          <div className={`${styles.card} ${styles.wideCard}`}>
            <div className={styles.cardTitle}>Regions</div>
            <div className={styles.sectionSummary}>
              {regionEntries.length} regions, {totalMemories} total memories, {(avgOrphan * 100).toFixed(0)}% avg orphan ratio
            </div>
            <div className={styles.regionGrid}>
              {visibleRegions.map(([name, region]) => (
                <div key={name} className={styles.regionItem}>
                  <div className={styles.regionName}>{name}</div>
                  <div className={styles.regionStats}>
                    <span>{region.memory_count} memories</span>
                    <span>{region.active_synapses} synapses</span>
                  </div>
                  <div className={styles.miniBarGroup}>
                    <span className={styles.miniBarLabel}>Orphans</span>
                    <div className={styles.miniBarTrack}>
                      <div
                        className={styles.miniBarFill}
                        style={{
                          width: `${region.orphan_ratio * 100}%`,
                          background: region.orphan_ratio > 0.2 ? "#ff6b6b" : "#4ecdc4",
                        }}
                      />
                    </div>
                    <span className={styles.miniBarValue}>{(region.orphan_ratio * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
            {regionEntries.length > 6 && (
              <button className={styles.toggleBtn} onClick={() => setShowAllRegions(!showAllRegions)}>
                {showAllRegions ? "Show less" : `Show all (${regionEntries.length})`}
              </button>
            )}
          </div>
        );
      })()}

      {/* Connectivity */}
      {(() => {
        const connEntries = Object.entries(data.connectivity);
        if (connEntries.length === 0) return null;
        const visibleConn = showAllConnectivity ? connEntries : connEntries.slice(0, 4);

        return (
          <div className={`${styles.card} ${styles.wideCard}`}>
            <div className={styles.cardTitle}>Connectivity</div>
            <div className={styles.connectGrid}>
              {visibleConn.map(([pair, conn]) => (
                <div key={pair} className={styles.connectItem}>
                  <div className={styles.connectPair}>{pair}</div>
                  <div className={styles.miniBarGroup}>
                    <span className={styles.miniBarLabel}>Permeability</span>
                    <div className={styles.miniBarTrack}>
                      <div className={styles.miniBarFill} style={{ width: `${conn.permeability_score * 100}%`, background: "#a78bfa" }} />
                    </div>
                    <span className={styles.miniBarValue}>{conn.permeability_score.toFixed(2)}</span>
                  </div>
                  <div className={styles.connectMeta}>{conn.myelinated_relations} myelinated</div>
                </div>
              ))}
            </div>
            {connEntries.length > 4 && (
              <button className={styles.toggleBtn} onClick={() => setShowAllConnectivity(!showAllConnectivity)}>
                {showAllConnectivity ? "Show less" : `Show all (${connEntries.length})`}
              </button>
            )}
          </div>
        );
      })()}

      {/* Sleep Cycles */}
      <div className={styles.card}>
        <div className={styles.cardTitle}>Sleep Cycles</div>
        <div className={styles.sleepGrid}>
          <div className={styles.sleepItem}>
            <span className={styles.sleepLabel}>Last NREM</span>
            <span className={styles.sleepValue}>{formatRelative(sleep.last_nrem)}</span>
          </div>
          <div className={styles.sleepItem}>
            <span className={styles.sleepLabel}>Last REM</span>
            <span className={styles.sleepValue}>{formatRelative(sleep.last_rem)}</span>
          </div>
        </div>
        <div className={styles.miniBarGroup}>
          <span className={styles.miniBarLabel}>
            Cross-activity {sleep.cross_activity_score} / {sleep.rem_threshold}
          </span>
          <div className={styles.miniBarTrack}>
            <div
              className={styles.miniBarFill}
              style={{
                width: `${Math.min((sleep.cross_activity_score / Math.max(sleep.rem_threshold, 1)) * 100, 100)}%`,
                background: sleep.cross_activity_score >= sleep.rem_threshold ? "#ff6b6b" : "#4ecdc4",
              }}
            />
          </div>
        </div>
        {sleep.cross_activity_score >= sleep.rem_threshold && (
          <div className={styles.remNeeded}>REM cycle needed</div>
        )}
      </div>

      {/* Alerts */}
      <div className={`${styles.card} ${styles.wideCard}`}>
        <div className={styles.cardTitle}>Alerts ({data.alerts.length})</div>
        {data.alerts.length === 0 ? (
          <div className={styles.allClear}>All clear</div>
        ) : (
          <>
            <div className={styles.alertList}>
              {(showAllAlerts ? data.alerts : data.alerts.slice(0, 5)).map((alert, i) => (
                <div key={i} className={`${styles.alert} ${styles[`alert_${alert.severity}`]}`}>
                  <span className={styles.alertSeverity}>{alert.severity}</span>
                  <span>{alert.message}</span>
                </div>
              ))}
            </div>
            {data.alerts.length > 5 && (
              <button className={styles.toggleBtn} onClick={() => setShowAllAlerts(!showAllAlerts)}>
                {showAllAlerts ? "Show less" : `Show all (${data.alerts.length})`}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
