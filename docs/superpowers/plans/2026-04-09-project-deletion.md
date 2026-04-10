# Project Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to permanently delete projects and all associated data from the API, MCP, and Brain UI with a confirmation dialog.

**Architecture:** A shared async function `delete_project_internal()` in `server.py` handles the full deletion flow (Qdrant vectors, Postgres cascade, Redis cleanup). Both the REST endpoint `DELETE /api/projects/{name}` and the MCP tool `delete_project` call it. The Brain UI adds a trash icon per project in `ProjectSelector` and a new `DeleteProjectModal` component for confirmation.

**Tech Stack:** Python/FastAPI, asyncpg, qdrant-client, redis.asyncio, React/TypeScript, CSS Modules

---

### Task 1: Backend — `delete_project_internal()` function and REST endpoint

**Files:**
- Modify: `api-server/server.py` (add function + endpoint)

- [ ] **Step 1: Write the `delete_project_internal` function**

Add this after the `ensure_project` function (around line 828 in `server.py`):

```python
async def delete_project_internal(project_name: str) -> dict:
    """Delete a project and all its data from Postgres, Qdrant, and Redis."""
    if not pg_pool:
        raise RuntimeError("Database not available")

    project_id = await get_project_id(project_name)
    if project_id is None:
        raise ValueError(f"Project '{project_name}' not found")

    # 1. Collect memory IDs for Qdrant cleanup
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id FROM memory_log WHERE project_id = $1", project_id
        )
    memory_ids = [str(row["id"]) for row in rows]

    # 2. Delete vectors from Qdrant
    if memory_ids:
        await qdrant.delete(
            collection_name=COLLECTION_NAME,
            points_selector=memory_ids,
        )

    # 3. Delete project from Postgres (CASCADE handles memory_log, relations, bridges, permeability)
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE id = $1", project_id)

    # 4. Invalidate Redis activation keys for deleted memories
    if redis_client and memory_ids:
        try:
            pipe = redis_client.pipeline()
            for mid in memory_ids:
                pipe.delete(f"activation_propagation:{mid}")
            await pipe.execute()
        except Exception as exc:
            logger.debug("Redis cleanup for project %s: %s", project_name, exc)

    logger.info(
        "Proyecto '%s' eliminado: %d memorias borradas", project_name, len(memory_ids)
    )
    return {"result": "OK", "project": project_name, "memories_deleted": len(memory_ids)}
```

- [ ] **Step 2: Add the REST endpoint**

Add this after the `api_bridge_projects` endpoint (around line 4059 in `server.py`):

```python
@app.delete("/api/projects/{name}")
async def api_delete_project(name: str):
    try:
        return await delete_project_internal(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("api_delete_project fallo")
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 3: Verify the server starts without errors**

Run: `cd /home/eerr/GitHub/ai-memory && docker compose build api-server && docker compose up -d api-server`

Expected: container starts and `/health` returns OK.

- [ ] **Step 4: Commit**

```bash
git add api-server/server.py
git commit -m "feat(api): add DELETE /api/projects/{name} endpoint for project deletion"
```

---

### Task 2: MCP Tool — `delete_project`

**Files:**
- Modify: `api-server/server.py` (add MCP tool)

- [ ] **Step 1: Add the MCP tool**

Add this after the `delete_memory` MCP tool (around line 3835 in `server.py`):

```python
@mcp.tool()
async def delete_project(project: str) -> str:
    """Elimina un proyecto completo y todos sus datos asociados (memorias, relaciones, bridges).

    Cuando usar:
    - Para limpiar proyectos de prueba, obsoletos o creados por error.
    - Solo cuando estas seguro de que el proyecto entero debe eliminarse.

    Como usar:
    - Pasa el nombre exacto del proyecto a eliminar.
    - Esta operacion es irreversible: borra memorias, vectores, relaciones y bridges.

    Devuelve:
    - `OK ...` con el conteo de memorias eliminadas.
    - `ERROR ...` si el proyecto no existe o la operacion falla.
    """
    try:
        result = await delete_project_internal(project)
        return f"OK deleted project={result['project']} memories_removed={result['memories_deleted']}"
    except ValueError as exc:
        return f"ERROR {exc}"
    except Exception as exc:
        logger.exception("delete_project fallo")
        return f"ERROR {exc}"
```

- [ ] **Step 2: Verify the MCP tool is registered**

Restart the api-server and check the MCP endpoint is functional.

- [ ] **Step 3: Commit**

```bash
git add api-server/server.py
git commit -m "feat(mcp): add delete_project tool for full project deletion"
```

---

### Task 3: Test — Integration test for project deletion

**Files:**
- Modify: `tests/conftest.py` (add `delete_project` helper to `BrainClient`)
- Modify: `tests/test_memory_brain_behavior.py` (add test)

- [ ] **Step 1: Add `delete_project` method to `BrainClient`**

Add this after the `brain_health` method in `tests/conftest.py` (around line 99):

```python
def delete_project(self, name: str):
    response = self._client.delete(f"/api/projects/{name}")
    response.raise_for_status()
    return response.json()

