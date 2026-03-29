# Guía de uso de MCP tools

Esta guía documenta las tools expuestas por `AI Memory Brain` desde `api-server/server.py`.

## Flujo recomendado para agentes

### 1. Al empezar una sesión

Usa estas tools para rehidratar contexto:

- `get_project_context`
- `search_memory`
- `list_active_tasks`

### 2. Mientras trabajas

Usa estas tools para dejar trazabilidad y memoria explícita:

- `update_task_state`
- `store_memory`
- `store_decision`
- `store_error`

### 3. Al cerrar una sesión

Usa:

- `record_session_summary`

### 4. Mantenimiento y consolidación

Usa:

- `run_memory_reflection`
- `get_reflection_status`
- `delete_memory`

## store_memory

Qué hace:

- Guarda una memoria explícita en Qdrant y en el log estructurado de PostgreSQL.

Cuándo usarla:

- Cuando descubres algo que debe seguir existiendo después de terminar la sesión.
- Cuando quieres guardar una convención, hallazgo, resultado, heurística o contexto durable.
- Cuando quieres evitar que el conocimiento dependa solo del historial del chat.

Cómo usarla:

- `content`: escribe el recuerdo de forma autocontenida.
- `project`: usa el nombre estable del proyecto.
- `memory_type`: clasifica el recuerdo, por ejemplo `general`, `decision`, `error`.
- `tags`: cadena CSV como `backend,postgres,migrations`.
- `importance`: número entre `0` y `1`.
- `agent_id`: identificador del agente que guarda la memoria.
- `skip_similar`: actívalo para deduplicación semántica.
- `dedupe_threshold`: umbral de similitud si activas dedupe.

Ejemplo:

```json
{
  "content": "El endpoint /ready depende de PostgreSQL, Redis, Qdrant, mem0 y reflection-worker.",
  "project": "ai-memory",
  "memory_type": "general",
  "tags": "api,healthchecks,architecture",
  "importance": 0.8,
  "agent_id": "codex",
  "skip_similar": true
}
```

Respuesta esperada:

- `OK memory_id=... project=ai-memory type=general`
- `SKIP similar_memory existing=... score=...`

## search_memory

Qué hace:

- Busca memorias por similitud semántica y devuelve un resumen textual con score.

Cuándo usarla:

- Al empezar una tarea para revisar conocimiento previo.
- Antes de rehacer una investigación o una decisión.
- Cuando buscas errores conocidos, decisiones pasadas o notas relevantes.

Cómo usarla:

- `query`: describe en lenguaje natural lo que quieres recuperar.
- `project`: úsalo para limitar la búsqueda al proyecto actual.
- `memory_type`: úsalo para buscar solo decisiones, errores o memoria general.
- `limit`: controla cuántos resultados quieres ver.

Ejemplo:

```json
{
  "query": "cómo se expone el servidor MCP y qué depende del endpoint ready",
  "project": "ai-memory",
  "limit": 5
}
```

Respuesta esperada:

- Texto con resultados enumerados y `score`.
- `No encontre memorias relevantes para '...'`

## get_project_context

Qué hace:

- Construye una vista compuesta del proyecto con tareas activas, decisiones recientes, working memory y búsqueda semántica contextual.

Cuándo usarla:

- Al abrir una sesión nueva.
- Cuando otro agente te pasa el relevo.
- Cuando necesitas entender rápidamente el estado del proyecto antes de actuar.

Cómo usarla:

- `project_name`: nombre canónico del proyecto.
- `agent_id`: opcional; ayuda a recuperar contexto operativo más cercano al agente.

Ejemplo:

```json
{
  "project_name": "ai-memory",
  "agent_id": "codex"
}
```

Respuesta esperada:

- Texto con bloques como `ACTIVE TASKS`, `DECISIONS`, `WORKING MEMORY` y `MEMORY SEARCH`.

## update_task_state

Qué hace:

- Crea o actualiza el estado de una tarea compartida en PostgreSQL.

Cuándo usarla:

