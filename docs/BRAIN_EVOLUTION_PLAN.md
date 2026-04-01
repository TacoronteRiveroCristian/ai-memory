# Plan de Evolución: Cerebro Artificial con Plasticidad Real

> Documento vivo. Última actualización: 2026-03-31
> Objetivo: convertir el sistema de memoria actual (base de conocimiento + metadatos) en un cerebro genuinamente plástico donde los conceptos se relacionen, se fortalezcan, decaigan y emerjan patrones de forma análoga a la cognición biológica.

---

## Estado actual del sistema

| Componente | Rol analógico | Tecnología |
|---|---|---|
| Qdrant | Corteza asociativa (semántica duradera) | Vector DB, cosine 1536d |
| PostgreSQL | Memoria procedimental / estructurada | pgvector, relaciones explícitas |
| Redis | Caché de embeddings + heartbeat | TTL 3600s |
| mem0 | Hipocampo (working memory) | DeepSeek + pgvector + Kuzu |
| api-server | Corteza prefrontal / control ejecutivo | FastAPI + MCP |
| reflection-worker | Fase de consolidación offline (sueño) | Asyncio + DeepSeek |

### Limitaciones actuales identificadas

| Mecanismo | Estado actual | Problema |
|---|---|---|
| Decay | Lineal fijo (`-0.03` cada 21 días) | No sigue la curva de olvido real de Ebbinghaus |
| Refuerzo | `+0.015` por co-activación | Plano, sin efecto en duración de memoria |
| Propagación | Ninguna | Activar memoria A no activa vecinas B, C |
| Emoción/Valencia | Solo `importance: float` | Sin carga afectiva diferenciada |
| Consolidación | Extrae memorias de sesiones | No detecta patrones abstractos ni resuelve contradicciones |
| Recuperación | 1 salto, score híbrido fijo | Sin cadenas de asociación ni priming contextual |
| Novedad | No detectada | Información nueva no recibe ventaja inicial |
| Esquemas | No existen | No emergen patrones generalizados |

---

## Roadmap de implementación

```
ALTA PRIORIDAD (impacto inmediato en comportamiento LLM)
  [1] Curva de Ebbinghaus        — memoria que dura de verdad
  [2] Valencia emocional          — errores y breakthroughs se graban más fuerte
  [3] Sesgo de novedad            — nuevas ideas no se pierden

MEDIA PRIORIDAD (plasticidad real)
  [4] Spreading Activation        — priming contextual
  [5] Recuperación Multi-Salto    — asociación encadenada
  [6] Extracción de Esquemas      — principios generales emergen

LARGO PLAZO (coherencia epistémica)
  [7] Resolución de Contradicciones
  [8] Deep Sleep Phase (worker fase 2)
```

---

## [1] Curva de Ebbinghaus — Forgetting Curve + Spaced Repetition

### Estado: ✅ IMPLEMENTADO

### Problema
El decay actual es lineal y fijo: cada relación pierde `-0.03` de peso cada 21 días independientemente de cuántas veces se ha accedido. En el cerebro real, la velocidad de olvido depende de cuántas veces has recordado algo antes (Ebbinghaus, 1885). Una memoria repasada múltiples veces puede durar años sin refuerzo.

### Solución

**Fórmula de retención** (en lugar de lineal):
$$R(t) = e^{-t / S}$$

Donde $S$ (estabilidad) representa la "resistencia al olvido" y crece con cada repaso:
$$S_{n+1} = S_n \times 2.0$$

**Cambios en BD** (`config/postgres/init.sql`):
- `memory_log` +`review_count INT DEFAULT 0` — número de repasos
- `memory_log` +`stability_halflife_days FLOAT DEFAULT 1.0` — media-vida actual

**Cambios en código** (`api-server/server.py`):
- `register_memory_access()` — incrementa `review_count`, dobla `stability_halflife_days`
- `decay_project_relations()` — usa media-vida exponencial en lugar de `-0.03` lineal

### Efecto esperado
Una memoria accedida 5 veces tiene `stability_halflife = 16 días`. Accedida 10 veces: `512 días`. Sin acceso: desaparece en 1-2 días. Esto crea diferenciación real entre conocimiento consolidado y ruido.

---

## [2] Valencia Emocional — Emotional Tagging

### Estado: ✅ IMPLEMENTADO

### Problema
`importance=0.7` no distingue entre "aprendí esto con esfuerzo" y "esto me costó 3 horas de debugging". Los recuerdos con carga negativa (errores críticos) y positivos (breakthroughs) deberían grabarse con diferente profundidad. La amígdala biológica modula la consolidación hipocampal según la carga emocional.

