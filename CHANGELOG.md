# Changelog

## 2026-03-30

### Added
- Added `scripts/smoke_test_local.sh` to validate the full local stack end-to-end: API, Mem0 ingestion, reflection, and MCP connectivity.
- Added this `CHANGELOG.md` to keep a concise record of the changes made during local stabilization.
- Added associative-memory primitives to the API and schema: `memory_relations`, `project_bridges`, manual `link_memories`, explicit `bridge_projects`, and a reflection plasticity endpoint.
- Added plastic activation metadata to `memory_log` so retrieval can track access frequency, last activation, stability, and manual curation.
- Added a deterministic integration suite under `tests/` plus `requirements-dev.txt` and `pytest.ini` to validate retrieval, bridges, false-positive link avoidance, and plasticity behaviour through the public API.
- Added `evals/brain_dataset.json` and `scripts/eval_brain.py` to seed benchmark scenarios, execute structured searches, and export recall/bridge/plasticity metrics as JSON.
- Added `Makefile` targets for deterministic stack bring-up, test execution, benchmark execution, and an end-to-end `brain-check`.
- Added `scripts/run_deterministic_suite.sh` as the canonical local runner for the deterministic CI flow.
- Added GitHub Actions workflow `.github/workflows/deterministic-brain-ci.yml` to run the deterministic brain suite on pushes and pull requests.

### Changed
- Updated `mem0/Dockerfile` to build the Mem0 service locally from `python:3.12-slim` while preserving the intended provider setup: DeepSeek for reasoning and OpenAI for embeddings.
- Updated `docker-compose.yaml` and `.env.example` to expose `MEM0_INGEST_TIMEOUT_SECONDS` as an explicit configurable parameter.
- Updated `docker-compose.yaml` and `.env.example` with `PROJECT_CONTEXT_WORKING_MEMORY_*` knobs to cap working-memory latency in project context retrieval.
- Updated `README.md` to include the local smoke test script in the quick command list.
- Updated the Mem0 REST wrapper to support optional graph memory with embedded Kuzu storage and graceful fallback to vector-only mode when graph operations fail.
- Updated `api-server/server.py` with canonical tag normalization, tag indexing in Qdrant, hybrid search scoring, related-idea context blocks, and automatic relation inference for newly stored memories.
- Updated `reflection-worker/worker.py` so each reflection run now triggers a second plasticity phase that reinforces associations and decays stale automatic links.
- Updated `api-server/server.py` with deterministic test mode hooks: fake stable embeddings, structured search output, relation/bridge inspection endpoints, and a test-only clock override API.
- Updated `reflection-worker/worker.py` so reflection can run in a deterministic heuristic mode when `AI_MEMORY_TEST_MODE=true`.
- Updated `api-server/server.py` so `get_project_context` now runs semantic search, related-idea lookup, and working-memory retrieval in parallel, using a shorter Mem0 timeout and graph-disabled working-memory reads by default.
- Updated `api-server/server.py` so `get_project_context` uses a fast path without Mem0 working-memory lookup when no `agent_id` is provided, while preserving `WORKING MEMORY` for agent-specific context requests.
- Updated `scripts/eval_brain.py` to report latency separately for `structured_search`, `project_context`, and `plasticity_session`, while enforcing deterministic p95 thresholds per endpoint.
- Updated `.github/workflows/deterministic-brain-ci.yml` to upload benchmark JSON artifacts from `evals/results/`.

### Fixed
- Fixed false-positive session ingestion success in `api-server/server.py` by validating actual Mem0 results instead of treating any `200 OK` response as a successful working-memory ingest.
- Added an atomic fallback path for session-summary ingestion so useful working memory is persisted even when Mem0 returns an empty extraction result for the full summary document.
- Increased resilience in `reflection-worker/worker.py` by recovering interrupted runs and re-queueing stuck `processing` sessions after worker interruptions or restarts.
- Improved reflection processing stability by refreshing the worker heartbeat during per-session processing.
- Fixed tag handling so API-level tags are normalized and deduplicated before persistence, filtering, and relation inference.
- Fixed deterministic embedding cache invalidation in `api-server/server.py` by versioning the Redis cache namespace for test embeddings.
- Fixed PostgreSQL timestamp and interval casting in relation upserts and decay logic so the plasticity endpoint works end-to-end.

### Verified
- Verified the stack locally with Qdrant, PostgreSQL, Redis, API server, Mem0, and reflection worker all healthy.
- Verified real provider usage against the live services: DeepSeek for chat/reflection and OpenAI for embeddings.
- Verified MCP connectivity with a real Streamable HTTP client session and a successful `search_memory` tool call.
- Verified Gemini CLI can see the `memory-brain` MCP server and read/write memory through the local brain service.
- Verified the deterministic suite still passes after the context and benchmark optimizations: `4 passed`.
- Verified deterministic benchmark output now separates endpoint latencies and currently reports roughly `structured_search p95 ~39.8 ms`, `project_context p95 ~9.4 ms`, and `plasticity_session p95 ~19.1 ms`, all within thresholds.
