#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${AI_MEMORY_ENV_FILE:-$PROJECT_DIR/.env}"
BASE_URL="${AI_MEMORY_BASE_URL:-http://127.0.0.1:8050}"
TEST_NOW="${AI_MEMORY_TEST_NOW_OVERRIDE:-2030-01-01T00:00:00+00:00}"
KEEP_STACK_UP="${KEEP_STACK_UP:-false}"
BRAIN_EVAL_ARGS="${BRAIN_EVAL_ARGS:-}"
# Proyectos "reales" que NO deben borrarse por el cleanup post-suite.
# Override con PROTECTED_PROJECTS="a,b,c".
PROTECTED_PROJECTS="${PROTECTED_PROJECTS:-claude-skills,ai-memory}"

cd "$PROJECT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Falta el archivo de entorno: $ENV_FILE" >&2
  echo "Crea .env a partir de .env.example antes de lanzar la suite determinista." >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

export AI_MEMORY_TEST_MODE=true
export AI_MEMORY_TEST_NOW="$TEST_NOW"
export AI_MEMORY_BASE_URL="$BASE_URL"
export CLASSIFIER_PROVIDER="${CLASSIFIER_PROVIDER:-fake}"
export INGEST_DISABLED_PROJECTS="${INGEST_DISABLED_PROJECTS:-ingest-disabled-test}"
export INGEST_ENABLED="${INGEST_ENABLED:-true}"

dump_logs() {
  echo
  echo "==> docker compose ps"
  docker compose ps || true
  echo
  echo "==> Ultimos logs de api-server"
  docker compose logs --tail=120 api-server || true
  echo
  echo "==> Ultimos logs de reflection-worker"
  docker compose logs --tail=120 reflection-worker || true
  echo
  echo "==> Ultimos logs de mem0"
  docker compose logs --tail=120 mem0 || true
}

cleanup() {
  local status="$1"
  if [[ "$status" -ne 0 ]]; then
    dump_logs
  fi
  if [[ "${KEEP_STACK_UP,,}" != "true" ]]; then
    docker compose down --remove-orphans >/dev/null 2>&1 || true
  fi
}

trap 'cleanup $?' EXIT

wait_for_ready() {
  local attempt
  for attempt in $(seq 1 60); do
    local ready_json
    ready_json="$(curl -fsS "$BASE_URL/ready" 2>/dev/null || true)"
    if [[ -n "$ready_json" ]]; then
      if python3 -c 'import json, sys; data = json.load(sys.stdin); raise SystemExit(0 if data.get("ready") is True and data.get("test_mode") is True else 1)' <<<"$ready_json"
      then
        echo "Stack listo en modo determinista tras $attempt intentos."
        return 0
      fi
    fi
    sleep 2
  done
  echo "La stack no alcanzo /ready en modo determinista." >&2
  return 1
}

echo "==> Levantando stack determinista"
docker compose up -d --build mem0 api-server reflection-worker

echo
echo "==> Esperando /ready"
wait_for_ready

echo
echo "==> Ejecutando pytest"
python3 -m pytest -q

echo
echo "==> Ejecutando benchmark determinista"
python3 scripts/eval_brain.py --mode deterministic $BRAIN_EVAL_ARGS

echo
echo "==> Limpiando proyectos de test (conserva: $PROTECTED_PROJECTS)"
PROTECTED_REGEX="^($(echo "$PROTECTED_PROJECTS" | sed 's/,/|/g'))$"
API_KEY_HEADER="X-API-Key: ${MEMORY_API_KEY:-}"
PROJECT_LIST="$(
    docker compose exec -T postgres \
        psql -U "${POSTGRES_USER:-memoryuser}" -d "${POSTGRES_DB:-memorydb}" \
        -tAc "SELECT name FROM projects" 2>/dev/null || true
)"
deleted=0
while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    if [[ "$name" =~ $PROTECTED_REGEX ]]; then
        continue
    fi
    code="$(curl -s -o /dev/null -w '%{http_code}' \
        -X DELETE -H "$API_KEY_HEADER" \
        "$BASE_URL/api/projects/$name" || true)"
    if [[ "$code" == "200" ]]; then
        deleted=$((deleted + 1))
    fi
done <<<"$PROJECT_LIST"
echo "Proyectos de test borrados: $deleted"

echo
echo "Suite determinista completada correctamente."
