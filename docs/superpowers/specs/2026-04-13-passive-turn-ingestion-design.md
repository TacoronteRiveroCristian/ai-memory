# Passive Turn Ingestion — Design Spec

**Status:** Draft for review
**Date:** 2026-04-13
**Branch:** `feat/passive-turn-ingestion`
**Author:** brainstorming session with Claude

## 1. Problem

Today the memoryBrain MCP relies on the **PROACTIVE MEMORY PROTOCOL** — a set
of instructions injected into the agent that says "save when you see a
decision, a bug, a pattern...". The agent (me, Claude) is the one responsible
for calling `store_decision`, `store_error`, `store_memory`, `link_memories`.

This has three structural weaknesses:

1. **Depends on agent discipline.** Long sessions, context pressure, distracted
   models, or subagents that don't inherit the protocol → memories get lost.
2. **Depends on the client.** Cursor, Codex, Gemini CLI, a custom agent — each
   one needs the protocol re-injected and followed. The brain only grows in
   the clients where the protocol is active.
3. **Orphan nodes.** Even when the agent remembers to save, it often forgets to
   call `link_memories` afterward. This is documented in the user's own
   feedback memory `feedback_memorybrain_workflow`.

The reflection-worker running every 6h is a safety net but not a substitute:
it consolidates what's already in the DB, it does not capture what was never
saved in the first place.

## 2. Goal

Make the memory brain grow **automatically** during conversations, without
relying on agent discipline, in a way that:

- Works across any client (via a shell hook per client).
- Adds zero perceived latency to the user's workflow.
- Coexists with the existing proactive protocol (no duplication).
- Preserves all of ai-memory's biological plasticity (Ebbinghaus, spreading
  activation, reflection-worker, etc.).
- Is cheap today (DeepSeek) and free tomorrow (Ollama) via a
  provider-agnostic LLM interface.

## 3. Non-goals

- Replacing the proactive MCP protocol. The two are complementary.
- Capturing every keystroke or streaming turns in real-time.
- Quality evaluation of classifier output (that belongs to the eval suite).
- Multi-client orchestration beyond "each client ships its own hook script".

## 4. High-level architecture

```
┌───────────────────────┐
│  Claude Code (agent)  │
│  finishes a turn      │
└──────────┬────────────┘
           │ Stop hook (fire-and-forget, & background)
           ▼
┌───────────────────────┐
│  .claude/hooks/       │
│  ingest-turn.sh       │─→ error log: ~/.claude/ai-memory-ingest.log
└──────────┬────────────┘
           │ HTTP POST (X-API-Key)
           ▼
┌─────────────────────────────────────────────────┐
│  api-server :8050                                │
│  POST /ingest_turn                               │
│                                                  │
│  1. Global / project opt-out gate                │
│  2. Rate limit per session_id                    │
│  3. sanitize()  — redact secrets                 │
│  4. Prefiltro heurístico → may short-circuit     │
│  5. Classifier LLM (OpenAI-compatible client)    │
│  6. Pydantic validation per action               │
│  7. Dedupe by normalized hash vs recent memories │
│  8. Execute internal store_* functions           │
│  9. Auto-linker: semantic top-k → link_memories  │
│ 10. Structured log + metrics                     │
└─────────────────────────────────────────────────┘
           ▼
     [qdrant + postgres + redis]
           ▼
     reflection-worker (6h, unchanged)
     consolidates / decays / extracts schemas
```

### 4.1 New components

| Component     | File                          | Responsibility                                     |
|---------------|-------------------------------|-----------------------------------------------------|
| Hook script   | `.claude/hooks/ingest-turn.sh`| Receive Claude Code JSON on stdin, fire curl async  |
| Endpoint      | `api-server/ingest.py`        | FastAPI router `POST /ingest_turn` + `GET /ingest/stats` |
| Prefilter     | `api-server/ingest_filter.py` | Pure function `should_classify(turn) -> (bool, reason)` |
| Sanitizer     | `api-server/ingest_sanitize.py` | Redact secrets from all string fields in-place     |
| Classifier    | `api-server/classifier.py`    | OpenAI-compatible client + prompt + JSON parsing    |
| Auto-linker   | `api-server/auto_linker.py`   | Semantic top-k search + `link_memories` calls       |
| Dedupe        | inline in `ingest.py`         | Normalized-hash lookup vs recent memories           |
| Fake classifier (test only) | `tests/fakes/fake_classifier.py` | Deterministic replacement for tests       |

