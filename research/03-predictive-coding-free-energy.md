# Codificación Predictiva y Principio de Energía Libre

## Resumen Ejecutivo

El cerebro funciona como una **máquina de predicción** que solo procesa lo inesperado (error de predicción). Aplicar este principio a AI Memory puede reducir **60-80% de retrievals innecesarios** y tokens consumidos, procesando solo memorias que violan las expectativas del agente.

---

## 1. Principio de Energía Libre de Friston

### Fundamento
Karl Friston propone que todos los sistemas biológicos minimizan **energía libre variacional** — la diferencia entre su modelo interno del mundo y las observaciones sensoriales reales.

### Fórmula Central
```
F = E_q(s)[log q(s) - log p(o, s)]

Donde:
- q(s) = creencia aproximada del agente sobre estados del mundo
- p(o, s) = modelo generativo (observaciones + estados)
- F = energía libre variacional (siempre ≥ sorpresa real)
```

Minimizar F logra dos objetivos simultáneos:
1. **Percepción**: Acercar creencias a la realidad (actualizar modelo interno)
2. **Acción**: Actuar para que la realidad se ajuste a expectativas

### Energía Libre Esperada (Selección de Acción)
```
G(π) = E_q(o_τ, s_τ | π)[log q(s_τ | π) - log p(o_τ, s_τ)]

Descomposible en:
- Término epistémico (ganancia de información / curiosidad)
- Término pragmático (cumplimiento de preferencias / objetivos)
```

**Fuente**: Friston et al. — "Predictive coding under the free-energy principle" — PMC:2666703
**Aplicaciones 2024-2025**: ResearchGate — "From Neuroscience to AI: Friston's Free Energy Principle and Active Inference"

---

## 2. Redes de Codificación Predictiva (PCNs)

### Paper Clave
**"Introduction to Predictive Coding Networks for Machine Learning"**
- arXiv:2506.06332 (Junio 2025)
- Primera guía comprensiva orientada a ML con implementaciones PyTorch

### Función de Energía
```
L = 1/2 * Σ(l=0 a L-1) ||ε(l)||²

ε(l) = x(l) - x̂(l)    # error de predicción en capa l
x̂(l) = f(l)(W(l) * x(l+1))  # predicción top-down
```

### Propagación de Error de Predicción
```
Actualización de estado latente (inferencia):
x(l) ← x(l) - η_infer * (ε(l) - W(l-1)ᵀ(f(l-1)'(a(l-1)) ⊙ ε(l-1)))

Donde:
- a(l) = W(l) * x(l+1)     # preactivación
- ⊙ = producto Hadamard (elementwise)
- f(l)' = derivada de activación

Actualización de pesos (aprendizaje):
W(l) ← W(l) + η_learn * ε(l) * (f(l)'(a(l)) ⊙ x(l+1))ᵀ
```

### Flujo Bidireccional
- **Bottom-up**: Errores de predicción propagados hacia arriba
- **Top-down**: Predicciones fluyen hacia abajo
- Solo los **errores** (sorpresa) consumen recursos computacionales

### Limitación Actual
- Degradación significativa más allá de 5-7 capas (errores exponencialmente desbalanceados)
- Paper de escalado: arXiv:2510.23323 (Oct 2025)

---

## 3. Active Inference para Agentes IA

### Implementación: pymdp
- **Librería**: https://github.com/infer-actively/pymdp
- Python, implementación de Active Inference para MDPs
- Tutoriales: https://pymdp-rtd.readthedocs.io/en/latest/notebooks/active_inference_from_scratch.html

### Ecuaciones de Actualización de Creencias
```
Estimación de estado via mensajes variacionales:
q(s_τ) ∝ σ(ln D + Σ ln B_π(τ)ᵀ q(s_{τ-1}) + ln A^T o_τ)

Donde:
- D = prior sobre estados iniciales
- B_π = matrices de transición bajo política π
- A = modelo de observación
- σ = softmax
```

### Aplicación en Medicina (Nature Digital Medicine, 2025)
- Active inference para prompting de LLMs en práctica médica
- Mejora fiabilidad de respuestas minimizando sorpresa clínica
- **URL**: https://www.nature.com/articles/s41746-025-01516-2

---

## 4. Titans: Memoria Dirigida por Sorpresa

### Paper
**"Titans: Learning to Memorize at Test Time"**
- Behrouz, Zhong & Mirrokni (Google Research)
- arXiv:2501.00663 (Diciembre 2024)

### Métrica de Sorpresa (Gradiente-Based)
```
Básica (Ecuación 8):
M_t = M_{t-1} - θ_t * ∇ℓ(M_{t-1}; x_t)

"Cuanto mayor el gradiente, más diferente es el input respecto a datos pasados"
```

### Sorpresa con Momentum (Ecuaciones 9-10)
```
M_t = M_{t-1} + S_t

S_t = η_t * S_{t-1} - θ_t * ∇ℓ(M_{t-1}; x_t)

Donde:
- η_t = decay de sorpresa dependiente de datos (coeficiente de sorpresa pasada)
- θ_t = peso de sorpresa momentánea
- S_t = señal de sorpresa combinada (momentum + actual)
```

### Principio Clave
> Solo almacenar lo **inesperado**. Si el modelo ya predice bien un input, no necesita memorizarlo.

---

## 5. Gated Surprise: Compresión de Eventos

### Paper
**"Fostering Event Compression using Gated Surprise"**
- arXiv:2005.05704

