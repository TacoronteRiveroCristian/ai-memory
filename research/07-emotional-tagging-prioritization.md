# Etiquetado Emocional y Priorización de Memorias

## Resumen Ejecutivo

El sistema amígdala-hipocampo del cerebro usa **valencia y arousal** como filtro de importancia natural: memorias emocionalmente cargadas se consolidan mejor y se recuerdan más rápido. El sistema ai-memory ya implementa valence/arousal pero los congela al momento de creación. Actualizar emociones dinámicamente y usar mood como modulador de consolidación puede mejorar significativamente la priorización.

---

## 1. Neurociencia del Etiquetado Emocional

### Dos Vías de Memoria Emocional
El cerebro procesa memorias emocionales por dos redes distintas:

```
1. AROUSING INFORMATION (alta excitación):
   Vía: Amígdala → Hipocampo
   - Memorias de errores críticos, crashes, breakthroughs
   - Norepinefrina (LC-NE) sesga atención hacia info de alta prioridad
   - Se consolidan preferentemente durante el sueño

2. VALENCED NON-AROUSING (valencia sin excitación):
   Vía: Corteza Prefrontal → Hipocampo
   - Preferencias, decisiones razonadas, aprendizajes graduales
   - Consolidación más lenta pero más estable
```

### Modelo Circumplejo del Afecto
```
        Alta Arousal
            |
   Enojado  |  Excitado
   Ansioso  |  Eufórico
            |
Neg --------+-------- Pos Valence
            |
   Triste   |  Calmado
   Aburrido |  Relajado
            |
        Baja Arousal

Cada memoria se ubica en este espacio 2D:
  valence ∈ [-1.0, +1.0]  (negativo → positivo)
  arousal ∈ [0.0, +1.0]   (calma → excitación)
```

### Paper Clave
**"Emotions in Artificial Intelligence"** (2025)
- arXiv:2505.01462
- Propone afecto teleológico: emociones como mecanismo adaptativo y dirigido a objetivos
- Aboga por modelado causal y meta-reinforcement learning

---

## 2. Estado Actual en ai-memory

### Implementado (server.py:484-493)
```python
# Inferencia de Valence
# Heurístico por keywords:
negative_keywords = [error, fail, bug, crash, fatal, timeout]  # -0.3 cada una
positive_keywords = [solution, success, fixed, deployed]         # +0.3 cada una
# Range: [-1.0, +1.0], default 0.0

# Inferencia de Arousal
# Base 0.4 + (high_urgency_count * 0.2) + (abs(valence) * 0.3)
high_urgency = [critical, fatal, emergency, crash, showstopper, breakthrough]
# Range: [0.0, +1.0], default 0.5
```

### Protecciones Emocionales
- Memorias con `arousal > 0.7` no decaen (server.py:1222)
- Proximidad emocional es 10% del cascade score (sensory_cortex.py:224)

### Limitaciones Críticas
1. **Congelamiento**: valence/arousal se calculan una vez en creación y nunca se actualizan
2. **Keywords hardcoded**: lista fija, no aprendible
3. **Sin intensidad**: todas las keywords tienen peso igual
4. **Sin contexto de dominio**: "critical error" vs "critical discovery" tratados igual
5. **Sin evolución temporal**: no hay tracking de mood histórico
6. **Arousal no decae**: una vez alto, siempre alto

---

## 3. Mejoras Propuestas

### 3.1 Evolución Emocional Dinámica

```python
async def update_emotional_state(memory_id: str, access_context: dict):
    """Actualizar valence/arousal en cada acceso basándose en contexto."""
    memory = await fetch_memory(memory_id)
    
    # Contexto emocional del acceso actual
    context_valence = infer_valence(access_context.get('content', ''))
    context_arousal = infer_arousal(access_context.get('content', ''))
    
    # Exponential moving average (EMA)
    # Peso 0.3 para nuevo contexto, 0.7 para valor existente
    EMOTIONAL_LEARNING_RATE = 0.3
    new_valence = (
        (1 - EMOTIONAL_LEARNING_RATE) * memory.valence +
        EMOTIONAL_LEARNING_RATE * context_valence
    )
    new_arousal = (
        (1 - EMOTIONAL_LEARNING_RATE) * memory.arousal +
        EMOTIONAL_LEARNING_RATE * context_arousal
    )
    
    # Arousal decae naturalmente con el tiempo (habituación)
    days_since_creation = (now() - memory.created_at).days
    habituation_factor = max(0.3, 1.0 - 0.02 * days_since_creation)
    new_arousal *= habituation_factor
    
    await conn.execute("""
        UPDATE memory_log
        SET valence = $2, arousal = $3
        WHERE id = $1
    """, memory_id, clamp(new_valence, -1, 1), clamp(new_arousal, 0, 1))
```

### 3.2 Sistema de Mood (Estado Emocional Global)

