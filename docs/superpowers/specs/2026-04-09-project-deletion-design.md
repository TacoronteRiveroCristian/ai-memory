# Project Deletion — Design Spec

**Date:** 2026-04-09
**Status:** Approved

## Goal

Allow users to permanently delete projects (and all their associated data) from the Brain UI, API, and MCP. Hard delete — no soft delete, no recovery.

## 1. API Endpoint

### `DELETE /api/projects/{name}`

**Auth:** `X-API-Key` header (same as all other endpoints).

**Flow:**

1. Look up project in Postgres by name. Return 404 if not found.
2. Fetch all `memory_log.id` UUIDs belonging to the project.
3. Batch-delete the corresponding points from Qdrant.
4. `DELETE FROM projects WHERE name = $1` — Postgres CASCADE handles:
   - `memory_log` (all memories)
   - `memory_relations` (via memory foreign keys)
   - `project_bridges`
   - `project_permeability`
5. Invalidate Redis keys for the project (embedding cache, activation scores).
6. Return `{"result": "OK", "project": "<name>", "memories_deleted": N}`.

**Error responses:**

- `404` — project not found
- `500` — internal error during deletion

## 2. MCP Tool

```python
@mcp.tool()
async def delete_project(project: str) -> str:
```

- Calls the same internal function as the REST endpoint.
- Returns `"OK deleted project={name} memories_removed={N}"` on success.
- Returns `"ERROR ..."` on failure.
- Docstring in Spanish (consistent with existing MCP tools).

## 3. Brain UI

### ProjectSelector changes

- Add a trash icon button next to each project name in the dropdown list.
- Clicking the trash icon opens a confirmation modal (does NOT delete immediately).

### Confirmation modal (new component: `DeleteProjectModal`)

**Content:**

- Project name (bold)
- Memory count and pinned memory count
- Warning text: "Vas a eliminar el proyecto **X** con **N memorias** (M pinneadas). Esta accion es irreversible."
- Two buttons: "Cancelar" (neutral) and "Eliminar" (red/destructive)

**Behavior:**

- "Eliminar" button shows a loading spinner while the DELETE request is in flight.
- On success: closes modal, refreshes facets and graph.
- On error: shows error message in the modal, keeps it open.

### Post-deletion state cleanup

- Remove the deleted project from `selectedProjects` if present.
- Re-fetch `fetchFacets()` to update project list.
- Re-load the graph with remaining projects.
- If `selectedNode` belonged to the deleted project, clear the selection.

## 4. Scope boundaries

**In scope:**

- Single-project deletion (one at a time)
- Confirmation modal in the UI
- API endpoint + MCP tool
- Qdrant vector cleanup
- Postgres cascade cleanup
- Redis cache invalidation

**Out of scope:**

- Bulk/multi-select deletion from UI (users delete one by one)
- Soft delete / archiving / undo
- Deletion of individual memories (already exists via other tools)
