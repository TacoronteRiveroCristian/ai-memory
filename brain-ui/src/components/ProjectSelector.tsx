import { useState, useRef, useEffect } from "react";
import type { FacetProject } from "../types";
import styles from "./ProjectSelector.module.css";

const PROJECT_COLORS = [
  "#ff6b6b",
  "#4ecdc4",
  "#ffd93d",
  "#a78bfa",
  "#ff9ff3",
  "#54a0ff",
  "#5f27cd",
  "#01a3a4",
];

interface ProjectSelectorProps {
  projects: FacetProject[];
  selected: string | null;
  onChange: (project: string | null) => void;
}

export default function ProjectSelector({
  projects,
  selected,
  onChange,
}: ProjectSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className={styles.wrapper} ref={ref}>
      <div className={styles.trigger} onClick={() => setOpen(!open)}>
        <span className={styles.label}>Scope:</span>
        <span className={styles.value}>{selected || "All Projects"}</span>
        <span className={styles.arrow}>{open ? "\u25B2" : "\u25BC"}</span>
      </div>
      {open && (
        <div className={styles.dropdown}>
          <div
            className={`${styles.item} ${
              selected === null ? styles.itemActive : ""
            }`}
            onClick={() => {
              onChange(null);
              setOpen(false);
            }}
          >
            <span style={{ fontSize: 14 }}>&#127760;</span>
            <div>
              <div className={styles.itemName}>All Projects</div>
              <div className={styles.itemMeta}>
                Full brain view &mdash; global scope
              </div>
            </div>
          </div>
          <div className={styles.divider} />
          {projects.map((p, i) => (
            <div
              key={p.project}
              className={`${styles.item} ${
                selected === p.project ? styles.itemActive : ""
              }`}
              onClick={() => {
                onChange(p.project);
                setOpen(false);
              }}
            >
              <div
                className={styles.itemDot}
                style={{
                  background: PROJECT_COLORS[i % PROJECT_COLORS.length],
                }}
              />
              <div>
                <div className={styles.itemName}>{p.project}</div>
                <div className={styles.itemMeta}>
                  {p.memory_count} memories &middot; {p.pinned_memory_count}{" "}
                  pinned
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export { PROJECT_COLORS };
