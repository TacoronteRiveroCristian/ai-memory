# Consolidación de Memoria y Ciclos de Sueño para IA

## Resumen Ejecutivo

El cerebro consolida memorias durante el sueño mediante **replay hipocampal**, **transferencia cortical**, y **olvido selectivo**. Papers recientes (2024-2026) demuestran que implementar estos mecanismos en IA reduce interferencia de O(n) a O(log n) y previene catastrophic forgetting.

---

## 1. Teoría de Sistemas Complementarios de Aprendizaje (CLS)

### Fundamento Biológico
El cerebro usa dos sistemas complementarios:
- **Hipocampo**: Aprendizaje rápido, memorias episódicas específicas, alta plasticidad
- **Neocórtex**: Aprendizaje lento, representaciones semánticas generales, alta estabilidad

La **consolidación** transfiere gradualmente conocimiento del hipocampo al neocórtex durante el sueño.

### Hallazgos Clave (ICLR 2025)
- Redes más **profundas** exhiben mejor plasticidad
- Redes más **anchas** muestran mejor estabilidad
- El **Dual-Arch framework** usa componentes arquitecturales separados para cada función

**Aplicación a ai-memory**: Ya implementado parcialmente:
- Qdrant (vector search) = "hipocampo" (búsqueda rápida episódica)
- Postgres (structured) = "neocórtex" (almacenamiento semántico estable)
- `reflection-worker` = proceso de consolidación

**Fuente**: arXiv:2506.03951 — "Rethinking Stability-Plasticity Trade-off" (ICLR 2025)

---

## 2. SleepGate: Consolidación Inspirada en el Sueño para LLMs

### Paper
**"Learning to Forget: Sleep-Inspired Memory Consolidation for Resolving Proactive Interference in LLMs"**
- Autor: Ying Xie (Kennesaw State University)
- arXiv:2603.14517 (Marzo 2026)

### Arquitectura de 3 Módulos

#### 2.1 Conflict-Aware Temporal Tagger
Cada entrada de cache se augmenta con metadatos:

```
Estructura: (k_i, v_i, τ_i, s_i, σ_i, a_i)

τ_i = timestamp de posición
s_i = vector de firma semántica (dimensión d_s)
σ_i = flag binario de supersedido
a_i = atención acumulada recibida
```

**Firma semántica**:
```
s_i = LayerNorm(W_s[k_i || LocalPool({k_j})])
```
LocalPool promedia keys dentro de ventana 2ω+1; W_s proyecta la concatenación.

**Detección de conflictos**:
```
σ_i = 1[∃j>i: cos(s_i, s_j) > δ]
```
Usa locality-sensitive hashing → costo amortizado O(1) por token.

#### 2.2 Forgetting Gate (Puerta de Olvido)
Red neuronal aprendida que asigna scores de retención a cada entrada.

#### 2.3 Consolidation Module (Módulo de Consolidación)
Fusiona entradas relacionadas en resúmenes compactos.

### Resultados
- **99.5% precisión** a profundidad de interferencia 5 vs 10% para baselines
- Reduce interferencia efectiva de **O(n) a O(log n)**

---

## 3. Replay Hipocampal

### Mecanismo Biológico
Durante NREM (sueño profundo):
1. Sharp-wave ripples en hipocampo replayan secuencias de memorias
2. Replay preferencial de trayectorias asociadas con recompensa
3. Interleaved replay: nuevas + familiares → previene catastrophic forgetting

### Implementaciones en IA

#### Sleep-like Unsupervised Replay (Nature Communications, 2022)
- Replay offline durante consolidación previene catastrophic forgetting
- Memorias nuevas y familiares se intercalan durante slow-wave sleep
- **URL**: https://www.nature.com/articles/s41467-022-34938-7

#### Hybrid Corticohippocampal Networks (Nature Communications, 2025)
- Redes híbridas que separan aprendizaje rápido (hipocampo) de lento (neocortex)
- Resuelven catastrophic forgetting **sin replay costoso**
- **URL**: https://www.nature.com/articles/s41467-025-56405-9