- Cuando empiezas una tarea y quieres marcarla `active`.
- Cuando un bloqueo aparece y necesitas dejarla `blocked`.
- Cuando terminas y quieres dejarla `done`.

Cómo usarla:

- `task_title`: debe ser estable para que la misma tarea se actualice en llamadas futuras.
- `project`: nombre del proyecto.
- `new_state`: uno de `pending`, `active`, `blocked`, `done`, `cancelled`.
- `details`: contexto útil, por ejemplo motivo del bloqueo o resultado.
- `agent_id`: quién hizo el cambio.

Ejemplo:

```json
{
  "task_title": "Documentar tools MCP",
  "project": "ai-memory",
  "new_state": "active",
  "details": "Añadiendo docstrings y guía de uso por tool.",
  "agent_id": "codex"
}
```

Respuesta esperada:

- `OK task='Documentar tools MCP' state=active project=ai-memory`
- `ERROR invalid_state`

## list_active_tasks

Qué hace:

- Lista tareas no cerradas, ya sea de un proyecto concreto o de todos los proyectos.

Cuándo usarla:

- Antes de planificar trabajo.
- Para coordinación entre agentes.
- Para detectar tareas bloqueadas o pendientes.

Cómo usarla:

- Sin parámetros para ver una vista global.
- Con `project` para ver solo las tareas de un proyecto.

Ejemplo:

```json
{
  "project": "ai-memory"
}
```

Respuesta esperada:

- Lista textual con formato `[proyecto] [estado] tarea (p=prioridad, agent=agente)`.
- `No active tasks`

## store_decision

Qué hace:

- Guarda una decisión estructurada en PostgreSQL y además la promueve a memoria semántica.

Cuándo usarla:

- Cuando se elige una arquitectura o convención importante.
- Cuando una decisión afecta a futuras sesiones o a otros agentes.
- Cuando quieres guardar no solo la decisión, sino también su rationale.

Cómo usarla:

- `title`: nombre corto y reconocible de la decisión.
- `decision`: qué se decidió exactamente.
- `project`: proyecto afectado.
- `rationale`: por qué se tomó la decisión.
- `alternatives`: opciones consideradas y descartadas.
- `tags`: clasificación rápida.
- `agent_id`: autor o responsable.

Ejemplo:

```json
{
  "title": "Documentar tools con docstrings y guía externa",
  "decision": "Cada tool MCP tendrá docstring operativa en server.py y una guía central en docs/MCP_TOOLS.md.",
  "project": "ai-memory",
  "rationale": "La documentación embebida ayuda al cliente MCP y la guía externa ayuda a humanos.",
  "alternatives": "Documentar solo en README.",
  "tags": "documentation,mcp",
  "agent_id": "codex"
}
```

Respuesta esperada:

- `OK decision='...' project=...`

## store_error

Qué hace:

- Registra un error conocido, su solución y acumula ocurrencias sobre la misma firma.

Cuándo usarla:

- Cuando ya entendiste el problema y no quieres investigarlo otra vez en el futuro.
- Cuando aparece un bug recurrente con solución conocida.
- Cuando quieres dejar un workaround explícito para otros agentes.

Cómo usarla:

- `error_description`: síntoma y contexto del error.
- `solution`: solución aplicada o workaround.
- `project`: proyecto donde ocurre.
- `error_signature`: identificador estable del error si quieres agrupar ocurrencias.
- `tags`: clasificación por stack, módulo o categoría.

Ejemplo:

```json
{
  "error_description": "El arranque falla si faltan variables obligatorias como OPENAI_API_KEY.",
  "solution": "Definir claves reales en .env antes de levantar docker compose.",
  "project": "ai-memory",
  "error_signature": "missing-required-env-vars",
  "tags": "config,bootstrap"
}
```

Respuesta esperada:

- `OK error_signature='missing-required-env-vars' project=ai-memory`

## record_session_summary

Qué hace:

- Cierra una sesión de trabajo con un resumen estructurado, decisiones, errores, cambios y follow-ups.

Cuándo usarla:

- Al final de una sesión importante.
- Antes de ceder el trabajo a otro agente.
- Cuando quieres dejar continuidad real y no solo cambios en archivos.

Cómo usarla:

- `session_id`: debe ser único por sesión.
- `goal`: objetivo inicial.
- `outcome`: resultado final.
- `summary`: resumen narrativo de alto nivel.
- `changes`: lista de cambios importantes.
- `decisions`: lista de objetos `{title, decision, rationale}`.
- `errors`: lista de objetos `{error_signature, description, solution}`.
- `follow_ups`: lista de objetos `{title, state, details}`.
- `tags`: clasificación adicional.

Ejemplo:

```json
{
  "project": "ai-memory",
  "agent_id": "codex",
  "session_id": "2026-03-30-doc-tools",
  "goal": "Documentar todas las tools MCP",
  "outcome": "Se añadieron docstrings y una guía operativa por tool",
  "summary": "Se documentó cuándo usar cada tool, cómo invocarla y qué esperar como respuesta.",
  "changes": [
    "Se añadieron docstrings a las 11 tools MCP",
    "Se creó docs/MCP_TOOLS.md"
  ],
  "decisions": [
    {
      "title": "Doble capa de documentación",
      "decision": "Documentar tanto en código como en markdown",
      "rationale": "Sirve al cliente MCP y al equipo humano"
    }
  ],
  "follow_ups": [
    {
      "title": "Exponer ejemplos también en README",
      "state": "pending",
      "details": "Opcional si se quiere una entrada más corta"
    }
  ],
  "tags": ["documentation", "mcp"]
}
```

Respuesta esperada:

- `OK session_id=... checksum=... working_memory_ingested=true`
- `ERROR duplicate_session checksum=...`

## run_memory_reflection

Qué hace:

- Encola una ejecución manual del worker de reflexión para consolidar memoria.

Cuándo usarla:

- Tras varias sesiones relevantes.
- Cuando quieres consolidar antes de que corra el ciclo automático.
- Cuando acabas de registrar contexto importante y quieres promoverlo.

Cómo usarla:

- No recibe parámetros.
- Lo normal es llamarla y luego consultar `get_reflection_status`.

Ejemplo:

```json
{}
```

Respuesta esperada:

- `OK run_id=... status=queued queued=true`

## get_reflection_status

Qué hace:

- Devuelve el estado del worker de reflexión, su heartbeat y el estado de la última ejecución conocida.

Cuándo usarla:

- Después de lanzar `run_memory_reflection`.
- Cuando quieres comprobar si el worker está vivo o atrasado.
- Como chequeo operativo del subsistema de reflexión.

Cómo usarla:

- No recibe parámetros.
- Interpreta la respuesta como JSON serializado en texto.

Ejemplo:

```json
{}
```

Respuesta esperada:

- JSON en texto con claves relacionadas con worker, ready, last_run y heartbeat.

## delete_memory

Qué hace:

- Elimina una memoria explícita de la colección vectorial.

Cuándo usarla:

- Cuando se guardó una memoria incorrecta.
- Cuando identificas duplicados que quieres limpiar manualmente.
- Cuando una memoria ya no debería estar disponible por ser inválida o sensible.

Cómo usarla:

- `memory_id`: identificador exacto de la memoria.
- Úsala con cuidado porque es una operación destructiva.

Ejemplo:

```json
{
  "memory_id": "6fd02478-3d20-4f4d-a640-b3d9c4fd20a9"
}
```

Respuesta esperada:

- `OK deleted=6fd02478-3d20-4f4d-a640-b3d9c4fd20a9`

## Recomendaciones prácticas

- No uses `store_memory` para pensamientos intermedios o ruido de ejecución.
- Usa `store_decision` y `store_error` cuando la información ya tiene una estructura clara.
- Usa `record_session_summary` como cierre estándar de sesiones importantes.
- Ejecuta `run_memory_reflection` solo cuando tenga sentido consolidar; no en cada acción.
- Antes de borrar con `delete_memory`, confirma que el identificador es correcto y que la memoria no sigue siendo útil.