def delete_project_raw(self, name: str):
    """Return the raw response without raising on error status."""
    return self._client.delete(f"/api/projects/{name}")
```

- [ ] **Step 2: Write the test**

Add this at the end of `tests/test_memory_brain_behavior.py`:

```python
def test_delete_project_removes_all_data(brain_client, unique_project_name):
    project = unique_project_name("delete-test")

    # Create two memories in the project
    mem_a = brain_client.create_memory(
        content="Memory alpha for deletion test project.",
        project=project,
        memory_type="general",
        tags="test/deletion",
        importance=0.5,
        agent_id="pytest",
    )["memory_id"]
    mem_b = brain_client.create_memory(
        content="Memory beta for deletion test project.",
        project=project,
        memory_type="general",
        tags="test/deletion",
        importance=0.5,
        agent_id="pytest",
    )["memory_id"]

    # Verify project appears in facets
    facets = brain_client.graph_facets()
    project_names = [p["project"] for p in facets["projects"]]
    assert project in project_names

    # Delete the project
    result = brain_client.delete_project(project)
    assert result["result"] == "OK"
    assert result["project"] == project
    assert result["memories_deleted"] == 2

    # Verify project no longer appears in facets
    facets_after = brain_client.graph_facets()
    project_names_after = [p["project"] for p in facets_after["projects"]]
    assert project not in project_names_after

    # Verify memories are gone (404)
    for mid in [mem_a, mem_b]:
        resp = brain_client._client.get(f"/api/memories/{mid}")
        assert resp.status_code == 404 or resp.json().get("memory") is None


def test_delete_nonexistent_project_returns_404(brain_client):
    resp = brain_client.delete_project_raw("nonexistent-project-xyz-999")
    assert resp.status_code == 404
```

- [ ] **Step 3: Run the tests to verify they pass**

Run: `AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_memory_brain_behavior.py::test_delete_project_removes_all_data tests/test_memory_brain_behavior.py::test_delete_nonexistent_project_returns_404 -v`

Expected: both tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_memory_brain_behavior.py
git commit -m "test: add integration tests for project deletion endpoint"
```

---

### Task 4: Brain UI — API client function

**Files:**
- Modify: `brain-ui/src/api/client.ts`

- [ ] **Step 1: Add `deleteProject` function**

Add this after the `fetchBrainHealth` function at the end of `brain-ui/src/api/client.ts`:

```typescript
export async function deleteProject(name: string): Promise<{ result: string; project: string; memories_deleted: number }> {
  const res = await fetch(`${API_URL}/api/projects/${encodeURIComponent(name)}`, {
    method: "DELETE",
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: `Delete failed: ${res.status}` }));
    throw new Error(body.detail || `Delete failed: ${res.status}`);
  }
  return res.json();
}
```

- [ ] **Step 2: Commit**

```bash
git add brain-ui/src/api/client.ts
git commit -m "feat(brain-ui): add deleteProject API client function"
```

---

### Task 5: Brain UI — `DeleteProjectModal` component

**Files:**
- Create: `brain-ui/src/components/DeleteProjectModal.tsx`
- Create: `brain-ui/src/components/DeleteProjectModal.module.css`

- [ ] **Step 1: Create the modal CSS**

Create `brain-ui/src/components/DeleteProjectModal.module.css`:

```css
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #12121f;
  border: 1px solid #2a2a4a;
  border-radius: 12px;
  padding: 24px;
  width: 380px;
  max-width: 90vw;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.8);
}

.title {
  color: #ff6b6b;
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 16px 0;
}

.projectName {
  color: #a78bfa;
  font-weight: 700;
}

.body {
  color: #aaa;
  font-size: 13px;
  line-height: 1.5;
  margin: 0 0 20px 0;
}

.warning {
  color: #ff6b6b;
  font-size: 12px;
  font-weight: 600;
  margin-top: 8px;
}

.actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.cancelBtn {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  padding: 8px 18px;
  color: #ccc;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: border-color 0.15s;
}

.cancelBtn:hover {
  border-color: #a78bfa;
}

.deleteBtn {
  background: #dc2626;
  border: 1px solid #dc2626;
  border-radius: 6px;
  padding: 8px 18px;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: opacity 0.15s;
}

.deleteBtn:hover {
  opacity: 0.85;
}

.deleteBtn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error {
  color: #ff6b6b;
  font-size: 12px;
  margin-top: 12px;
}
```

- [ ] **Step 2: Create the modal component**

Create `brain-ui/src/components/DeleteProjectModal.tsx`:

```tsx
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
```

- [ ] **Step 3: Commit**

```bash
git add brain-ui/src/components/DeleteProjectModal.tsx brain-ui/src/components/DeleteProjectModal.module.css
git commit -m "feat(brain-ui): add DeleteProjectModal confirmation component"
```

