import { useState, useEffect } from "react";
import { fetchHealth } from "../api/client";
import type { FacetProject } from "../types";
import type { TabId } from "./TabSwitcher";
import TabSwitcher from "./TabSwitcher";
import ProjectSelector from "./ProjectSelector";
import KeywordFilter from "./KeywordFilter";
import styles from "./TopBar.module.css";

interface TopBarProps {
  projects: FacetProject[];
  selectedProjects: Set<string>;
  onProjectChange: (projects: Set<string>) => void;
  keywords: string[];
  onKeywordsChange: (keywords: string[]) => void;
  onCenterView: () => void;
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  onDeleteRequest?: (project: FacetProject) => void;
  onBulkDeleteRequest?: (projects: FacetProject[]) => void;
}

export default function TopBar({
  projects,
  selectedProjects,
  onProjectChange,
  keywords,
  onKeywordsChange,
  onCenterView,
  activeTab,
  onTabChange,
  onDeleteRequest,
  onBulkDeleteRequest,
}: TopBarProps) {
  const [healthy, setHealthy] = useState(true);

  useEffect(() => {
    let mounted = true;
    const check = () =>
      fetchHealth()
        .then(() => mounted && setHealthy(true))
        .catch(() => mounted && setHealthy(false));
    check();
    const id = setInterval(check, 30_000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className={styles.topbar}>
      <div className={styles.left}>
        <div className={styles.logo}>{"\u{1f9e0}"} AI Memory Brain</div>
        <TabSwitcher activeTab={activeTab} onTabChange={onTabChange} />
      </div>
      <div className={styles.right}>
        <KeywordFilter keywords={keywords} onChange={onKeywordsChange} />
        <button className={styles.centerBtn} onClick={onCenterView} title="Center view">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="8" cy="8" r="3" />
            <line x1="8" y1="1" x2="8" y2="4" />
            <line x1="8" y1="12" x2="8" y2="15" />
            <line x1="1" y1="8" x2="4" y2="8" />
            <line x1="12" y1="8" x2="15" y2="8" />
          </svg>
        </button>
        <ProjectSelector
          projects={projects}
          selected={selectedProjects}
          onChange={onProjectChange}
          onDeleteRequest={onDeleteRequest}
          onBulkDeleteRequest={onBulkDeleteRequest}
        />
        <div className={styles.health}>
          <div
            className={`${styles.healthDot} ${
              healthy ? styles.healthy : styles.unhealthy
            }`}
          />
          {healthy ? "System healthy" : "Unreachable"}
        </div>
      </div>
    </div>
  );
}
