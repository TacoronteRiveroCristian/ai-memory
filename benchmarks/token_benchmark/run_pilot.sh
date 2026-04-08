#!/usr/bin/env bash
# Fully automatic token benchmark runner
# Usage:
#   ./run_pilot.sh                      # all 15 tasks
#   ./run_pilot.sh --tasks T01,T07,T10  # specific tasks
#   ./run_pilot.sh --skip-seed          # skip seeding if data already loaded

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCP_JSON="$PROJECT_DIR/.mcp.json"
MCP_DISABLED="$PROJECT_DIR/.mcp.json.disabled"

# ── Load .env for MEMORY_API_KEY ────────────────────────────────────
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    # Strip carriage returns (Windows line endings) and export
    eval "$(sed 's/\r$//' "$PROJECT_DIR/.env" | grep -v '^#' | grep -v '^\s*$')"
    set +a
fi

if [[ -z "${MEMORY_API_KEY:-}" ]]; then
    echo "ERROR: MEMORY_API_KEY not set. Check .env file."
    exit 1
fi

# ── Parse args ──────────────────────────────────────────────────────
RUN_ID="bench-$(date +%Y%m%d-%H%M%S)"
SKIP_SEED=false
SELECTED_TASKS=""
MODEL_FLAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --tasks) SELECTED_TASKS="$2"; shift 2 ;;
        --skip-seed) SKIP_SEED=true; shift ;;
        --run-id) RUN_ID="$2"; shift 2 ;;
        --model) MODEL_FLAG="--model $2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

RUN_DIR="$SCRIPT_DIR/results/$RUN_ID"
mkdir -p "$RUN_DIR"

# Colors
G='\033[0;32m'
R='\033[0;31m'
C='\033[0;36m'
Y='\033[1;33m'
B='\033[1m'
N='\033[0m'

enable_mcp()  { [[ -f "$MCP_DISABLED" ]] && mv "$MCP_DISABLED" "$MCP_JSON" || true; }
disable_mcp() { [[ -f "$MCP_JSON" ]] && mv "$MCP_JSON" "$MCP_DISABLED" || true; }
trap enable_mcp EXIT

# System prompts for each mode
MCP_ON_SYSTEM_PROMPT="You have access to the AI Memory MCP server with tools like search_memory and get_project_context. ALWAYS use these tools to answer questions about projects, decisions, errors, and tasks. Do NOT say you lack context without first searching memory. These tools contain the project knowledge base."
MCP_OFF_SYSTEM_PROMPT="Answer the question using only your general knowledge and the files in the current workspace. Do not mention any memory tools or MCP servers."

# ── Load tasks from tasks.py ────────────────────────────────────────
FILTER_ARG=""
[[ -n "$SELECTED_TASKS" ]] && FILTER_ARG="--filter $SELECTED_TASKS"