---

### Task 6: Brain UI — Integrate delete into `ProjectSelector` and `App`

**Files:**
- Modify: `brain-ui/src/components/ProjectSelector.tsx`
- Modify: `brain-ui/src/components/ProjectSelector.module.css`
- Modify: `brain-ui/src/App.tsx`

- [ ] **Step 1: Add trash button styles to `ProjectSelector.module.css`**

Add at the end of `brain-ui/src/components/ProjectSelector.module.css`:

```css
.deleteBtn {
  margin-left: auto;
  background: none;
  border: none;
  color: #555;
  font-size: 13px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
  flex-shrink: 0;
}

.deleteBtn:hover {
  color: #ff6b6b;
  background: rgba(255, 107, 107, 0.1);
}
```

- [ ] **Step 2: Update `ProjectSelector` to accept `onDeleteRequest` prop and show trash icons**

Replace the full `ProjectSelector.tsx` content with:

```tsx
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
                    {isSelected && <span className={styles.checkmark}>&#10003;</span>}
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
```

- [ ] **Step 3: Update `App.tsx` to wire up deletion**

In `brain-ui/src/App.tsx`, add the import for `deleteProject` and `DeleteProjectModal`:

At the top, update the import from `./api/client`:

```typescript
import { fetchSubgraph, fetchFacets, deleteProject } from "./api/client";
```

Add the import for the modal and the type:

```typescript
import DeleteProjectModal from "./components/DeleteProjectModal";
```

Add state for the deletion target inside the `App` component, after the existing state declarations (around line 70):

```typescript
const [deleteTarget, setDeleteTarget] = useState<FacetProject | null>(null);
```

Add the delete handler function after the existing `loadGraph` callback:

```typescript
const handleDeleteProject = useCallback(
  async (projectName: string) => {
    await deleteProject(projectName);
    setDeleteTarget(null);
    // Refresh facets and graph
    const facetsData = await fetchFacets();
    const updatedProjects = facetsData.projects || [];
    setProjects(updatedProjects);
    projectsRef.current = updatedProjects;
    // Remove deleted project from selection
    const nextSelected = new Set(selectedProjects);
    nextSelected.delete(projectName);
    setSelectedProjects(nextSelected);
    // Clear selected node if it belonged to deleted project
    if (selectedNode?.project === projectName) {
      setSelectedNode(null);
    }
    // Reload graph
    await loadGraph(nextSelected, updatedProjects);
  },
  [selectedProjects, selectedNode, loadGraph]
);
```

Pass `onDeleteRequest` to `ProjectSelector` — find where `<ProjectSelector` is rendered and add the prop:

```tsx
<ProjectSelector
  projects={projects}
  selected={selectedProjects}
  onChange={/* existing handler */}
  onDeleteRequest={setDeleteTarget}
/>
```

Render the modal at the end of the component's return, just before the closing fragment/div:

```tsx
{deleteTarget && (
  <DeleteProjectModal
    project={deleteTarget}
    onConfirm={handleDeleteProject}
    onCancel={() => setDeleteTarget(null)}
  />
)}
```

- [ ] **Step 4: Verify the UI builds**

Run: `cd /home/eerr/GitHub/ai-memory/brain-ui && npm run build`

Expected: Build succeeds with no errors.

- [ ] **Step 5: Commit**

```bash
git add brain-ui/src/components/ProjectSelector.tsx brain-ui/src/components/ProjectSelector.module.css brain-ui/src/App.tsx
git commit -m "feat(brain-ui): integrate project deletion with trash icon and confirmation modal"
```

---

### Task 7: Manual E2E verification

- [ ] **Step 1: Start the full stack in test mode**

Run: `make stack-test-up`

- [ ] **Step 2: Seed test data and verify deletion from API**

```bash
# Create a test project with a memory
curl -s -X POST http://127.0.0.1:8050/api/memories \
  -H "X-API-Key: $MEMORY_API_KEY" -H "Content-Type: application/json" \
  -d '{"content":"test memory for deletion","project":"delete-me-test","memory_type":"general","tags":"test","importance":0.5,"agent_id":"manual"}'

# Delete the project
curl -s -X DELETE http://127.0.0.1:8050/api/projects/delete-me-test \
  -H "X-API-Key: $MEMORY_API_KEY"
```

Expected: `{"result": "OK", "project": "delete-me-test", "memories_deleted": 1}`

- [ ] **Step 3: Open the Brain UI and test the delete flow**

Open `http://localhost:3080`, click the project scope dropdown, hover over a project, click the trash icon, verify the modal appears, and cancel/confirm.

- [ ] **Step 4: Run the full test suite**

Run: `make test-deterministic`

Expected: All tests pass including the two new deletion tests.

- [ ] **Step 5: Commit if any fixes were needed**

```bash
git add -u
git commit -m "fix: address issues found during E2E verification"
```
