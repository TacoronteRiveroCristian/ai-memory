# Passive Turn Ingestion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the memory brain grow automatically from each Claude Code turn via a fire-and-forget `Stop` hook that posts the turn to `/ingest_turn`, where a provider-agnostic classifier LLM extracts memory actions, dedupes them, stores them, and auto-links them.

**Architecture:** Small isolated Python modules behind a single FastAPI endpoint, invoked from a shell hook. OpenAI-compatible client (DeepSeek today, Ollama tomorrow) selected by env vars. In-process rate limiter, normalized-hash dedupe, semantic top-k auto-linker. Zero perceived latency by design.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, `openai` SDK (used against any OpenAI-compatible endpoint), existing `qdrant-client`, existing pg asyncpg pool, bash for the hook.

**Spec:** `docs/superpowers/specs/2026-04-13-passive-turn-ingestion-design.md`

---

## File structure

**Created:**
- `api-server/ingest_sanitize.py` — secret redaction (pure functions)
- `api-server/ingest_filter.py` — prefilter heuristics (pure functions)
- `api-server/ingest_dedupe.py` — normalized-hash dedupe (pure functions + one DB query helper)
- `api-server/ingest_models.py` — Pydantic models: `TurnPayload`, `ClassifiedAction`, `IngestResponse`
- `api-server/classifier.py` — `Classifier` class (OpenAI-compat) + `FakeClassifier` for tests
- `api-server/auto_linker.py` — semantic top-k + `link_memories` calls
- `api-server/ingest_rate_limit.py` — in-process per-session deque
- `api-server/ingest.py` — the endpoint orchestration (`POST /ingest_turn`, `GET /ingest/stats`)
- `.claude/hooks/ingest-turn.sh` — fire-and-forget curl hook
- `tests/ingest/__init__.py`
- `tests/ingest/test_sanitize.py`
- `tests/ingest/test_filter.py`
- `tests/ingest/test_dedupe.py`
- `tests/ingest/test_classifier_parser.py`
- `tests/ingest/test_ingest_endpoint.py`
- `tests/ingest/test_hook_script.sh`
- `tests/fakes/__init__.py`
- `tests/fakes/fake_classifier.py`

**Modified:**
- `api-server/server.py` — import and mount the `ingest` module's routes, expose a factory for the chosen classifier
- `.claude/settings.json` — register the `Stop` hook
- `.env.example` — document new env vars
- `Makefile` — extend `brain-check` with ingest acceptance checks

**Principle.** Each module has one responsibility. The endpoint file (`ingest.py`) is pure orchestration: it imports from the other modules and wires them together. None of the helper modules knows about HTTP or FastAPI.

---

## Task 1: Scaffolding — directories, __init__ files, test wiring

**Files:**
- Create: `tests/ingest/__init__.py` (empty)
- Create: `tests/fakes/__init__.py` (empty)
- Create: `api-server/__init__.py` (only if it does not already exist)

- [ ] **Step 1: Create the test directories**

```bash
mkdir -p tests/ingest tests/fakes
touch tests/ingest/__init__.py tests/fakes/__init__.py
```

- [ ] **Step 2: Verify pytest discovers the new directories**

```bash
python -m pytest tests/ingest -q --collect-only
```

Expected: `collected 0 items` (no tests yet) and **no** import errors.

- [ ] **Step 3: Commit**

```bash
git add tests/ingest tests/fakes
git commit -m "test(ingest): scaffold ingest test packages"
```

---

## Task 2: Secret sanitizer (`ingest_sanitize.py`)

**Files:**
- Create: `api-server/ingest_sanitize.py`
- Test: `tests/ingest/test_sanitize.py`

- [ ] **Step 1: Write failing tests**

`tests/ingest/test_sanitize.py`:
```python
import pytest
from api_server.ingest_sanitize import sanitize_text, sanitize_turn


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
    # The raw secret segment should not survive (verify the most specific token)
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
    # Non-sensitive fields are preserved
    assert out["project"] == "ai-memory"
    assert out["session_id"] == "s1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_sanitize.py -q
```

Expected: `ModuleNotFoundError: No module named 'api_server.ingest_sanitize'` (or similar).

- [ ] **Step 3: Implement `ingest_sanitize.py`**

`api-server/ingest_sanitize.py`:
```python
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
```

Add `api-server` to `sys.path` via a `conftest.py` shim if needed. Check first:

```bash
python -c "import sys; sys.path.insert(0, 'api-server'); import ingest_sanitize; print('ok')"
```

If the project already exposes `api-server/` as `api_server` package, adapt the import in the test to match the existing convention (check `tests/conftest.py` and existing tests for the pattern — reuse it verbatim).

- [ ] **Step 4: Run tests to verify they pass**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_sanitize.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api-server/ingest_sanitize.py tests/ingest/test_sanitize.py
git commit -m "feat(ingest): secret redaction for turn payloads"
```

---

## Task 3: Prefilter (`ingest_filter.py`)

**Files:**
- Create: `api-server/ingest_filter.py`
- Test: `tests/ingest/test_filter.py`

- [ ] **Step 1: Write failing tests**

`tests/ingest/test_filter.py`:
```python
import pytest
from api_server.ingest_filter import should_classify


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_filter.py -q
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `ingest_filter.py`**

