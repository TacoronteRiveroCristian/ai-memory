SHELL := /usr/bin/env bash

PYTHON ?= python3
DOCKER_COMPOSE ?= docker compose
TEST_NOW ?= 2030-01-01T00:00:00+00:00
KEEP_STACK_UP ?= false

.PHONY: dev-deps health smoke stack-up stack-down stack-test-up test-deterministic eval-deterministic brain-check demo-up demo-seed demo-check demo-down

dev-deps:
	$(PYTHON) -m pip install -r requirements-dev.txt

health:
	./scripts/health_check.sh

smoke:
	./scripts/smoke_test_local.sh

stack-up:
	$(DOCKER_COMPOSE) up -d --build

stack-down:
	$(DOCKER_COMPOSE) down --remove-orphans

stack-test-up:
	AI_MEMORY_TEST_MODE=true AI_MEMORY_TEST_NOW=$(TEST_NOW) $(DOCKER_COMPOSE) up -d --build mem0 api-server reflection-worker

test-deterministic:
	AI_MEMORY_BASE_URL=http://127.0.0.1:8050 $(PYTHON) -m pytest -q

eval-deterministic:
	AI_MEMORY_BASE_URL=http://127.0.0.1:8050 $(PYTHON) scripts/eval_brain.py --mode deterministic

brain-check:
	KEEP_STACK_UP=$(KEEP_STACK_UP) AI_MEMORY_TEST_NOW_OVERRIDE=$(TEST_NOW) ./scripts/run_deterministic_suite.sh

demo-up:
	AI_MEMORY_TEST_MODE=true AI_MEMORY_TEST_NOW=$(TEST_NOW) ./scripts/demo_compose.sh up -d --build qdrant postgres redis mem0 api-server reflection-worker ui

demo-seed:
	SANITIZED_ENV=$$(mktemp); tr -d '\r' < .env > $$SANITIZED_ENV; source $$SANITIZED_ENV && AI_MEMORY_BASE_URL=http://127.0.0.1:8050 $(PYTHON) scripts/seed_demo_brain.py --base-url http://127.0.0.1:8050 --api-key $$MEMORY_API_KEY --deterministic --with-plasticity; rm -f $$SANITIZED_ENV

demo-check:
	AI_MEMORY_TEST_NOW_OVERRIDE=$(TEST_NOW) ./scripts/run_demo_brain.sh
	AI_MEMORY_BASE_URL=http://127.0.0.1:8050 $(PYTHON) -m pytest -q tests/test_demo_brain_dataset.py
	cd ui && npm install
	cd ui && npx playwright install chromium
	cd ui && UI_BASE_URL=http://127.0.0.1:4173 npm run test:e2e -- e2e/demo-brain.spec.ts

demo-down:
	./scripts/demo_compose.sh down --remove-orphans