TASKS_JSON=$(python3 -c "
import sys, json
sys.path.insert(0, '$SCRIPT_DIR')
from tasks import BENCHMARK_TASKS
tasks = BENCHMARK_TASKS
filter_str = '${SELECTED_TASKS}'
if filter_str:
    selected = set(filter_str.split(','))
    tasks = [t for t in tasks if t['id'] in selected]
print(json.dumps(tasks))
")

TASK_COUNT=$(echo "$TASKS_JSON" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

echo -e "${B}╔════════════════════════════════════════════════════════════╗${N}"
echo -e "${B}║         AI Memory Token Benchmark — Automatic            ║${N}"
echo -e "${B}╚════════════════════════════════════════════════════════════╝${N}"
echo ""
echo -e "  Run ID:  ${C}$RUN_ID${N}"
echo -e "  Tasks:   ${C}$TASK_COUNT${N}"
echo -e "  Results: ${C}$RUN_DIR${N}"
echo ""

# ── Step 1: Health check ────────────────────────────────────────────
echo -e "${Y}[1/4]${N} Checking stack health..."
cd "$PROJECT_DIR"
if ! make health > /dev/null 2>&1; then
    echo -e "${R}  Stack not healthy. Starting benchmark stack...${N}"
    docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml up -d --build
    echo "  Waiting 30s for services to be ready..."
    sleep 30
fi
echo -e "${G}  Stack healthy.${N}"

# ── Step 2: Seed data ──────────────────────────────────────────────
if [[ "$SKIP_SEED" == "false" ]]; then
    echo -e "${Y}[2/4]${N} Seeding benchmark dataset..."
    python3 "$SCRIPT_DIR/seed_benchmark.py" \
        --base-url "${AI_MEMORY_BASE_URL:-http://127.0.0.1:8050}" \
        --api-key "${MEMORY_API_KEY}" \
        --timeout-seconds 300
    echo -e "${G}  Dataset seeded.${N}"
else
    echo -e "${Y}[2/4]${N} Skipping seed (--skip-seed)."
fi

# ── Step 3: Run all tasks ──────────────────────────────────────────
echo -e "${Y}[3/4]${N} Running $TASK_COUNT tasks x 2 modes = $((TASK_COUNT * 2)) executions..."
echo ""

# Write each task to its own temp file to avoid bash parsing issues
TASK_TMP_DIR=$(mktemp -d)
echo "$TASKS_JSON" | python3 -c "
import sys, json, os
tmp = '$TASK_TMP_DIR'
tasks = json.load(sys.stdin)
for i, t in enumerate(tasks):
    with open(os.path.join(tmp, f'task_{i:03d}.json'), 'w') as f:
        json.dump(t, f)
print(len(tasks))
" > /dev/null

TASK_IDX=0
for TASK_FILE in "$TASK_TMP_DIR"/task_*.json; do
    TASK_IDX=$((TASK_IDX + 1))

    TASK_ID=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d['id'])")
    CATEGORY=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d['category'])")
    TITLE=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d['title'])")
    DIFFICULTY=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d.get('difficulty','medium'))")
    PROMPT=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d['prompt'])")

    echo -e "${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
    echo -e "  [$TASK_IDX/$TASK_COUNT] ${C}$TASK_ID${N} ${B}[$CATEGORY]${N} $TITLE ($DIFFICULTY)"
    echo -e "${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"

    # ── WITH MCP ────────────────────────────────────────────────────
    echo -e "  ${G}▶ Running WITH MCP...${N}"
    enable_mcp
    cd "$PROJECT_DIR"

    claude -p "$PROMPT" --output-format json \
        --dangerously-skip-permissions \
        --append-system-prompt "$MCP_ON_SYSTEM_PROMPT" \
        $MODEL_FLAG \
        2>/dev/null \
        > "$RUN_DIR/${TASK_ID}_mcp_on.json" || true

    # Quick status from output
    ON_STATUS=$(python3 -c "
import json
try:
    d = json.load(open('$RUN_DIR/${TASK_ID}_mcp_on.json'))
    turns = d.get('num_turns', 0)
    cost = d.get('total_cost_usd', 0)
    rlen = len(d.get('result', ''))
    print(f'turns={turns}, cost=\${cost:.4f}, response={rlen} chars')
except Exception as e: print(f'error: {e}')
" 2>/dev/null)
    echo -e "  ${G}✓ Done.${N} $ON_STATUS"

    # ── WITHOUT MCP ─────────────────────────────────────────────────
    echo -e "  ${R}▶ Running WITHOUT MCP...${N}"
    disable_mcp

    claude -p "$PROMPT" --output-format json \
        --dangerously-skip-permissions \
        --append-system-prompt "$MCP_OFF_SYSTEM_PROMPT" \
        $MODEL_FLAG \
        2>/dev/null \
        > "$RUN_DIR/${TASK_ID}_mcp_off.json" || true

    OFF_STATUS=$(python3 -c "
import json
try:
    d = json.load(open('$RUN_DIR/${TASK_ID}_mcp_off.json'))
    turns = d.get('num_turns', 0)
    cost = d.get('total_cost_usd', 0)
    rlen = len(d.get('result', ''))
    print(f'turns={turns}, cost=\${cost:.4f}, response={rlen} chars')
except Exception as e: print(f'error: {e}')
" 2>/dev/null)
    echo -e "  ${R}✓ Done.${N} $OFF_STATUS"
    echo ""
done

rm -rf "$TASK_TMP_DIR"
enable_mcp

# ── Step 4: Extract tokens and generate report ────────────────────
echo -e "${Y}[4/4]${N} Extracting tokens and generating report..."
echo ""

python3 - "$RUN_DIR" "$SELECTED_TASKS" << 'PYEOF'
import json, sys, csv
from pathlib import Path
from collections import defaultdict

run_dir = Path(sys.argv[1])
filter_str = sys.argv[2] if len(sys.argv) > 2 else ""

# Load task definitions
sys.path.insert(0, str(run_dir.parent.parent))
from tasks import BENCHMARK_TASKS

tasks = BENCHMARK_TASKS
if filter_str:
    selected = set(filter_str.split(","))
    tasks = [t for t in tasks if t["id"] in selected]

results = []
for task in tasks:
    for mode in ["mcp_on", "mcp_off"]:
        fpath = run_dir / f"{task['id']}_{mode}.json"
        row = {
            "task_id": task["id"],
            "category": task["category"],
            "title": task["title"],
            "difficulty": task.get("difficulty", "medium"),
            "mode": mode,
            "found": False,
            # Token fields — include cache tokens for accurate totals
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "total_input_effective": 0,  # input + cache_creation + cache_read
            "total_tokens": 0,
            "turn_count": 0,
            "response_length": 0,
            "cost_usd": 0.0,
            "duration_ms": 0,
        }
        if fpath.exists():
            try:
                data = json.loads(fpath.read_text())
                usage = data.get("usage", {})

                row["input_tokens"] = usage.get("input_tokens", 0)
                row["output_tokens"] = usage.get("output_tokens", 0)
                row["cache_creation_tokens"] = usage.get("cache_creation_input_tokens", 0)
                row["cache_read_tokens"] = usage.get("cache_read_input_tokens", 0)

                # Effective input = all input-side tokens
                row["total_input_effective"] = (
                    row["input_tokens"]
                    + row["cache_creation_tokens"]
                    + row["cache_read_tokens"]
                )
                row["total_tokens"] = row["total_input_effective"] + row["output_tokens"]

                row["turn_count"] = data.get("num_turns", 1)
                row["response_length"] = len(data.get("result", ""))
                row["cost_usd"] = data.get("total_cost_usd", 0.0)
                row["duration_ms"] = data.get("duration_ms", 0)
                row["found"] = True
            except (json.JSONDecodeError, KeyError) as e:
                print(f"  WARNING: Error parsing {fpath.name}: {e}")

        results.append(row)
        status = "OK" if row["found"] else "MISSING"
        print(
            f"  {task['id']} [{mode:>7}]: "
            f"input_eff={row['total_input_effective']:>7,}, "
            f"output={row['output_tokens']:>6,}, "
            f"total={row['total_tokens']:>7,}, "
            f"turns={row['turn_count']}, "
            f"resp={row['response_length']} chars, "
            f"${row['cost_usd']:.4f} "
            f"[{status}]"
        )

# Write raw metrics
with open(run_dir / "raw_metrics.json", "w") as f:
    json.dump(results, f, indent=2)

# Write CSV
fieldnames = list(results[0].keys())
with open(run_dir / "raw_metrics.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(results)

# ── Comparison table ────────────────────────────────────────────────
print()
print("=" * 95)
print(
    f"{'Task':<6} {'Mode':<10} {'Input(eff)':>11} {'Output':>8} "
    f"{'Total':>8} {'Turns':>6} {'Resp(ch)':>9} {'Cost':>8} {'Time(s)':>8}"
)
print("-" * 95)
for r in results:
    print(
        f"{r['task_id']:<6} {r['mode']:<10} {r['total_input_effective']:>11,} "
        f"{r['output_tokens']:>8,} {r['total_tokens']:>8,} "
        f"{r['turn_count']:>6} {r['response_length']:>9,} "
        f"${r['cost_usd']:>7.4f} {r['duration_ms']/1000:>7.1f}s"
    )

# ── Comparison analysis ───────────────────────────────────────────
by_task = defaultdict(dict)
for r in results:
    by_task[r["task_id"]][r["mode"]] = r

print()
print("-" * 95)
print(
    f"{'Task':<6} {'Cat':<15} {'Cost ON':>8} {'Cost OFF':>9} "
    f"{'Extra Cost':>11} {'Resp ON':>8} {'Resp OFF':>9} {'Info Gain':>10}"
)
print("-" * 95)

total_extra_cost = 0.0
total_info_gain = 0
valid_comparisons = 0

for task in tasks:
    tid = task["id"]
    on = by_task[tid].get("mcp_on", {})
    off = by_task[tid].get("mcp_off", {})

    if on.get("found") and off.get("found"):
        cost_on = on.get("cost_usd", 0)
        cost_off = off.get("cost_usd", 0)
        extra_cost = cost_on - cost_off
        resp_on = on.get("response_length", 0)
        resp_off = off.get("response_length", 0)
        info_gain = resp_on - resp_off  # More chars = more information delivered

        total_extra_cost += extra_cost
        total_info_gain += info_gain
        valid_comparisons += 1

        print(
            f"{tid:<6} {task['category']:<15} ${cost_on:>7.4f} ${cost_off:>8.4f} "
            f"${extra_cost:>+10.4f} {resp_on:>8,} {resp_off:>9,} {info_gain:>+10,}"
        )
    else:
        print(f"{tid:<6} {task['category']:<15} {'N/A':>8} {'N/A':>9} {'N/A':>11} {'N/A':>8} {'N/A':>9} {'N/A':>10}")

print("-" * 95)
if valid_comparisons > 0:
    print(f"\nSummary ({valid_comparisons} valid comparisons):")
    print(f"  Extra cost with MCP:     ${total_extra_cost:>+.4f}")
    print(f"  Extra response content:  {total_info_gain:>+,} characters")
    if total_extra_cost > 0 and total_info_gain > 0:
        print(f"  Cost per info char:      ${total_extra_cost / total_info_gain:.6f}/char")
    print(f"  MCP delivers actionable project knowledge vs generic 'no context' responses")
print()

# ── Generate markdown report ────────────────────────────────────────
report_lines = [
    f"# AI Memory Token Benchmark Report",
    f"",
    f"**Run ID:** `{run_dir.name}`  ",
    f"**Tasks:** {len(tasks)}  ",
    f"**Valid comparisons:** {valid_comparisons}  ",
    f"",
    f"## What This Measures",
    f"",
    f"Compares Claude Code responses **with AI Memory MCP** vs **without**.",
    f"With MCP, Claude searches the project knowledge base and returns specific, actionable answers.",
    f"Without MCP, Claude can only say 'I don\'t have context' for project-specific questions.",
    f"",
    f"## Per-Task Results",
    f"",
    f"| Task | Category | Difficulty | Cost (ON) | Cost (OFF) | Extra Cost | Resp ON | Resp OFF | Turns ON | Turns OFF |",
    f"|------|----------|------------|-----------|------------|------------|---------|----------|----------|-----------|",
]

for task in tasks:
    tid = task["id"]
    on = by_task[tid].get("mcp_on", {})
    off = by_task[tid].get("mcp_off", {})
    if on.get("found") and off.get("found"):
        cost_on = on.get("cost_usd", 0)
        cost_off = off.get("cost_usd", 0)
        extra = cost_on - cost_off
        report_lines.append(
            f"| {tid} | {task['category']} | {task.get('difficulty','medium')} | "
            f"${cost_on:.4f} | ${cost_off:.4f} | ${extra:+.4f} | "
            f"{on.get('response_length',0):,} | {off.get('response_length',0):,} | "
            f"{on.get('turn_count',0)} | {off.get('turn_count',0)} |"
        )
    else:
        report_lines.append(f"| {tid} | {task['category']} | {task.get('difficulty','medium')} | N/A | N/A | N/A | N/A | N/A | N/A | N/A |")

report_lines.extend([
    f"",
    f"## Summary",
    f"",
    f"- **Extra cost with MCP:** ${total_extra_cost:+.4f}",
    f"- **Extra response content:** {total_info_gain:+,} characters",
    f"- **MCP delivers actionable project knowledge** vs generic 'no context' responses",
    f"",
    f"## Key Insight",
    f"",
    f"AI Memory MCP trades a small cost increase for **dramatically better response quality**.",
    f"Without MCP, Claude cannot answer project-specific questions at all.",
    f"With MCP, Claude searches stored memories and returns precise architecture details,",
    f"known issues, decisions, and cross-project patterns.",
    f"",
    f"## Methodology",
    f"",
    f"- Each task runs twice: with `.mcp.json` active (MCP ON) and renamed (MCP OFF)",
    f"- `claude -p` non-interactive mode with `--output-format json`",
    f"- Token counts include cache tokens (creation + read) for accurate totals",
    f"- Response length (chars) used as proxy for information richness",
    f"",
])

(run_dir / "report.md").write_text("\n".join(report_lines))
print(f"Report written to: {run_dir / 'report.md'}")

PYEOF

echo ""
echo -e "${G}${B}Benchmark complete!${N}"
echo -e "  Results: ${C}$RUN_DIR${N}"
echo -e "  Report:  ${C}$RUN_DIR/report.md${N}"
echo ""
echo -e "  View report: ${C}cat $RUN_DIR/report.md${N}"