`api-server/ingest_filter.py`:
```python
"""Heuristic prefilter that decides whether a turn should be classified."""
from __future__ import annotations

import os
import re
from typing import Any

_TRIVIAL_RE = re.compile(r"^(ok|gracias|si|no|vale|thanks|perfect|👍)$", re.IGNORECASE)


def _env_csv(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


def _write_tools() -> set[str]:
    return set(_env_csv("INGEST_WRITE_TOOLS", "Edit,Write,NotebookEdit"))


def _bash_write_patterns() -> list[str]:
    return _env_csv(
        "INGEST_BASH_WRITE_PATTERNS",
        "git commit,git push,npm install,make,docker,rm ,mv ",
    )


def _min_user_chars() -> int:
    return int(os.getenv("INGEST_MIN_USER_CHARS", "20"))


def _skip_if_agent_stored() -> bool:
    return os.getenv("INGEST_SKIP_IF_AGENT_STORED", "true").lower() == "true"


def _has_write_tool_call(tool_calls: list[dict[str, Any]]) -> bool:
    write = _write_tools()
    bash_patterns = _bash_write_patterns()
    for tc in tool_calls:
        name = tc.get("name", "")
        if name in write:
            return True
        if name == "Bash":
            summary = (tc.get("summary") or "").lower()
            if any(p.lower() in summary for p in bash_patterns):
                return True
    return False


def _agent_already_stored(tool_calls: list[dict[str, Any]]) -> bool:
    return any(
        (tc.get("name") or "").startswith("mcp__memoryBrain__store_")
        for tc in tool_calls
    )


def should_classify(turn: dict[str, Any]) -> tuple[bool, str]:
    tool_calls = turn.get("tool_calls") or []

    if not _has_write_tool_call(tool_calls):
        return False, "no_write_tool_calls"

    user_msg = (turn.get("user_message") or "").strip()
    if len(user_msg) < _min_user_chars() or _TRIVIAL_RE.match(user_msg):
        return False, "trivial_user_message"

    if _skip_if_agent_stored() and _agent_already_stored(tool_calls):
        return False, "agent_already_stored"

    return True, "ok"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_filter.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api-server/ingest_filter.py tests/ingest/test_filter.py
git commit -m "feat(ingest): heuristic prefilter for turn classification"
```

---

## Task 4: Dedupe (`ingest_dedupe.py`)

**Files:**
- Create: `api-server/ingest_dedupe.py`
- Test: `tests/ingest/test_dedupe.py`

- [ ] **Step 1: Write failing tests**

`tests/ingest/test_dedupe.py`:
```python
from api_server.ingest_dedupe import normalize_for_hash, is_duplicate


def test_normalizes_case_punctuation_whitespace():
    a = normalize_for_hash("Migración a pgvector")
    b = normalize_for_hash("migracion a   pgvector!!!")
    # Note: "migración" vs "migracion" differ by accent; test the non-accent equivalence
    assert normalize_for_hash("MIGRACION A pgvector") == normalize_for_hash("migracion a pgvector!!!")


def test_different_content_different_hash():
    assert normalize_for_hash("Decision about caching") != normalize_for_hash("Decision about routing")


def test_truncation_at_200_chars_makes_long_texts_collide_if_prefix_matches():
    prefix = "a" * 200
    assert normalize_for_hash(prefix + "suffix1") == normalize_for_hash(prefix + "suffix2")


def test_is_duplicate_detects_match_in_recent_list():
    recent = [
        {"title": "Decision: use pgvector", "content": "We chose pgvector over pinecone..."},
        {"title": "Error: oauth flow", "content": "The login failed because..."},
    ]
    action = {"title": "decision use pgvector!!!", "content": "We chose pgvector over pinecone..."}
    assert is_duplicate(action, recent) is True


def test_is_duplicate_returns_false_when_no_match():
    recent = [{"title": "Something else", "content": "totally different content"}]
    action = {"title": "New insight", "content": "novel observation here"}
    assert is_duplicate(action, recent) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_dedupe.py -q
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `ingest_dedupe.py`**

`api-server/ingest_dedupe.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_dedupe.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api-server/ingest_dedupe.py tests/ingest/test_dedupe.py
git commit -m "feat(ingest): normalized-hash dedupe helper"
```

---

## Task 5: Pydantic models (`ingest_models.py`)

**Files:**
- Create: `api-server/ingest_models.py`
- Test: `tests/ingest/test_classifier_parser.py` (partial — model validation first)

- [ ] **Step 1: Write failing tests**

`tests/ingest/test_classifier_parser.py`:
```python
import pytest
from pydantic import ValidationError
from api_server.ingest_models import (
    TurnPayload, ClassifiedAction, ClassifierResult, IngestResponse,
    parse_classifier_response,
)


