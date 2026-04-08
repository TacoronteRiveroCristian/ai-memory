# Token Benchmark: Midiendo el Ahorro de Tokens de AI Memory

**Fecha**: 2026-04-07  
**Rama**: `feat/token-benchmark`

## Contexto

AI Memory proporciona contexto persistente a Claude Code via MCP. La hipótesis es que esto reduce significativamente los tokens necesarios para completar tareas, porque Claude Code no necesita redescubrir contexto en cada conversación. Este benchmark mide ese ahorro de forma rigurosa.

## Objetivo

Medir cuántos tokens de Claude Code (input + output) se ahorran al usar AI Memory MCP vs no usarlo, ejecutando tareas predefinidas sobre un dataset controlado.

---

## Fase 1: Benchmark Controlado

### 1. Dataset

**15 proyectos** (8 energía/industrial + 7 software), **20-30 memorias** por proyecto (~375 total).

#### Proyectos Energía (8)

| Slug | Dominio |
|------|---------|
| `bench-ems-fotovoltaica` | EMS planta solar: irradiancia, PPC, clipping, disponibilidad inversores |
| `bench-estaciones-meteorologicas` | Monitorización estaciones meteo: sensor drift, QA/QC, validación cruzada |
| `bench-scada-hibrido-solar-bess` | SCADA híbrido solar+BESS: SoC, despacho, ramp-rate |
| `bench-calidad-red-ppc` | Calidad de red y PPC: THD, flicker, reactiva en PCC |
| `bench-mantenimiento-predictivo` | Mantenimiento predictivo inversores: IGBT, residuos térmicos |
| `bench-observabilidad-subestaciones` | Observabilidad subestaciones OT: IEC-104, transformadores |
| `bench-parque-eolico-scada` | SCADA parque eólico: pitch, yaw, vibración gearbox |
| `bench-gestion-curtailment` | Gestión curtailment: señales operador, ramp-down, energía perdida |

#### Proyectos Software (7)

| Slug | Dominio |
|------|---------|
| `bench-api-gateway-auth` | API gateway OAuth2/JWT, rate limiting, routing |
| `bench-react-dashboard` | Dashboard React+TS, datos real-time, WebSocket |
| `bench-data-pipeline-etl` | ETL pipeline: Kafka, Spark, data quality, Parquet |
| `bench-ml-model-serving` | ML serving: model registry, A/B testing, canary |
| `bench-mobile-app-flutter` | App Flutter offline-first, push, biometrics |
| `bench-infra-terraform-k8s` | IaC: Terraform, K8s, CI/CD, secrets |
| `bench-event-driven-microservices` | Event-driven: Sagas, DLQ, schema evolution |

#### Memorias por Proyecto (20-30)

| Tipo | Cantidad | Propósito |
|------|----------|-----------|
| `architecture` | 3-4 | Diseño del sistema, stack, flujo de datos |
| `general` | 8-12 | Conocimiento de dominio, convenciones, patrones |
| `decision` | 3-4 | Decisiones arquitectónicas con rationale y alternativas |
| `error` | 3-4 | Errores conocidos con firma y solución |
| `session` | 1-2 | Resúmenes de sesión pasados |
| `task` | 2-3 | Tareas activas con estado |

#### Bridges (~15) y Relaciones (~35)

Bridges conectan proyectos relacionados (ej: EMS ↔ Estaciones Meteo, API Gateway ↔ Dashboard). Relaciones manuales (`supports`, `derived_from`, `complements`, `depends_on`) entre memorias compartidas de proyectos bridgeados.

### 2. Tareas de Benchmark (15)

#### Onboarding (3)

**T01** — Contexto de proyecto nuevo:
```
I'm new to the bench-ems-fotovoltaica project. Give me a summary of its architecture,
key decisions, and any known issues I should be aware of.
```

**T02** — Retomar trabajo:
```
I was working on the bench-react-dashboard project yesterday. What was I doing,
what decisions were made, and what follow-ups are pending?
```

