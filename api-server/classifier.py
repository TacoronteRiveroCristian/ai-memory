"""Classifier wrapper: OpenAI-compatible client + factory for test/fake provider."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Protocol

from ingest_models import ClassifierResult, parse_classifier_response

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a memory classifier for an AI coding agent. Analyze this turn and \
extract ONLY concrete memory-worthy actions. Return strict JSON.

Valid action types:
- store_decision: a technical/architectural decision was actually taken (not options considered).
- store_error: a bug was encountered AND resolved within this turn (not errors left unresolved).
- store_observation: a pattern, insight, or non-obvious finding useful in future sessions.
- store_architecture: an explicit system design discussion with concrete structural conclusions.

If nothing qualifies, return {"actions": []}. Prefer an empty list over invented content.

For each action emit:
{
  "type": "store_decision" | "store_error" | "store_observation" | "store_architecture",
  "title": "<=80 chars, imperative, specific",
  "content": "self-contained paragraph: WHAT + WHY + CONTEXT",
  "tags": "hierarchical/slash,comma-separated",
  "importance": number between 0.5 and 0.95
}

Return strict JSON: {"actions": [...]}
"""


class ClassifierProtocol(Protocol):
    def classify(self, turn: dict[str, Any]) -> ClassifierResult: ...


class OpenAICompatClassifier:
    def __init__(self) -> None:
        from openai import OpenAI  # lazy import so fake-mode tests don't need the dep
        self.client = OpenAI(
            base_url=os.getenv("CLASSIFIER_BASE_URL", "https://api.deepseek.com/v1"),
            api_key=os.getenv("CLASSIFIER_API_KEY", "missing"),
        )
        self.model = os.getenv("CLASSIFIER_MODEL", "deepseek-chat")
        self.timeout = float(os.getenv("CLASSIFIER_TIMEOUT", "15"))
        self.max_tokens = int(os.getenv("CLASSIFIER_MAX_TOKENS", "1500"))
        self.temperature = float(os.getenv("CLASSIFIER_TEMPERATURE", "0.1"))

    def _render_user_msg(self, turn: dict[str, Any]) -> str:
        tools_block = "\n".join(
            f"- {tc.get('name', '?')} {tc.get('target') or ''}: {tc.get('summary') or ''}"
            for tc in (turn.get("tool_calls") or [])
        ) or "(no tool calls)"
        return (
            f"USER: {turn.get('user_message', '')}\n\n"
            f"ASSISTANT: {turn.get('assistant_message', '')}\n\n"
            f"TOOLS:\n{tools_block}"
        )

    def classify(self, turn: dict[str, Any]) -> ClassifierResult:
        raw_text = "{}"
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": self._render_user_msg(turn)},
                ],
            )
            raw_text = resp.choices[0].message.content or "{}"
            parsed = json.loads(raw_text)
            return parse_classifier_response(parsed)
        except json.JSONDecodeError as e:
            logger.warning("classifier returned non-JSON: %s", raw_text[:500])
            raise ValueError("classifier returned non-JSON") from e


def get_classifier() -> ClassifierProtocol:
    provider = os.getenv("CLASSIFIER_PROVIDER", "openai-compat").lower()
    if provider == "fake":
        import sys
        from pathlib import Path
        fakes_dir = Path(__file__).resolve().parents[1] / "tests" / "fakes"
        if str(fakes_dir) not in sys.path:
            sys.path.insert(0, str(fakes_dir))
        from fake_classifier import FakeClassifier  # type: ignore
        return FakeClassifier()
    return OpenAICompatClassifier()
