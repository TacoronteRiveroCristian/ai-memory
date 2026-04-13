"""Per-session in-process rate limiter for /ingest_turn."""
from __future__ import annotations

import os
import time
from threading import Lock


class RateLimiter:
    def __init__(self, window_seconds: float | None = None) -> None:
        self.window = (
            window_seconds
            if window_seconds is not None
            else float(os.getenv("INGEST_RATE_LIMIT_WINDOW_SECONDS", "2"))
        )
        self._last: dict[str, float] = {}
        self._lock = Lock()

    def allow(self, session_id: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._last.get(session_id, 0.0)
            if now - last < self.window:
                return False
            self._last[session_id] = now
        return True