**Isolation principle.** Each module has one public function and no knowledge
of its neighbors' internals. The endpoint is pure orchestration; the prefilter
has no I/O; the classifier has no DB access; the auto-linker has no knowledge
of the classifier.

## 5. Hook scope and execution mode

### 5.1 Scope: `Stop` event only (Question 1 answer: A)

One POST per completed turn. A turn is the natural unit of "something
happened": user asked → agent acted → agent finished. Other hook events
(`UserPromptSubmit`, `PostToolUse`, `SessionEnd`) are explicitly excluded —
they add cost and noise without adding signal.

### 5.2 Execution: fire-and-forget with error log (Question 2 answer: A)

The hook script launches curl in the background (`&`) and exits immediately.
The user never perceives latency. If the endpoint is down or returns an error,
the hook appends one line to `~/.claude/ai-memory-ingest.log` with timestamp,
turn_id, and error. No retries, no queue.

**Rationale.** A single lost turn is not critical: the reflection-worker and
the proactive protocol remain as safety nets. Zero perceived latency is
non-negotiable — adding 500ms to every turn end would be unbearable within a
week. A local queue (Redis, file) was considered and rejected as premature.

## 6. Endpoint contract

### 6.1 Request body

```json
{
  "project": "ai-memory",
  "session_id": "abc-123",
  "turn_id": "turn-42",
  "timestamp": "2026-04-13T14:30:00Z",
  "user_message": "full text of the user's last message",
  "assistant_message": "full text of the assistant's final reply",
  "tool_calls": [
    {"name": "Edit", "target": "api-server/server.py", "summary": "added /ingest_turn route"},
    {"name": "Bash", "summary": "pytest -q"}
  ]
}
```

Notes:
- `tool_calls` is a **summary** (name + target/summary), not raw payloads.
  Cuts tokens ~10x and avoids leaking secrets through tool arguments.
- `project` is read by the hook from env `AI_MEMORY_PROJECT` with a fallback
  to the current directory basename.
- `session_id` and `turn_id` come from the Claude Code hook payload (already
  part of the hook JSON contract).

### 6.2 Response shapes

**Success with actions stored:**
```json
{
  "status": "ok",
  "filtered": false,
  "actions_taken": 2,
  "actions": [
    {"type": "store_decision", "memory_id": "mem_abc", "links_created": 3},
    {"type": "store_error", "memory_id": "mem_def", "links_created": 1}
  ],
  "latency_ms": 820
}
```

**Filtered (prefilter short-circuit):**
```json
{"status": "ok", "filtered": true, "reason": "no_write_tool_calls", "latency_ms": 3}
```

Valid `reason` values: `no_write_tool_calls`, `trivial_user_message`,
`agent_already_stored`, `project_disabled`, `global_disabled`, `rate_limited`.

**Error:**
```json
{"status": "error", "stage": "classifier", "detail": "JSON parse failed", "latency_ms": 2100}
```

Valid `stage` values: `classifier`, `store`, `auto_linker`.

The hook discards the response. The shapes exist for the `GET /ingest/stats`
endpoint and for manual debugging via `curl`.

### 6.3 Hard truncation limits (applied before classifier)

| Field               | Limit     |
|---------------------|-----------|
| `user_message`      | 4000 chars |
| `assistant_message` | 8000 chars |
| `tool_calls`        | 20 entries |
| each `tool_call.summary` | 500 chars |

## 7. Prefilter (`ingest_filter.py`)

Pure function, no I/O, 100% testable. Returns `(bool, reason_str)`. Discards
if **any** of these hold:

