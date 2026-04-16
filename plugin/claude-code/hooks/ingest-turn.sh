#!/usr/bin/env bash
# Fire-and-forget Claude Code Stop hook: POST the completed turn to /ingest_turn.
# Designed to return in < 100ms regardless of endpoint health.
# The install.sh script replaces the API_URL placeholder with the real address.
set -u

LOG_FILE="${AI_MEMORY_INGEST_LOG:-$HOME/.claude/ai-memory-ingest.log}"
API_URL="${AI_MEMORY_BASE_URL:-http://192.168.1.156:8050}/ingest_turn"
API_KEY="${MEMORY_API_KEY:-}"
PROJECT="${AI_MEMORY_PROJECT:-$(basename "$PWD")}"

HOOK_JSON="$(cat || true)"
if [[ -z "$HOOK_JSON" ]]; then
    exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "$(date -Iseconds) [warn] jq not installed, ingest hook disabled" >> "$LOG_FILE"
    exit 0
fi

PAYLOAD=$(echo "$HOOK_JSON" | jq --arg project "$PROJECT" '{
    project: $project,
    session_id: (.session_id // "unknown"),
    turn_id: (.transcript_path // .session_id // "unknown" | tostring),
    timestamp: (now | todate),
    user_message: (.user_message // ""),
    assistant_message: (.assistant_message // ""),
    tool_calls: (.tool_calls // [] | map({
        name: (.name // .tool_name // "?"),
        target: (.target // .file_path // null),
        summary: (.summary // .command // .content // "" | tostring | .[0:500])
    }))
}')

(
    RESPONSE=$(curl -s -S -o /tmp/ai-memory-ingest.out -w "%{http_code}" \
        --max-time 20 \
        -X POST "$API_URL" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" 2>/tmp/ai-memory-ingest.err)
    if [[ "$RESPONSE" != "200" ]]; then
        echo "$(date -Iseconds) [error] ingest_turn http=$RESPONSE project=$PROJECT $(cat /tmp/ai-memory-ingest.err 2>/dev/null)" >> "$LOG_FILE"
    fi
) &

disown 2>/dev/null || true
exit 0
