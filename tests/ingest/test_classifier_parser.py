import pytest
from pydantic import ValidationError
from ingest_models import (
    TurnPayload,
    ClassifiedAction,
    parse_classifier_response,
)


def test_turn_payload_accepts_minimal_valid():
    t = TurnPayload(
        project="ai-memory",
        session_id="s1",
        turn_id="t1",
        timestamp="2026-04-13T00:00:00Z",
        user_message="a " * 20,
        assistant_message="done",
        tool_calls=[],
    )
    assert t.project == "ai-memory"


def test_classified_action_rejects_bad_type():
    with pytest.raises(ValidationError):
        ClassifiedAction(
            type="store_invalid", title="x", content="a" * 11, tags="", importance=0.7
        )


def test_classified_action_rejects_importance_out_of_range():
    with pytest.raises(ValidationError):
        ClassifiedAction(
            type="store_decision", title="x", content="a" * 11, tags="", importance=0.4
        )


def test_parse_classifier_response_drops_bad_actions_keeps_good():
    raw = {
        "actions": [
            {"type": "store_decision", "title": "Good", "content": "a" * 20, "tags": "x", "importance": 0.8},
            {"type": "nope", "title": "Bad", "content": "a" * 20, "tags": "", "importance": 0.8},
        ]
    }
    result = parse_classifier_response(raw)
    assert len(result.actions) == 1
    assert result.actions[0].title == "Good"


def test_parse_classifier_response_empty_list_is_valid():
    result = parse_classifier_response({"actions": []})
    assert result.actions == []


def test_parse_classifier_response_malformed_raises():
    with pytest.raises(ValueError):
        parse_classifier_response({"not_actions": "hello"})
