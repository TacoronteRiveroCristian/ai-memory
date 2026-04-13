"""Heuristic prefilter that decides whether a turn should be classified."""
from __future__ import annotations

import os
import re
from typing import Any

_TRIVIAL_RE = re.compile(r"^(ok|gracias|si|no|vale|thanks|perfect|👍)$", re.IGNORECASE)


def _env_csv(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


def _write_tools() -> set[str]:
    return set(_env_csv("INGEST_WRITE_TOOLS", "Edit,Write,NotebookEdit"))


def _bash_write_patterns() -> list[str]:
    return _env_csv(
        "INGEST_BASH_WRITE_PATTERNS",
        "git commit,git push,npm install,make,docker,rm ,mv ",
    )


def _min_user_chars() -> int:
    return int(os.getenv("INGEST_MIN_USER_CHARS", "20"))


def _skip_if_agent_stored() -> bool:
    return os.getenv("INGEST_SKIP_IF_AGENT_STORED", "true").lower() == "true"


def _has_write_tool_call(tool_calls: list[dict[str, Any]]) -> bool:
    write = _write_tools()
    bash_patterns = _bash_write_patterns()
    for tc in tool_calls:
        name = tc.get("name", "")
        if name in write:
            return True
        if name == "Bash":
            summary = (tc.get("summary") or "").lower()
            if any(p.lower() in summary for p in bash_patterns):
                return True
    return False


def _agent_already_stored(tool_calls: list[dict[str, Any]]) -> bool:
    return any(
        (tc.get("name") or "").startswith("mcp__memoryBrain__store_")
        for tc in tool_calls
    )


def should_classify(turn: dict[str, Any]) -> tuple[bool, str]:
    tool_calls = turn.get("tool_calls") or []

    if not _has_write_tool_call(tool_calls):
        return False, "no_write_tool_calls"

    user_msg = (turn.get("user_message") or "").strip()
    if len(user_msg) < _min_user_chars() or _TRIVIAL_RE.match(user_msg):
        return False, "trivial_user_message"

    if _skip_if_agent_stored() and _agent_already_stored(tool_calls):
        return False, "agent_already_stored"

    return True, "ok"
