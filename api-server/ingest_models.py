"""Pydantic models for the passive ingest pipeline."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

ActionType = Literal[
    "store_decision", "store_error", "store_observation", "store_architecture"
]


class ToolCallSummary(BaseModel):
    name: str
    target: str | None = None
    summary: str | None = None


class TurnPayload(BaseModel):
    project: str = Field(min_length=1, max_length=200)
    session_id: str = Field(min_length=1, max_length=200)
    turn_id: str = Field(min_length=1, max_length=200)
    timestamp: str
    user_message: str = Field(default="", max_length=4000)
    assistant_message: str = Field(default="", max_length=8000)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list, max_length=20)


class ClassifiedAction(BaseModel):
    type: ActionType
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=10, max_length=4000)
    tags: str = Field(default="", max_length=400)
    importance: float = Field(ge=0.5, le=0.95)


class ClassifierResult(BaseModel):
    actions: list[ClassifiedAction] = Field(default_factory=list)


class ActionOutcome(BaseModel):
    type: ActionType
    memory_id: str | None = None
    links_created: int = 0
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None


class IngestResponse(BaseModel):
    status: Literal["ok", "error"]
    filtered: bool = False
    reason: str | None = None
    stage: str | None = None
    detail: str | None = None
    actions_taken: int = 0
    actions: list[ActionOutcome] = Field(default_factory=list)
    latency_ms: int = 0


def parse_classifier_response(raw: dict[str, Any]) -> ClassifierResult:
    if not isinstance(raw, dict) or "actions" not in raw:
        raise ValueError("classifier response missing 'actions' key")
    items = raw.get("actions") or []
    if not isinstance(items, list):
        raise ValueError("'actions' must be a list")
    good: list[ClassifiedAction] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            good.append(ClassifiedAction(**item))
        except ValidationError:
            continue
    return ClassifierResult(actions=good)
