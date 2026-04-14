"""Normalized-hash dedupe against recently-stored memories."""
from __future__ import annotations

import hashlib
import os
import re
import string
import unicodedata
from typing import Any

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_for_hash(text: str) -> str:
    if not text:
        return hashlib.sha256(b"").hexdigest()[:16]
    text = _strip_accents(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.translate(_PUNCT_TABLE)
    text = text[:200]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def action_fingerprint(action: dict[str, Any]) -> str:
    title = action.get("title", "") or ""
    content = (action.get("content", "") or "")[:200]
    return normalize_for_hash(f"{title} {content}")


def is_duplicate(action: dict[str, Any], recent_memories: list[dict[str, Any]]) -> bool:
    target = action_fingerprint(action)
    return any(action_fingerprint(m) == target for m in recent_memories)


def lookback_limit() -> int:
    return int(os.getenv("INGEST_DEDUPE_LOOKBACK", "10"))
