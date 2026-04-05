# Roadmap de Implementación: Cerebro Bio-Inspirado para IA

## Visión

Transformar ai-memory de un sistema de memoria con conceptos biológicos en un **cerebro artificial completo** con consciencia, predicción, curiosidad y auto-optimización, que ahorre tokens, reduzca errores, y haga a las IAs genuinamente más inteligentes.

---

## Resumen de Investigación

| # | Documento | Concepto Clave | Impacto en Tokens | Impacto en Inteligencia |
|---|-----------|---------------|-------------------|------------------------|
| 01 | Neuromorphic/SNNs | Event-driven sparse activation | -80% cómputo | Robustez adversarial 2x |
| 02 | Consolidación/Sleep | SleepGate, interleaved replay | -O(n)→O(log n) | Previene forgetting |
| 03 | Predictive Coding | Free energy, surprise-driven | -60-80% retrieval | Predicción proactiva |
| 04 | Sparse Representations | SDR pre-filter, keyphrases | -95% candidatos | Detección de novedad |
| 05 | Consciousness/GWT | Global Workspace, C0-C1-C2 | Atención selectiva | Metacognición |
| 06 | SYNAPSE Architecture | Inhibición lateral, uncertainty | -95% tokens | 2x rendimiento |
| 07 | Emotional Tagging | Mood dinámico, evolución | Priorización | Consolidación adaptativa |
| 08 | Spaced Repetition | FSRS scheduling | Retención 85%+ | Menos re-aprendizaje |
| 09 | ALMA Meta-learning | Auto-optimización de diseño | Adaptado al dominio | Mejora continua |
| 10 | Curiosity/ToM | Gap detection, agent beliefs | Menos duplicación | Aprendizaje proactivo |

---

## Fases de Implementación

### FASE 1: Quick Wins (1-2 semanas) — Ahorro Inmediato de Tokens

#### 1.1 SDR Pre-filter con Keyphrases
```
Archivos: api-server/server.py (structured_search_memories)
Esfuerzo: Bajo
Impacto: -80% candidatos evaluados, -50% latencia

Acción: Antes de embedding search, pre-filtrar por keyphrases overlap
  - Ya existe: keyphrases en memory_log, GIN index
  - Añadir: WHERE keyphrases && $query_keyphrases antes de Qdrant
  - Fallback: si pre-filter retorna <limit, hacer búsqueda full
```

#### 1.2 Novelty Score Activo
```
Archivos: api-server/server.py (store_memory)
Esfuerzo: Bajo
Impacto: -30% memorias redundantes

Acción: Calcular novelty_score al ingestar (campo ya existe, no se calcula)
  - Buscar top-3 memorias similares en mismo proyecto
  - novelty = 1 - max_similarity
  - Si novelty < 0.15 → merge con existente en vez de crear nueva
```

#### 1.3 Uncertainty-Aware Retrieval
```
Archivos: api-server/server.py (structured_search_memories)
Esfuerzo: Bajo
Impacto: Elimina ~15% false positives

Acción: Añadir campo confidence al response
  - confidence = max_score / mean_score
  - Si confidence < 1.5 → warning "low confidence"
  - Agentes pueden decidir no usar resultados con baja confianza
```

#### 1.4 Retrievability Score (FSRS)
```
Archivos: api-server/server.py, config/postgres/init.sql
Esfuerzo: Bajo
Impacto: Saber qué memorias se están olvidando

Acción:
  - Añadir columnas: next_review_at, retrievability, difficulty
  - Calcular R(t) = (1 + t/S)^(-1) en cada lectura
  - Endpoint: GET /api/memories/due-for-review
```

---

### FASE 2: Core Intelligence (2-4 semanas) — Inteligencia Real

#### 2.1 Inhibición Lateral en Spreading Activation
```
Archivos: api-server/server.py (propagate_activation)
Esfuerzo: Medio
Impacto: Retrieval más preciso, menos ruido

Acción: Implementar winner-take-all en propagación
  - Tras propagar, aplicar inhibición lateral
  - Solo memorias con energy > mean + σ pasan threshold
  - Sigmoid gate para comportamiento todo-o-nada
```

#### 2.2 Evolución Emocional Dinámica
```
Archivos: api-server/server.py (register_memory_access)
Esfuerzo: Medio
Impacto: Priorización más inteligente

Acción:
  - Actualizar valence/arousal en cada acceso con EMA
  - Implementar habituación de arousal (decay temporal)
  - Tabla emotional_history para tracking
```

