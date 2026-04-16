#!/usr/bin/env bash
# install.sh — Instala AI Memory Brain como plugin global de Claude Code.
#
# Uso:
#   ./plugin/claude-code/install.sh <API_URL> <API_KEY>
#
# Ejemplo:
#   ./plugin/claude-code/install.sh http://192.168.1.156:8050 mi-clave-secreta
#
# Qué hace:
#   1. Copia el hook de ingestión a ~/.claude/hooks/
#   2. Añade el MCP server a ~/.claude/.mcp.json
#   3. Añade el hook Stop a ~/.claude/settings.json
#   4. Crea ~/.claude/CLAUDE.md con el protocolo de memoria
#
# Tras instalar, CUALQUIER proyecto que abras con Claude Code tendrá
# el cerebro conectado automáticamente.

set -euo pipefail

# ── Args ────────────────────────────────────────────────────────────
API_URL="${1:-}"
API_KEY="${2:-}"

if [[ -z "$API_URL" || -z "$API_KEY" ]]; then
    echo "Uso: $0 <API_URL> <API_KEY>"
    echo ""
    echo "Ejemplo:"
    echo "  $0 http://192.168.1.156:8050 mi-clave-secreta"
    echo ""
    echo "API_URL = dirección donde corre ai-memory (con puerto)"
    echo "API_KEY = valor de MEMORY_API_KEY en tu .env"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "[memory-brain] Instalando plugin global de AI Memory Brain..."
echo "  API: $API_URL"
echo "  Dir: $CLAUDE_DIR"
echo ""

# ── 1. Hooks ────────────────────────────────────────────────────────
mkdir -p "$CLAUDE_DIR/hooks"

# Hook de ingestión (Stop) — envía cada turno al cerebro
sed "s|http://192.168.1.156:8050|${API_URL}|g" \
    "$SCRIPT_DIR/hooks/ingest-turn.sh" > "$CLAUDE_DIR/hooks/ingest-turn.sh"
chmod +x "$CLAUDE_DIR/hooks/ingest-turn.sh"
echo "[✓] Hook de ingestión instalado"

# Hook de session-start — inyecta sección AI Memory Brain en CLAUDE.md del proyecto
cp "$SCRIPT_DIR/hooks/session-start.sh" "$CLAUDE_DIR/hooks/session-start.sh"
chmod +x "$CLAUDE_DIR/hooks/session-start.sh"
echo "[✓] Hook de session-start instalado"

# ── 2. MCP server ──────────────────────────────────────────────────
MCP_FILE="$CLAUDE_DIR/.mcp.json"
if [[ -f "$MCP_FILE" ]]; then
    # Merge: añadir memoryBrain sin machacar otros servers
    if command -v jq >/dev/null 2>&1; then
        EXISTING=$(cat "$MCP_FILE")
        echo "$EXISTING" | jq --arg url "${API_URL}/mcp" --arg key "$API_KEY" \
            '.mcpServers.memoryBrain = {type: "http", url: $url, headers: {"X-API-Key": $key}}' \
            > "$MCP_FILE"
        echo "[✓] MCP server añadido a $MCP_FILE (merge con config existente)"
    else
        echo "[!] jq no encontrado — no se puede hacer merge seguro de $MCP_FILE"
        echo "    Añade manualmente memoryBrain. Ver plugin/claude-code/README.md"
    fi
else
    cat > "$MCP_FILE" << MCPEOF
{
  "mcpServers": {
    "memoryBrain": {
      "type": "http",
      "url": "${API_URL}/mcp",
      "headers": {
        "X-API-Key": "${API_KEY}"
      }
    }
  }
}
MCPEOF
    echo "[✓] MCP server creado en $MCP_FILE"
fi

# ── 3. Hook en settings.json ───────────────────────────────────────
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
HOOK_CMD="~/.claude/hooks/ingest-turn.sh"

