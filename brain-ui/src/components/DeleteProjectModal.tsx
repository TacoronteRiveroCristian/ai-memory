import { useState } from "react";
import type { FacetProject } from "../types";
import styles from "./DeleteProjectModal.module.css";

interface DeleteProjectModalProps {
  projects: FacetProject[];
  onConfirm: (projectNames: string[]) => Promise<void>;
  onCancel: () => void;
}

export default function DeleteProjectModal({
  projects,
  onConfirm,
  onCancel,
}: DeleteProjectModalProps) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalMemories = projects.reduce((s, p) => s + p.memory_count, 0);
  const totalPinned = projects.reduce((s, p) => s + p.pinned_memory_count, 0);
  const isBulk = projects.length > 1;

  const handleDelete = async () => {
    setDeleting(true);
    setError(null);
    try {
      await onConfirm(projects.map((p) => p.project));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
      setDeleting(false);
    }
  };

  return (
    <div className={styles.overlay} data-modal-overlay onClick={onCancel}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h3 className={styles.title}>
          {isBulk
            ? `Eliminar ${projects.length} proyectos`
            : "Eliminar proyecto"}
        </h3>
        <div className={styles.body}>
          {isBulk ? (
            <>
              <p>
                Vas a eliminar los siguientes proyectos con un total de{" "}
                <strong>{totalMemories}</strong> memorias ({totalPinned}{" "}
                pinneadas):
              </p>
              <ul className={styles.projectList}>
                {projects.map((p) => (
                  <li key={p.project}>
                    <span className={styles.projectName}>{p.project}</span>
                    <span className={styles.projectCount}>
                      {p.memory_count} mem.
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p>
              Vas a eliminar el proyecto{" "}
              <span className={styles.projectName}>
                {projects[0].project}
              </span>{" "}
              con <strong>{projects[0].memory_count}</strong> memorias (
              {projects[0].pinned_memory_count} pinneadas).
            </p>
          )}
          <span className={styles.warning}>
            Esta accion es irreversible.
          </span>
        </div>
        <div className={styles.actions}>
          <button
            className={styles.cancelBtn}
            onClick={onCancel}
            disabled={deleting}
          >
            Cancelar
          </button>
          <button
            className={styles.deleteBtn}
            onClick={handleDelete}
            disabled={deleting}
          >
            {deleting
              ? "Eliminando..."
              : isBulk
                ? `Eliminar ${projects.length} proyectos`
                : "Eliminar"}
          </button>
        </div>
        {error && <p className={styles.error}>{error}</p>}
      </div>
    </div>
  );
}
