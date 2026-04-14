"""Redact secrets from turn payloads before classification or storage."""
from __future__ import annotations

import os
import re
from typing import Any

REDACTION_MARKER = "[REDACTED]"

_BUILTIN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    re.compile(
        r"(?i)\b(?:PASSWORD|SECRET|TOKEN|API[_-]?KEY|APIKEY|PRIVATE[_-]?KEY)\s*=\s*([^\s'\"]+)"
    ),
]


def _extra_patterns() -> list[re.Pattern[str]]:
    raw = os.getenv("INGEST_REDACTION_PATTERNS", "").strip()
    if not raw:
        return []
    return [re.compile(p) for p in raw.split(";") if p.strip()]


def sanitize_text(text: str) -> str:
    if not text:
        return text
    patterns = _BUILTIN_PATTERNS + _extra_patterns()
    for pat in patterns:
        if pat.groups:
            text = pat.sub(lambda m: m.group(0).replace(m.group(1), REDACTION_MARKER), text)
        else:
            text = pat.sub(REDACTION_MARKER, text)
    return text


def sanitize_turn(turn: dict[str, Any]) -> dict[str, Any]:
    out = dict(turn)
    for key in ("user_message", "assistant_message"):
        if isinstance(out.get(key), str):
            out[key] = sanitize_text(out[key])
    tool_calls = out.get("tool_calls") or []
    new_calls = []
    for tc in tool_calls:
        tc2 = dict(tc)
        for k in ("summary", "target"):
            if isinstance(tc2.get(k), str):
                tc2[k] = sanitize_text(tc2[k])
        new_calls.append(tc2)
    out["tool_calls"] = new_calls
    return out
