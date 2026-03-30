# AI Memory

Proyecto autocontenido para la stack de memoria:

- `docker-compose.yaml`
- `.env.example`
- `volumes/`
- `scripts/`
- `api-server/`, `mem0/`, `reflection-worker/`

Uso rápido:

```bash
cp .env.example .env
docker compose up -d
```

Comandos útiles:

```bash
docker compose ps
./scripts/health_check.sh
./scripts/smoke_test_local.sh
./scripts/backup.sh
make health
make smoke
```

Tests y benchmark:

```bash
pip install -r requirements-dev.txt
pytest
python3 scripts/eval_brain.py --mode deterministic
python3 scripts/eval_brain.py --mode live
make dev-deps
make stack-test-up
make test-deterministic
make eval-deterministic
make brain-check
```

Para pruebas deterministas, activa en `.env`:

```bash
AI_MEMORY_TEST_MODE=true
AI_MEMORY_TEST_NOW=2030-01-01T00:00:00+00:00
PROJECT_CONTEXT_WORKING_MEMORY_TIMEOUT_SECONDS=2.0
PROJECT_CONTEXT_WORKING_MEMORY_LIMIT=3
PROJECT_CONTEXT_WORKING_MEMORY_USE_GRAPH=false
```

Runner recomendado para validar el cerebro de extremo a extremo:

```bash
cp .env.example .env
make brain-check
```

Si quieres dejar la stack de test levantada al terminar:

```bash
make brain-check KEEP_STACK_UP=true
```

CI:

- `.github/workflows/deterministic-brain-ci.yml` levanta la stack en modo determinista y ejecuta `pytest` + `eval_brain.py`.
- La CI sube `evals/results/*.json` como artifact para comparar latencias y regresiones del cerebro.
- `scripts/run_deterministic_suite.sh` es el runner único para reproducir localmente exactamente ese flujo.

Lectura recomendada del benchmark:

- `search_latency_*` mide solo `structured_search`, no una mezcla de endpoints.
- `project_context_latency_*` mide la rehidratación completa de contexto del proyecto.
- `plasticity_session_latency_*` mide la fase de refuerzo/decay.
- `aggregate.thresholds_passed` indica si la suite determinista quedó dentro de latencias aceptables por endpoint.
- `project_context` toma una ruta rápida cuando no recibe `agent_id`; si se pide `agent_id`, añade `WORKING MEMORY` desde Mem0 y puede tardar más.

Documentación útil:

- `docs/MCP_TOOLS.md`: qué hace cada tool MCP, cuándo usarla y cómo invocarla.
- `docs/CEREBRO_CONSCIENTE_SUPERDOCS.md`: arquitectura completa y funcionamiento del sistema.
