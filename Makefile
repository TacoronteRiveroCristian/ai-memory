SHELL := /usr/bin/env bash

PYTHON ?= python3
DOCKER_COMPOSE ?= docker compose
TEST_NOW ?= 2030-01-01T00:00:00+00:00
KEEP_STACK_UP ?= false

.PHONY: dev-deps health smoke stack-up stack-down stack-test-up test-deterministic eval-deterministic brain-check demo-up demo-seed demo-check demo-down heartbeat-fast heartbeat-prod heartbeat-status heartbeat-stop

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
	AI_MEMORY_TEST_MODE=true AI_MEMORY_TEST_NOW=$(TEST_NOW) ./scripts/demo_compose.sh up -d --build qdrant postgres redis mem0 api-server reflection-worker

demo-seed:
	SANITIZED_ENV=$$(mktemp); tr -d '\r' < .env > $$SANITIZED_ENV; source $$SANITIZED_ENV && AI_MEMORY_BASE_URL=http://127.0.0.1:8050 $(PYTHON) scripts/seed_demo_brain.py --base-url http://127.0.0.1:8050 --api-key $$MEMORY_API_KEY --deterministic --with-plasticity; rm -f $$SANITIZED_ENV

demo-check:
	AI_MEMORY_TEST_NOW_OVERRIDE=$(TEST_NOW) ./scripts/run_demo_brain.sh
	AI_MEMORY_BASE_URL=http://127.0.0.1:8050 $(PYTHON) -m pytest -q tests/test_demo_brain_dataset.py

demo-down:
	./scripts/demo_compose.sh down --remove-orphans

heartbeat-fast:
	HEARTBEAT_ENABLED=true $(DOCKER_COMPOSE) --profile heartbeat up -d --build

heartbeat-prod:
	HEARTBEAT_ENABLED=true HEARTBEAT_MODE=production HEARTBEAT_INJECT_INTERVAL=3600 HEARTBEAT_SLEEP_INTERVAL=86400 HEARTBEAT_VERIFY_INTERVAL=7200 $(DOCKER_COMPOSE) --profile heartbeat up -d --build

heartbeat-status:
	@SANITIZED_ENV=$$(mktemp); tr -d '\r' < .env > $$SANITIZED_ENV; source $$SANITIZED_ENV && curl -s -H "X-API-Key: $$MEMORY_API_KEY" http://127.0.0.1:8050/api/heartbeat/status | $(PYTHON) -m json.tool; rm -f $$SANITIZED_ENV

heartbeat-stop:
	$(DOCKER_COMPOSE) --profile heartbeat stop heartbeat-monitor
