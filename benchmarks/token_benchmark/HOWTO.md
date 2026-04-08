# Guia Paso a Paso: Token Benchmark

Esta guia explica como ejecutar el benchmark de tokens para medir el ahorro que AI Memory MCP proporciona a Claude Code.

## Requisitos Previos

- Docker y Docker Compose instalados
- Claude Code CLI instalado y autenticado (OAuth)
- El repositorio `ai-memory` clonado con `.env` configurado
- Estar en la rama `feat/token-benchmark`

## Conceptos Clave

- **Con MCP**: Claude Code tiene `.mcp.json` activo y puede usar las herramientas de AI Memory (search_memory, get_project_context, etc.)
- **Sin MCP**: Claude Code NO tiene `.mcp.json` y solo puede responder con su conocimiento general — no tiene acceso a las memorias del proyecto
- **Session ID**: Cada ejecucion usa un ID unico para que los logs se guarden en ficheros separados en `~/.claude/projects/`
- **JSONL**: Los logs de Claude Code se guardan en formato JSON Lines con datos de tokens por cada respuesta

## Estructura del Benchmark

```
15 tareas x 2 modos (con/sin MCP) = 30 ejecuciones totales
```

Cada tarea simula un escenario real: onboarding, buscar errores, retomar trabajo, etc.

---

## Paso 0: Preparar el Stack con Datos Limpios

Si el stack benchmark no esta corriendo, levantalo con volumenes aislados:

```bash
# Desde la raiz del proyecto
cd /home/cristiantr/GitHub/ai-memory

# Bajar stack actual (si esta corriendo)
docker compose down --remove-orphans

# Subir con volumenes benchmark (aislados de tus datos de desarrollo)
docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml up -d --build

# Esperar ~30s a que todo este healthy
docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml ps
```

Luego seedear el dataset:

```bash
# Cargar 274 memorias en 15 proyectos
make bench-seed
```

Deberias ver:
```
Benchmark dataset seeded successfully.
  Projects: 15
  Memories: 274
  Bridges: 15
  Relations: 31
```

**IMPORTANTE**: Esto crea datos en `volumes/benchmark-*`, NO toca tus datos en `volumes/`.

---

## Paso 1: Ejecutar el Benchmark (Opcion A — Runner Automatico)

El runner te guia paso a paso:

```bash
cd benchmarks/token_benchmark
./runner.sh
```

O para un piloto con solo 3 tareas:
```bash
./runner.sh --tasks T01,T07,T10
```

El script:
1. Verifica que el stack este sano
2. Seedea datos (saltar con `--skip-seed` si ya estan)
3. Para cada tarea:
   - Te muestra el prompt y el modo (CON/SIN MCP)
   - Te dice que comando ejecutar en otra terminal
   - Espera a que pulses ENTER cuando termines
4. Al final, extrae tokens y genera el informe

---

## Paso 1: Ejecutar el Benchmark (Opcion B — Manual)

Si prefieres control total, sigue estos pasos para cada tarea.

### 1.1 Crear directorio de resultados

```bash
RUN_ID=$(date +%Y%m%d-%H%M%S)
mkdir -p benchmarks/token_benchmark/results/$RUN_ID
```

### 1.2 Ejecutar una tarea CON MCP

Asegurate de que `.mcp.json` existe (estado normal):

```bash
# Verificar que .mcp.json esta en su sitio
ls -la .mcp.json
# Si no existe:
# mv .mcp.json.disabled .mcp.json
```

Abre una terminal y ejecuta:

```bash
cd /home/cristiantr/GitHub/ai-memory
source .env && claude --session-id bench-${RUN_ID}-T01-mcp_on
```

Dentro de Claude Code, pega el prompt de la tarea T01:

```
I'm new to the bench-ems-fotovoltaica project. Give me a summary of its architecture, key decisions, and any known issues I should be aware of.
```

Espera a que Claude Code responda completamente. Observa:
- Deberia usar herramientas MCP como `get_project_context` o `search_memory`
- La respuesta sera especifica y precisa con datos reales del proyecto

Cuando termine, escribe `/exit` para cerrar la sesion.

### 1.3 Ejecutar la misma tarea SIN MCP

Desactiva el MCP renombrando el fichero:

```bash
mv .mcp.json .mcp.json.disabled
```

Ejecuta Claude Code con un session ID diferente:

```bash
cd /home/cristiantr/GitHub/ai-memory
claude --session-id bench-${RUN_ID}-T01-mcp_off
```

