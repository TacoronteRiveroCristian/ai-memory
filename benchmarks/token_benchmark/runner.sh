#!/usr/bin/env bash
# Token Benchmark Runner — guides user through benchmark execution
# Usage: ./runner.sh [--run-id RUN_ID] [--tasks T01,T02,...] [--skip-seed]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCP_JSON="$PROJECT_DIR/.mcp.json"
MCP_DISABLED="$PROJECT_DIR/.mcp.json.disabled"
RESULTS_DIR="$SCRIPT_DIR/results"

# Defaults
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
SKIP_SEED=false
SELECTED_TASKS=""

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --run-id) RUN_ID="$2"; shift 2 ;;
        --tasks) SELECTED_TASKS="$2"; shift 2 ;;
        --skip-seed) SKIP_SEED=true; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

RUN_DIR="$RESULTS_DIR/$RUN_ID"
SESSIONS_FILE="$RUN_DIR/sessions.json"

mkdir -p "$RUN_DIR"

# ── Colors ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

# ── Helper functions ────────────────────────────────────────────────

enable_mcp() {
    if [[ -f "$MCP_DISABLED" ]]; then
        mv "$MCP_DISABLED" "$MCP_JSON"
    fi
}

disable_mcp() {
    if [[ -f "$MCP_JSON" ]]; then
        mv "$MCP_JSON" "$MCP_DISABLED"
    fi
}

restore_mcp() {
    enable_mcp 2>/dev/null || true
}
trap restore_mcp EXIT

# ── Load tasks from Python ──────────────────────────────────────────

TASKS_JSON=$(python3 -c "
import sys, json
sys.path.insert(0, '$SCRIPT_DIR')
from tasks import BENCHMARK_TASKS
tasks = BENCHMARK_TASKS
print(json.dumps(tasks))
")

if [[ -n "$SELECTED_TASKS" ]]; then
    IFS=',' read -ra FILTER <<< "$SELECTED_TASKS"
    TASKS_JSON=$(echo "$TASKS_JSON" | python3 -c "
import sys, json
tasks = json.load(sys.stdin)
selected = set('${SELECTED_TASKS}'.split(','))
print(json.dumps([t for t in tasks if t['id'] in selected]))
")
fi

TASK_COUNT=$(echo "$TASKS_JSON" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")

# ── Banner ──────────────────────────────────────────────────────────

echo -e "${BOLD}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       AI Memory Token Benchmark Runner                ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Run ID:  ${CYAN}$RUN_ID${NC}"
echo -e "  Tasks:   ${CYAN}$TASK_COUNT${NC}"
echo -e "  Results: ${CYAN}$RUN_DIR${NC}"
echo ""

# ── Step 1: Health check ────────────────────────────────────────────

echo -e "${YELLOW}[1/4]${NC} Checking stack health..."
cd "$PROJECT_DIR"
if ! make health > /dev/null 2>&1; then
    echo -e "${RED}Stack not healthy. Run: make stack-up${NC}"
    exit 1
fi
echo -e "${GREEN}  Stack healthy.${NC}"

# ── Step 2: Seed (optional) ─────────────────────────────────────────

if [[ "$SKIP_SEED" == "false" ]]; then
    echo -e "${YELLOW}[2/4]${NC} Seeding benchmark dataset..."
    python3 "$SCRIPT_DIR/seed_benchmark.py" \
        --base-url "${AI_MEMORY_BASE_URL:-http://127.0.0.1:8050}" \
        --api-key "${MEMORY_API_KEY}" \
        --timeout-seconds 300
    echo -e "${GREEN}  Dataset seeded.${NC}"
else
    echo -e "${YELLOW}[2/4]${NC} Skipping seed (--skip-seed)."
fi

# ── Step 3: Run tasks ───────────────────────────────────────────────

echo -e "${YELLOW}[3/4]${NC} Running benchmark tasks..."
echo ""

# Initialize sessions file
echo '{"run_id": "'"$RUN_ID"'", "sessions": []}' > "$SESSIONS_FILE"

TASK_IDX=0
echo "$TASKS_JSON" | python3 -c "
import sys, json
for t in json.load(sys.stdin):
    print(f\"{t['id']}|{t['category']}|{t['title']}|{t['prompt']}|{t.get('difficulty','medium')}\")
" | while IFS='|' read -r TASK_ID CATEGORY TITLE PROMPT DIFFICULTY; do
    TASK_IDX=$((TASK_IDX + 1))

    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  Task ${CYAN}$TASK_IDX/$TASK_COUNT${NC}: ${BOLD}[$CATEGORY]${NC} $TITLE ($DIFFICULTY)"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # ── WITH MCP ────────────────────────────────────────────────────
    SESSION_ON="bench-${RUN_ID}-${TASK_ID}-mcp_on"

    echo -e "  ${GREEN}▶ Mode: WITH MCP${NC}"
    enable_mcp
    echo -e "  Session ID: ${CYAN}$SESSION_ON${NC}"
    echo ""
    echo -e "  ${BOLD}Prompt:${NC}"
    echo -e "  ${YELLOW}$PROMPT${NC}"
    echo ""
    echo -e "  Run this command in another terminal:"
    echo -e "  ${CYAN}cd $PROJECT_DIR && claude --session-id $SESSION_ON${NC}"
    echo ""
    echo -e "  Then paste the prompt above, wait for the response, and type ${BOLD}/exit${NC}."
    echo ""
    read -rp "  Press ENTER when done with MCP run... "

    # ── WITHOUT MCP ─────────────────────────────────────────────────
    SESSION_OFF="bench-${RUN_ID}-${TASK_ID}-mcp_off"

    echo ""
    echo -e "  ${RED}▶ Mode: WITHOUT MCP${NC}"
    disable_mcp
    echo -e "  Session ID: ${CYAN}$SESSION_OFF${NC}"
    echo ""
    echo -e "  ${BOLD}Prompt (same):${NC}"
    echo -e "  ${YELLOW}$PROMPT${NC}"
    echo ""
    echo -e "  Run this command in another terminal:"
    echo -e "  ${CYAN}cd $PROJECT_DIR && claude --session-id $SESSION_OFF${NC}"
    echo ""
    echo -e "  Then paste the prompt above, wait for the response, and type ${BOLD}/exit${NC}."
    echo ""
    read -rp "  Press ENTER when done without MCP run... "

    # Record sessions
    python3 -c "
import json
with open('$SESSIONS_FILE', 'r') as f:
    data = json.load(f)
data['sessions'].append({
    'task_id': '$TASK_ID',
    'category': '$CATEGORY',
    'title': '$TITLE',
    'difficulty': '$DIFFICULTY',
    'session_mcp_on': '$SESSION_ON',
    'session_mcp_off': '$SESSION_OFF',
})
with open('$SESSIONS_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"

    echo -e "  ${GREEN}✓ Task $TASK_ID recorded.${NC}"
    echo ""
done

# ── Step 4: Extract and report ──────────────────────────────────────

echo -e "${YELLOW}[4/4]${NC} Extracting tokens and generating report..."
enable_mcp

python3 "$SCRIPT_DIR/extract_tokens.py" --run-dir "$RUN_DIR"
python3 "$SCRIPT_DIR/report.py" --run-dir "$RUN_DIR"

echo ""
echo -e "${GREEN}${BOLD}Benchmark complete!${NC}"
echo -e "  Results: ${CYAN}$RUN_DIR${NC}"
echo -e "  Report:  ${CYAN}$RUN_DIR/report.md${NC}"