if [[ -f "$SETTINGS_FILE" ]]; then
    if command -v jq >/dev/null 2>&1; then
        # Comprobar si el hook ya existe
        EXISTING_HOOK=$(jq -r '.hooks.Stop // [] | .[].hooks // [] | .[].command // empty' "$SETTINGS_FILE" 2>/dev/null || true)
        if echo "$EXISTING_HOOK" | grep -q "ingest-turn.sh"; then
            echo "[✓] Hook Stop ya existe en $SETTINGS_FILE (sin cambios)"
        else
            HOOK_ENTRY='[{"matcher":"*","hooks":[{"type":"command","command":"~/.claude/hooks/ingest-turn.sh"}]}]'
            jq --argjson hook "$HOOK_ENTRY" '.hooks.Stop = ((.hooks.Stop // []) + $hook)' \
                "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
            echo "[✓] Hook Stop añadido a $SETTINGS_FILE"
        fi
        # Hook SessionStart — inyecta CLAUDE.md en cada proyecto
        EXISTING_START=$(jq -r '.hooks.SessionStart // [] | .[].hooks // [] | .[].command // empty' "$SETTINGS_FILE" 2>/dev/null || true)
        if echo "$EXISTING_START" | grep -q "session-start.sh"; then
            echo "[✓] Hook SessionStart ya existe en $SETTINGS_FILE (sin cambios)"
        else
            START_ENTRY='[{"matcher":"*","hooks":[{"type":"command","command":"~/.claude/hooks/session-start.sh"}]}]'
            jq --argjson hook "$START_ENTRY" '.hooks.SessionStart = ((.hooks.SessionStart // []) + $hook)' \
                "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
            echo "[✓] Hook SessionStart añadido a $SETTINGS_FILE"
        fi
    else
        echo "[!] jq no encontrado — añade el hook manualmente. Ver plugin/claude-code/README.md"
    fi
else
    cat > "$SETTINGS_FILE" << SETEOF
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/ingest-turn.sh"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/session-start.sh"
          }
        ]
      }
    ]
  }
}
SETEOF
    echo "[✓] Settings creado en $SETTINGS_FILE"
fi

# ── 4. CLAUDE.md con protocolo ──────────────────────────────────────
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
MARKER="## AI Memory Brain"

if [[ -f "$CLAUDE_MD" ]] && grep -q "$MARKER" "$CLAUDE_MD"; then
    echo "[✓] Protocolo ya presente en $CLAUDE_MD (sin cambios)"
else
    cat >> "$CLAUDE_MD" << 'PROTEOF'

## AI Memory Brain — Protocolo de memoria persistente

Tienes conectado **AI Memory Brain**, un sistema de memoria compartido entre agentes y sesiones. Usalo proactivamente en TODOS los proyectos.

### Ciclo de sesion

1. **Al empezar**: llama a `get_project_context` con el nombre del proyecto (usa el nombre del directorio actual). Lee lo que devuelve para no duplicar conocimiento.
2. **Mientras trabajas**: guarda proactivamente con las tools MCP cuando ocurra algo relevante (ver triggers).
3. **Al cerrar**: llama a `record_session_summary` resumiendo lo que se hizo.

### Triggers — cuando guardar

| Evento | Tool MCP | Importancia |
|--------|----------|-------------|
| Decision de arquitectura | `store_decision` | 0.85 |
| Bug/error encontrado | `store_error` | 0.7-0.85 |
| Bug resuelto (incluir solucion!) | `store_error` (con resolution) | 0.85 |
| Patron o insight descubierto | `store_memory` (type=observation) | 0.7 |
| Cambio de estado de tarea | `update_task_state` | 0.5-0.7 |
| Conexion entre proyectos | `bridge_projects` | 0.7 |

### Formato

- **content**: QUE paso + POR QUE importa + CONTEXTO (parrafo autocontenido)
- **tags**: jerarquicos, separados por coma (ej: `backend/api, bug/resolved, tech/fastapi`)
- **importance**: 0.5 rutina, 0.7 notable, 0.85 importante, 0.95 critico

### NO guardar

- Resumenes de conversacion (eso lo hace `record_session_summary`)
- Hechos obvios del codigo (para eso esta git)
- Info temporal de debug
- Decisiones triviales
PROTEOF
    echo "[✓] Protocolo añadido a $CLAUDE_MD"
fi

# ── 5. MEMORY_API_KEY en shell ──────────────────────────────────────
SHELL_RC="$HOME/.bashrc"
[[ -f "$HOME/.zshrc" ]] && SHELL_RC="$HOME/.zshrc"

if grep -q "MEMORY_API_KEY" "$SHELL_RC" 2>/dev/null; then
    echo "[✓] MEMORY_API_KEY ya exportada en $SHELL_RC"
else
    echo "" >> "$SHELL_RC"
    echo "# AI Memory Brain" >> "$SHELL_RC"
    echo "export MEMORY_API_KEY=\"${API_KEY}\"" >> "$SHELL_RC"
    echo "[✓] MEMORY_API_KEY añadida a $SHELL_RC"
    echo "    Ejecuta: source $SHELL_RC"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo " AI Memory Brain instalado correctamente."
echo ""
echo " Abre Claude Code en cualquier proyecto y el cerebro"
echo " estará conectado automáticamente."
echo ""
echo " Verificar: claude y comprobar que memoryBrain"
echo " aparece en el panel MCP."
echo "═══════════════════════════════════════════════════════"
