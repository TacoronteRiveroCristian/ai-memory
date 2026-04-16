#!/usr/bin/env bash
# uninstall.sh — Desinstala AI Memory Brain de Claude Code.
#
# Uso:
#   ./plugin/claude-code/uninstall.sh
#
# Qué hace:
#   1. Elimina el hook de ingestión de ~/.claude/hooks/
#   2. Quita memoryBrain de ~/.claude/.mcp.json
#   3. Quita el hook Stop de ~/.claude/settings.json
#   4. Quita el bloque de protocolo de ~/.claude/CLAUDE.md
#
# No toca MEMORY_API_KEY en .bashrc/.zshrc (es inofensiva).

set -euo pipefail

CLAUDE_DIR="$HOME/.claude"

echo "[memory-brain] Desinstalando plugin de AI Memory Brain..."

# 1. Hooks
for HOOK in ingest-turn.sh session-start.sh; do
    if [[ -f "$CLAUDE_DIR/hooks/$HOOK" ]]; then
        rm "$CLAUDE_DIR/hooks/$HOOK"
        echo "[✓] Hook $HOOK eliminado"
    else
        echo "[-] Hook $HOOK no encontrado (ya limpio)"
    fi
done

# 2. MCP server
MCP_FILE="$CLAUDE_DIR/.mcp.json"
if [[ -f "$MCP_FILE" ]] && command -v jq >/dev/null 2>&1; then
    if jq -e '.mcpServers.memoryBrain' "$MCP_FILE" >/dev/null 2>&1; then
        jq 'del(.mcpServers.memoryBrain)' "$MCP_FILE" > "${MCP_FILE}.tmp" && mv "${MCP_FILE}.tmp" "$MCP_FILE"
        echo "[✓] memoryBrain eliminado de $MCP_FILE"
    else
        echo "[-] memoryBrain no encontrado en $MCP_FILE"
    fi
fi

# 3. Hook en settings.json
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
if [[ -f "$SETTINGS_FILE" ]] && command -v jq >/dev/null 2>&1; then
    # Eliminar hooks de memory-brain (Stop y SessionStart)
    jq '
      (.hooks.Stop // []) |= [.[] | select(.hooks | all(.command | test("ingest-turn") | not))] |
      (.hooks.SessionStart // []) |= [.[] | select(.hooks | all(.command | test("session-start") | not))] |
      if .hooks.Stop == [] then del(.hooks.Stop) else . end |
      if .hooks.SessionStart == [] then del(.hooks.SessionStart) else . end |
      if .hooks == {} then del(.hooks) else . end
    ' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
    echo "[✓] Hooks eliminados de $SETTINGS_FILE"
fi

# 4. Bloque en CLAUDE.md
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [[ -f "$CLAUDE_MD" ]]; then
    # Eliminar desde "## AI Memory Brain" hasta el siguiente "## " o fin de archivo
    python3 -c "
import re, sys
text = open('$CLAUDE_MD').read()
text = re.sub(r'\n*## AI Memory Brain.*?(?=\n## |\Z)', '', text, flags=re.DOTALL)
open('$CLAUDE_MD', 'w').write(text.strip() + '\n')
" 2>/dev/null && echo "[✓] Protocolo eliminado de $CLAUDE_MD" || echo "[-] No se pudo limpiar $CLAUDE_MD (hazlo manualmente)"
fi

echo ""
echo "AI Memory Brain desinstalado. Los datos del cerebro siguen intactos."