### Arquitectura Jerárquica
1. **Contextual LSTM**: Genera compresiones generativas de contextos
2. **Capa GRU**: Usa señales de sorpresa para actualizar estado latente
3. **Processing LSTM**: Integra contexto + sorpresa

### Mecanismo
La señal de sorpresa (alto error de predicción) actúa como **puerta** que segmenta el flujo continuo en "eventos" discretos — similar a cómo el cerebro divide experiencia continua en episodios.

---

## 6. Free Energy en Knowledge Graphs (Retrieval)

### Sorpresa Geométrica para Grafos
```
S_geo(e | C) = {
    min_{c ∈ C} d_G(c, e)    si existe camino
    α                         si no existe camino
}

Donde:
- d_G(c, e) = longitud del camino dirigido más corto (BFS)
- α = hiperparámetro de penalización por desconexión (> diámetro del grafo)
```

Combinada con complejidad algorítmica, la energía libre completa para retrieval:
```
F(e | C) = w_geo * S_geo(e | C) + w_alg * S_alg(e | C)
```

**Fuente**: arXiv:2011.14963 — "Free Energy Minimization: A Unified Framework"

---

## 7. Aplicación Directa al Proyecto ai-memory

### 7.1 Predictive Memory Gate (MÁXIMO IMPACTO)

```python
# ANTES (actual): toda query hace embedding search completo
async def search(query, project):
    embedding = await get_embedding(query)  # Costo: ~$0.0001 + 200ms
    results = await qdrant.search(embedding)  # Costo: ~50ms
    return results  # Siempre N resultados

# DESPUÉS (propuesto): predecir si necesitamos buscar
async def predictive_search(query, project, agent_context):
    # 1. Predecir qué memorias necesita el agente
    prediction = await predict_needed_memories(agent_context)
    
    # 2. Calcular sorpresa: ¿la query viola predicción?
    surprise = compute_surprise(query, prediction)
    
    if surprise < SURPRISE_THRESHOLD:
        # Query rutinaria — usar cache de predicción
        return prediction.cached_results
    else:
        # Query sorprendente — hacer búsqueda completa
        results = await full_search(query, project)
        # Actualizar modelo predictivo
        await update_prediction_model(query, results)
        return results
```

**Ahorro estimado**: 60-80% menos embedding calls en queries repetitivas

### 7.2 Surprise-Driven Memory Storage

```python
# Calcular novelty_score activamente (campo existe pero no se calcula)
async def compute_novelty(new_memory_content, project):
    # Buscar memorias similares existentes
    similar = await search_similar(new_memory_content, limit=5)
    
    if not similar:
        return 1.0  # Completamente novel
    
    max_similarity = max(m['semantic_score'] for m in similar)
    
    # Surprise = 1 - max_similarity
    # Solo almacenar si surprise > threshold
    novelty = 1.0 - max_similarity
    
    if novelty < NOVELTY_THRESHOLD:
        # Memoria redundante → fusionar con existente
        await merge_with_existing(similar[0], new_memory_content)
        return novelty
    else:
        # Memoria novel → almacenar normalmente
        return novelty
```

**Ahorro estimado**: 30-50% menos memorias almacenadas

### 7.3 Prediction Error como Señal de Aprendizaje

```python
# Cuando un agente accede una memoria y el resultado
# no coincide con lo esperado → trigger reconsolidación
async def on_memory_access(memory_id, actual_outcome):
    memory = await fetch_memory(memory_id)
    
    prediction_error = compute_pred_error(memory.content, actual_outcome)
    
    if prediction_error > HIGH_ERROR_THRESHOLD:
        # Alto error → memoria necesita actualización
        # Incrementar arousal (señal de importancia)
        await update_arousal(memory_id, min(1.0, memory.arousal + 0.3))
        # Añadir a contradiction_queue si contradice
        if prediction_error > CONTRADICTION_THRESHOLD:
            await queue_contradiction(memory_id, actual_outcome)
    
    elif prediction_error < LOW_ERROR_THRESHOLD:
        # Predicción correcta → reforzar memoria
        await reinforce_memory(memory_id)  # Dobla halflife
```

---

## 8. Métricas de Impacto

| Métrica | Actual | Con Predictive Coding | Mejora |
|---------|--------|----------------------|--------|
| Embedding calls/query | 1.0 | ~0.3 | 70% menos |
| Memorias almacenadas | 100% | ~60% | 40% menos redundancia |
| Tokens por retrieval | ~2000 | ~600 | 70% menos |
| Contradiction detection | Pasivo | Proactivo (pred. error) | Más temprano |
| False positives en search | ~15% | ~5% | 3x mejor precisión |

---

## 9. Referencias

1. Friston — "Predictive coding under the free-energy principle" — PMC:2666703
2. arXiv:2506.06332 (2025) — "Introduction to Predictive Coding Networks for ML"
3. arXiv:2510.23323 (2025) — "Towards Scaling Deep PCNs"
4. arXiv:2501.00663 (2024) — "Titans: Learning to Memorize at Test Time"
5. arXiv:2005.05704 — "Fostering Event Compression using Gated Surprise"
6. arXiv:2011.14963 — "Free Energy Minimization: A Unified Framework"
7. pymdp — https://github.com/infer-actively/pymdp
8. Nature Digital Medicine (2025) — Active inference for LLM prompting — https://www.nature.com/articles/s41746-025-01516-2