```python
async def compute_project_mood(project: str) -> dict:
    """Estado emocional global del proyecto basado en memorias recientes."""
    recent = await conn.fetch("""
        SELECT valence, arousal, importance, created_at
        FROM memory_log m
        JOIN projects p ON p.id = m.project_id
        WHERE p.name = $1
          AND m.created_at > NOW() - INTERVAL '24 hours'
        ORDER BY created_at DESC
        LIMIT 20
    """, project)
    
    if not recent:
        return {"mood_valence": 0.0, "mood_arousal": 0.4, "mood_label": "neutral"}
    
    # Weighted average: memorias más recientes pesan más
    total_weight = 0
    weighted_valence = 0
    weighted_arousal = 0
    for i, row in enumerate(recent):
        weight = 1.0 / (1.0 + i * 0.1)  # Decay por posición
        weight *= float(row['importance'])  # Peso por importancia
        weighted_valence += float(row['valence']) * weight
        weighted_arousal += float(row['arousal']) * weight
        total_weight += weight
    
    mood_v = weighted_valence / total_weight
    mood_a = weighted_arousal / total_weight
    
    # Clasificar mood
    if mood_a > 0.7:
        label = "alert" if mood_v > 0 else "stressed"
    elif mood_a > 0.4:
        label = "engaged" if mood_v > 0 else "concerned"
    else:
        label = "calm" if mood_v > 0 else "fatigued"
    
    return {
        "mood_valence": round(mood_v, 3),
        "mood_arousal": round(mood_a, 3),
        "mood_label": label
    }
```

### 3.3 Mood-Dependent Consolidation

```python
async def modulate_consolidation_by_mood(project: str):
    """El mood modula la agresividad de consolidación."""
    mood = await compute_project_mood(project)
    
    if mood['mood_label'] == 'stressed':
        # Alto estrés → consolidar errores más agresivamente
        # Priorizar memorias negativas con alto arousal
        await consolidate_with_priority(project, 
            filter="arousal > 0.7 AND valence < -0.3",
            aggressiveness=1.5  # 50% más schemas de errores
        )
    
    elif mood['mood_label'] == 'calm':
        # Calma → consolidación equilibrada, explorar conexiones
        await consolidate_with_priority(project,
            filter=None,  # Todo tipo de memorias
            aggressiveness=1.0  # Normal
        )
    
    elif mood['mood_label'] == 'engaged':
        # Engaged → priorizar patrones y soluciones
        await consolidate_with_priority(project,
            filter="valence > 0.2",
            aggressiveness=1.2  # 20% más schemas de éxitos
        )
```

### 3.4 Emotional Proximity Mejorada

```python
# Actual (sensory_cortex.py): distancia Euclidiana simple
# Propuesto: modelo circular del afecto

def emotional_proximity_circular(mem_a: dict, mem_b: dict) -> float:
    """Proximidad emocional usando modelo circular del afecto."""
    # Convertir valence/arousal a coordenadas polares
    angle_a = math.atan2(mem_a['arousal'] - 0.5, mem_a['valence'])
    angle_b = math.atan2(mem_b['arousal'] - 0.5, mem_b['valence'])
    
    # Distancia angular (0 = misma emoción, π = opuesta)
    angular_dist = abs(angle_a - angle_b)
    if angular_dist > math.pi:
        angular_dist = 2 * math.pi - angular_dist
    
    # Intensidad: distancia al centro (neutro)
    intensity_a = math.sqrt(mem_a['valence']**2 + (mem_a['arousal'] - 0.5)**2)
    intensity_b = math.sqrt(mem_b['valence']**2 + (mem_b['arousal'] - 0.5)**2)
    
    # Proximidad: alta si misma emoción y similar intensidad
    angle_proximity = 1.0 - angular_dist / math.pi
    intensity_proximity = 1.0 - abs(intensity_a - intensity_b)
    
    return 0.7 * angle_proximity + 0.3 * intensity_proximity
```

---

## 4. Tabla de Datos Propuesta

```sql
-- Historial de evolución emocional
CREATE TABLE IF NOT EXISTS emotional_history (
    id SERIAL PRIMARY KEY,
    memory_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
    valence_before FLOAT,
    valence_after FLOAT,
    arousal_before FLOAT,
    arousal_after FLOAT,
    trigger_context TEXT,  -- qué causó el cambio
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Mood global por proyecto
CREATE TABLE IF NOT EXISTS project_mood (
    id SERIAL PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    mood_valence FLOAT DEFAULT 0.0,
    mood_arousal FLOAT DEFAULT 0.4,
    mood_label VARCHAR(20) DEFAULT 'neutral',
    sample_size INT,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. Métricas de Impacto

| Aspecto | Actual | Propuesto | Beneficio |
|---------|--------|-----------|-----------|
| Actualización emocional | Nunca (frozen) | En cada acceso | Emociones precisas |
| Arousal decay | No (siempre alto) | Habituación temporal | Menos falsos críticos |
| Mood global | No existe | Por proyecto/24h | Consolidación adaptativa |
| Proximidad emocional | Euclidiana | Circular (ángulo+intensidad) | Relaciones más precisas |
| Consolidación por mood | Uniforme | Adaptativa | Priorización inteligente |

---

## 6. Referencias

1. arXiv:2505.01462 (2025) — "Emotions in Artificial Intelligence"
2. PMC:12349093 — "Multimodal Sensing-Enabled LLMs for Automated Emotional Regulation"
3. ACL (2025) — "Exploring Emotional Expressions in Large Language Models"
4. Neuroscience — Sistema LC-NE (locus coeruleus-norepinefrina) en priorización
5. Modelo circumplejo del afecto — Russell (1980), Posner et al. (2005)
