# Changelog

## 2026-03-30

### Added
- Added `scripts/smoke_test_local.sh` to validate the full local stack end-to-end: API, Mem0 ingestion, reflection, and MCP connectivity.
- Added this `CHANGELOG.md` to keep a concise record of the changes made during local stabilization.
- Added associative-memory primitives to the API and schema: `memory_relations`, `project_bridges`, manual `link_memories`, explicit `bridge_projects`, and a reflection plasticity endpoint.
- Added plastic activation metadata to `memory_log` so retrieval can track access frequency, last activation, stability, and manual curation.

### Changed
- Updated `mem0/Dockerfile` to build the Mem0 service locally from `python:3.12-slim` while preserving the intended provider setup: DeepSeek for reasoning and OpenAI for embeddings.
- Updated `docker-compose.yaml` and `.env.example` to expose `MEM0_INGEST_TIMEOUT_SECONDS` as an explicit configurable parameter.
- Updated `README.md` to include the local smoke test script in the quick command list.
- Updated the Mem0 REST wrapper to support optional graph memory with embedded Kuzu storage and graceful fallback to vector-only mode when graph operations fail.
- Updated `api-server/server.py` with canonical tag normalization, tag indexing in Qdrant, hybrid search scoring, related-idea context blocks, and automatic relation inference for newly stored memories.
- Updated `reflection-worker/worker.py` so each reflection run now triggers a second plasticity phase that reinforces associations and decays stale automatic links.

### Fixed
- Fixed false-positive session ingestion success in `api-server/server.py` by validating actual Mem0 results instead of treating any `200 OK` response as a successful working-memory ingest.
- Added an atomic fallback path for session-summary ingestion so useful working memory is persisted even when Mem0 returns an empty extraction result for the full summary document.
- Increased resilience in `reflection-worker/worker.py` by recovering interrupted runs and re-queueing stuck `processing` sessions after worker interruptions or restarts.
- Improved reflection processing stability by refreshing the worker heartbeat during per-session processing.
- Fixed tag handling so API-level tags are normalized and deduplicated before persistence, filtering, and relation inference.

### Verified
- Verified the stack locally with Qdrant, PostgreSQL, Redis, API server, Mem0, and reflection worker all healthy.
- Verified real provider usage against the live services: DeepSeek for chat/reflection and OpenAI for embeddings.
- Verified MCP connectivity with a real Streamable HTTP client session and a successful `search_memory` tool call.
- Verified Gemini CLI can see the `memory-brain` MCP server and read/write memory through the local brain service.