1. **No write tool calls.** None of the tool calls are in the write set
   (default: `Edit`, `Write`, `NotebookEdit`, `Bash`-with-side-effects).
   `Bash` is classified per command: `git log`, `ls`, `cat`, `grep`, `pytest`,
   `find`, `wc` → read. `git commit`, `git push`, `npm install`, `make`,
   `docker`, `rm`, `mv` → write. The write list is configurable by env var.
2. **Trivial user message.** `< INGEST_MIN_USER_CHARS` after strip, OR matches
   the pattern `^(ok|gracias|si|no|vale|thanks|perfect|👍)$` (case-insensitive).
3. **Agent already stored.** Any tool call with name starting
   `mcp__memoryBrain__store_` is present → the agent already did its job,
   running the classifier would only create duplicates.

Config:
```
INGEST_MIN_USER_CHARS=20
INGEST_SKIP_IF_AGENT_STORED=true
INGEST_WRITE_TOOLS=Edit,Write,NotebookEdit
INGEST_BASH_WRITE_PATTERNS=git commit,git push,npm install,make,docker,rm,mv
```

## 8. Classifier (`classifier.py`)

### 8.1 Provider-agnostic via OpenAI-compatible API (Question 3 answer: C)

A single class using `openai.OpenAI(base_url=..., api_key=...)`. No abstract
base classes, no strategy pattern. Provider swap is an env var change:

```
CLASSIFIER_BASE_URL=https://api.deepseek.com/v1    # → http://ollama:11434/v1
CLASSIFIER_MODEL=deepseek-chat                      # → llama3.1:8b
CLASSIFIER_API_KEY=${DEEPSEEK_API_KEY}              # → "ollama" (dummy)
CLASSIFIER_TIMEOUT=15
CLASSIFIER_MAX_TOKENS=1500
CLASSIFIER_PROVIDER=openai-compat                   # "fake" in tests
```

This covers DeepSeek, OpenAI, Groq, Together, Ollama, vLLM, LM Studio — every
modern inference stack exposes an OpenAI-compatible `/v1/chat/completions`.
If a future provider (Anthropic native, Gemini native) becomes necessary,
extracting an interface is a one-day refactor — YAGNI until then.

### 8.2 Prompt (final wording)

```
You are a memory classifier for an AI coding agent. Analyze this turn and
extract ONLY concrete memory-worthy actions. Return strict JSON.

Valid action types:
- store_decision: a technical/architectural decision was actually taken
  (not options considered — only the chosen outcome).
- store_error: a bug was encountered AND resolved within this turn
  (not errors left unresolved).
- store_observation: a pattern, insight, or non-obvious finding that would
  help in a future session.
- store_architecture: an explicit system design discussion with concrete
  structural conclusions.

If nothing in this turn qualifies, return {"actions": []}. Prefer an empty
list over invented content. Do not paraphrase generic statements.

For each action emit:
{
  "type": "store_decision" | "store_error" | "store_observation" | "store_architecture",
  "title": "≤80 chars, imperative, specific",
  "content": "self-contained paragraph: WHAT + WHY + CONTEXT",
  "tags": "hierarchical/slash,comma-separated",
  "importance": 0.5 | 0.7 | 0.85 | 0.95
}

Turn:
USER: <user_message>
ASSISTANT: <assistant_message>
TOOLS: <tool_calls>
```

Request is made with `response_format={"type": "json_object"}`. Temperature
fixed at `0.1` for classification stability.

### 8.3 Parsing and validation

Pydantic model `ClassifiedAction` with:
- `type: Literal["store_decision", "store_error", "store_observation", "store_architecture"]`
- `title: constr(min_length=1, max_length=80)`
- `content: constr(min_length=10, max_length=4000)`
- `tags: str` (comma-separated)
- `importance: confloat(ge=0.5, le=0.95)`

Failures:
- Malformed JSON from LLM → log output (truncated to 500 chars), return
  `status=error stage=classifier`, 0 actions stored.
- Individual action fails validation → that action is dropped, other actions
  in the same turn proceed normally.

## 9. Dedupe (Question 4/5 answer: C)

```python
def normalize_for_hash(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.translate(str.maketrans("", "", string.punctuation))
    return hashlib.sha256(text[:200].encode()).hexdigest()[:16]
```