#### 2.3 Reconsolidación de Memorias
```
Archivos: api-server/server.py, reflection-worker/worker.py
Esfuerzo: Medio
Impacto: Memorias más precisas y actualizadas

Acción:
  - Cuando memoria se accede con contexto diferente → calcular prediction error
  - Si error > threshold → memoria entra en estado lábil
  - Actualizar contenido, reducir stability 30%
  - Trigger detección de contradicciones
```

#### 2.4 Consolidación Adaptativa (Sleep Debt)
```
Archivos: reflection-worker/worker.py
Esfuerzo: Medio
Impacto: Consolidación oportuna vs cada 6h fijo

Acción:
  - sleep_debt metric basada en: tiempo, contradicciones, memorias nuevas
  - Trigger consolidación cuando sleep_debt > 1.0
  - NREM prioriza clusters con alto error rate
  - Interleaved replay: nuevas + antiguas juntas
```

---

### FASE 3: Consciousness Layer (4-6 semanas) — Consciencia Computacional

#### 3.1 Global Workspace Hub
```
Archivos: Nuevo api-server/global_workspace.py
Esfuerzo: Alto
Impacto: Atención selectiva, coordinación global

Acción:
  - Implementar compete_and_select() con scoring multi-señal
  - Broadcast de ganadores a todos los subsistemas
  - Capacity limit de 5 items en workspace
  - Logging de consciousness_state
```

#### 3.2 Consciousness Score (C0-C1-C2)
```
Archivos: api-server/brain_health.py
Esfuerzo: Medio
Impacto: Auto-evaluación del sistema

Acción:
  - C0: salud de procesos automáticos (decay, activation, consolidation)
  - C1: accesibilidad (search success rate, latencia, cobertura)
  - C2: metacognición (prediction accuracy, calibración, gaps)
  - Endpoint: GET /api/brain/consciousness/{project}
```

#### 3.3 Curiosity Engine
```
Archivos: Nuevo api-server/curiosity_engine.py
Esfuerzo: Medio
Impacto: Detección proactiva de gaps

Acción:
  - 3 tipos de gaps: preguntas sin respuesta, memorias huérfanas, dominios sin cobertura
  - curiosity_score por proyecto
  - Endpoint: GET /api/brain/curiosity/{project}
  - Tabla: knowledge_gaps
```

#### 3.4 Theory of Mind (Agent Beliefs)
```
Archivos: Nuevo api-server/agent_beliefs.py
Esfuerzo: Medio
Impacto: Coordinación multi-agente

Acción:
  - Tracking de conocimiento por agent_id
  - Detección de gaps entre agentes
  - Recomendaciones de sharing
  - Tabla: agent_beliefs
  - Endpoint: GET /api/brain/agents/{project}
```

---

### FASE 4: Predictive Intelligence (6-8 semanas) — Eficiencia Máxima

#### 4.1 Predictive Memory Gate
```
Archivos: Nuevo api-server/predictive_gate.py, server.py
Esfuerzo: Alto
Impacto: -60-80% embedding calls

Acción:
  - Predecir qué memorias necesita el agente basándose en patrón de query
  - Solo hacer embedding search si query viola predicción (surprise > threshold)
  - Cache de predicciones por query-pattern
  - Actualización del modelo predictivo con feedback
```

#### 4.2 Extracción Semántica Incremental
```
Archivos: reflection-worker/worker.py, server.py
Esfuerzo: Medio
Impacto: Schemas más oportunos

Acción:
  - Cada N=5 memorias nuevas → extraer conceptos semánticos
  - En lugar de esperar a deep_sleep para schemas
  - Deduplicación con threshold 0.92 (como SYNAPSE)
```

#### 4.3 Schema Jerárquico Multi-Nivel
```
Archivos: reflection-worker/worker.py, config/postgres/init.sql
Esfuerzo: Alto
Impacto: Respuestas con 40% menos contexto

Acción:
  - abstraction_level > 1: patrones → principios → leyes
  - Queries se resuelven al nivel más abstracto posible
  - Bidirectional links: schema ↔ ejemplares
  - Schema confidence tracking
```

#### 4.4 Mini-ALMA: Auto-optimización
```
Archivos: Nuevo api-server/design_optimizer.py
Esfuerzo: Alto
Impacto: Parámetros adaptados por proyecto

Acción:
  - Optimizar cascade thresholds, signal weights, decay rates por proyecto
  - Evaluación basada en search precision + retention + schema quality
  - Tabla: memory_design_archive, active_memory_design
  - Hill-climbing simple (futuro: Meta Agent LLM)
```