Pega **exactamente el mismo prompt**:

```
I'm new to the bench-ems-fotovoltaica project. Give me a summary of its architecture, key decisions, and any known issues I should be aware of.
```

Observa la diferencia:
- Sin MCP, Claude Code NO tiene acceso a las memorias
- Probablemente dira que no tiene informacion o pedira que le des mas contexto
- Puede intentar buscar en ficheros locales pero no encontrara nada relevante

Escribe `/exit` cuando termine.

### 1.4 Restaurar MCP

```bash
mv .mcp.json.disabled .mcp.json
```

**CRITICO**: Siempre restaura `.mcp.json` al terminar. Si lo olvidas, Claude Code no tendra MCP en tu uso normal.

### 1.5 Repetir para cada tarea

Repite los pasos 1.2-1.4 cambiando el ID de tarea (T01, T02, ..., T15).

---

## Paso 2: Crear el Fichero de Sesiones

Despues de ejecutar las tareas, crea `sessions.json` en el directorio de resultados:

```bash
cat > benchmarks/token_benchmark/results/$RUN_ID/sessions.json << 'EOF'
{
  "run_id": "TU_RUN_ID_AQUI",
  "sessions": [
    {
      "task_id": "T01",
      "category": "onboarding",
      "title": "Project overview",
      "difficulty": "simple",
      "session_mcp_on": "bench-TU_RUN_ID-T01-mcp_on",
      "session_mcp_off": "bench-TU_RUN_ID-T01-mcp_off"
    },
    {
      "task_id": "T07",
      "category": "debugging",
      "title": "Known error lookup",
      "difficulty": "simple",
      "session_mcp_on": "bench-TU_RUN_ID-T07-mcp_on",
      "session_mcp_off": "bench-TU_RUN_ID-T07-mcp_off"
    },
    {
      "task_id": "T10",
      "category": "decisions",
      "title": "Decision archaeology",
      "difficulty": "simple",
      "session_mcp_on": "bench-TU_RUN_ID-T10-mcp_on",
      "session_mcp_off": "bench-TU_RUN_ID-T10-mcp_off"
    }
  ]
}
EOF
```

**Nota**: Si usas el runner automatico (`runner.sh`), este fichero se crea solo.

---

## Paso 3: Extraer Tokens

```bash
python3 benchmarks/token_benchmark/extract_tokens.py \
  --run-dir benchmarks/token_benchmark/results/$RUN_ID
```

Esto parsea los JSONL de `~/.claude/projects/-home-cristiantr-GitHub-ai-memory/` buscando los session IDs del benchmark.

Salida esperada:
```
Claude projects dir: /home/cristiantr/.claude/projects/-home-cristiantr-GitHub-ai-memory
  T01 [mcp_on]: input=4523, output=1205, turns=2
  T01 [mcp_off]: input=3100, output=2500, turns=4
  ...

Raw metrics written to: benchmarks/token_benchmark/results/RUN_ID/raw_metrics.csv
```

---

## Paso 4: Generar Informe

```bash
python3 benchmarks/token_benchmark/report.py \
  --run-dir benchmarks/token_benchmark/results/$RUN_ID
```

Genera:
- `report.md` — Informe markdown con tablas de savings
- `comparison.csv` — CSV con metricas comparativas
- `raw_metrics.csv` / `raw_metrics.json` — Datos crudos

---

## Paso 5: Leer el Informe

```bash
cat benchmarks/token_benchmark/results/$RUN_ID/report.md
```

El informe incluye:

### Metricas por tarea
| Metrica | Que mide |
|---------|----------|
| Input Savings % | Reduccion de tokens de entrada (contexto) |
| Output Savings % | Reduccion de tokens de salida (respuesta) |
| Total Savings % | Ahorro total combinado |
| Turn Reduction % | Menos idas y vueltas necesarias |

### Metricas agregadas
- Media/mediana de ahorro por categoria
- Mejor y peor caso
- Total de tokens ahorrados
- Estimacion de coste en USD

---

## Lista de Tareas del Benchmark

### Onboarding (3 tareas)

**T01** — Contexto de proyecto nuevo (simple)
```
I'm new to the bench-ems-fotovoltaica project. Give me a summary of its architecture, key decisions, and any known issues I should be aware of.
```

**T02** — Retomar trabajo (medium)
```
I was working on the bench-react-dashboard project yesterday. What was I doing, what decisions were made, and what follow-ups are pending?
```

