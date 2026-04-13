# Changelog

## 2026-04-12

### Added
- **Heartbeat monitor service** (`heartbeat-monitor/`) — living proof system that injects synthetic "trap" memories, triggers biological processes (decay, activation, consolidation), and verifies end-to-end that the brain is actually functioning. New Docker Compose service + Makefile targets. Includes 8 verification checks, all now passing in test mode. Backed by new tables `heartbeat_cycles` and `manual_deep_sleep_runs`, new API endpoints for deep-sleep trigger and heartbeat status, and worker support for manual deep sleep triggers. Design spec + 11-task implementation plan under `docs/`.
- **Deep sleep NREM/REM phases** (`reflection-worker/worker.py`) — deep sleep is no longer a flat consolidation pass; it now runs a NREM phase (slow-wave consolidation, myelin strengthening) followed by a REM phase (associative replay, weak-link pruning) with adaptive decay. New columns `nrem_stats` and `rem_stats` in `sleep_cycles` for per-phase telemetry.
- **Adaptive myelination** (`api-server/myelination.py`) — adaptive myelin functions and co-activation strengthening: frequently co-activated memories strengthen their shared paths over time, mirroring activity-dependent myelination.
- **Proactive save protocol** — the MCP server now exposes a `serverInstructions` block and resource that tells connected agents to save memories proactively on defined triggers (decisions, errors, patterns, architecture). Documented in `docs/MCP_TOOLS.md`. Paired with proactive contradiction detection in `sensory-cortex/compute_contradiction_score` and integrated into automatic relation inference.
- **Novelty-based merge at ingestion** — near-identical memories are now merged at store time instead of creating duplicates, controlled by a novelty threshold. Part of "Phase 1 brain quick wins" alongside uncertainty-aware confidence scoring, keyphrase SDR pre-filter, and lateral inhibition in spreading activation.
- **Project deletion flow** — new `DELETE /api/projects/{name}` endpoint, MCP `delete_project` tool, Brain UI trash icon + confirmation modal + bulk delete. FK on `memory_log.project_id` is `SET NULL` (not `CASCADE`), so the endpoint explicitly deletes `memory_log` rows before the project row and wraps everything in a single Postgres transaction.
- **Brain UI "Living Brain" evolution** — biological brain visualization with radial layout and health dashboard, new Guide tab (design spec → implementation → CSS module), multi-keyword chip filter, center-view button, stable node selection, smooth transitions and accurate relation click handling.
- **Critical reviewer plugin** — Claude Code plugin scaffold (`SKILL.md`, hooks, settings) for adversarial review of proposals before implementation.
- **MCP effectiveness measurement** + token benchmark suite for cost analysis of MCP tool usage.

### Fixed
- **`store_decision` now exposes `memory_id` of the derived semantic memory** (`api-server/server.py:3816`). Previously returned only `OK decision='...' project=...`, discarding the `store_memory` result. This forced callers to fall back to SQL or similarity search to find the derived memory, and in practice left orphan decision nodes in the Living Brain graph. Return shape is now `OK decision='...' project=... memory_id=<uuid>`, letting agents immediately call `link_memories` with the real id.
- **`delete_memory` is now transactional and consistent across Qdrant + Postgres** (`api-server/server.py:4060`). Before this fix the tool only deleted the Qdrant point and returned a misleading `OK deleted=<id>`, leaving the `memory_log` row and all `memory_relations` pointing at a ghost memory — the vector disappeared from semantic search but the node remained visible in the UI graph. `delete_memory` now wraps `memory_relations` + `memory_log` deletions in a single Postgres transaction before touching Qdrant, and returns `log_removed=<n>` / `relations_removed=<n>` counters so callers can confirm the cleanup.
- **Heartbeat test-mode flow** — restructured so all 8 verification checks pass deterministically under `AI_MEMORY_TEST_MODE=true`, including fixing `bridge_projects` field names.
- **Code review follow-ups** across proactive protocol, runtime biology, and deep sleep evolution branches.
- **Test suite stabilization** — project-filtered facets in demo test (avoids `LIMIT 100` cap), `overall_health` vs `status` assertion in brain health test, tag format + contradiction score parsing, flaky assertions in novelty/subgraph/delete tests.
- **Docker build context** for heartbeat service corrected to its own directory.

### Changed
- **Activation consolidation from Redis → Postgres** (`api-server/server.py`) — activation scores accumulated in Redis are now periodically consolidated back to `memory_log`, so plasticity state survives Redis restarts.
- **Partial index on suspected contradictions** — new partial index speeds up contradiction-queue scans.

### Notes
- The `store_decision` / `delete_memory` fixes were discovered while populating the memory graph for the `claude-skills` project analysis: a decision node ended up orphaned because the derived `memory_id` was not returned, and then `delete_memory` failed to clean up the row on the first cleanup attempt. Both bugs are registered as `error`-type memories in the `ai-memory` project for future reference.

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