**T03** — Entender dominio:
```
I need to understand how the bench-data-pipeline-etl project handles data quality.
What are the QA/QC patterns used, what errors have been encountered, and what's the
current approach?
```

#### Cross-Project Search (3)

**T04** — Patrones compartidos:
```
Which projects use condition monitoring and anomaly detection? I want to understand
the shared methodology across the energy portfolio.
```

**T05** — Descubrimiento de bridges:
```
I'm working on bench-scada-hibrido-solar-bess. What other projects are related to it
and why? Are there shared patterns or decisions I should know about?
```

**T06** — Reutilización tecnológica:
```
I need to implement rate limiting in the bench-mobile-app-flutter project. Have we
solved this in other projects? Show me relevant patterns and decisions.
```

#### Debugging con Contexto (3)

**T07** — Error conocido:
```
I'm seeing inverted reactive power signs between the EMS and PPC. Has this happened
before? What was the solution?
```

**T08** — Patrón de error cross-project:
```
We're getting timestamp misalignment issues in the bench-parque-eolico-scada project.
Have similar timing problems been solved in other projects?
```

**T09** — Debugging con arquitectura:
```
The bench-api-gateway-auth is returning 429 errors under normal load. What do we know
about the rate limiting architecture and any past issues with it?
```

#### Decisiones y Patrones (2)

**T10** — Arqueología de decisiones:
```
Why did we choose 1-minute sampling for the EMS telemetry pipeline? What alternatives
were considered?
```

**T11** — Consistencia de patrones:
```
I want to add a new data validation step to bench-ml-model-serving. What validation
patterns do we use across the software projects? Are there conventions I should follow?
```

#### Consolidación (2)

**T12** — Estado del portfolio:
```
Give me a status summary of all energy projects: what's the current state of each,
what are the pending follow-ups, and what cross-project dependencies exist?
```

**T13** — Análisis de gaps:
```
Looking at the bench-gestion-curtailment project, what knowledge might be missing?
What do related projects know that this project should also capture?
```

#### Working Memory / Tareas (2)

**T14** — Tareas entre proyectos:
```
What are all the pending tasks across the bench-infra-terraform-k8s and
bench-event-driven-microservices projects? Which ones are blocked or have dependencies?
```

**T15** — Continuidad de sesión:
```
I'm starting a new session on bench-parque-eolico-scada. Load my context: what
happened in the last session, what's pending, and what should I focus on?
```

### 3. Protocolo de Ejecución

#### Toggle MCP On/Off

```bash
# CON MCP: .mcp.json existe normalmente
# SIN MCP: mv .mcp.json .mcp.json.disabled
```

Claude Code lee `.mcp.json` al arrancar. Renombrar el fichero antes de lanzar Claude Code es el método más limpio.

#### Aislamiento de Sesión

Cada tarea usa una sesión nueva con ID determinista:
```
claude --session-id bench-{run_id}-T{nn}-mcp_on
claude --session-id bench-{run_id}-T{nn}-mcp_off
```

#### Flujo del Runner Script (`runner.sh`)

```
1. Verificar stack healthy (make health)
2. Seed dataset benchmark (python seed_benchmark.py)
3. Para cada tarea T01..T15:
   a. Restaurar .mcp.json → modo CON MCP
   b. Mostrar prompt + session ID
   c. Usuario ejecuta: claude --session-id {id}, pega prompt, /exit al terminar
   d. Mover .mcp.json.disabled → modo SIN MCP
   e. Mostrar mismo prompt + nuevo session ID
   f. Usuario ejecuta de nuevo
4. Restaurar .mcp.json
5. Extraer tokens: python extract_tokens.py --run-id {run}
6. Generar informe: python report.py --run-id {run}
```

### 4. Extracción de Tokens

**Fuente**: `~/.claude/projects/-home-cristiantr-GitHub-ai-memory/{session_id}.jsonl`

Cada línea `type: "assistant"` contiene:
```json
{
  "usage": {
    "input_tokens": N,
    "output_tokens": N,
    "cache_creation_input_tokens": N,
    "cache_read_input_tokens": N
  }
}
```