**T03** — Entender dominio (medium)
```
I need to understand how the bench-data-pipeline-etl project handles data quality. What are the QA/QC patterns used, what errors have been encountered, and what's the current approach?
```

### Cross-Project Search (3 tareas)

**T04** — Patrones compartidos (complex)
```
Which projects use condition monitoring and anomaly detection? I want to understand the shared methodology across the energy portfolio.
```

**T05** — Descubrimiento de bridges (medium)
```
I'm working on bench-scada-hibrido-solar-bess. What other projects are related to it and why? Are there shared patterns or decisions I should know about?
```

**T06** — Reutilizacion tecnologica (complex)
```
I need to implement rate limiting in the bench-mobile-app-flutter project. Have we solved this in other projects? Show me relevant patterns and decisions.
```

### Debugging con Contexto (3 tareas)

**T07** — Error conocido (simple)
```
I'm seeing inverted reactive power signs between the EMS and PPC. Has this happened before? What was the solution?
```

**T08** — Patron de error cross-project (complex)
```
We're getting timestamp misalignment issues in the bench-parque-eolico-scada project. Have similar timing problems been solved in other projects?
```

**T09** — Debugging con arquitectura (medium)
```
The bench-api-gateway-auth is returning 429 errors under normal load. What do we know about the rate limiting architecture and any past issues with it?
```

### Decisiones y Patrones (2 tareas)

**T10** — Arqueologia de decisiones (simple)
```
Why did we choose 1-minute sampling for the EMS telemetry pipeline? What alternatives were considered?
```

**T11** — Consistencia de patrones (complex)
```
I want to add a new data validation step to bench-ml-model-serving. What validation patterns do we use across the software projects? Are there conventions I should follow?
```

### Consolidacion (2 tareas)

**T12** — Estado del portfolio (complex)
```
Give me a status summary of all energy projects: what's the current state of each, what are the pending follow-ups, and what cross-project dependencies exist?
```

**T13** — Analisis de gaps (complex)
```
Looking at the bench-gestion-curtailment project, what knowledge might be missing? What do related projects know that this project should also capture?
```

### Working Memory / Tareas (2 tareas)

**T14** — Tareas entre proyectos (medium)
```
What are all the pending tasks across the bench-infra-terraform-k8s and bench-event-driven-microservices projects? Which ones are blocked or have dependencies?
```

**T15** — Continuidad de sesion (medium)
```
I'm starting a new session on bench-parque-eolico-scada. Load my context: what happened in the last session, what's pending, and what should I focus on?
```

---

## Piloto Rapido (3 tareas recomendadas)

Para un primer test, ejecuta solo T01, T07 y T10. Son las mas simples y las que mostraran la diferencia mas clara:

```bash
./runner.sh --tasks T01,T07,T10 --skip-seed
```

O manualmente, sigue los pasos del Paso 1B para cada una.

---

## Troubleshooting

### "Stack not healthy"
```bash
docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml ps
# Si algo no esta healthy, reinicia:
docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml restart
```

### "Session file not found" al extraer tokens
Los JSONL estan en `~/.claude/projects/-home-cristiantr-GitHub-ai-memory/`. Verifica que el session ID coincide:
```bash
ls ~/.claude/projects/-home-cristiantr-GitHub-ai-memory/bench-*
```

### "Illegal header value" al seedear
El `.env` tiene retornos de carro Windows. Usa:
```bash
make bench-seed
```
(el Makefile sanitiza el `.env` automaticamente)

### Olvidaste restaurar .mcp.json
```bash
# Si .mcp.json.disabled existe, restauralo:
mv .mcp.json.disabled .mcp.json
```

### Quiero volver al stack normal (desarrollo)
```bash
# Bajar stack benchmark
docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml down --remove-orphans

# Subir stack normal
docker compose up -d --build
```
Tus datos de desarrollo siguen intactos en `volumes/`.

---

## Despues del Benchmark

Una vez tengas el informe:

1. **Revisa `report.md`** — Las tablas muestran el ahorro por tarea y por categoria
2. **Identifica patrones** — Que tipo de tareas se benefician mas de AI Memory?
3. **Anota observaciones cualitativas** — La respuesta con MCP fue mas precisa? Hubo alucinaciones sin MCP?
4. **Comparte** — El informe es autocontenido y se puede compartir como evidencia del valor de AI Memory

## Volver al Stack Normal

Cuando termines el benchmark:

```bash
# Bajar benchmark
docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml down --remove-orphans

# Subir stack de desarrollo normal
make stack-up
```
