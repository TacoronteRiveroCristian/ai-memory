#!/usr/bin/env bash
# Hook: session-start
# 1. Asegura que CLAUDE.md del proyecto tiene la sección de AI Memory Brain
# 2. Recuerda al agente que cargue contexto
set -u

PROJECT_NAME="$(basename "$PWD")"
CLAUDE_MD="./CLAUDE.md"
MARKER="## AI Memory Brain"

# ── Inyectar sección si no existe ───────────────────────────────────
if [[ ! -f "$CLAUDE_MD" ]]; then
    # Crear CLAUDE.md con la sección
    cat > "$CLAUDE_MD" << CLAUDEEOF
# ${PROJECT_NAME}

${MARKER}

Este proyecto usa **AI Memory Brain** como sistema de memoria persistente entre sesiones.

### Nombre del proyecto en el cerebro

Usa siempre \`${PROJECT_NAME}\` como valor de \`project\` en todas las llamadas MCP.

### Al iniciar sesion

Llama a \`get_project_context(project_name="${PROJECT_NAME}")\` para cargar:
- Memorias relevantes del proyecto
- Tareas activas
- Decisiones recientes
- Working memory

Lee lo que devuelve antes de trabajar. No dupliques lo que ya existe.

### Mientras trabajas

Guarda proactivamente cuando ocurra algo relevante:

| Evento | Tool | Importancia |
|--------|------|-------------|
| Decision de arquitectura | \`store_decision(project="${PROJECT_NAME}", ...)\` | 0.85 |
| Bug encontrado o resuelto | \`store_error(project="${PROJECT_NAME}", ...)\` | 0.7-0.85 |
| Patron o insight | \`store_memory(project="${PROJECT_NAME}", ...)\` | 0.7 |
| Tarea cambia de estado | \`update_task_state(project="${PROJECT_NAME}", ...)\` | 0.5-0.7 |
| Conexion con otro proyecto | \`bridge_projects(project="${PROJECT_NAME}", ...)\` | 0.7 |

### Al cerrar sesion

Llama a \`record_session_summary(project="${PROJECT_NAME}", agent_id="claude-code")\` con un resumen de lo que se hizo.

### Formato de memorias

- **content**: QUE paso + POR QUE importa + CONTEXTO (parrafo autocontenido)
- **tags**: jerarquicos, separados por coma (ej: \`backend/api, bug/resolved\`)
- **importance**: 0.5 rutina | 0.7 notable | 0.85 importante | 0.95 critico

### NO guardar

- Resumenes de conversacion (eso lo hace \`record_session_summary\`)
- Hechos que se pueden ver en el codigo o en git
- Info temporal de debug
- Decisiones triviales
CLAUDEEOF
    echo "[memory-brain] Creado CLAUDE.md con configuración de AI Memory Brain para '${PROJECT_NAME}'"

elif ! grep -q "$MARKER" "$CLAUDE_MD"; then
    # Archivo existe pero no tiene la sección — añadirla al final
    cat >> "$CLAUDE_MD" << APPENDEOF

${MARKER}

Este proyecto usa **AI Memory Brain** como sistema de memoria persistente entre sesiones.

### Nombre del proyecto en el cerebro

Usa siempre \`${PROJECT_NAME}\` como valor de \`project\` en todas las llamadas MCP.

### Al iniciar sesion

Llama a \`get_project_context(project_name="${PROJECT_NAME}")\` para cargar:
- Memorias relevantes del proyecto
- Tareas activas
- Decisiones recientes
- Working memory

Lee lo que devuelve antes de trabajar. No dupliques lo que ya existe.

### Mientras trabajas

Guarda proactivamente cuando ocurra algo relevante:

| Evento | Tool | Importancia |
|--------|------|-------------|
| Decision de arquitectura | \`store_decision(project="${PROJECT_NAME}", ...)\` | 0.85 |
| Bug encontrado o resuelto | \`store_error(project="${PROJECT_NAME}", ...)\` | 0.7-0.85 |
| Patron o insight | \`store_memory(project="${PROJECT_NAME}", ...)\` | 0.7 |
| Tarea cambia de estado | \`update_task_state(project="${PROJECT_NAME}", ...)\` | 0.5-0.7 |
| Conexion con otro proyecto | \`bridge_projects(project="${PROJECT_NAME}", ...)\` | 0.7 |

### Al cerrar sesion

Llama a \`record_session_summary(project="${PROJECT_NAME}", agent_id="claude-code")\` con un resumen de lo que se hizo.

### Formato de memorias

- **content**: QUE paso + POR QUE importa + CONTEXTO (parrafo autocontenido)
- **tags**: jerarquicos, separados por coma (ej: \`backend/api, bug/resolved\`)
- **importance**: 0.5 rutina | 0.7 notable | 0.85 importante | 0.95 critico

### NO guardar

- Resumenes de conversacion (eso lo hace \`record_session_summary\`)
- Hechos que se pueden ver en el codigo o en git
- Info temporal de debug
- Decisiones triviales
APPENDEOF
    echo "[memory-brain] Sección AI Memory Brain añadida a CLAUDE.md para '${PROJECT_NAME}'"

else
    echo "[memory-brain] CLAUDE.md ya tiene configuración de AI Memory Brain"
fi

# ── Recordatorio al agente ──────────────────────────────────────────
echo "[memory-brain] Llama a get_project_context(project_name=\"${PROJECT_NAME}\") para cargar contexto."
