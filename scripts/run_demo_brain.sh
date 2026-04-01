#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${AI_MEMORY_ENV_FILE:-$PROJECT_DIR/.env}"
TMP_DIR="${AI_MEMORY_DEMO_TMP_DIR:-$PROJECT_DIR/.tmp/demo}"
SANITIZED_ENV_FILE="${AI_MEMORY_DEMO_ENV_FILE:-$TMP_DIR/runtime.env}"
BASE_URL="${AI_MEMORY_BASE_URL:-http://127.0.0.1:8050}"
TEST_NOW="${AI_MEMORY_TEST_NOW_OVERRIDE:-2030-01-01T00:00:00+00:00}"
DEMO_NAMESPACE="${DEMO_NAMESPACE:-}"
DEMO_WITH_PLASTICITY="${DEMO_WITH_PLASTICITY:-true}"
DEMO_WITH_REFLECTION="${DEMO_WITH_REFLECTION:-false}"

cd "$PROJECT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Falta el archivo de entorno: $ENV_FILE" >&2
  echo "Crea .env a partir de .env.example antes de lanzar la demo." >&2
  exit 1
fi

mkdir -p "$TMP_DIR"
tr -d '\r' < "$ENV_FILE" > "$SANITIZED_ENV_FILE"

set -a
source "$SANITIZED_ENV_FILE"
set +a

if [[ -z "${MEMORY_API_KEY:-}" ]]; then
  echo "MEMORY_API_KEY no está configurada en $ENV_FILE" >&2
  exit 1
fi

wait_for_api_ready() {
  local attempt
  for attempt in $(seq 1 90); do
    local ready_json
    ready_json="$(curl -fsS "$BASE_URL/ready" 2>/dev/null || true)"
    if [[ -n "$ready_json" ]]; then
      if python3 -c 'import json, sys; data = json.load(sys.stdin); raise SystemExit(0 if data.get("ready") is True else 1)' <<<"$ready_json"
      then
        echo "API lista tras $attempt intentos."
        return 0
      fi
    fi
    sleep 2
  done
  echo "La API no alcanzó /ready." >&2
  return 1
}

echo "==> Levantando stack de demo"
AI_MEMORY_TEST_MODE=true AI_MEMORY_TEST_NOW="$TEST_NOW" "$PROJECT_DIR/scripts/demo_compose.sh" up -d --build \
  qdrant postgres redis mem0 api-server reflection-worker

echo
echo "==> Esperando backend"
wait_for_api_ready

echo
echo "==> Sembrando cerebro demo"
SEED_ARGS=(
  --base-url "$BASE_URL"
  --api-key "$MEMORY_API_KEY"
  --deterministic
)
if [[ -n "$DEMO_NAMESPACE" ]]; then
  SEED_ARGS+=(--namespace "$DEMO_NAMESPACE")
fi
if [[ "${DEMO_WITH_PLASTICITY,,}" == "true" ]]; then
  SEED_ARGS+=(--with-plasticity)
fi
if [[ "${DEMO_WITH_REFLECTION,,}" == "true" ]]; then
  SEED_ARGS+=(--with-reflection)
fi
python3 scripts/seed_demo_brain.py "${SEED_ARGS[@]}"

echo
echo "Demo lista."
echo "API: $BASE_URL"
echo "Proyecto EMS: ${DEMO_NAMESPACE:+$DEMO_NAMESPACE-}demo-ems-fotovoltaica"
echo "Proyecto meteo: ${DEMO_NAMESPACE:+$DEMO_NAMESPACE-}demo-monitorizacion-estaciones-meteorologicas"
echo "Proyecto SCADA: ${DEMO_NAMESPACE:+$DEMO_NAMESPACE-}demo-scada-hibrido-solar-bess"
echo "Proyecto PPC: ${DEMO_NAMESPACE:+$DEMO_NAMESPACE-}demo-calidad-de-red-y-ppc"
echo "Proyecto predictivo: ${DEMO_NAMESPACE:+$DEMO_NAMESPACE-}demo-mantenimiento-predictivo-inversores"
echo "Proyecto OT: ${DEMO_NAMESPACE:+$DEMO_NAMESPACE-}demo-observabilidad-subestaciones-y-ot"