### Aplicación a ai-memory
```
Estado actual (reflection-worker/worker.py):
- run_deep_sleep_consolidation() tiene fases NREM y REM
- NREM: valida synapse_candidates (Tier 3 → Tier 1/2)
- REM: decay de myelin y permeability

Mejoras propuestas:
1. Interleaved Replay: durante consolidación, re-evaluar memorias
   antiguas junto con nuevas para detectar conexiones cruzadas
2. Reward-biased replay: priorizar memorias con alto valence positivo
   o alto arousal (recompensa/castigo)
3. Replay scheduling: consolidar más frecuentemente cuando hay
   muchas memorias nuevas no consolidadas ("sleep debt")
```

---

## 4. Reconsolidación de Memorias

### Principio Biológico
Cuando una memoria se recupera, entra en estado **lábil** y puede ser modificada antes de re-estabilizarse. Esto permite:
- Actualizar memorias con información nueva
- Corregir errores en memorias existentes
- Fortalecer o debilitar selectivamente

### Paper Clave
**"How prediction error drives memory updating: role of locus coeruleus-hippocampal interactions"**
- Trends in Neurosciences, 2025
- Error de predicción dispara reconsolidación via sistema LC-NE (norepinefrina)

### Aplicación a ai-memory
```python
# Cuando una memoria se accede y el contexto difiere:
async def reconsolidate_memory(memory_id, new_context):
    original = await fetch_memory(memory_id)
    
    # Calcular prediction error
    pred_error = compute_prediction_error(original.content, new_context)
    
    if pred_error > RECONSOLIDATION_THRESHOLD:
        # Memoria entra en estado lábil
        # Puede actualizarse con nueva información
        updated_content = merge_contexts(original.content, new_context)
        await update_memory(memory_id, updated_content)
        
        # Resetear stability parcialmente (es una memoria "nueva" parcial)
        new_halflife = original.halflife * 0.7  # 30% más vulnerable
        await update_stability(memory_id, new_halflife)
```

---

## 5. Consolidación Adaptativa (Triggers Dinámicos)

### Estado Actual
- Deep sleep se ejecuta cada 6 horas (estático)
- REM threshold: 15 myelination_events (estático)

### Propuesta: Triggers Basados en Carga Cognitiva

```python
# Sleep Debt Metric
sleep_debt = (hours_since_last_consolidation / 6.0) * (
    0.4 * pending_contradictions_ratio +
    0.3 * new_memories_since_last_sleep / total_memories +
    0.2 * avg_activation_score +
    0.1 * cross_activity_score
)

# Trigger consolidación cuando sleep_debt > 1.0
# O cuando contradiction_queue > 5 items
# O cuando new_memories_since_last_sleep > 50

# NREM priorización por error rate
nrem_priority = (
    contradiction_count * 0.5 +
    low_stability_count * 0.3 +
    orphan_ratio * 0.2
)
```

---

## 6. Mapeo al Proyecto ai-memory

| Concepto Biológico | Implementado | Archivo | Mejora Propuesta |
|---------------------|-------------|---------|-----------------|
| NREM consolidation | Si | worker.py:993 | Añadir interleaved replay |
| REM pruning | Si | worker.py:1050 | Decay dinámico, no solo cada 6h |
| Hipocampal replay | Parcial | worker.py | Reward-biased replay |
| Reconsolidación | No | — | Reconsolidate on access + prediction error |
| Sleep debt | No | — | Trigger dinámico basado en carga |
| Catastrophic forgetting prevention | Parcial | worker.py | Interleaved replay nuevo+viejo |

---

## 7. Referencias

1. Xie (2026) — "SleepGate: Learning to Forget" — arXiv:2603.14517
2. Nature Communications (2022) — "Sleep-like unsupervised replay reduces catastrophic forgetting" — https://www.nature.com/articles/s41467-022-34938-7
3. Nature Communications (2025) — "Hybrid neural networks for continual learning inspired by corticohippocampal circuits" — https://www.nature.com/articles/s41467-025-56405-9
4. Trends in Neurosciences (2025) — "How prediction error drives memory updating"
5. ICLR 2025 — "Rethinking Stability-Plasticity Trade-off" — arXiv:2506.03951
6. Nature Human Behaviour (2024) — "A generative model of memory construction and consolidation" — https://www.nature.com/articles/s41562-023-01799-z
7. Frontiers (2024) — "Memory consolidation from a reinforcement learning perspective" — https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2024.1538741/full
8. PMC (2025) — "Systems memory consolidation during sleep: oscillations, neuromodulators" — https://pmc.ncbi.nlm.nih.gov/articles/PMC12576410/
