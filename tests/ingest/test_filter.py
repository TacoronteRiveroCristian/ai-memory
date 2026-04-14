import pytest
from ingest_filter import should_classify


def _turn(user="Please refactor the auth module to use JWT", assistant="done", tools=None):
    return {
        "user_message": user,
        "assistant_message": assistant,
        "tool_calls": tools or [],
    }


def test_discards_turn_with_no_tool_calls():
    ok, reason = should_classify(_turn(tools=[]))
    assert ok is False
    assert reason == "no_write_tool_calls"


def test_discards_turn_with_only_read_bash():
    ok, reason = should_classify(_turn(tools=[
        {"name": "Bash", "summary": "git log --oneline -5"},
        {"name": "Bash", "summary": "ls -la"},
    ]))
    assert ok is False
    assert reason == "no_write_tool_calls"


def test_accepts_turn_with_edit_tool():
    ok, reason = should_classify(_turn(tools=[{"name": "Edit", "summary": "fix bug"}]))
    assert ok is True


def test_accepts_turn_with_write_bash():
    ok, reason = should_classify(_turn(tools=[
        {"name": "Bash", "summary": "git commit -m 'fix'"},
    ]))
    assert ok is True


def test_discards_trivial_user_message():
    ok, reason = should_classify(_turn(user="ok", tools=[{"name": "Edit", "summary": "x"}]))
    assert ok is False
    assert reason == "trivial_user_message"


def test_discards_short_user_message():
    ok, reason = should_classify(_turn(user="hola", tools=[{"name": "Edit", "summary": "x"}]))
    assert ok is False
    assert reason == "trivial_user_message"


def test_discards_when_agent_already_stored():
    ok, reason = should_classify(_turn(tools=[
        {"name": "Edit", "summary": "fix"},
        {"name": "mcp__memoryBrain__store_decision", "summary": "stored"},
    ]))
    assert ok is False
    assert reason == "agent_already_stored"