### Solución

**Nuevos campos en `memory_log`**:
- `valence FLOAT DEFAULT 0.0` — rango [-1, +1]: negativo=malo/doloroso, positivo=bueno/satisfactorio
- `arousal FLOAT DEFAULT 0.5` — rango [0, 1]: intensidad emocional (0=neutro, 1=máximo impacto)

**Extracción automática**: el LLM infiere `valence` y `arousal` del contenido durante `store_memory`. Heurístico rápido: keywords de errores/fallos → valence negativo + arousal alto; breakthroughs/soluciones → valence positivo.

**Fórmula de estabilidad efectiva**:
$$S_{eff} = stability + 0.3 \cdot arousal + 0.2 \cdot |valence|$$

**Decay protegido**: memorias con `arousal > 0.7` tienen `stability_halflife` conservado (sus errores dolorosos perduran).

**Prominence en grafo**:
$$prominence_{new} = prominence_{old} + 0.08 \cdot arousal + 0.05 \cdot |valence|$$

### Efecto esperado
Los errores críticos y los breakthroughs son las memorias que más influyen en el comportamiento del LLM a largo plazo. El cerebro "aprende con más fuerza" de las experiencias intensas.

---

## [3] Sesgo de Novedad — Novelty Bias

### Estado: ✅ IMPLEMENTADO

### Problema
Información completamente nueva debería recibir un boost inicial de atención. Ahora todas las memorias entran con `importance=0.7` estático. En el cerebro, el hipocampo y la amígdala responden más fuerte ante novelty — es el mecanismo evolutivo para actualizar el modelo del mundo.

### Solución

**En `store_memory`** (antes de guardar):
1. Busca similitud máxima contra memorias existentes del proyecto
2. `novelty_score = 1.0 - max_similarity`
3. Si `max_similarity < 0.50` → `importance = min(1.0, importance + 0.15 * novelty_score)`
4. Si `max_similarity > 0.90` → posible duplicado → `importance = max(0.3, importance - 0.1)`

**Nuevo campo**: `novelty_score FLOAT DEFAULT 0.5` en `memory_log`

**En el grafo**: memorias con `novelty_score > 0.7` reciben prominence boost para destacar ideas realmente nuevas.

### Efecto esperado
Ideas genuinamente nuevas no se ahogan en el mar de lo conocido. El cerebro presta más atención a lo que no sabe. También actúa como detector de redundancia.

---

## [4] Spreading Activation — Activación Propagada

### Estado: ✅ IMPLEMENTADO

### Problema
Recuperar memoria A no activa sus vecinas B y C. En el cerebro, acceder a un concepto activa toda la red asociada (priming). Si llevas 3 sesiones trabajando en tema X, los conceptos relacionados con X deberían subir espontáneamente en búsquedas.

### Solución

**Nueva función** `propagate_activation(memory_id, depth=2, decay_factor=0.4)`:
1. Parte de la memoria activada con `activation_energy = 1.0`
2. Por cada relación activa: propaga `energy * decay_factor * relation_weight`
3. Guarda activación temporal en Redis: `activation_propagation:{memory_id}` → JSON, TTL 15 min

**En `structured_search_memories`**: el score híbrido incluye `propagation_bonus` desde Redis:
$$hybrid\_score_{new} = hybrid\_score + 0.15 \cdot propagation\_bonus$$

**En `apply_session_plasticity`**: tras reforzar memorias relevantes, dispara `propagate_activation` en background para las top-3 memorias de la sesión.

### Efecto esperado
El cerebro entra en "modo de pensamiento temático". Al trabajar en infraestructura de redes, todos los conceptos de red se priman automáticamente. Las búsquedas posteriores se hacen en el contexto del tema activo.

---

## [5] Recuperación Multi-Salto — Associative Chaining

### Estado: ✅ IMPLEMENTADO

### Problema
La búsqueda actual es `query → vector → 1 resultado`. Un cerebro real sigue cadenas asociativas: "PHP → Apache → configuración → error que tuve → solución". La recuperación encadenada permite conectar conceptos que no son semánticamente similares pero están relacionados por experiencia.

### Solución

**Parámetro adicional en `POST /api/search/structured`**: `chain_hops: int = 0` (0=comportamiento actual, 1=1 salto, 2=2 saltos)