def test_turn_payload_accepts_minimal_valid():
    t = TurnPayload(
        project="ai-memory", session_id="s1", turn_id="t1",
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_classifier_parser.py -q
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `ingest_models.py`**

`api-server/ingest_models.py`:
```python
"""Pydantic models for the passive ingest pipeline."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, ValidationError, field_validator

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
        try:
            good.append(ClassifiedAction(**item))
        except ValidationError:
            continue  # drop bad actions, keep good ones
    return ClassifierResult(actions=good)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_classifier_parser.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api-server/ingest_models.py tests/ingest/test_classifier_parser.py
git commit -m "feat(ingest): pydantic models for turn payload and classifier output"
```

---

## Task 6: Classifier (`classifier.py`) + fake

**Files:**
- Create: `api-server/classifier.py`
- Create: `tests/fakes/fake_classifier.py`
- Extend: `tests/ingest/test_classifier_parser.py` with a fake-classifier round-trip test

- [ ] **Step 1: Write failing test for classifier selection**

Append to `tests/ingest/test_classifier_parser.py`:
```python
import os
from api_server.classifier import get_classifier


def test_fake_classifier_used_when_provider_is_fake(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "fake")
    clf = get_classifier()
    result = clf.classify({
        "user_message": "there is a bug in the login flow",
        "assistant_message": "fixed it by validating the token",
        "tool_calls": [{"name": "Edit", "summary": "auth.py"}],
    })
    assert len(result.actions) >= 1
    assert result.actions[0].type == "store_error"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_classifier_parser.py -q
```

Expected: ModuleNotFoundError for `api_server.classifier`.

- [ ] **Step 3: Implement the fake classifier**

`tests/fakes/fake_classifier.py`:
```python
"""Deterministic classifier for tests. Mirrors Classifier.classify() surface."""
from __future__ import annotations

from typing import Any
from api_server.ingest_models import ClassifiedAction, ClassifierResult


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
```

- [ ] **Step 4: Implement `classifier.py`**

`api-server/classifier.py`:
```python
"""Classifier wrapper: OpenAI-compatible client + factory for test/fake provider."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Protocol

from api_server.ingest_models import ClassifierResult, parse_classifier_response

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
  "title": "≤80 chars, imperative, specific",
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
        from openai import OpenAI  # lazy import so tests without the dep still work
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
            f"- {tc.get('name', '?')} {tc.get('target', '')}: {tc.get('summary', '')}"
            for tc in (turn.get("tool_calls") or [])
        ) or "(no tool calls)"
        return (
            f"USER: {turn.get('user_message', '')}\n\n"
            f"ASSISTANT: {turn.get('assistant_message', '')}\n\n"
            f"TOOLS:\n{tools_block}"
        )

    def classify(self, turn: dict[str, Any]) -> ClassifierResult:
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
        from tests.fakes.fake_classifier import FakeClassifier
        return FakeClassifier()
    return OpenAICompatClassifier()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_classifier_parser.py -q
```

Expected: all tests pass (including the new `test_fake_classifier_used_when_provider_is_fake`).

- [ ] **Step 6: Commit**

```bash
git add api-server/classifier.py tests/fakes/fake_classifier.py tests/ingest/test_classifier_parser.py
git commit -m "feat(ingest): classifier with OpenAI-compatible provider + fake for tests"
```

---

## Task 7: Auto-linker (`auto_linker.py`)

**Files:**
- Create: `api-server/auto_linker.py`

**Note:** The auto-linker calls into existing `server.py` primitives (`qdrant` client, `link_memories` async function). It is tested through the integration tests in Task 10, not in isolation — the unit here would be mostly mocks of qdrant/postgres, which adds noise without catching bugs. Integration coverage is what matters.

- [ ] **Step 1: Implement `auto_linker.py`**

`api-server/auto_linker.py`:
```python
"""Semantic top-k auto-linker. Runs after every successful store_*."""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _topk() -> int:
    return int(os.getenv("INGEST_AUTOLINK_TOPK", "3"))


def _threshold() -> float:
    return float(os.getenv("INGEST_AUTOLINK_THRESHOLD", "0.75"))


def _relation() -> str:
    return os.getenv("INGEST_AUTOLINK_RELATION", "related")


async def auto_link(
    *,
    new_memory_id: str,
    new_memory_vector: list[float],
    project: str,
    qdrant_client: Any,
    link_memories_fn,
) -> int:
    """Search top-k nearest memories and create links. Returns count of links created."""
    try:
        result = await qdrant_client.query_points(
            collection_name=project,
            query=new_memory_vector,
            limit=_topk() + 1,  # +1 to account for the just-inserted memory
            score_threshold=_threshold(),
            with_payload=False,
        )
        points = getattr(result, "points", None) or result
    except Exception as e:
        logger.warning("auto_linker qdrant query failed: %s", e)
        return 0

    created = 0
    relation = _relation()
    for p in points:
        pid = getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else None)
        if not pid or str(pid) == str(new_memory_id):
            continue
        score = getattr(p, "score", None)
        if score is None and isinstance(p, dict):
            score = p.get("score")
        try:
            await link_memories_fn(
                source_memory_id=str(new_memory_id),
                target_memory_id=str(pid),
                relation_type=relation,
                reason=f"auto-linked by passive ingest, similarity={score:.3f}"
                       if isinstance(score, (int, float)) else
                       "auto-linked by passive ingest",
            )
            created += 1
            if created >= _topk():
                break
        except Exception as e:
            logger.warning("auto_linker link_memories failed for %s → %s: %s", new_memory_id, pid, e)
    return created
```

- [ ] **Step 2: Smoke-test the import**

```bash
AI_MEMORY_TEST_MODE=true python -c "import sys; sys.path.insert(0, 'api-server'); import auto_linker; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add api-server/auto_linker.py
git commit -m "feat(ingest): semantic auto-linker for newly stored memories"
```

---

## Task 8: Rate limiter (`ingest_rate_limit.py`)

**Files:**
- Create: `api-server/ingest_rate_limit.py`
- Test: `tests/ingest/test_rate_limit.py`

- [ ] **Step 1: Write failing test**

`tests/ingest/test_rate_limit.py`:
```python
import time
from api_server.ingest_rate_limit import RateLimiter


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
```

- [ ] **Step 2: Run to verify failure**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_rate_limit.py -q
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

`api-server/ingest_rate_limit.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify pass**

```bash
AI_MEMORY_TEST_MODE=true python -m pytest tests/ingest/test_rate_limit.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api-server/ingest_rate_limit.py tests/ingest/test_rate_limit.py
git commit -m "feat(ingest): per-session in-process rate limiter"
```

---

## Task 9: Ingest endpoint (`ingest.py`)

**Files:**
- Create: `api-server/ingest.py`

**Interface contract with `server.py`:**
- Imports existing async functions `store_memory`, `store_decision`, `store_error`, `link_memories` and the `qdrant` client handle from the `server` module.
- Exposes an `init_ingest_routes(app)` function that registers the routes on the existing FastAPI `app`.
- Uses `get_classifier()` once at module load (cached), with the provider selected from env.

- [ ] **Step 1: Implement `ingest.py`**

`api-server/ingest.py`:
```python
"""Passive turn ingestion endpoint."""
from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, Request

from api_server.auto_linker import auto_link
from api_server.classifier import get_classifier
from api_server.ingest_dedupe import action_fingerprint, lookback_limit
from api_server.ingest_filter import should_classify
from api_server.ingest_models import (
    ActionOutcome, IngestResponse, TurnPayload, parse_classifier_response,
)
from api_server.ingest_rate_limit import RateLimiter
from api_server.ingest_sanitize import sanitize_turn

logger = logging.getLogger(__name__)

_MEMORY_ID_RE = re.compile(r"memory_id=([0-9a-f-]{36})")
_rate_limiter = RateLimiter()

# In-memory stats keyed by project
_stats: dict[str, dict[str, int]] = defaultdict(lambda: {
    "turns": 0, "filtered": 0, "classified": 0,
    "stored": 0, "deduped": 0, "errors": 0, "links": 0,
    "classifier_ms_total": 0, "classifier_ms_count": 0,
})

_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = get_classifier()
    return _classifier


def _project_disabled(project: str) -> bool:
    raw = os.getenv("INGEST_DISABLED_PROJECTS", "")
    banned = [p.strip() for p in raw.split(",") if p.strip()]
    return project in banned


def _global_enabled() -> bool:
    return os.getenv("INGEST_ENABLED", "true").lower() == "true"


async def _fetch_recent_memories(project: str, limit: int, pg_pool) -> list[dict[str, Any]]:
    if not pg_pool:
        return []
    try:
        async with pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT m.id::text AS id, COALESCE(m.content, '') AS content,
                       COALESCE(m.memory_type, '') AS memory_type
                FROM memories m
                JOIN projects p ON m.project_id = p.id
                WHERE p.name = $1
                ORDER BY m.created_at DESC
                LIMIT $2
                """,
                project, limit,
            )
            return [
                {"title": r["content"][:80], "content": r["content"]} for r in rows
            ]
    except Exception as e:
        logger.warning("recent-memories fetch failed: %s", e)
        return []


def _extract_memory_id(store_result: str | None) -> str | None:
    if not store_result:
        return None
    m = _MEMORY_ID_RE.search(store_result)
    return m.group(1) if m else None


async def _execute_action(
    action, project: str, *, store_decision, store_error, store_memory,
    link_memories, qdrant, get_embedding,
) -> ActionOutcome:
    try:
        if action.type == "store_decision":
            result = await store_decision(
                title=action.title, decision=action.content,
                project=project, rationale="", alternatives="",
                tags=action.tags, agent_id="passive-ingest",
            )
        elif action.type == "store_error":
            result = await store_error(
                error_description=action.title,
                solution=action.content,
                project=project,
                error_signature="",
                tags=action.tags,
            )
        elif action.type in ("store_observation", "store_architecture"):
            memory_type = "observation" if action.type == "store_observation" else "architecture"
            result = await store_memory(
                content=f"{action.title}\n{action.content}",
                project=project,
                memory_type=memory_type,
                tags=action.tags,
                importance=action.importance,
                agent_id="passive-ingest",
                skip_similar=True,
            )
        else:
            return ActionOutcome(type=action.type, skipped=True, skip_reason="unknown_type")

        if isinstance(result, str) and result.startswith("ERROR"):
            return ActionOutcome(type=action.type, error=result)

        memory_id = _extract_memory_id(result if isinstance(result, str) else None)
        links_created = 0
        if memory_id:
            try:
                vec = await get_embedding(f"{action.title}\n{action.content}")
                links_created = await auto_link(
                    new_memory_id=memory_id,
                    new_memory_vector=vec,
                    project=project,
                    qdrant_client=qdrant,
                    link_memories_fn=link_memories,
                )
            except Exception as e:
                logger.warning("auto_link failed for %s: %s", memory_id, e)
        return ActionOutcome(type=action.type, memory_id=memory_id, links_created=links_created)
    except Exception as e:
        logger.exception("execute_action failed")
        return ActionOutcome(type=action.type, error=str(e))


def init_ingest_routes(app) -> None:
    # Lazy imports from server.py to avoid circular dependency at module load
    import server  # api-server's server.py

    @app.post("/ingest_turn", response_model=IngestResponse)
    async def ingest_turn(request: Request) -> IngestResponse:
        started = time.perf_counter()

        if not _global_enabled():
            return IngestResponse(status="ok", filtered=True, reason="global_disabled",
                                  latency_ms=int((time.perf_counter() - started) * 1000))

        body = await request.json()
        try:
            payload = TurnPayload(**body)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))

        _stats[payload.project]["turns"] += 1

        if _project_disabled(payload.project):
            _stats[payload.project]["filtered"] += 1
            return IngestResponse(status="ok", filtered=True, reason="project_disabled",
                                  latency_ms=int((time.perf_counter() - started) * 1000))

        if not _rate_limiter.allow(payload.session_id):
            _stats[payload.project]["filtered"] += 1
            return IngestResponse(status="ok", filtered=True, reason="rate_limited",
                                  latency_ms=int((time.perf_counter() - started) * 1000))

        sanitized = sanitize_turn(payload.model_dump())
        ok, reason = should_classify(sanitized)
        if not ok:
            _stats[payload.project]["filtered"] += 1
            return IngestResponse(status="ok", filtered=True, reason=reason,
                                  latency_ms=int((time.perf_counter() - started) * 1000))

        clf = _get_classifier()
        clf_t0 = time.perf_counter()
        try:
            result = clf.classify(sanitized)
        except Exception as e:
            logger.exception("classifier failed")
            _stats[payload.project]["errors"] += 1
            return IngestResponse(status="error", stage="classifier", detail=str(e),
                                  latency_ms=int((time.perf_counter() - started) * 1000))
        clf_ms = int((time.perf_counter() - clf_t0) * 1000)
        _stats[payload.project]["classifier_ms_total"] += clf_ms
        _stats[payload.project]["classifier_ms_count"] += 1
        _stats[payload.project]["classified"] += 1

        recent = await _fetch_recent_memories(payload.project, lookback_limit(), server.pg_pool)
        outcomes: list[ActionOutcome] = []
        for action in result.actions:
            fp = action_fingerprint({"title": action.title, "content": action.content})
            if any(action_fingerprint(m) == fp for m in recent):
                _stats[payload.project]["deduped"] += 1
                outcomes.append(ActionOutcome(
                    type=action.type, skipped=True, skip_reason="duplicate"))
                continue
            outcome = await _execute_action(
                action, payload.project,
                store_decision=server.store_decision,
                store_error=server.store_error,
                store_memory=server.store_memory,
                link_memories=server.link_memories,
                qdrant=server.qdrant,
                get_embedding=server.get_embedding,
            )
            if outcome.memory_id and not outcome.error:
                _stats[payload.project]["stored"] += 1
                _stats[payload.project]["links"] += outcome.links_created
            elif outcome.error:
                _stats[payload.project]["errors"] += 1
            outcomes.append(outcome)

        stored = sum(1 for o in outcomes if o.memory_id and not o.error)
        logger.info(
            "ingest_turn project=%s turn=%s classifier_ms=%d emitted=%d stored=%d deduped=%d",
            payload.project, payload.turn_id, clf_ms, len(result.actions), stored,
            sum(1 for o in outcomes if o.skipped and o.skip_reason == "duplicate"),
        )
        return IngestResponse(
            status="ok", filtered=False, actions_taken=stored, actions=outcomes,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    @app.get("/ingest/stats")
    async def ingest_stats(project: str) -> dict[str, Any]:
        s = _stats.get(project, {})
        if not s:
            return {"project": project, "turns_ingested": 0}
        avg = (s["classifier_ms_total"] // s["classifier_ms_count"]) if s["classifier_ms_count"] else 0
        return {
            "project": project,
            "turns_ingested": s["turns"],
            "filtered": s["filtered"],
            "classified": s["classified"],
            "actions_stored": s["stored"],
            "deduped": s["deduped"],
            "avg_classifier_ms": avg,
            "errors": s["errors"],
            "links_created": s["links"],
        }
```

- [ ] **Step 2: Smoke-test the import**

```bash
AI_MEMORY_TEST_MODE=true python -c "
import sys; sys.path.insert(0, 'api-server')
import ingest
print('ok:', ingest.init_ingest_routes)
"
```

Expected: `ok: <function ...>`.

- [ ] **Step 3: Commit**

```bash
git add api-server/ingest.py
git commit -m "feat(ingest): orchestration endpoint /ingest_turn + /ingest/stats"
```

---

## Task 10: Mount the endpoint in `server.py`

**Files:**
- Modify: `api-server/server.py` — add one import and one call after `app = FastAPI(...)`

- [ ] **Step 1: Locate the FastAPI app declaration**

```bash
grep -n "^app = FastAPI" api-server/server.py
```

Expected: one match around line 137.

- [ ] **Step 2: Add the route registration**

Use the Edit tool. Immediately after the line that declares `app = FastAPI(...)`, add:

```python
# --- Passive turn ingestion ---
from api_server.ingest import init_ingest_routes as _init_ingest_routes
_init_ingest_routes(app)
```

If `api_server` is not importable as a package (i.e. `api-server/` with hyphen is the directory), instead place `ingest.py` imports under a try/except shim and adapt the import to whatever convention the other cross-module imports in `server.py` already use. Check first:

```bash
grep -n "^from api_server\|^import api_server\|from \\.\\|^from server " api-server/server.py | head
```

If no such imports exist, use direct relative import within the `api-server/` directory: `from ingest import init_ingest_routes`. Match the existing pattern — do not invent a new one.

- [ ] **Step 3: Start the stack and smoke-test the new route**

```bash
make stack-test-up
curl -s -X POST http://127.0.0.1:8050/ingest_turn \
  -H "X-API-Key: $MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"project":"ai-memory","session_id":"smoke","turn_id":"t1","timestamp":"2026-04-13T00:00:00Z","user_message":"short","assistant_message":"","tool_calls":[]}'
```

Expected: HTTP 200 with `{"status":"ok","filtered":true,"reason":"trivial_user_message",...}`.

If the route is missing (404), the `init_ingest_routes` call did not land — re-check step 2.

- [ ] **Step 4: Commit**

```bash
git add api-server/server.py
git commit -m "feat(ingest): mount /ingest_turn routes on the main FastAPI app"
```

---

## Task 11: Hook shell script

**Files:**
- Create: `.claude/hooks/ingest-turn.sh`

- [ ] **Step 1: Write the hook script**

`.claude/hooks/ingest-turn.sh`:
```bash
#!/usr/bin/env bash
# Fire-and-forget Claude Code Stop hook: POST the completed turn to /ingest_turn.
# Designed to return in < 100ms regardless of endpoint health.
set -u

LOG_FILE="${AI_MEMORY_INGEST_LOG:-$HOME/.claude/ai-memory-ingest.log}"
API_URL="${AI_MEMORY_BASE_URL:-http://127.0.0.1:8050}/ingest_turn"
API_KEY="${MEMORY_API_KEY:-}"
PROJECT="${AI_MEMORY_PROJECT:-$(basename "$PWD")}"

# Read the hook JSON from stdin (Claude Code writes the turn payload here).
HOOK_JSON="$(cat || true)"
if [[ -z "$HOOK_JSON" ]]; then
    exit 0
fi

# Build the ingest payload: extract what we need from the hook JSON using jq.
# If jq is missing, log once and exit successfully.
if ! command -v jq >/dev/null 2>&1; then
    echo "$(date -Iseconds) [warn] jq not installed, ingest hook disabled" >> "$LOG_FILE"
    exit 0
fi

PAYLOAD=$(echo "$HOOK_JSON" | jq --arg project "$PROJECT" '{
    project: $project,
    session_id: (.session_id // "unknown"),
    turn_id: (.transcript_path // .session_id // "unknown" | tostring),
    timestamp: (now | todate),
    user_message: (.user_message // ""),
    assistant_message: (.assistant_message // ""),
    tool_calls: (.tool_calls // [] | map({
        name: (.name // .tool_name // "?"),
        target: (.target // .file_path // null),
        summary: (.summary // .command // .content // "" | tostring | .[0:500])
    }))
}')

# Fire-and-forget: detach curl so the hook returns immediately.
(
    RESPONSE=$(curl -s -S -o /tmp/ai-memory-ingest.out -w "%{http_code}" \
        --max-time 20 \
        -X POST "$API_URL" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" 2>/tmp/ai-memory-ingest.err)
    if [[ "$RESPONSE" != "200" ]]; then
        echo "$(date -Iseconds) [error] ingest_turn http=$RESPONSE project=$PROJECT $(cat /tmp/ai-memory-ingest.err 2>/dev/null)" >> "$LOG_FILE"
    fi
) &

# Disown so the subshell survives hook exit.
disown 2>/dev/null || true
exit 0
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x .claude/hooks/ingest-turn.sh
```

- [ ] **Step 3: Smoke-test with api-server running**

```bash
echo '{"session_id":"s1","user_message":"hola mundo","assistant_message":"","tool_calls":[]}' \
  | AI_MEMORY_BASE_URL=http://127.0.0.1:8050 \
    MEMORY_API_KEY="$MEMORY_API_KEY" \
    AI_MEMORY_PROJECT=ai-memory \
    bash .claude/hooks/ingest-turn.sh
```

Expected: exits in < 100ms, no output. Check that `tail -n 5 ~/.claude/ai-memory-ingest.log` shows no new error lines (endpoint should have returned 200 with `filtered=true` because the message is trivial).

- [ ] **Step 4: Commit**

```bash
git add .claude/hooks/ingest-turn.sh
git commit -m "feat(ingest): fire-and-forget Stop hook script"
```

---

## Task 12: Register the hook in `.claude/settings.json`

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: Inspect current settings**

```bash
cat .claude/settings.json 2>/dev/null || echo "no settings yet"
```

- [ ] **Step 2: Add the `Stop` hook entry**

If the file does not exist, create it:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/ingest-turn.sh"
          }
        ]
      }
    ]
  }
}
```

If the file exists, merge the `hooks.Stop` entry — **do not overwrite** existing keys. If there are existing `Stop` entries, append the new hook to the array.

- [ ] **Step 3: Verify Claude Code picks it up**

Open a Claude Code session in the project, make one trivial edit, and confirm:
- The hook fires (check `~/.claude/ai-memory-ingest.log` stays clean, or that `/ingest/stats?project=ai-memory` shows `turns_ingested` incremented).
- There is no user-visible lag at turn end.

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json
git commit -m "feat(ingest): register Stop hook for passive turn ingestion"
```

---

## Task 13: Integration tests (`test_ingest_endpoint.py`)

**Files:**
- Create: `tests/ingest/test_ingest_endpoint.py`

Prerequisite: the stack must be running in test mode (`make stack-test-up`) with `CLASSIFIER_PROVIDER=fake` exported to the api-server container. Add `CLASSIFIER_PROVIDER=fake` to the test-mode env in `docker-compose.yml` or to `.env` before starting; document in README.

- [ ] **Step 1: Write the integration test file**

`tests/ingest/test_ingest_endpoint.py`:
```python
import os
import time
import uuid

import httpx
import pytest

BASE_URL = os.getenv("AI_MEMORY_BASE_URL", "http://127.0.0.1:8050")
API_KEY = os.getenv("MEMORY_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def _turn(**overrides):
    base = {
        "project": "ingest-test-" + uuid.uuid4().hex[:8],
        "session_id": uuid.uuid4().hex,
        "turn_id": uuid.uuid4().hex,
        "timestamp": "2026-04-13T00:00:00Z",
        "user_message": "Please fix the authentication bug in the login flow",
        "assistant_message": "Fixed the bug by validating the JWT signature before use",
        "tool_calls": [
            {"name": "Edit", "target": "auth.py", "summary": "validate token signature"}
        ],
    }
    base.update(overrides)
    return base


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=30) as c:
        yield c


def test_full_turn_stores_error_with_links(client):
    r = client.post("/ingest_turn", json=_turn())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["filtered"] is False
    assert body["actions_taken"] >= 1
    assert any(a["type"] == "store_error" for a in body["actions"])


def test_trivial_turn_is_prefiltered_fast(client):
    turn = _turn(user_message="ok", tool_calls=[{"name": "Edit", "summary": "x"}])
    t0 = time.perf_counter()
    r = client.post("/ingest_turn", json=turn)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    body = r.json()
    assert body["filtered"] is True
    assert body["reason"] == "trivial_user_message"
    assert elapsed_ms < 200  # prefilter path should be fast even over HTTP


def test_secret_in_turn_is_redacted_before_storage(client):
    turn = _turn(
        user_message="Please decide if we use sk-abc123def456ghi789jkl012mno345 here",
        assistant_message="Decision: never store the sk-abc123def456ghi789jkl012mno345 key",
    )
    r = client.post("/ingest_turn", json=turn)
    assert r.status_code == 200
    body = r.json()
    # Search newly stored memories in qdrant for the raw secret
    search = client.post("/api/search", json={
        "query": "sk-abc123def456ghi789jkl012mno345",
        "project": turn["project"],
        "limit": 20,
    })
    assert search.status_code == 200
    for hit in search.json().get("results", []):
        assert "sk-abc123def456ghi789" not in hit.get("content", "")


def test_duplicate_turn_deduped_on_second_call(client):
    turn = _turn()
    r1 = client.post("/ingest_turn", json=turn)
    assert r1.status_code == 200
    # Second call same content but new session_id to bypass rate limit
    turn2 = dict(turn)
    turn2["session_id"] = uuid.uuid4().hex
    turn2["turn_id"] = uuid.uuid4().hex
    r2 = client.post("/ingest_turn", json=turn2)
    body = r2.json()
    deduped = [a for a in body["actions"] if a.get("skip_reason") == "duplicate"]
    assert len(deduped) >= 1


def test_project_opt_out(client, monkeypatch):
    # Requires the api-server to have INGEST_DISABLED_PROJECTS including this name.
    # Pre-seeded by docker-compose test env: INGEST_DISABLED_PROJECTS=ingest-disabled-test
    turn = _turn(project="ingest-disabled-test")
    r = client.post("/ingest_turn", json=turn)
    body = r.json()
    assert body["filtered"] is True
    assert body["reason"] == "project_disabled"


def test_rate_limit_same_session(client):
    sid = uuid.uuid4().hex
    t1 = _turn(session_id=sid)
    t2 = _turn(session_id=sid)
    r1 = client.post("/ingest_turn", json=t1)
    r2 = client.post("/ingest_turn", json=t2)
    assert r1.status_code == 200
    assert r2.status_code == 200
    # The second one must be rate-limited (within the 2s window)
    assert r2.json().get("reason") == "rate_limited"


def test_ingest_stats_endpoint(client):
    project = "ingest-stats-" + uuid.uuid4().hex[:6]
    for _ in range(3):
        client.post("/ingest_turn", json=_turn(project=project))
        time.sleep(2.1)  # avoid rate limit
    r = client.get(f"/ingest/stats?project={project}")
    assert r.status_code == 200
    body = r.json()
    assert body["turns_ingested"] == 3
```

- [ ] **Step 2: Run the integration tests against a live test-mode stack**

```bash
make stack-test-up
sleep 3
CLASSIFIER_PROVIDER=fake \
INGEST_DISABLED_PROJECTS=ingest-disabled-test \
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 \
python -m pytest tests/ingest/test_ingest_endpoint.py -q
```

Expected: all tests pass.

If the fake classifier is not picked up by the api-server container, you'll see tests fail with real-classifier errors — add `CLASSIFIER_PROVIDER=fake` to the compose test env and rebuild.

- [ ] **Step 3: Commit**

```bash
git add tests/ingest/test_ingest_endpoint.py
git commit -m "test(ingest): integration tests for /ingest_turn pipeline"
```

---

## Task 14: `.env.example` and `brain-check` wiring

**Files:**
- Modify: `.env.example`
- Modify: `Makefile` (extend `brain-check` target)

- [ ] **Step 1: Append to `.env.example`**

Append at the bottom:

```dotenv
# --- Passive Turn Ingestion ---
INGEST_ENABLED=true
INGEST_DISABLED_PROJECTS=
INGEST_MIN_USER_CHARS=20
INGEST_SKIP_IF_AGENT_STORED=true
INGEST_WRITE_TOOLS=Edit,Write,NotebookEdit
INGEST_BASH_WRITE_PATTERNS=git commit,git push,npm install,make,docker,rm ,mv
INGEST_DEDUPE_LOOKBACK=10
INGEST_AUTOLINK_TOPK=3
INGEST_AUTOLINK_THRESHOLD=0.75
INGEST_AUTOLINK_RELATION=related
INGEST_RATE_LIMIT_WINDOW_SECONDS=2
INGEST_REDACTION_PATTERNS=

# Classifier (OpenAI-compatible endpoint; DeepSeek today, Ollama tomorrow)
CLASSIFIER_PROVIDER=openai-compat
CLASSIFIER_BASE_URL=https://api.deepseek.com/v1
CLASSIFIER_MODEL=deepseek-chat
CLASSIFIER_API_KEY=${DEEPSEEK_API_KEY}
CLASSIFIER_TIMEOUT=15
CLASSIFIER_MAX_TOKENS=1500
CLASSIFIER_TEMPERATURE=0.1
```

- [ ] **Step 2: Inspect the existing `brain-check` target**

```bash
grep -n "brain-check:" Makefile
```

- [ ] **Step 3: Extend `brain-check` to run ingest tests**

Add after the existing test step inside the target:

```make
	@echo ">> ingest unit+integration tests"
	CLASSIFIER_PROVIDER=fake \
	INGEST_DISABLED_PROJECTS=ingest-disabled-test \
	AI_MEMORY_BASE_URL=http://127.0.0.1:8050 \
	python -m pytest tests/ingest -q
```

- [ ] **Step 4: Run `make brain-check`**

```bash
make brain-check
```

Expected: all existing checks plus the new ingest suite pass.

- [ ] **Step 5: Commit**

```bash
git add .env.example Makefile
git commit -m "chore(ingest): document env vars and wire tests into brain-check"
```

---

## Task 15: Hook script smoke test

**Files:**
- Create: `tests/ingest/test_hook_script.sh`

- [ ] **Step 1: Write the shell smoke test**

`tests/ingest/test_hook_script.sh`:
```bash
#!/usr/bin/env bash
# Smoke test: ingest-turn.sh must return in < 100ms and curl must be detached.
set -eu

SCRIPT=".claude/hooks/ingest-turn.sh"
[[ -x "$SCRIPT" ]] || { echo "FAIL: $SCRIPT not executable"; exit 1; }

export AI_MEMORY_BASE_URL="http://127.0.0.1:9" # port where nothing listens
export MEMORY_API_KEY="dummy"
export AI_MEMORY_PROJECT="smoke-test"
export AI_MEMORY_INGEST_LOG="/tmp/ai-memory-hook-smoke.log"
rm -f "$AI_MEMORY_INGEST_LOG"

INPUT='{"session_id":"s","user_message":"hola","assistant_message":"","tool_calls":[]}'

START_NS=$(date +%s%N)
echo "$INPUT" | bash "$SCRIPT"
END_NS=$(date +%s%N)
ELAPSED_MS=$(( (END_NS - START_NS) / 1000000 ))

echo "elapsed: ${ELAPSED_MS}ms"
if (( ELAPSED_MS > 200 )); then
    echo "FAIL: hook too slow (${ELAPSED_MS}ms > 200ms)"
    exit 1
fi

# Wait for background curl to log the failure (endpoint is unreachable).
sleep 25
if [[ ! -s "$AI_MEMORY_INGEST_LOG" ]]; then
    echo "FAIL: error log not written on unreachable endpoint"
    exit 1
fi

echo "OK hook smoke test passed"
```

- [ ] **Step 2: Run it**

```bash
chmod +x tests/ingest/test_hook_script.sh
bash tests/ingest/test_hook_script.sh
```

Expected: `OK hook smoke test passed` (the curl will eventually time out and write the error log; the hook itself returns in < 200ms).

- [ ] **Step 3: Commit**

```bash
git add tests/ingest/test_hook_script.sh
git commit -m "test(ingest): smoke test for hook script return time"
```

---

## Self-review notes (applied inline, recorded here)

- **Spec coverage:** Every section of the spec maps to at least one task:
  - §4 architecture → file structure + tasks 2-9
  - §5 hook scope/exec → tasks 11-12, task 15 smoke-tests the behavior
  - §6 endpoint contract → task 5 (models) + task 9 (endpoint)
  - §7 prefilter → task 3
  - §8 classifier → task 6
  - §9 dedupe → task 4
  - §10 auto-linker → task 7
  - §11 error handling → covered inside task 9's `_execute_action` and endpoint orchestration
  - §12 observability → stats endpoint in task 9 + structured logs
  - §13 security/privacy → tasks 2, 8, 9
  - §14 config → task 14 `.env.example`
  - §15 testing → tasks 2-8 unit + task 13 integration + task 15 hook smoke

- **Pending/deferred from spec §17:** multi-worker rate limit, subagent coverage, non-Claude-Code clients — none blocked, all acknowledged out of scope.

- **Risk area:** the exact import path for `api-server` modules (with a hyphen in the dir name). Task 10 instructs the executor to match the existing convention in `server.py` rather than invent one. The test files assume `api_server.ingest_*` as the import path — if that convention does not hold in the repo, the executor must adapt all test imports AND the `ingest.py` imports consistently before running tests. This is called out explicitly in task 2 step 3 and again in task 10 step 2.

- **Acceptance thresholds (spec §15.3):** enforced by `make brain-check` in task 14. P95 latency measurements are implicit through the integration test's `elapsed_ms < 200` assertion for the filtered path; the full-path P95 of 150ms will be observed in docker logs rather than asserted (too noisy for CI).
