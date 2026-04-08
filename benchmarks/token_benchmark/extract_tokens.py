#!/usr/bin/env python3
"""Extract token usage from Claude Code session JSONL files."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def find_claude_projects_dir() -> Path:
    """Find the Claude Code projects directory for the ai-memory project."""
    home = Path.home()
    claude_dir = home / ".claude" / "projects"
    if not claude_dir.exists():
        raise FileNotFoundError(f"Claude projects dir not found: {claude_dir}")

    # Look for the ai-memory project dir (path-encoded)
    candidates = list(claude_dir.glob("*ai-memory*"))
    if not candidates:
        # Try broader search
        candidates = list(claude_dir.iterdir())
        candidates = [c for c in candidates if c.is_dir()]

    if len(candidates) == 1:
        return candidates[0]

    # Return the most likely match
    for c in candidates:
        if "ai-memory" in c.name:
            return c

    raise FileNotFoundError(
        f"Could not find ai-memory project dir in {claude_dir}. "
        f"Candidates: {[c.name for c in candidates]}"
    )


def extract_session_tokens(session_file: Path) -> dict:
    """Extract token usage from a single session JSONL file."""
    total_input = 0
    total_output = 0
    total_cache_write = 0
    total_cache_read = 0
    turn_count = 0
    tool_calls = 0
    seen_request_ids: set[str] = set()
    first_timestamp = None
    last_timestamp = None

    with open(session_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            record_type = record.get("type")
            timestamp = record.get("timestamp")

            if timestamp:
                if first_timestamp is None:
                    first_timestamp = timestamp
                last_timestamp = timestamp

            if record_type != "assistant":
                continue

            message = record.get("message", {})
            usage = message.get("usage")
            if not usage:
                continue

            # Deduplicate by requestId (multiple lines per response)
            request_id = record.get("requestId")
            if request_id:
                if request_id in seen_request_ids:
                    continue
                seen_request_ids.add(request_id)

            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)
            total_cache_write += usage.get("cache_creation_input_tokens", 0)
            total_cache_read += usage.get("cache_read_input_tokens", 0)
            turn_count += 1

            # Count tool calls in content blocks
            content = message.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls += 1

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_write_tokens": total_cache_write,
        "total_cache_read_tokens": total_cache_read,
        "total_tokens": total_input + total_output,
        "turn_count": turn_count,
        "tool_calls": tool_calls,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract token usage from benchmark sessions.")
    parser.add_argument("--run-dir", required=True, help="Path to the run results directory")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    sessions_file = run_dir / "sessions.json"

    if not sessions_file.exists():
        print(f"Sessions file not found: {sessions_file}", file=sys.stderr)
        return 1

    with open(sessions_file) as f:
        sessions_data = json.load(f)

    try:
        claude_projects_dir = find_claude_projects_dir()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Claude projects dir: {claude_projects_dir}")

    # Extract tokens for each session pair
    results = []
    for session in sessions_data["sessions"]:
        task_id = session["task_id"]
        category = session["category"]

        for mode, session_id_key in [("mcp_on", "session_mcp_on"), ("mcp_off", "session_mcp_off")]:
            session_id = session[session_id_key]
            session_file = claude_projects_dir / f"{session_id}.jsonl"

            if not session_file.exists():
                print(f"  Warning: Session file not found: {session_file}")
                results.append({
                    "task_id": task_id,
                    "category": category,
                    "title": session.get("title", ""),
                    "difficulty": session.get("difficulty", ""),
                    "mode": mode,
                    "session_id": session_id,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cache_write_tokens": 0,
                    "total_cache_read_tokens": 0,
                    "total_tokens": 0,
                    "turn_count": 0,
                    "tool_calls": 0,
                    "first_timestamp": None,
                    "last_timestamp": None,
                    "found": False,
                })
                continue

            tokens = extract_session_tokens(session_file)
            results.append({
                "task_id": task_id,
                "category": category,
                "title": session.get("title", ""),
                "difficulty": session.get("difficulty", ""),
                "mode": mode,
                "session_id": session_id,
                **tokens,
                "found": True,
            })
            print(f"  {task_id} [{mode}]: input={tokens['total_input_tokens']}, output={tokens['total_output_tokens']}, turns={tokens['turn_count']}")

    # Write CSV
    csv_path = run_dir / "raw_metrics.csv"
    fieldnames = [
        "task_id", "category", "title", "difficulty", "mode", "session_id",
        "total_input_tokens", "total_output_tokens", "total_cache_write_tokens",
        "total_cache_read_tokens", "total_tokens", "turn_count", "tool_calls",
        "first_timestamp", "last_timestamp", "found",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nRaw metrics written to: {csv_path}")

    # Also save as JSON for easier processing
    json_path = run_dir / "raw_metrics.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