Before executing each classified action:
```python
content_hash = normalize_for_hash(action.title + " " + action.content[:200])
recent = db.query_recent_memories(project, limit=INGEST_DEDUPE_LOOKBACK)
if any(normalize_for_hash(m.title + " " + m.content[:200]) == content_hash
       for m in recent):
    skip_action(reason="duplicate")
    continue
```

Config: `INGEST_DEDUPE_LOOKBACK=10`.

Purpose: protect against agent-vs-classifier double-save, where the agent
wrote a decision with wording X and the classifier re-extracts it with
near-identical wording. The normalization (lowercase, strip punctuation,
collapse whitespace, truncate to 200 chars) makes those collisions catchable.

## 10. Auto-linker (Question 4 answer: C)

After each `store_*` succeeds, the linker runs automatically:

```python
def auto_link(new_memory_id, new_embedding, project):
    matches = qdrant.search(
        collection=project,
        vector=new_embedding,
        top_k=INGEST_AUTOLINK_TOPK,
        score_threshold=INGEST_AUTOLINK_THRESHOLD,
    )
    links_created = 0
    for m in matches:
        if m.id == new_memory_id:
            continue
        link_memories(
            source_memory_id=new_memory_id,
            target_memory_id=m.id,
            relation_type=INGEST_AUTOLINK_RELATION,
            reason=f"auto-linked by passive ingest, similarity={m.score:.3f}",
        )
        links_created += 1
    return links_created
```

Config:
```
INGEST_AUTOLINK_TOPK=3
INGEST_AUTOLINK_THRESHOLD=0.75
INGEST_AUTOLINK_RELATION=related
```

If no neighbors pass the threshold, the memory is still stored with zero
links — reflection-worker will connect it later during consolidation.

**Refactor note.** For the endpoint to call `store_decision` / `store_error` /
`store_memory` directly (not through MCP), these must exist as plain Python
functions in the api-server core. If they currently live only inside MCP
handlers or FastAPI route bodies, a prerequisite task is to factor them out
into a reusable `api-server/memory_core.py` module. This will be addressed in
the implementation plan.

## 11. Error handling

| Failure                                      | Behavior                                                  |
|----------------------------------------------|-----------------------------------------------------------|
| Hook cannot reach endpoint                   | Append one line to `~/.claude/ai-memory-ingest.log`; exit 0 |
| Classifier timeout / 5xx                     | Return `status=error stage=classifier`; no retry          |
| Classifier returns invalid JSON              | Log truncated output; skip turn                           |
| Single action fails Pydantic validation      | Drop that action; continue with others                    |
| Dedupe finds duplicate                       | Skip action with `reason=duplicate`; not an error         |
| Auto-linker fails (qdrant transient)         | Memory already stored; log warning; reflection-worker picks it up later |
| Internal `store_*` raises                    | Per-action transactional rollback (same pattern as commit `a294ab1`) |

**Principle.** No failure in the ingest pipeline may affect the agent's main
flow. The hook runs in background, the response is ignored, and a completely
dead api-server is invisible to the user.

## 12. Observability

### 12.1 Structured logs (stdout, docker-captured)

One line per turn, JSON:
```json
{"ts":"2026-04-13T14:30:05Z","evt":"ingest_turn","project":"ai-memory",
 "session_id":"abc","turn_id":"t42","filtered":false,"classifier_ms":820,
 "actions_emitted":2,"actions_dedupe_skipped":0,"actions_stored":2,
 "links_created":5,"status":"ok"}
```

### 12.2 Prometheus metrics

- `ingest_turns_total{status,stage}` — counter
- `ingest_classifier_latency_ms` — histogram
- `ingest_actions_stored_total{type}` — counter
- `ingest_actions_deduped_total` — counter
- `ingest_links_created_total` — counter

Exposed through the existing `/metrics` endpoint if it exists, otherwise added
as part of this work.

### 12.3 Inspection endpoint

`GET /ingest/stats?project=<name>&hours=24`:
```json
{
  "turns_ingested": 142,
  "filtered": 89,
  "classified": 53,
  "actions_stored": 41,
  "deduped": 12,
  "avg_classifier_ms": 780,
  "errors": 2
}
```

