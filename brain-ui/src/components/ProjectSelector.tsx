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
  selected: Set<string>;
  onChange: (projects: Set<string>) => void;
  onDeleteRequest?: (project: FacetProject) => void;
}

export default function ProjectSelector({
  projects,
  selected,
  onChange,
  onDeleteRequest,
}: ProjectSelectorProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  const filtered = search
    ? projects.filter((p) =>
        p.project.toLowerCase().includes(search.toLowerCase())
      )
    : projects;

  const totalMemories = projects.reduce((s, p) => s + p.memory_count, 0);
  const isAll = selected.size === 0;

  const toggleProject = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) {
      next.delete(name);
    } else {
      next.add(name);
    }
    onChange(next);
  };

  const selectAll = () => {
    onChange(new Set());
    setOpen(false);
    setSearch("");
  };

  // Display label
  let displayLabel: string;
  if (isAll) {
    displayLabel = "All Projects";
  } else if (selected.size === 1) {
    displayLabel = [...selected][0];
  } else {
    displayLabel = `${selected.size} Projects`;
  }

  return (
    <div className={styles.wrapper} ref={ref}>
      <div className={styles.trigger} onClick={() => setOpen(!open)}>
        <span className={styles.label}>Scope:</span>
        <span className={styles.value}>{displayLabel}</span>
        <span className={styles.arrow}>{open ? "\u25B2" : "\u25BC"}</span>
      </div>
      {open && (
        <div className={styles.dropdown}>
          <div className={styles.searchBox}>
            <input
              ref={inputRef}
              className={styles.searchInput}
              type="text"
              placeholder="Search projects..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className={styles.scrollArea}>
            <div
              className={`${styles.item} ${isAll ? styles.itemActive : ""}`}
              onClick={selectAll}
            >
              <span className={styles.itemIcon}>&#127760;</span>
              <div>
                <div className={styles.itemName}>All Projects</div>
                <div className={styles.itemMeta}>
                  {projects.length} projects &middot; {totalMemories} memories
                </div>
              </div>
            </div>
            <div className={styles.divider} />
            {filtered.map((p) => {
              const origIndex = projects.indexOf(p);
              const isSelected = selected.has(p.project);
              return (
                <div
                  key={p.project}
                  className={`${styles.item} ${isSelected ? styles.itemActive : ""}`}
                  onClick={() => toggleProject(p.project)}
                >
                  <div
                    className={`${styles.checkbox} ${isSelected ? styles.checkboxChecked : ""}`}
                    style={{
                      borderColor: PROJECT_COLORS[origIndex % PROJECT_COLORS.length],
                      background: isSelected
                        ? PROJECT_COLORS[origIndex % PROJECT_COLORS.length]
                        : "transparent",
                    }}
                  >
                    {isSelected && <span className={styles.checkmark}>✓</span>}
                  </div>
                  <div>
                    <div className={styles.itemName}>{p.project}</div>
                    <div className={styles.itemMeta}>
                      {p.memory_count} memories &middot; {p.pinned_memory_count} pinned
                    </div>
                  </div>
                  {onDeleteRequest && (
                    <button
                      className={styles.deleteBtn}
                      title={`Delete ${p.project}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteRequest(p);
                      }}
                    >
                      &#128465;
                    </button>
                  )}
                </div>
              );
            })}
            {filtered.length === 0 && (
              <div className={styles.noResults}>No projects match</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export { PROJECT_COLORS };
