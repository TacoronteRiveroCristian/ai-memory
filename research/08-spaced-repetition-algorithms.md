# Algoritmos de Repetición Espaciada para Memoria de IA

## Resumen Ejecutivo

La repetición espaciada (SM-2, FSRS) es el método más eficiente conocido para retener información a largo plazo. El proyecto ai-memory ya tiene `stability_halflife_days` que se dobla con cada acceso, pero carece de **scheduling proactivo** — no sabe cuándo una memoria necesita ser revisada. Implementar scheduling tipo Anki/FSRS puede reducir memoria perdida y mejorar disponibilidad.

---

## 1. Algoritmo SM-2 (SuperMemo)

### Fórmulas Core

#### Factor de Facilidad (EF)
```
EF' = EF + (0.1 - (5 - q) × (0.08 + (5 - q) × 0.02))
EF' = max(1.3, EF')

q = quality score (0-5):
  0 = Blackout completo, sin recuerdo
  1 = Respuesta incorrecta, respuesta correcta recordada
  2 = Respuesta incorrecta, respuesta correcta parecía fácil
  3 = Respuesta correcta con dificultad seria
  4 = Respuesta correcta tras hesitación
  5 = Respuesta perfecta sin hesitación
```

#### Cálculo de Intervalo I(n)
```
Si q < 3: I(1) = 1, repetition_count = 0  (reset)
Si q >= 3:
  I(1) = 1 día
  I(2) = 6 días
  I(n) = I(n-1) × EF  para n > 2

Ejemplo con EF = 2.5:
  Review 1: 1 día
  Review 2: 6 días
  Review 3: 15 días
  Review 4: 37 días
  Review 5: 93 días
```

---

## 2. FSRS (Free Spaced Repetition Scheduler)

### Paper & Implementación
- **GitHub**: https://github.com/open-spaced-repetition/free-spaced-repetition-scheduler
- Sucesor moderno de SM-2, usado en Anki 23.10+
- Basado en modelo DSR (Difficulty, Stability, Retrievability)

### Modelo de Tres Componentes

#### Stability (S) — Resistencia al Olvido
```
Estabilidad inicial (primera review):
S_0 = parameters[rating - 1]
  rating ∈ {1=Again, 2=Hard, 3=Good, 4=Easy}

Estabilidad después de review exitosa:
S' = S × (1 + e^(w8) × (11 - D) × S^(-w9) × (e^(w10 × (1-R)) - 1))

Donde:
  D = difficulty
  R = retrievability al momento de review
  w8, w9, w10 = parámetros entrenados
```

#### Difficulty (D) — Dificultad Intrínseca
```
Dificultad inicial:
D_0 = w4 - e^(w5 × (rating - 1)) + 1

Actualización:
D' = w6 × D_0(3) + (1 - w6) × (D - w7 × (rating - 3))

Donde:
  w4-w7 = parámetros entrenados
  D_0(3) = dificultad de referencia para rating "Good"
  Clamped a [1, 10]
```

#### Retrievability (R) — Probabilidad de Recuerdo
```
R(t) = (1 + t/S)^(-1)

t = días desde última review
S = stability actual

Cuando R cae a desired_retention (default 0.9):
  t_threshold = S × (1/desired_retention - 1)
  → Este es el momento de programar la próxima review
```

### Ventajas sobre SM-2
| Aspecto | SM-2 | FSRS |
|---------|------|------|
| Parámetros | 1 (EF) | 19 (w0-w18, entrenables) |
| Personalización | Manual | Automática (ML) |
| Predicción | Heurística | Basada en modelo |
| Accuracy | ~75% | ~85% retention prediction |

---

## 3. Curvas de Olvido Humanas en DNNs

### Paper
**"Human-like Forgetting Curves in Deep Neural Networks"**
- Dylan Kline (University of Rochester, 2025)
- arXiv:2506.12034

### Hallazgo Clave
> MLPs muestran curvas de retención análogas a las humanas:
> La retención "empieza en 0.29 y cae rápidamente a 0.20, después de lo cual
> la tasa de declive se desacelera."

**Validación directa** del modelo Ebbinghaus implementado en ai-memory:
- El conocimiento se vuelve progresivamente más robusto con reviews programadas
- El patrón de decay coincide con la fórmula exponencial del sistema

### YourMemory: Implementación Práctica
```
Score = cosine_similarity × Ebbinghaus_strength

strength = importance × e^(-λ_eff × days) × (1 + recall_count × 0.2)

λ_eff = 0.16 × (1 - importance × 0.8)

Interpretación:
- Memorias importantes decaen más lento (λ_eff menor)
- Cada recall suma 20% de fuerza
- importance modula el decay rate
```

**Fuente**: DEV Community — "I built memory decay for AI agents using the Ebbinghaus forgetting curve"

---

## 4. Aplicación al Proyecto ai-memory

### 4.1 Estado Actual
```python
# server.py:1382-1422 (register_memory_access)
# review_count se incrementa en cada acceso
# stability_halflife_days se dobla (capped at 512)
# stability_score aumenta, capped at 1.0

# PROBLEMA: No hay scheduling proactivo
# El sistema no sabe CUÁNDO una memoria necesita refuerzo
# Las memorias simplemente decaen pasivamente
```

