import { useState, useEffect } from "react";
import { fetchHealth } from "../api/client";
import type { FacetProject } from "../types";
import ProjectSelector from "./ProjectSelector";
import KeywordFilter from "./KeywordFilter";
import styles from "./TopBar.module.css";

interface TopBarProps {
  projects: FacetProject[];
  selectedProjects: Set<string>;
  onProjectChange: (projects: Set<string>) => void;
  keyword: string;
  onKeywordChange: (keyword: string) => void;
}

export default function TopBar({
  projects,
  selectedProjects,
  onProjectChange,
  keyword,
  onKeywordChange,
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
      <div className={styles.logo}>&#x1f9e0; AI Memory Brain</div>
      <div className={styles.right}>
        <KeywordFilter value={keyword} onChange={onKeywordChange} />
        <ProjectSelector
          projects={projects}
          selected={selectedProjects}
          onChange={onProjectChange}
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
