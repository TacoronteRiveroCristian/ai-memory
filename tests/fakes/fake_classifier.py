"""Deterministic classifier for tests. Mirrors Classifier.classify() surface."""
from __future__ import annotations

from typing import Any

from ingest_models import ClassifiedAction, ClassifierResult


class FakeClassifier:
    def classify(self, turn: dict[str, Any]) -> ClassifierResult:
        user = (turn.get("user_message") or "").lower()
        assistant = (turn.get("assistant_message") or "").lower()
        actions: list[ClassifiedAction] = []
        if "bug" in user or "error" in user:
            actions.append(ClassifiedAction(
                type="store_error",
                title="Fake detected bug",
                content=f"User reported a bug and assistant responded: {assistant[:200] or 'n/a'}",
                tags="fake/error",
                importance=0.85,
            ))
        if "decision" in user or "decisión" in user or "decide" in assistant:
            actions.append(ClassifiedAction(
                type="store_decision",
                title="Fake decision captured",
                content=f"A decision was taken in this turn: {assistant[:200] or 'n/a'}",
                tags="fake/decision",
                importance=0.9,
            ))
        if "pattern" in assistant or "insight" in assistant:
            actions.append(ClassifiedAction(
                type="store_observation",
                title="Fake observation",
                content=f"Observation from assistant reply: {assistant[:200]}",
                tags="fake/observation",
                importance=0.7,
            ))
        return ClassifierResult(actions=actions)
