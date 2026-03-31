#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${AI_MEMORY_ENV_FILE:-$PROJECT_DIR/.env}"
TMP_DIR="${AI_MEMORY_DEMO_TMP_DIR:-$PROJECT_DIR/.tmp/demo}"
SANITIZED_ENV_FILE="${AI_MEMORY_DEMO_ENV_FILE:-$TMP_DIR/compose.env}"
DEMO_VOLUME_ROOT="${AI_MEMORY_DEMO_VOLUME_ROOT:-$PROJECT_DIR/.tmp/demo-volumes}"

mkdir -p "$TMP_DIR" \
  "$DEMO_VOLUME_ROOT/qdrant" \
  "$DEMO_VOLUME_ROOT/postgres" \
  "$DEMO_VOLUME_ROOT/redis" \
  "$DEMO_VOLUME_ROOT/mem0"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Falta el archivo de entorno: $ENV_FILE" >&2
  exit 1
fi

tr -d '\r' < "$ENV_FILE" > "$SANITIZED_ENV_FILE"
cat >> "$SANITIZED_ENV_FILE" <<EOF
AI_MEMORY_QDRANT_VOLUME=$DEMO_VOLUME_ROOT/qdrant
AI_MEMORY_POSTGRES_VOLUME=$DEMO_VOLUME_ROOT/postgres
AI_MEMORY_REDIS_VOLUME=$DEMO_VOLUME_ROOT/redis
AI_MEMORY_MEM0_VOLUME=$DEMO_VOLUME_ROOT/mem0
EOF

exec docker compose --env-file "$SANITIZED_ENV_FILE" "$@"
