#!/usr/bin/env python3
"""Generate markdown report from benchmark token extraction results."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# Anthropic pricing (USD per million tokens) — Claude Opus via OAuth/Pro plan
# These are approximate; adjust if needed
PRICE_INPUT_PER_M = 15.0
PRICE_OUTPUT_PER_M = 75.0
PRICE_CACHE_WRITE_PER_M = 3.75
PRICE_CACHE_READ_PER_M = 0.30


def load_metrics(run_dir: Path) -> list[dict]:
    json_path = run_dir / "raw_metrics.json"
    if json_path.exists():
        with open(json_path) as f:
            return json.load(f)

    csv_path = run_dir / "raw_metrics.csv"
    if csv_path.exists():
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = []
            for row in reader:
                for key in ["total_input_tokens", "total_output_tokens", "total_cache_write_tokens",
                            "total_cache_read_tokens", "total_tokens", "turn_count", "tool_calls"]:
                    row[key] = int(row.get(key, 0))
                row["found"] = row.get("found", "True") == "True"
                rows.append(row)
            return rows

    raise FileNotFoundError(f"No metrics file found in {run_dir}")


def compute_cost_usd(metrics: dict) -> float:
    return (
        metrics.get("total_input_tokens", 0) / 1_000_000 * PRICE_INPUT_PER_M
        + metrics.get("total_output_tokens", 0) / 1_000_000 * PRICE_OUTPUT_PER_M
        + metrics.get("total_cache_write_tokens", 0) / 1_000_000 * PRICE_CACHE_WRITE_PER_M
        + metrics.get("total_cache_read_tokens", 0) / 1_000_000 * PRICE_CACHE_READ_PER_M
    )


def pct_change(with_val: float, without_val: float) -> float | None:
    if without_val == 0:
        return None
    return (without_val - with_val) / without_val * 100


def generate_report(run_dir: Path) -> str:
    metrics = load_metrics(run_dir)

    # Group by task_id
    by_task: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in metrics:
        by_task[row["task_id"]][row["mode"]] = row

    lines = []
    lines.append("# Token Benchmark Report")
    lines.append("")

    # Load run metadata
    sessions_file = run_dir / "sessions.json"
    if sessions_file.exists():
        with open(sessions_file) as f:
            sessions_data = json.load(f)
        lines.append(f"**Run ID**: `{sessions_data.get('run_id', 'unknown')}`")
    lines.append("")

    # ── Summary table ───────────────────────────────────────────────
    lines.append("## Summary by Task")
    lines.append("")
    lines.append("| Task | Category | Difficulty | Input Savings | Output Savings | Total Savings | Turn Reduction |")
    lines.append("|------|----------|------------|---------------|----------------|---------------|----------------|")

    task_savings = []
    category_savings: dict[str, list[dict]] = defaultdict(list)

    for task_id in sorted(by_task.keys()):
        modes = by_task[task_id]
        mcp_on = modes.get("mcp_on", {})
        mcp_off = modes.get("mcp_off", {})

        if not mcp_on.get("found") or not mcp_off.get("found"):
            continue

        input_save = pct_change(mcp_on["total_input_tokens"], mcp_off["total_input_tokens"])
        output_save = pct_change(mcp_on["total_output_tokens"], mcp_off["total_output_tokens"])
        total_save = pct_change(mcp_on["total_tokens"], mcp_off["total_tokens"])
        turn_save = pct_change(mcp_on["turn_count"], mcp_off["turn_count"])

        savings_row = {
            "task_id": task_id,
            "category": mcp_on.get("category", ""),
            "difficulty": mcp_on.get("difficulty", ""),
            "input_savings_pct": input_save,
            "output_savings_pct": output_save,
            "total_savings_pct": total_save,
            "turn_reduction_pct": turn_save,
            "mcp_on_cost": compute_cost_usd(mcp_on),
            "mcp_off_cost": compute_cost_usd(mcp_off),
            "mcp_on_total": mcp_on["total_tokens"],
            "mcp_off_total": mcp_off["total_tokens"],
        }
        task_savings.append(savings_row)
        category_savings[mcp_on.get("category", "")].append(savings_row)

        fmt = lambda v: f"{v:+.1f}%" if v is not None else "N/A"
        lines.append(
            f"| {task_id} | {mcp_on.get('category', '')} | {mcp_on.get('difficulty', '')} "
            f"| {fmt(input_save)} | {fmt(output_save)} | {fmt(total_save)} | {fmt(turn_save)} |"
        )

    lines.append("")

    # ── Aggregate metrics ───────────────────────────────────────────
    if task_savings:
        lines.append("## Aggregate Metrics")
        lines.append("")

        valid_total = [s["total_savings_pct"] for s in task_savings if s["total_savings_pct"] is not None]
        valid_input = [s["input_savings_pct"] for s in task_savings if s["input_savings_pct"] is not None]
        valid_turn = [s["turn_reduction_pct"] for s in task_savings if s["turn_reduction_pct"] is not None]

        if valid_total:
            mean_total = sum(valid_total) / len(valid_total)
            median_total = sorted(valid_total)[len(valid_total) // 2]
            best_case = max(valid_total)
            worst_case = min(valid_total)
            best_task = next(s["task_id"] for s in task_savings if s["total_savings_pct"] == best_case)
            worst_task = next(s["task_id"] for s in task_savings if s["total_savings_pct"] == worst_case)

            total_mcp_on = sum(s["mcp_on_total"] for s in task_savings)
            total_mcp_off = sum(s["mcp_off_total"] for s in task_savings)
            total_saved = total_mcp_off - total_mcp_on

            total_cost_on = sum(s["mcp_on_cost"] for s in task_savings)
            total_cost_off = sum(s["mcp_off_cost"] for s in task_savings)

            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Mean total savings | {mean_total:+.1f}% |")
            lines.append(f"| Median total savings | {median_total:+.1f}% |")
            lines.append(f"| Best case | {best_case:+.1f}% ({best_task}) |")
            lines.append(f"| Worst case | {worst_case:+.1f}% ({worst_task}) |")
            if valid_input:
                lines.append(f"| Mean input savings | {sum(valid_input)/len(valid_input):+.1f}% |")
            if valid_turn:
                lines.append(f"| Mean turn reduction | {sum(valid_turn)/len(valid_turn):+.1f}% |")
            lines.append(f"| Total tokens (with MCP) | {total_mcp_on:,} |")
            lines.append(f"| Total tokens (without MCP) | {total_mcp_off:,} |")
            lines.append(f"| Total tokens saved | {total_saved:,} |")
            lines.append(f"| Est. cost with MCP | ${total_cost_on:.4f} |")
            lines.append(f"| Est. cost without MCP | ${total_cost_off:.4f} |")
            lines.append(f"| Est. cost saved | ${total_cost_off - total_cost_on:.4f} |")
            lines.append("")

        # ── By category ─────────────────────────────────────────────
        lines.append("## Savings by Category")
        lines.append("")
        lines.append("| Category | Tasks | Mean Total Savings | Mean Input Savings |")
        lines.append("|----------|-------|--------------------|--------------------|")

        for cat in sorted(category_savings.keys()):
            cat_rows = category_savings[cat]
            cat_total = [s["total_savings_pct"] for s in cat_rows if s["total_savings_pct"] is not None]
            cat_input = [s["input_savings_pct"] for s in cat_rows if s["input_savings_pct"] is not None]
            mean_t = sum(cat_total) / len(cat_total) if cat_total else 0
            mean_i = sum(cat_input) / len(cat_input) if cat_input else 0
            lines.append(f"| {cat} | {len(cat_rows)} | {mean_t:+.1f}% | {mean_i:+.1f}% |")

        lines.append("")

    # ── Raw data ────────────────────────────────────────────────────
    lines.append("## Raw Data per Session")
    lines.append("")
    lines.append("| Task | Mode | Input | Output | Cache Write | Cache Read | Total | Turns | Tools |")
    lines.append("|------|------|-------|--------|-------------|------------|-------|-------|-------|")

    for row in sorted(metrics, key=lambda r: (r["task_id"], r["mode"])):
        if not row.get("found"):
            continue
        lines.append(
            f"| {row['task_id']} | {row['mode']} "
            f"| {row['total_input_tokens']:,} | {row['total_output_tokens']:,} "
            f"| {row['total_cache_write_tokens']:,} | {row['total_cache_read_tokens']:,} "
            f"| {row['total_tokens']:,} | {row['turn_count']} | {row['tool_calls']} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("*Generated by AI Memory Token Benchmark*")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate benchmark report.")
    parser.add_argument("--run-dir", required=True, help="Path to the run results directory")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)

    try:
        report = generate_report(run_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    report_path = run_dir / "report.md"
    with open(report_path, "w") as f:
        f.write(report)

    print(f"Report written to: {report_path}")

    # Also write comparison CSV
    metrics = load_metrics(run_dir)
    by_task: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in metrics:
        by_task[row["task_id"]][row["mode"]] = row

    comparison_path = run_dir / "comparison.csv"
    with open(comparison_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "task_id", "category", "difficulty",
            "mcp_on_input", "mcp_on_output", "mcp_on_total", "mcp_on_turns",
            "mcp_off_input", "mcp_off_output", "mcp_off_total", "mcp_off_turns",
            "input_savings_pct", "output_savings_pct", "total_savings_pct", "turn_reduction_pct",
            "cost_mcp_on", "cost_mcp_off", "cost_saved",
        ])
        for task_id in sorted(by_task.keys()):
            on = by_task[task_id].get("mcp_on", {})
            off = by_task[task_id].get("mcp_off", {})
            if not on.get("found") or not off.get("found"):
                continue

            is_pct = lambda a, b: f"{pct_change(a, b):.1f}" if pct_change(a, b) is not None else ""
            cost_on = compute_cost_usd(on)
            cost_off = compute_cost_usd(off)
            writer.writerow([
                task_id, on.get("category", ""), on.get("difficulty", ""),
                on["total_input_tokens"], on["total_output_tokens"], on["total_tokens"], on["turn_count"],
                off["total_input_tokens"], off["total_output_tokens"], off["total_tokens"], off["turn_count"],
                is_pct(on["total_input_tokens"], off["total_input_tokens"]),
                is_pct(on["total_output_tokens"], off["total_output_tokens"]),
                is_pct(on["total_tokens"], off["total_tokens"]),
                is_pct(on["turn_count"], off["turn_count"]),
                f"{cost_on:.4f}", f"{cost_off:.4f}", f"{cost_off - cost_on:.4f}",
            ])

    print(f"Comparison CSV written to: {comparison_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
