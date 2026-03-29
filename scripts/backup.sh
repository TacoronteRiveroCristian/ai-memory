#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
BACKUP_BASE="$PROJECT_DIR/volumes/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$BACKUP_BASE/$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

set -a
source "$ENV_FILE"
set +a

echo "Backup iniciado en $BACKUP_DIR"

SNAP_JSON="$(curl -fsS -X POST "http://127.0.0.1:6333/collections/memories/snapshots" -H "api-key: $QDRANT_API_KEY")"
SNAP_NAME="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["name"])' <<<"$SNAP_JSON")"
curl -fsS "http://127.0.0.1:6333/collections/memories/snapshots/$SNAP_NAME" \
  -H "api-key: $QDRANT_API_KEY" \
  -o "$BACKUP_DIR/qdrant_memories.snapshot"

docker exec ai-memory-postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_DIR/postgres_memorydb.sql.gz"

find "$BACKUP_BASE" -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +

echo "Backup completado en $BACKUP_DIR"
