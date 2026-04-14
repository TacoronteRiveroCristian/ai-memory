# Revisión obligatoria — una semana tras el despliegue de la Fase A

> **Fecha de despliegue de Fase A:** 2026-04-14
> **Fecha objetivo de revisión:** 2026-04-21
> **Propósito:** auditar los datos reales recogidos por `ingest_daily_stats` y `classifier_audit` antes de decidir las siguientes fases. **No saltarse este paso.**

La Fase A (observabilidad persistente) se construyó precisamente para responder preguntas que hasta ahora eran ciegas. Las Fases B–E estaban diseñadas a partir de suposiciones. Esta revisión es el momento de confirmar o descartar esas suposiciones con datos reales antes de escribir más código.

---

## Por qué esta revisión es crítica

Antes de la Fase A no había forma de saber:
- Qué rechaza el clasificador, con qué frecuencia, y por qué
- Cuántas clasificaciones fallan por timeouts/errores transitorios (motivación original de los retries de la Fase B)
- Qué porcentaje del dedupe es por hash vs. qué se cuela reformulado (motivación original del dedupe semántico de la Fase D)
- Si el pre-filter es demasiado agresivo (bucket `trivial_user_message`, `no_write_tool_calls`, etc.)

Atacar las Fases B–E sin estos datos sería repetir el error que cometió el documento original de análisis: optimizar prematuramente basándose en intuiciones. **No lo hagamos.**

---

## Qué hay que revisar exactamente

### 1. Volumen y distribución de outcomes

```bash
source .env
# Totales de los últimos 7 días
curl -s -H "X-API-Key: $MEMORY_API_KEY" http://127.0.0.1:8050/ingest/stats | jq .totals

# Por proyecto
curl -s -H "X-API-Key: $MEMORY_API_KEY" http://127.0.0.1:8050/ingest/stats | jq '.projects | to_entries | map({project: .key, turns: .value.turns, stored: .value.stored, errors: .value.errors, filtered: .value.filtered, reasons: .value.filtered_by_reason})'
```

**Preguntas a responder:**
- ¿Cuántos turnos por día, en total y por proyecto? Si hay un proyecto con 0, ¿por qué?
- ¿Qué ratio `stored / turns` tiene cada proyecto? Si es <20%, algo está rechazando demasiado.
- ¿Hay picos sospechosos de `errors`? Si pasa de 0% a 5%, mirar `classifier_audit` para ver el detalle.

### 2. Salud del pre-filter

```bash
curl -s -H "X-API-Key: $MEMORY_API_KEY" http://127.0.0.1:8050/ingest/stats | jq '.projects | to_entries[] | {p: .key, r: .value.filtered_by_reason}'
```

**Preguntas:**
- ¿Qué razón domina el `filtered_by_reason`?
  - Si `no_write_tool_calls` > 80% → el filtro de tool calls probablemente está bien, conversaciones "puras" no merecen ingesta.
  - Si `trivial_user_message` > 50% → ajustar `INGEST_MIN_USER_CHARS`.
  - Si `agent_already_stored` es significativo → el agente está usando bien el protocolo proactivo, no hay que hacer nada.
  - Si `rate_limited` > 5% → subir `INGEST_RATE_LIMIT_SECONDS` o quitarlo para sesiones largas.
  - Si `project_disabled` aparece cuando no debería → revisar `INGEST_DISABLED_PROJECTS`.

### 3. Auditoría cualitativa del clasificador

```bash
# Muestrear decisiones aceptadas con acciones concretas
curl -s -H "X-API-Key: $MEMORY_API_KEY" \
  "http://127.0.0.1:8050/ingest/audit?outcome=accepted_actions&limit=30" | jq '.rows[] | {project, turn_hash, action_types, classifier_ms, user_len, assistant_len}'

# Muestrear decisiones donde el clasificador decidió NO guardar nada
curl -s -H "X-API-Key: $MEMORY_API_KEY" \
  "http://127.0.0.1:8050/ingest/audit?outcome=accepted_empty&limit=30" | jq '.rows[] | {project, turn_hash, classifier_ms, user_len, assistant_len}'

# Errores del clasificador
curl -s -H "X-API-Key: $MEMORY_API_KEY" \
  "http://127.0.0.1:8050/ingest/audit?outcome=error&limit=30" | jq '.rows[] | {project, ts, error_detail, classifier_ms}'
```

**Preguntas:**
- De los `accepted_empty`, ¿cuántos eran realmente vacíos justificadamente y cuántos deberían haber producido al menos una acción? **Esto es lo más importante que esta revisión puede responder.** Si >20% son falsos negativos, el prompt del clasificador (`api-server/classifier.py:_SYSTEM_PROMPT`) está mal calibrado.
- De los `accepted_actions`, ¿los tipos emitidos tienen sentido (`store_error`/`store_decision`/`store_observation`/`store_architecture` bien distribuidos) o hay sesgo hacia uno solo?
- ¿Qué latencia típica tiene el clasificador (`classifier_ms`)? Si el P95 supera los 2000ms, el 3% de turns lentos empieza a morder por culpa del timeout de 15s.
- ¿Hay errores recurrentes con el mismo `error_detail`? Eso justifica retries (Fase B) o cambio de modelo.

### 4. Comprobar que el clasificador no tiene un bug de formato

Si ves muchos `outcome=error` con `error_detail="classifier returned non-JSON"`, significa que DeepSeek (o el modelo que uses) está violando `response_format=json_object` ocasionalmente. Eso es un bug conocido de algunos modelos y se resuelve con retries + validación defensiva. **Confirmar frecuencia antes de hacer Fase B.**

