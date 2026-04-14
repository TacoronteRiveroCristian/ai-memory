#!/usr/bin/env bash
# Smoke test for .claude/hooks/ingest-turn.sh
# Validates:
#   1. Exits 0 even when endpoint is unreachable (fire-and-forget)
#   2. Returns in < 200ms (background curl must not block)
#   3. Logs an error entry when the endpoint is unreachable
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/.claude/hooks/ingest-turn.sh"

if [[ ! -x "$HOOK" ]]; then
    echo "FAIL: hook not executable at $HOOK" >&2
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "SKIP: jq not installed" >&2
    exit 0
fi

TMPDIR_T="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_T"' EXIT
LOG_FILE="$TMPDIR_T/ingest.log"

PAYLOAD='{"session_id":"smoke","transcript_path":"smoke","user_message":"hi","assistant_message":"ok","tool_calls":[]}'

# Point at an unreachable port so curl fails fast
export AI_MEMORY_BASE_URL="http://127.0.0.1:1"
export AI_MEMORY_INGEST_LOG="$LOG_FILE"
export AI_MEMORY_PROJECT="hook-smoke"
export MEMORY_API_KEY="test"

START_NS=$(date +%s%N)
echo "$PAYLOAD" | "$HOOK"
RC=$?
END_NS=$(date +%s%N)
ELAPSED_MS=$(( (END_NS - START_NS) / 1000000 ))

if [[ $RC -ne 0 ]]; then
    echo "FAIL: hook exited $RC (expected 0)" >&2
    exit 1
fi

if [[ $ELAPSED_MS -ge 200 ]]; then
    echo "FAIL: hook took ${ELAPSED_MS}ms (expected < 200ms)" >&2
    exit 1
fi

# Wait up to 25s for the backgrounded curl to timeout and log the error
for _ in $(seq 1 50); do
    if [[ -s "$LOG_FILE" ]] && grep -q "ingest_turn" "$LOG_FILE"; then
        echo "PASS: hook returned in ${ELAPSED_MS}ms, error logged"
        exit 0
    fi
    sleep 0.5
done

echo "FAIL: no error entry in $LOG_FILE after 25s" >&2
cat "$LOG_FILE" >&2 || true
exit 1
