# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Memory Brain — a biologically-inspired memory system for AI agents. Provides semantic search, working memory extraction, plasticity (Ebbinghaus decay, spreading activation, reinforcement), and offline consolidation. Built for multi-agent collaboration with project-level isolation.

## Architecture

```
Agent Request → [api-server (FastAPI+MCP, :8050)]
                  ├→ [qdrant (:6333)]       — 1536-dim vector search (OpenAI embeddings)
                  ├→ [postgres (:5434)]      — structured storage, pgvector, relations
                  ├→ [redis (:6379)]         — embedding cache, activation propagation
                  └→ [mem0 (:8000)]          — working memory extraction (Mem0 AI)

Offline (every 6h) → [reflection-worker]     — consolidation via DeepSeek reasoning
```

**Key services** (all in Docker Compose):
- `api-server/server.py` — core API: memory CRUD, hybrid search, project context, plasticity sessions, MCP tool interface
- `mem0/main.py` — working memory extraction wrapper around Mem0 AI
- `reflection-worker/worker.py` — async consolidation: promotes memories, updates relation weights, applies Ebbinghaus decay, detects contradictions
- `config/postgres/init.sql` — full schema (13 tables, 25+ indexes, pgvector + pg_trgm extensions)

**Test mode**: `AI_MEMORY_TEST_MODE=true` enables deterministic behavior — frozen timestamps, stable hash-based embeddings (no OpenAI calls), heuristic reasoning (no DeepSeek calls).

## Commands

```bash
# Setup
cp .env.example .env              # configure API keys and credentials
make dev-deps                     # install pytest, httpx, python-dotenv

# Stack management
make stack-up                     # docker compose up -d --build (all services)
make stack-down                   # tear down
make stack-test-up                # start in test mode (deterministic)

# Testing (requires test stack running)
make test-deterministic           # pytest -q against localhost:8050
make eval-deterministic           # benchmark suite (latency + recall metrics)
make brain-check                  # full E2E: starts stack, seeds, tests, benchmarks

# Run a single test file
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_memory_brain_behavior.py

# Run a single test
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python -m pytest -q tests/test_memory_brain_behavior.py::test_name

# Demo
make demo-up && make demo-seed    # spin up with sample data
make demo-check                   # validate demo dataset
make demo-down

# Health & smoke
make health                       # service health check
make smoke                        # full stack e2e smoke test
```

## Brain UI (Frontend)

Located in `brain-ui/`. React + TypeScript SPA using react-force-graph-2d for "Living Brain" visualization.

```bash
# Development
cd brain-ui && npm install && npm run dev    # Vite dev server on :5173

# Docker
docker compose build brain-ui                 # Build production image
docker compose up -d brain-ui                 # Serve on :3000
```

Requires `VITE_API_URL` and `VITE_API_KEY` environment variables. In Docker, these are passed as build args from the root `.env` (`MEMORY_API_KEY`).

## Test Markers

- Unmarked tests: run in deterministic mode (no external API calls)
- `@pytest.mark.live`: requires live stack with real OpenAI/DeepSeek providers

## Key External Dependencies

- **OpenAI**: `text-embedding-3-small` for embeddings
- **DeepSeek**: `deepseek-reasoner` for reflection/consolidation
- **Mem0 AI**: working memory extraction with optional Kuzu graph

## Plasticity Concepts

These terms appear throughout the codebase:
- **Ebbinghaus decay**: stability_halflife doubles with each access; memories decay if unused
- **Spreading activation**: accessing a memory boosts related memories via Redis
- **Valence/Arousal**: emotional tagging (errors=high arousal, breakthroughs=positive valence)
- **Novelty score**: how novel a memory is relative to existing knowledge
- **Schema extraction**: abstract patterns detected across multiple concrete memories

## Performance Targets (CI-enforced)

| Endpoint | P95 Threshold |
|----------|---------------|
| structured_search | ≤ 250ms |
| project_context | ≤ 2500ms |
| plasticity_session | ≤ 1500ms |
| graph_subgraph | ≤ 900ms |
