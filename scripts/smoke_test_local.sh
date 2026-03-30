#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
BASE_URL="${AI_MEMORY_BASE_URL:-http://127.0.0.1:8050}"
RUN_SUFFIX="${1:-$(date +%Y%m%d_%H%M%S)}"
PROJECT_NAME="ai-memory-smoke-$RUN_SUFFIX"
SESSION_ID="smoke-session-$RUN_SUFFIX"

cd "$PROJECT_DIR"

set -a
source "$ENV_FILE"
set +a

json_get() {
  local expression="$1"
  python3 -c "import json,sys; data=json.load(sys.stdin); print($expression)"
}

echo "==> Verificando /ready"
READY_JSON="$(curl -fsS "$BASE_URL/ready")"
READY_OK="$(json_get "data['ready']" <<<"$READY_JSON")"
OPENAI_OK="$(json_get "data['openai_configured']" <<<"$READY_JSON")"
DEEPSEEK_OK="$(json_get "data['deepseek_configured']" <<<"$READY_JSON")"
if [[ "$READY_OK" != "True" || "$OPENAI_OK" != "True" || "$DEEPSEEK_OK" != "True" ]]; then
  echo "Stack no listo: $READY_JSON" >&2
  exit 1
fi
echo "ready=true openai_configured=true deepseek_configured=true"

echo
echo "==> Creando memoria semantica en $PROJECT_NAME"
CREATE_JSON="$(cat <<JSON | curl -fsS -X POST "$BASE_URL/api/memories" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $MEMORY_API_KEY" \
  -d @-
{
  "content": "La arquitectura local valida usa DeepSeek para razonamiento y OpenAI para embeddings.",
  "project": "$PROJECT_NAME",
  "memory_type": "architecture_confirmation",
  "tags": "smoke,local,providers",
  "importance": 0.9,
  "agent_id": "smoke-test"
}
JSON
)"
echo "$CREATE_JSON"

echo
echo "==> Buscando la memoria creada"
SEARCH_JSON="$(cat <<JSON | curl -fsS -X POST "$BASE_URL/api/search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $MEMORY_API_KEY" \
  -d @-
{
  "query": "DeepSeek OpenAI embeddings",
  "project": "$PROJECT_NAME",
  "limit": 3
}
JSON
)"
echo "$SEARCH_JSON"
if ! grep -q "architecture_confirmation" <<<"$SEARCH_JSON"; then
  echo "La busqueda semantica no devolvio la memoria esperada" >&2
  exit 1
fi

echo
echo "==> Registrando resumen de sesion con ingest a mem0"
SESSION_JSON="$(cat <<JSON | curl -fsS -X POST "$BASE_URL/api/sessions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $MEMORY_API_KEY" \
  -d @-
{
  "project": "$PROJECT_NAME",
  "agent_id": "smoke-test",
  "session_id": "$SESSION_ID",
  "goal": "Validar memoria local end-to-end",
  "outcome": "Flujo funcional con DeepSeek y OpenAI",
  "summary": "Se confirmo que el stack local usa DeepSeek para razonamiento y OpenAI para embeddings sin Ollama.",
  "changes": [
    "Smoke test local ejecutada contra API y MCP",
    "Ingestion de session summary validada"
  ],
  "decisions": [
    {
      "title": "Mantener filosofia cloud actual",
      "decision": "Usar DeepSeek para razonamiento y OpenAI para embeddings",
      "rationale": "Es la arquitectura deseada del proyecto"
    }
  ],
  "errors": [],
  "follow_ups": [
    {
      "title": "Revisar reflejos promovidos",
      "state": "pending",
      "details": "Confirmar que el worker extrae memorias duraderas"
    }
  ],
  "tags": ["smoke", "providers", "local"]
}
JSON
)"
echo "$SESSION_JSON"
SESSION_INGEST_OK="$(json_get "data['working_memory_ingested']" <<<"$SESSION_JSON")"
if [[ "$SESSION_INGEST_OK" != "True" ]]; then
  echo "Mem0 no confirmo la ingest de la sesion: $SESSION_JSON" >&2
  exit 1
fi

echo
echo "==> Consultando contexto de proyecto"
CONTEXT_JSON="$(curl -fsS "$BASE_URL/api/project-context?project_name=$PROJECT_NAME&agent_id=smoke-test" \
  -H "X-API-Key: $MEMORY_API_KEY")"
echo "$CONTEXT_JSON"
if ! grep -q "WORKING MEMORY" <<<"$CONTEXT_JSON"; then
  echo "El contexto de proyecto no incluyo working memory" >&2
  exit 1
fi

echo
echo "==> Lanzando reflexion manual"
RUN_JSON="$(curl -fsS -X POST "$BASE_URL/api/reflections/run" -H "X-API-Key: $MEMORY_API_KEY")"
echo "$RUN_JSON"
RUN_ID="$(json_get "data['run_id']" <<<"$RUN_JSON")"

ATTEMPT=1
MAX_ATTEMPTS=24
while (( ATTEMPT <= MAX_ATTEMPTS )); do
  STATUS_JSON="$(curl -fsS "$BASE_URL/api/reflections/status" -H "X-API-Key: $MEMORY_API_KEY")"
  LAST_RUN_ID="$(json_get "data.get('last_run', {}).get('id')" <<<"$STATUS_JSON")"
  LAST_RUN_STATUS="$(json_get "data.get('last_run', {}).get('status')" <<<"$STATUS_JSON")"
  echo "intent $ATTEMPT/$MAX_ATTEMPTS run_id=$LAST_RUN_ID status=$LAST_RUN_STATUS"
  if [[ "$LAST_RUN_ID" == "$RUN_ID" && "$LAST_RUN_STATUS" == "completed" ]]; then
    echo "$STATUS_JSON"
    break
  fi
  sleep 5
  ((ATTEMPT++))
done

if (( ATTEMPT > MAX_ATTEMPTS )); then
  echo "La reflexion manual no termino a tiempo" >&2
  exit 1
fi

echo
echo "==> Verificando transporte MCP"
docker compose exec -T -e SMOKE_PROJECT_NAME="$PROJECT_NAME" api-server python - <<'PY'
import os
import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    headers = {"X-API-Key": os.environ["API_KEY"]}
    async with streamablehttp_client("http://127.0.0.1:8050/mcp", headers=headers) as (read_stream, write_stream, _):
        session = ClientSession(read_stream, write_stream)
        async with session:
            init = await session.initialize()
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            if "search_memory" not in tool_names:
                raise RuntimeError(f"search_memory no aparece en las tools: {tool_names}")
            result = await session.call_tool(
                "search_memory",
                {"query": "DeepSeek OpenAI embeddings", "project": os.environ["SMOKE_PROJECT_NAME"], "limit": 3},
            )
            text_chunks = [getattr(item, "text", "") for item in result.content]
            output = "\n".join(chunk for chunk in text_chunks if chunk)
            print(output)
            if "DeepSeek" not in output and "OpenAI" not in output:
                raise RuntimeError("La respuesta MCP no contiene el contexto esperado")

anyio.run(main)
PY

echo
echo "Smoke test completada para $PROJECT_NAME"