Purpose: quick visual check for "is the classifier too aggressive/passive?",
"is the auto-link threshold leaving too many orphans?", "did something break
silently last night?".

## 13. Security and privacy

1. **Authentication.** Reuses `X-API-Key` header with `MEMORY_API_KEY`. The
   hook reads it from env.
2. **Network binding.** `/ingest_turn` is served from the same api-server
   process as everything else; same internal-network binding rules apply.
3. **Secret redaction** (`ingest_sanitize.py`), applied **before** the
   classifier and **before** storage. Patterns matched:
   - OpenAI / Anthropic: `sk-[A-Za-z0-9_-]{20,}`, `sk-ant-[A-Za-z0-9_-]{20,}`
   - AWS: `AKIA[0-9A-Z]{16}`
   - GitHub: `gh[pousr]_[A-Za-z0-9]{36,}`
   - JWT: `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`
   - Generic `.env` style: `(PASSWORD|SECRET|TOKEN|KEY|APIKEY)=[^\s]+`
   Matches are replaced with `[REDACTED]`. Configurable via
   `INGEST_REDACTION_PATTERNS` (regex list, `;`-separated).
4. **Hard truncation** (see §6.3), applied before sanitize and before LLM.
5. **Per-session rate limit.** In-memory deque keyed by `session_id`, limit
   1 request per 2 seconds. On breach: return `filtered=true reason=rate_limited`.
   Acceptable for a single-worker uvicorn; revisit if we scale to multi-worker.
6. **Per-project opt-out.** `INGEST_DISABLED_PROJECTS=proj_a,proj_b`. Matching
   projects short-circuit with `reason=project_disabled`.
7. **Global opt-out.** `INGEST_ENABLED=true|false` (default true). Kill switch
   without touching hooks.

## 14. Configuration summary

All env vars introduced, with defaults:

```
# Pipeline
INGEST_ENABLED=true
INGEST_DISABLED_PROJECTS=

# Prefilter
INGEST_MIN_USER_CHARS=20
INGEST_SKIP_IF_AGENT_STORED=true
INGEST_WRITE_TOOLS=Edit,Write,NotebookEdit
INGEST_BASH_WRITE_PATTERNS=git commit,git push,npm install,make,docker,rm,mv

# Classifier (OpenAI-compatible)
CLASSIFIER_PROVIDER=openai-compat
CLASSIFIER_BASE_URL=https://api.deepseek.com/v1
CLASSIFIER_MODEL=deepseek-chat
CLASSIFIER_API_KEY=${DEEPSEEK_API_KEY}
CLASSIFIER_TIMEOUT=15
CLASSIFIER_MAX_TOKENS=1500
CLASSIFIER_TEMPERATURE=0.1

# Dedupe
INGEST_DEDUPE_LOOKBACK=10

# Auto-linker
INGEST_AUTOLINK_TOPK=3
INGEST_AUTOLINK_THRESHOLD=0.75
INGEST_AUTOLINK_RELATION=related

# Security
INGEST_REDACTION_PATTERNS=  # extra patterns appended to built-in defaults

# Rate limit
INGEST_RATE_LIMIT_WINDOW_SECONDS=2
```

Ollama migration example:
```
CLASSIFIER_BASE_URL=http://ollama:11434/v1
CLASSIFIER_MODEL=llama3.1:8b
CLASSIFIER_API_KEY=ollama
```
No code changes, no redeploy of other services.

## 15. Testing

### 15.1 Unit tests (pure, no I/O)

- `tests/ingest/test_ingest_filter.py` — prefilter rules, parameterized cases
  covering each heuristic (write tools, trivial messages, agent-already-stored)
- `tests/ingest/test_sanitize.py` — each secret pattern redacts correctly,
  clean text passes through unchanged, applied across all string fields
- `tests/ingest/test_dedupe.py` — normalization: "Migración a pgvector" and
  "migracion a pgvector!!!" collide; lookback respected; 200-char truncation