**Deduplicación**: Múltiples líneas pueden compartir el mismo `requestId` (thinking + text). Deduplicar por `requestId`, tomar la última línea por request.

### 5. Métricas

#### Por Sesión (raw)

| Métrica | Descripción |
|---------|-------------|
| `total_input_tokens` | Suma de input_tokens |
| `total_output_tokens` | Suma de output_tokens |
| `total_cache_write` | Suma de cache_creation_input_tokens |
| `total_cache_read` | Suma de cache_read_input_tokens |
| `turn_count` | Número de mensajes del asistente |
| `wall_clock_seconds` | Duración de la sesión |

#### Por Par de Tareas (MCP vs sin MCP)

| Métrica | Fórmula |
|---------|---------|
| `input_token_savings_pct` | `(sin_mcp - con_mcp) / sin_mcp * 100` |
| `output_token_savings_pct` | `(sin_mcp - con_mcp) / sin_mcp * 100` |
| `total_token_savings_pct` | Combinado input + output |
| `turn_reduction_pct` | Reducción en número de turnos |
| `context_efficiency_ratio` | `output / input` (mayor = más eficiente) |

#### Agregados

- Media/mediana de ahorro por categoría
- Mejor/peor caso
- Total tokens ahorrados
- Estimación de ahorro mensual en USD (aplicando precios Anthropic)

#### Cualitativos (anotación manual)

| Métrica | Escala | Qué mide |
|---------|--------|----------|
| `answer_completeness` | 1-5 | ¿Respuesta completa? |
| `answer_accuracy` | 1-5 | ¿Información correcta y específica? |
| `hallucination_count` | Entero | Hechos inventados en respuesta sin MCP |
| `follow_up_needed` | Boolean | ¿Necesitó preguntas adicionales? |

### 6. Aislamiento de Datos

Docker compose override para volúmenes dedicados del benchmark:

```yaml
# docker-compose.benchmark.yaml
services:
  qdrant:
    volumes:
      - ./volumes/benchmark-qdrant:/qdrant/storage
  postgres:
    volumes:
      - ./volumes/benchmark-postgres:/var/lib/postgresql/data
```

Lanzar con: `docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml up -d`

### 7. Informe de Salida

El script `report.py` genera:

- `results/{run_id}/raw_metrics.csv` — Datos crudos por sesión
- `results/{run_id}/comparison.csv` — Pares MCP vs sin-MCP con deltas
- `results/{run_id}/report.md` — Informe markdown con tablas y resumen ejecutivo
- (Opcional) gráficos matplotlib en `results/{run_id}/charts/`

---

## Fase 2: Medición Pasiva (posterior)

Hook de Claude Code que registra token usage al final de cada conversación:

- Se configura en `~/.claude/settings.json`
- Registra en `benchmarks/passive_log.jsonl`: sessionId, proyecto, timestamp, MCP activo, tokens
- El mismo `extract_tokens.py` procesa este log
- Acumula datos durante semanas de uso real

Se implementa una vez validada la Fase 1.

---

## Estructura de Ficheros

```
benchmarks/
  token_benchmark/
    catalog.py              # 15 proyectos con memorias, bridges, relaciones
    tasks.py                # 15 tareas con prompts y categorías
    seed_benchmark.py       # Seed del dataset (reutiliza DemoBrainClient)
    runner.sh               # Orquestador del benchmark
    extract_tokens.py       # Parser de JSONL → métricas
    report.py               # Generador de informe markdown + CSV
    README.md               # Documentación
  results/                  # Resultados por ejecución (gitignored)
docker-compose.benchmark.yaml  # Override de volúmenes
```

---

## Verificación

1. **Dataset**: Seed del benchmark y verificar con `make health` + queries manuales al API
2. **Ejecución**: Correr 2-3 tareas piloto para validar el flujo del runner
3. **Extracción**: Verificar que `extract_tokens.py` parsea correctamente los JSONL de las tareas piloto
4. **Informe**: Generar informe con las tareas piloto y validar métricas
5. **E2E**: Ejecutar las 15 tareas completas y revisar el informe final
