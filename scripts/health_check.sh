#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
echo "=== AI Memory Brain - Estado $(date) ==="

set -a
source "$ENV_FILE"
set +a

TEMP="$(vcgencmd measure_temp 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' || true)"
if [ -n "${TEMP:-}" ]; then
  echo "CPU Temp: ${TEMP}C"
else
  echo "CPU Temp: N/A"
fi

free -h | awk '/^Mem:/ {printf "RAM: %s usada de %s (disponible: %s)\n", $3, $2, $7}'
df -h "$PROJECT_DIR/volumes" | awk 'NR==2 {printf "Storage: %s usado de %s (%s)\n", $3, $2, $5}'

echo
docker ps --format "  {{.Names}}: {{.Status}}" | grep -E "ai-memory-(qdrant|postgres|redis|mem0|api|reflection-worker)" || true

echo
curl -fsS http://127.0.0.1:8050/health >/dev/null && echo "API /health: OK" || echo "API /health: FAIL"
curl -s http://127.0.0.1:8050/ready || true
echo
curl -fsS -H "X-API-Key: $MEMORY_API_KEY" http://127.0.0.1:8050/api/reflections/status || true
echo