- `tests/ingest/test_classifier_parser.py` — valid JSON with N actions parses;
  one invalid action in a batch is dropped, others survive; empty list is valid;
  malformed JSON raises a catchable exception

### 15.2 Integration tests (api-server in test mode)

Fake classifier at `tests/fakes/fake_classifier.py`:
```python
class FakeClassifier:
    def classify(self, turn):
        if "bug" in turn.user_message.lower():
            return [ClassifiedAction(type="store_error", ...)]
        if "decisión" in turn.assistant_message.lower():
            return [ClassifiedAction(type="store_decision", ...)]
        return []
```
Injected via `CLASSIFIER_PROVIDER=fake`.

`tests/ingest/test_ingest_endpoint.py` — cases:
- Full turn with bug+fix → one `store_error` created, linked to semantically
  nearby memories
- Trivial turn → prefiltered, 0 actions, latency < 20ms
- Turn containing a secret → stored content has `[REDACTED]` (verified by
  querying qdrant)
- Duplicate turn (same content twice) → second call skips with `reason=duplicate`
- Classifier returns invalid JSON → response `status=error stage=classifier`,
  0 memories, endpoint still alive for next call
- Two related memories → second one creates a link to the first (verified via
  `link_memories` query)
- Project in `INGEST_DISABLED_PROJECTS` → `filtered=true reason=project_disabled`
- `INGEST_ENABLED=false` globally → same
- 3 calls in 1s to the same `session_id` → third rejected with `rate_limited`

`tests/ingest/test_hook_script.sh` — hook shell smoke test:
- Runs script with sample JSON on stdin
- Verifies it returns 0 within 100ms
- Verifies curl is launched in background (parent does not wait)
- With endpoint down: verifies error log is written at the correct path

### 15.3 Acceptance metrics (`make brain-check`)

| Metric                                                              | Threshold   |
|---------------------------------------------------------------------|-------------|
| P95 `/ingest_turn` (filtered path)                                  | ≤ 20 ms     |
| P95 `/ingest_turn` (full path with fake classifier)                 | ≤ 150 ms    |
| Unit coverage of `ingest/` modules                                   | ≥ 85%       |
| Memories containing detectable secrets (regex scan post-test)        | 0           |
| Orphan-rate in a 20-turn related corpus (auto-linker effectiveness)  | ≤ 20%       |

### 15.4 Out of scope for the initial test suite

- Live LLM tests with real DeepSeek/OpenAI/Ollama — marked `@pytest.mark.live`,
  run manually for prompt-quality validation, not in CI.
- Classifier prompt quality evaluation — belongs to `make eval-deterministic`,
  not unit tests.
- Concurrent load testing — YAGNI until an observed problem exists.

## 16. Rollout plan

1. Land the spec and the implementation plan on `feat/passive-turn-ingestion`.
2. Implement modules bottom-up: sanitize → prefilter → dedupe → classifier →
   auto-linker → endpoint → hook.
3. Full unit + integration test pass under `AI_MEMORY_TEST_MODE=true` with
   the fake classifier.
4. Local live smoke test: set `CLASSIFIER_PROVIDER=openai-compat` pointing at
   DeepSeek, run a real Claude Code session against the ai-memory repo, check
   `/ingest/stats` and `git log` of generated memories.
5. Enable the hook for the ai-memory project only (`INGEST_DISABLED_PROJECTS`
   on everything else) for a week of dogfooding.
6. Review: prompt quality, dedupe effectiveness, auto-link threshold tuning.
7. Enable globally.

## 17. Open questions / deferred

- **Subagent coverage.** Subagents spawned inside Claude Code may not fire a
  `Stop` hook in the parent client. Out of scope for v1; revisit after
  dogfooding.
- **Multi-worker rate limiting.** In-memory deque is per-process. If
  api-server runs with `uvicorn --workers N > 1`, rate limit becomes per-worker.
  Acceptable until observed as a problem.
- **Non-Claude-Code clients.** Each client needs its own equivalent hook
  script. Only `.claude/hooks/ingest-turn.sh` is in scope here. Cursor/Codex/
  Gemini CLI hook scripts are follow-up work.
