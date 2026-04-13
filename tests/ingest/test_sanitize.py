import pytest
from ingest_sanitize import sanitize_text, sanitize_turn


@pytest.mark.parametrize("raw,expected_marker", [
    ("my key is sk-abc123def456ghi789jkl012mno345", "[REDACTED]"),
    ("anthropic sk-ant-api03-AAAAAAAAAAAAAAAAAAAA key", "[REDACTED]"),
    ("access AKIAABCDEFGHIJKLMNOP token", "[REDACTED]"),
    ("use ghp_1234567890abcdefghij1234567890abcdef to auth", "[REDACTED]"),
    ("bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdef", "[REDACTED]"),
    ("line PASSWORD=hunter2 here", "[REDACTED]"),
    ("export API_KEY=very-secret", "[REDACTED]"),
])
def test_sanitize_redacts_known_patterns(raw, expected_marker):
    out = sanitize_text(raw)
    assert expected_marker in out
    for token in ("sk-abc123", "AKIAABCDEFGHIJKLMNOP", "ghp_1234567890", "hunter2", "very-secret"):
        if token in raw:
            assert token not in out


def test_sanitize_leaves_clean_text_alone():
    raw = "This is just a normal sentence with no secrets."
    assert sanitize_text(raw) == raw


def test_sanitize_turn_applies_to_all_string_fields():
    turn = {
        "user_message": "use sk-abc123def456ghi789jkl012mno345 to call",
        "assistant_message": "sure, export API_KEY=secret-value",
        "tool_calls": [
            {"name": "Bash", "summary": "curl -H 'Authorization: Bearer eyJhbGc.eyJzdWI.abc'"}
        ],
        "project": "ai-memory",
        "session_id": "s1",
        "turn_id": "t1",
        "timestamp": "2026-04-13T00:00:00Z",
    }
    out = sanitize_turn(turn)
    assert "[REDACTED]" in out["user_message"]
    assert "[REDACTED]" in out["assistant_message"]
    assert "[REDACTED]" in out["tool_calls"][0]["summary"]
    assert out["project"] == "ai-memory"
    assert out["session_id"] == "s1"