**Lógica**:
1. Búsqueda semántica normal (capa 0)
2. Para los top-3: expande por relaciones activas con `weight > 0.35` (capa 1), score *= 0.7
3. Si `chain_hops=2`: expande capa 1 un salto más, score *= 0.7 otra vez
4. Los resultados de todas las capas se mezclan, deduplicados, ordenados por score final

**En MCP tool `search_memory`**: parámetro `chain_hops` opcional.

**Organización del contexto para LLM**: los resultados incluyen `hop_distance` y se agrupan por hilo de asociación en la respuesta.

### Efecto esperado
El LLM recibe no solo los hechos más similares, sino también los conceptualmente adyacentes por experiencia. Esto simula el fenómeno de "de repente me acuerdo de algo relacionado que no estaba buscando".

---

## [6] Extracción de Esquemas — Schema Abstraction

### Estado: ✅ IMPLEMENTADO

### Problema
El cerebro actual solo guarda hechos concretos. Un cerebro real también genera reglas abstractas ("cuando hago X en contexto Y, suele pasar Z"). Estos esquemas cognitivos son los que configuran el comportamiento experto — el LLM con acceso a esquemas razona con principios, no solo recita hechos.

### Solución

**Nuevo `memory_type = "schema"`** con campo `abstraction_level: int` (0=concreto, 3=muy abstracto)

**Nueva tabla** `schema_sources`: vincula una memoria-esquema con las memorias concretas de las que emergió.

**En el reflection worker** (Fase 1 ampliada):
1. Agrupa memorias de `same_concept` + `extends` con `activation_score > 0.3` por proyecto/tags
2. Si cluster tiene ≥ 3 memorias: prompt al LLM — *"Dados estos N hechos sobre X, extrae el principio general subyacente en una frase"*
3. Guarda como `memory_type="schema"`, `manual_pin=True`, relaciones `derived_from` apuntando a fuentes
4. Los esquemas existentes se revisan: si nuevas memorias contradicen el esquema → actualización o contradicción

**En búsqueda**: los esquemas aparecen en las búsquedas con etiqueta visual diferenciada y peso extra de `+0.1` en el score por ser generalizaciones.

### Efecto esperado
Con el tiempo emerge una capa de conocimiento abstracto. El LLM recibe principios generales junto con ejemplos concretos. Comportamiento más consistente y menos dependiente de memorias específicas.

---

## [7] Resolución de Contradicciones — Active Contradiction Management

### Estado: ✅ IMPLEMENTADO

### Problema
Las relaciones `contradicts` se crean pero no generan ninguna acción. En un cerebro real, la contradicción genera tensión activa que fuerza reconciliación o selección. Mantener creencias contradictorias sin decidir degrada la calidad del razonamiento del LLM.

### Solución

