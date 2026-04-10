import { useState } from "react";
import type { FacetProject } from "../types";
import styles from "./DeleteProjectModal.module.css";

interface DeleteProjectModalProps {
  project: FacetProject;
  onConfirm: (projectName: string) => Promise<void>;
  onCancel: () => void;
}

export default function DeleteProjectModal({
  project,
  onConfirm,
  onCancel,
}: DeleteProjectModalProps) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    setDeleting(true);
    setError(null);
    try {
      await onConfirm(project.project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
      setDeleting(false);
    }
  };

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h3 className={styles.title}>Eliminar proyecto</h3>
        <p className={styles.body}>
          Vas a eliminar el proyecto{" "}
          <span className={styles.projectName}>{project.project}</span> con{" "}
          <strong>{project.memory_count}</strong> memorias (
          {project.pinned_memory_count} pinneadas).
          <span className={styles.warning}>
            <br />
            Esta accion es irreversible.
          </span>
        </p>
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
            {deleting ? "Eliminando..." : "Eliminar"}
          </button>
        </div>
        {error && <p className={styles.error}>{error}</p>}
      </div>
    </div>
  );
}