---

## Nuevas Tablas SQL (Todas las Fases)

```sql
-- FASE 1
ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS next_review_at TIMESTAMPTZ;
ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS retrievability FLOAT DEFAULT 1.0;
ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS difficulty FLOAT DEFAULT 5.0;

-- FASE 2
CREATE TABLE IF NOT EXISTS emotional_history (...);
CREATE TABLE IF NOT EXISTS project_mood (...);

-- FASE 3
CREATE TABLE IF NOT EXISTS consciousness_state (...);
CREATE TABLE IF NOT EXISTS knowledge_gaps (...);
CREATE TABLE IF NOT EXISTS agent_beliefs (...);

-- FASE 4
CREATE TABLE IF NOT EXISTS prediction_cache (...);
CREATE TABLE IF NOT EXISTS memory_design_archive (...);
CREATE TABLE IF NOT EXISTS active_memory_design (...);
```

---

## Nuevos Archivos

```
api-server/
├── global_workspace.py      # FASE 3 — GWT hub
├── curiosity_engine.py       # FASE 3 — Gap detection
├── agent_beliefs.py          # FASE 3 — Theory of Mind
├── predictive_gate.py        # FASE 4 — Free Energy prediction
├── design_optimizer.py       # FASE 4 — Mini-ALMA
└── consciousness_metrics.py  # FASE 3 — C0-C1-C2 scoring
```

---

## Métricas de Éxito (CI-Enforced)

| Métrica | Actual | Post-Fase 1 | Post-Fase 2 | Post-Fase 4 |
|---------|--------|-------------|-------------|-------------|
| Tokens por retrieval | ~2,000 | ~1,000 | ~800 | ~400 |
| Search latency P95 | ≤250ms | ≤150ms | ≤100ms | ≤80ms |
| False positive rate | ~15% | ~8% | ~5% | ~3% |
| Memory retention | ~60% | ~75% | ~80% | ~85% |
| Redundant memories | ~30% | ~10% | ~5% | ~3% |
| Contradiction detection | Pasivo | Pasivo | Proactivo | Predictivo |
| Consciousness score | N/A | N/A | Implementado | Calibrado |
| Knowledge gap detection | No | No | Si (3 tipos) | Si + proactivo |
| Multi-agent coordination | Aislado | Aislado | Knowledge-aware | ToM-enabled |

---

## Dependencias Externas Nuevas

| Dependencia | Fase | Propósito |
|-------------|------|-----------|
| Ninguna nueva | 1-2 | Todas las mejoras usan infraestructura existente |
| Posible: pymdp | 4 | Active inference (opcional) |

---

## Papers Fundamentales (Top 15)

1. **SYNAPSE** (2025) — arXiv:2601.02744 — Spreading activation + 95% token reduction
2. **Titans** (2024) — arXiv:2501.00663 — Surprise-driven memory
3. **SleepGate** (2026) — arXiv:2603.14517 — Sleep-inspired consolidation, O(n)→O(log n)
4. **ALMA** (2026) — arXiv:2602.07755 — Meta-learned memory designs
5. **HippoRAG** (2024) — arXiv:2405.14831 — Hippocampal indexing for LLMs
6. **Mem0** (2025) — arXiv:2504.19413 — Production memory layer, 90% token savings
7. **TransformerFAM** (2024) — arXiv:2404.09173 — Feedback attention as working memory
8. **PCN for ML** (2025) — arXiv:2506.06332 — Predictive coding networks, PyTorch
9. **GWT for AI** (2024) — arXiv:2410.11407 — Consciousness via Global Workspace
10. **LLM Consciousness Survey** (2025) — arXiv:2505.19806 — C0-C1-C2 framework
11. **Cognitive Design Patterns** (2025) — arXiv:2505.07087 — ACT-R/SOAR → LLM agents
12. **Neuro-inspired Sparsity** (2025) — Nature Comms — 5-10x energy reduction
13. **Corticohippocampal Hybrid** (2025) — Nature Comms — Continual learning
14. **Forgetting Curves in DNNs** (2025) — arXiv:2506.12034 — Validates Ebbinghaus
15. **Memory in AI Agents Survey** (2025) — arXiv:2512.13564 — 200+ papers taxonomy