### 4.2 Spaced Repetition Scheduler para AI

```python
# Nuevo: calcular next_review_at para cada memoria

def compute_next_review(memory) -> datetime:
    """Calcula cuándo esta memoria debe ser revisada/reforzada."""
    S = memory.stability_halflife_days  # Stability
    R_target = 0.85  # Desired retention (85%)
    
    # Fórmula FSRS para intervalo óptimo
    # t = S × (1/R_target - 1)
    interval_days = S * (1.0 / R_target - 1.0)
    
    # Ajustar por importancia
    importance_factor = 0.5 + memory.importance  # [0.5, 1.5]
    interval_days *= importance_factor
    
    # Ajustar por arousal (memorias críticas se revisan más frecuentemente)
    if memory.arousal > 0.7:
        interval_days *= 0.7  # 30% más frecuente
    
    next_review = memory.last_accessed_at + timedelta(days=interval_days)
    return next_review

# API endpoint: memorias que necesitan revisión
@app.get("/api/memories/due-for-review")
async def get_due_memories(project: str, limit: int = 10):
    """Retorna memorias que están por debajo del threshold de retención."""
    now = now_utc()
    
    rows = await conn.fetch("""
        SELECT id, summary, stability_halflife_days, 
               stability_score, importance, last_accessed_at,
               -- Retrievability estimate
               POWER(
                   1 + EXTRACT(EPOCH FROM ($2 - COALESCE(last_accessed_at, created_at))) 
                       / 86400.0 / GREATEST(stability_halflife_days, 0.1),
                   -1
               ) AS retrievability
        FROM memory_log m
        JOIN projects p ON p.id = m.project_id
        WHERE p.name = $1
          AND manual_pin = FALSE
          AND stability_score > 0.1
        ORDER BY retrievability ASC  -- Más urgentes primero
        LIMIT $3
    """, project, now, limit)
    
    return [{
        "id": str(row['id']),
        "summary": row['summary'],
        "retrievability": round(float(row['retrievability']), 3),
        "needs_review": float(row['retrievability']) < 0.85,
        "urgency": "critical" if float(row['retrievability']) < 0.5 else
                   "high" if float(row['retrievability']) < 0.7 else
                   "moderate" if float(row['retrievability']) < 0.85 else "ok"
    } for row in rows]
```

### 4.3 Quality Score para Memoria de IA

```python
# Adaptar q (quality 0-5) de SM-2 para contexto de agentes IA

def compute_memory_quality(memory, access_context) -> int:
    """Determina la calidad del recall de esta memoria."""
    
    # q=5: La memoria fue exactamente lo que el agente necesitaba
    # q=4: Útil pero requirió algo de procesamiento adicional
    # q=3: Parcialmente útil, necesitó complementarse
    # q=2: Encontrada pero no útil en este contexto
    # q=1: Confusa o desactualizada
    # q=0: Completamente irrelevante o contradictoria
    
    if access_context.get('outcome') == 'perfect_match':
        return 5
    elif access_context.get('outcome') == 'helpful':
        return 4
    elif access_context.get('outcome') == 'partial':
        return 3
    elif access_context.get('outcome') == 'used_but_outdated':
        return 2
    elif access_context.get('outcome') == 'irrelevant':
        return 1
    else:
        return 3  # Default: asumir parcialmente útil
```

### 4.4 Esquema de Datos

```sql
-- Añadir columnas a memory_log
ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS
    next_review_at TIMESTAMPTZ;
ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS
    retrievability FLOAT DEFAULT 1.0;
ALTER TABLE memory_log ADD COLUMN IF NOT EXISTS
    difficulty FLOAT DEFAULT 5.0;  -- [1-10], FSRS difficulty

-- Índice para queries de due-for-review
CREATE INDEX IF NOT EXISTS idx_memory_next_review
    ON memory_log (next_review_at)
    WHERE manual_pin = FALSE AND stability_score > 0.1;
```

---

## 5. Métricas de Impacto

| Aspecto | Actual | Con Spaced Repetition | Beneficio |
|---------|--------|----------------------|-----------|
| Scheduling | Ninguno (pasivo) | Proactivo (next_review_at) | Previene pérdida |
| Decay model | Exponencial simple | FSRS con difficulty | Más preciso |
| Retrieval prediction | No existe | Retrievability R(t) | Saber qué se olvida |
| Refuerzo | Solo por acceso casual | Programado + casual | Retención ~85% |
| Quality feedback | No existe | q-score por acceso | Adapta difficulty |

---

## 6. Referencias

1. SM-2 Algorithm — https://github.com/thyagoluciano/sm2
2. FSRS — https://github.com/open-spaced-repetition/free-spaced-repetition-scheduler
3. arXiv:2506.12034 (2025) — "Human-like Forgetting Curves in Deep Neural Networks"
4. DEV Community — "I built memory decay for AI agents using Ebbinghaus forgetting curve"
5. arXiv:2508.03275 — "LECTOR: LLM-Enhanced Spaced Repetition"
6. Tegaru — "SM-2 Algorithm Explained" — https://tegaru.app/en/blog/sm2-algorithm-explained