**Nueva tabla** `contradiction_queue`:
```sql
CREATE TABLE contradiction_queue (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  memory_a_id UUID REFERENCES memory_log(id),
  memory_b_id UUID REFERENCES memory_log(id),
  resolution_status VARCHAR(20) DEFAULT 'pending',  -- pending/resolved/coexisting
  resolution_type VARCHAR(30),  -- a_wins/b_wins/synthesis/conditional
  resolution_memory_id UUID REFERENCES memory_log(id),  -- si se crea síntesis
  condition_text TEXT,  -- si coexisten bajo condiciones distintas
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Disparador**: cuando `auto_link_memory` infiere una relación `contradicts`, inserta en `contradiction_queue`.

**En el reflection worker** (procesamiento de contradicciones):
1. Recupera pares en `resolution_status='pending'`
2. Prompt al LLM: *"Estas dos memorias se contradicen. Evalúa cuál es más reciente, más reforzada, o si pueden coexistir bajo condiciones distintas"*
3. Posibles resoluciones:
   - `a_wins`: baja `stability_score` de B a 0.1
   - `b_wins`: baja `stability_score` de A a 0.1
   - `synthesis`: crea nueva memoria que las integra
   - `conditional`: añade metadata de condición a ambas + las mantiene activas
4. Marca `resolved_at` y actualiza `resolution_status`

**En búsqueda**: si dos resultados tienen `contradicts` activo entre ellos, se señaliza en la respuesta para que el LLM sea consciente de la ambigüedad.

### Efecto esperado
El cerebro no mantiene creencias contradictorias sin decidir. Forzar coherencia epistémica mejora la consistencia del comportamiento del LLM a lo largo del tiempo.

---

## [8] Deep Sleep Phase — Consolidación Profunda del Worker

### Estado: ✅ IMPLEMENTADO

### Problema
El reflection worker actual (Fase 1) extrae memorias de sesiones y las promociona. Falta la fase equivalente al sueño REM donde el cerebro *reorganiza* lo que ya sabe — sin input nuevo, solo consolidando y podando lo existente.

### Solución

**Nueva Fase 2** (cada 24h, controlada por `DEEP_SLEEP_INTERVAL=86400`):

```
FASE 1 (existente, cada 6h): sesiones pendientes → nuevas memorias
FASE 2 (nueva, cada 24h):    memorias existentes → reorganización
```

**Fase 2 hace**:

1. **Detección de clusters semánticos**: agrupa memorias con `activation_score > 0.3` del último período. Identifica temas calientes.

2. **Extracción de esquemas** (sistema [6]): genera memorias `schema` para clusters con ≥ 3 elementos.

3. **Resolución de contradicciones** (sistema [7]): procesa `contradiction_queue` pendiente.

4. **Poda de memorias frías**: memorias con `access_count=0`, `created_at > 30 días`, `manual_pin=FALSE` → `stability_score *= 0.5`. Si `stability_score < 0.1` → marca como archivadas (no se borran, pero no aparecen en búsquedas por defecto).

5. **Refuerzo intra-cluster**: relaciones entre memorias calientes del mismo cluster reciben `+0.02` de peso.

6. **Report a PostgreSQL**: tabla `deep_sleep_runs` con estadísticas de cada ejecución.

### Efecto esperado
El cerebro se reorganiza periódicamente. Los clusters de conocimiento activo se consolidan. El ruido se poda. Los esquemas emergen. Similar al sueño profundo donde se consolida la memoria a largo plazo.

---

## Resumen de cambios de BD

### `memory_log` — columnas añadidas
```sql
review_count              INT DEFAULT 0,
stability_halflife_days   FLOAT DEFAULT 1.0,
valence                   FLOAT DEFAULT 0.0,
arousal                   FLOAT DEFAULT 0.5,
novelty_score             FLOAT DEFAULT 0.5,
abstraction_level         INT DEFAULT 0
```

### Nuevas tablas
```sql
contradiction_queue       -- pares de contradicción + resolución
schema_sources            -- vínculo esquema → memorias origen
deep_sleep_runs           -- historial de ejecuciones Fase 2
```

### Redis — nuevas claves
```
activation_propagation:{memory_id}   TTL 15min   -- energía propagada temporalmente
deep_sleep:last_run                  persistente -- timestamp de último deep sleep
```

---

## Matrices de impacto

| Sistema | Comportamiento LLM | Plasticidad | Coherencia | Coste computacional |
|---|---|---|---|---|
| [1] Ebbinghaus | ★★★★★ | ★★★★☆ | ★★★☆☆ | Bajo |
| [2] Valencia | ★★★★☆ | ★★★☆☆ | ★★★★☆ | Bajo |
| [3] Novedad | ★★★☆☆ | ★★★★☆ | ★★★☆☆ | Bajo |
| [4] Spreading | ★★★★★ | ★★★★★ | ★★★☆☆ | Medio |
| [5] Multi-salto | ★★★★★ | ★★★☆☆ | ★★★★☆ | Medio |
| [6] Esquemas | ★★★★★ | ★★★★★ | ★★★★★ | Alto (LLM) |
| [7] Contradicciones | ★★★☆☆ | ★★☆☆☆ | ★★★★★ | Alto (LLM) |
| [8] Deep Sleep | ★★★★☆ | ★★★★★ | ★★★★★ | Alto (batch) |

---

## Progreso de implementación

- [x] Plan documentado
- [x] [1] Curva de Ebbinghaus — `init.sql` + `server.py` (`register_memory_access`, `decay_memory_stability`)
- [x] [2] Valencia Emocional — `init.sql` + `server.py` (`infer_valence_arousal`, `compute_memory_prominence`)
- [x] [3] Sesgo de Novedad — `server.py` (`store_memory`: novelty check antes de INSERT)
- [x] [4] Spreading Activation — `server.py` (`propagate_activation`, Redis, `structured_search_memories`)
- [x] [5] Recuperación Multi-Salto — `server.py` (`expand_search_with_hops`, `chain_hops` en búsqueda)
- [x] [6] Extracción de Esquemas — `init.sql` + `worker.py` (`run_schema_extraction`, `schema_sources`)
- [x] [7] Resolución de Contradicciones — `init.sql` + `worker.py` + `server.py` (`contradiction_queue`)
- [x] [8] Deep Sleep Phase — `worker.py` (`handle_deep_sleep`, `prune_cold_memories`, `reinforce_hot_clusters`)