### 5. Distribución por proyecto

```bash
curl -s -H "X-API-Key: $MEMORY_API_KEY" http://127.0.0.1:8050/ingest/stats | jq '.projects | keys'
```

**Preguntas:**
- ¿Aparecen proyectos duplicados por casing (`ai-memory` vs `AI-Memory`) o por path diferente? Si sí, hay que normalizar en `.claude/hooks/ingest-turn.sh` (usar un canonical lower-case en lugar de `basename $PWD`).
- ¿Hay proyectos "fantasma" con 1-2 turnos que luego desaparecen? Puede indicar que el hook está capturando directorios temporales (worktrees, test dirs).

---

## Decisiones a tomar tras la revisión

Con los datos recogidos, **decidir en este orden** qué fases siguientes ejecutar y en qué forma:

### Fase B — Retries + dead-letter queue

**Ejecutar si:** `errors / turns > 2%` **o** hay errores recurrentes con el mismo `error_detail` en `classifier_audit`.

**No ejecutar si:** los errores son <1% y puntuales. Añadir retries entonces es overhead innecesario.

**Ajuste del diseño según datos:** si los errores son timeouts (>14s `classifier_ms` justo antes del error), aumentar `CLASSIFIER_TIMEOUT` antes de añadir retries. Si son errores de formato, añadir validación + retry. Si son rate limits de DeepSeek, añadir backoff exponencial.

### Fase C — Endpoint `/ops` unificado

**Ejecutar si:** durante la semana has hecho más de 5 veces `curl /ingest/stats; curl /brain/health; curl /api/reflections/status` seguidos. Eso es señal de que quieres un dashboard único.

**No ejecutar si:** los tres endpoints separados te han bastado. Es ergonomía, no fiabilidad.

### Fase D — Dedupe semántico vía Qdrant

**Ejecutar si:** encuentras en `classifier_audit` turnos con `action_types` similares a memorias ya almacenadas pero que pasaron el dedupe por hash. Hacer este análisis cruzando `turn_hash` con búsquedas Qdrant sobre el proyecto.

**No ejecutar si:** el dedupe por hash normalizado está atrapando el 95%+ de los duplicados reales. Añadir una consulta Qdrant por cada turn clasificado cuesta 20-50ms y no vale la pena si el problema no existe.

**Ajuste del diseño según datos:** elegir el umbral de similitud (0.88, 0.92, 0.95) basándose en muestras reales del `classifier_audit`, no a ojo.

### Fase E — Test E2E real no-determinista

**Ejecutar siempre.** Este no depende de los datos, depende de la confianza operacional. Escribir `scripts/e2e_real_test.sh` que:

1. Inyecta una conversación técnica concreta vía `/ingest_turn`
2. Espera 2 minutos
3. Hace una query semánticamente distinta vía `/api/search/structured`
4. Verifica que el memory_id aparece en los resultados con score razonable
5. Reinicia la stack (`docker compose restart api-server`)
6. Repite la query
7. Verifica persistencia

Enganchar como cron diario (`schedule` o cron del sistema). Alertar en fallo.

---

## Acciones adicionales a considerar durante la semana

Estas son observaciones que pueden surgir del uso diario y que conviene anotar aquí según aparezcan:

- [ ] Proyectos duplicados por casing/path → normalizar en el hook
- [ ] Categorías que nunca aparecen en `action_types` → revisar el prompt del clasificador
- [ ] Picos de `rate_limited` en sesiones largas → ajustar rate limit por sesión
- [ ] Memorias huérfanas creciendo → correlacionar con `brain/health.regions.<proj>.orphan_ratio`
- [ ] Latencia del clasificador subiendo con el tiempo → cache de embeddings o modelo más ligero
- [ ] (añadir hallazgos nuevos aquí)

---

## Qué hay que tener listo ANTES de la revisión

- **Stack arriba durante la semana completa** (no apagarla, no `docker compose down`). Si se reinicia por mantenimiento está bien — las tablas son persistentes.
- **Uso real desde múltiples proyectos y herramientas** (Claude Code en al menos 2 proyectos diferentes). Sin volumen real, esta revisión no vale nada.
- **No tocar `ingest.py` ni `classifier.py` durante la semana** salvo bugs críticos. Queremos datos limpios de la configuración actual, no de una versión que cambió tres veces.

---

## Cómo ejecutar la revisión

1. Crear una sesión nueva de Claude Code en este repo
2. Decir: "estamos en la revisión semanal de la Fase A de observabilidad. Empieza corriendo los comandos curl del documento `docs/PENDING_WEEK_REVIEW.md` y analiza los resultados. Dame hallazgos concretos, no genéricos."
3. Decidir juntos qué fases ejecutar, en qué orden, y con qué ajustes

---

## Referencias al código relevante

- `api-server/ingest_persistence.py` — módulo de persistencia (inspeccionar si dudas del formato de alguna columna)
- `api-server/ingest.py:init_ingest_routes` — lógica del handler y de los endpoints nuevos
- `api-server/classifier.py:_SYSTEM_PROMPT` — el prompt que está tomando todas las decisiones; candidato #1 a ajuste
- `api-server/ingest_filter.py:should_classify` — el pre-filter heurístico
- `api-server/server.py:run_schema_migrations` — las tablas nuevas (DDL)
- `tests/ingest/test_observability_endpoints.py` — tests de los endpoints (usar como referencia de las respuestas esperadas)

---

*Este documento se actualiza durante la revisión del 2026-04-21 con hallazgos, decisiones tomadas, y el plan de ejecución de las fases siguientes. No borrar — sirve como registro histórico de por qué se decidió lo que se decidió.*
