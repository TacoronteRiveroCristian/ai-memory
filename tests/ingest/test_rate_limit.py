import time

from ingest_rate_limit import RateLimiter


def test_allows_first_call():
    rl = RateLimiter(window_seconds=2)
    assert rl.allow("session-1") is True


def test_blocks_second_call_in_window():
    rl = RateLimiter(window_seconds=2)
    rl.allow("session-1")
    assert rl.allow("session-1") is False


def test_different_sessions_independent():
    rl = RateLimiter(window_seconds=2)
    rl.allow("a")
    assert rl.allow("b") is True


def test_allows_after_window_elapsed():
    rl = RateLimiter(window_seconds=0.05)
    rl.allow("s")
    time.sleep(0.1)
    assert rl.allow("s") is True
