# Curiosidad, Theory of Mind y Autonomía Cognitiva

## Resumen Ejecutivo

Dos capacidades cognitivas clave faltan completamente en ai-memory: **curiosidad** (detección proactiva de gaps de conocimiento) y **Theory of Mind** (modelar lo que otros agentes saben/creen). Implementarlas permite al sistema buscar activamente información faltante y coordinar mejor entre múltiples agentes.

---

## 1. Curiosidad: Exploración Dirigida por Información

### Fundamento Neurobiológico
La curiosidad es un **drive intrínseco** que motiva la exploración cuando se detecta un gap entre lo que se sabe y lo que se podría saber. El sistema dopaminérgico recompensa la adquisición de información nueva.

### Modelos Computacionales

#### ICM (Intrinsic Curiosity Module)
```
Curiosity = prediction_error entre:
  - Estado predicho por forward model: ŝ_{t+1} = f(s_t, a_t)
  - Estado real observado: s_{t+1}

reward_intrinsic = ||ŝ_{t+1} - φ(s_{t+1})||²

Donde φ() es un feature extractor entrenado para ignorar
aspectos del entorno que son impredecibles pero irrelevantes
(ruido estocástico).
```

#### RND (Random Network Distillation)
```
Curiosity = discrepancia entre:
  - Red target aleatoria fija: f_target(s)
  - Red predictor entrenada: f_predict(s)

reward_intrinsic = ||f_target(s) - f_predict(s)||²

Intuición: estados visitados frecuentemente → predictor aprende
bien → baja curiosidad. Estados nuevos → predictor malo → alta
curiosidad.
```

### Paper de Capacidades Faltantes
Un paper identificó **7 deficiencias fundamentales** que previenen autonomía en IA:

```
EVALUACIÓN INTERNA:
1. Self-monitoring (evaluación de confianza, detección de errores)
2. Meta-cognitive awareness (tracking de límites de conocimiento)
3. Representation repair (reconsolidación de memorias)

CONTROL ADAPTATIVO:
4. Adaptive learning rules (plasticidad contextual)
5. Goal restructuring (ajuste dinámico de prioridades)

AUTONOMÍA EMBODIED:
6. Embodied feedback (retroalimentación sensorial)
7. Environmental probing (exploración activa)
```

---

## 2. Theory of Mind para Sistemas Multi-Agente

### Paper Clave
**"Theory of Mind in Multi-Agent Systems"**
- Ini Oguntola, CMU-ML-25-118 (Septiembre 2025)
- PhD dissertation, Carnegie Mellon University

### Paper de Implementación
**"Theory of Mind Using Active Inference: Framework for Multi-Agent Cooperation"**
- arXiv:2508.00401 (2025)

### Arquitectura de Belief Tracking

```
Cada agente mantiene modelos de:

1. PROPIO CONOCIMIENTO:
   K_self = {memorias que yo tengo}

2. MODELO DE OTROS AGENTES:
   K_agent_j = {lo que creo que agente j sabe}
   
   Actualizado por:
   - Comunicación directa: si j dice X, K_j += X
   - Inferencia: si j actuó de modo Y, probablemente sabe Z
   - Tiempo: información vieja de j puede estar desactualizada

3. CONOCIMIENTO COMPARTIDO:
   K_shared = K_self ∩ K_agent_j ∩ ...
   
4. GAPS DETECTADOS:
   gaps_j = K_self - K_agent_j  (lo que yo sé pero j no)
   needs_j = K_agent_j - K_self  (lo que j sabe pero yo no)
```

### Implementación en LLM Agents (GPT-3.5/4)
```
Cada agente tiene:
- Observación parcial del entorno
- Historial de interacciones propio
- Comunicación inter-agente como único medio de difusión

"A textual description storing key task-related beliefs"
sobre contenido de habitaciones, secuencias, estado del mundo.

Resultado: mejora coordinación en tareas cooperativas descentralizadas
```

---

## 3. Aplicación al Proyecto ai-memory

### 3.1 Curiosity Engine (Detección de Gaps)

```python
# Nuevo módulo: api-server/curiosity_engine.py

class CuriosityEngine:
    """Detecta gaps de conocimiento y genera preguntas proactivas."""
    
    async def detect_knowledge_gaps(self, project: str) -> list[dict]:
        """Analiza memorias para encontrar gaps de conocimiento."""
        gaps = []
        
        # Gap Tipo 1: Preguntas sin respuesta en sessions
        unanswered = await conn.fetch("""
            SELECT DISTINCT s.payload_json->>'summary' AS summary
            FROM session_summaries s
            JOIN projects p ON p.id = s.project_id
            WHERE p.name = $1
              AND s.payload_json->>'follow_ups' IS NOT NULL
              AND s.payload_json->>'follow_ups' != '[]'
              AND NOT EXISTS (
                  SELECT 1 FROM memory_log m
                  WHERE m.project_id = s.project_id
                    AND m.action_type = 'decision'
                    AND m.created_at > s.created_at
                    AND similarity(m.summary, s.payload_json->>'summary') > 0.5
              )
            ORDER BY s.created_at DESC
            LIMIT 10
        """, project)
        
        for row in unanswered:
            gaps.append({
                "type": "unanswered_question",
                "description": row['summary'],
                "urgency": "moderate"
            })
        
        # Gap Tipo 2: Memorias huérfanas (sin relaciones)
        orphans = await conn.fetch("""
            SELECT m.id, m.summary, m.importance
            FROM memory_log m
            JOIN projects p ON p.id = m.project_id
            WHERE p.name = $1
              AND m.importance > 0.6
              AND NOT EXISTS (
                  SELECT 1 FROM memory_relations mr
                  WHERE (mr.source_memory_id = m.id OR mr.target_memory_id = m.id)
                    AND mr.active = TRUE
              )
            ORDER BY m.importance DESC
            LIMIT 10
        """, project)
        
        for row in orphans:
            gaps.append({
                "type": "isolated_important_memory",
                "memory_id": str(row['id']),
                "description": f"Importante pero sin conexiones: {row['summary'][:100]}",
                "urgency": "high" if float(row['importance']) > 0.8 else "moderate"
            })
        
        # Gap Tipo 3: Dominios con baja cobertura
        domain_coverage = await conn.fetch("""
            SELECT unnest(tags) AS tag, COUNT(*) AS cnt
            FROM memory_log m
            JOIN projects p ON p.id = m.project_id
            WHERE p.name = $1
            GROUP BY tag
            HAVING COUNT(*) < 3
            ORDER BY cnt ASC
            LIMIT 10
        """, project)
        
        for row in domain_coverage:
            gaps.append({
                "type": "low_coverage_domain",
                "domain": row['tag'],
                "memory_count": row['cnt'],
                "urgency": "low"
            })
        
        return gaps
    
    async def compute_curiosity_score(self, project: str) -> float:
        """Score de curiosidad: cuánto debería el sistema buscar info nueva."""
        gaps = await self.detect_knowledge_gaps(project)
        
        high_urgency = sum(1 for g in gaps if g['urgency'] == 'high')
        moderate = sum(1 for g in gaps if g['urgency'] == 'moderate')
        low = sum(1 for g in gaps if g['urgency'] == 'low')
        
        score = min(1.0, (high_urgency * 0.3 + moderate * 0.1 + low * 0.05))
        return round(score, 3)
```

### 3.2 Agent Belief Model (Theory of Mind)

```python
# Extensión para tracking de creencias por agente

class AgentBeliefModel:
    """Modela lo que cada agente sabe/cree."""
    
    async def get_agent_knowledge(self, agent_id: str, project: str) -> dict:
        """Qué memorias ha accedido/creado este agente."""
        created = await conn.fetch("""
            SELECT id, summary, action_type
            FROM memory_log m
            JOIN projects p ON p.id = m.project_id
            WHERE m.agent_id = $1 AND p.name = $2
        """, agent_id, project)
        
        accessed = await conn.fetch("""
            -- Memorias que este agente ha accedido (via session logs)
            SELECT DISTINCT m.id, m.summary
            FROM memory_log m
            JOIN session_summaries ss ON ss.agent_id = $1
            WHERE m.project_id = ss.project_id
        """, agent_id)
        
        return {
            "agent_id": agent_id,
            "created_count": len(created),
            "accessed_count": len(accessed),
            "knowledge_domains": list(set(r['action_type'] for r in created)),
        }
    
    async def compute_knowledge_gap(self, agent_a: str, agent_b: str, project: str) -> dict:
        """Qué sabe A que B no sabe, y viceversa."""
        ka = set(r['id'] for r in await self.get_memories(agent_a, project))
        kb = set(r['id'] for r in await self.get_memories(agent_b, project))
        
        return {
            "a_knows_b_doesnt": list(ka - kb),
            "b_knows_a_doesnt": list(kb - ka),
            "shared_knowledge": list(ka & kb),
            "gap_ratio": len(ka.symmetric_difference(kb)) / max(len(ka | kb), 1)
        }
    
    async def recommend_sharing(self, project: str) -> list[dict]:
        """Recomendar memorias que deberían compartirse entre agentes."""
        agents = await get_active_agents(project)
        recommendations = []
        
        for i, a in enumerate(agents):
            for b in agents[i+1:]:
                gap = await self.compute_knowledge_gap(a, b, project)
                if gap['gap_ratio'] > 0.3:  # >30% no compartido
                    recommendations.append({
                        "agents": [a, b],
                        "gap_ratio": gap['gap_ratio'],
                        "suggestion": f"Agent {a} tiene {len(gap['a_knows_b_doesnt'])} memorias que {b} no conoce"
                    })
        
        return recommendations
```

### 3.3 Tablas de Datos

```sql
-- Knowledge gaps detectados
CREATE TABLE IF NOT EXISTS knowledge_gaps (
    id SERIAL PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    gap_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    urgency VARCHAR(20) DEFAULT 'moderate',
    resolved BOOLEAN DEFAULT FALSE,
    resolved_by_memory_id UUID REFERENCES memory_log(id),
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- Modelo de creencias por agente
CREATE TABLE IF NOT EXISTS agent_beliefs (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(100) NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    knowledge_summary JSONB,  -- Resumen del conocimiento del agente
    last_active_at TIMESTAMPTZ,
    reliability_score FLOAT DEFAULT 0.5,  -- Cuán confiables son sus contribuciones
    total_contributions INT DEFAULT 0,
    contradictions_caused INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT agent_beliefs_unique UNIQUE (agent_id, project_id)
);
```

### 3.4 API Endpoints

```python
@app.get("/api/brain/curiosity/{project}")
async def get_curiosity_report(project: str):
    """Retorna gaps de conocimiento y score de curiosidad."""
    engine = CuriosityEngine()
    gaps = await engine.detect_knowledge_gaps(project)
    score = await engine.compute_curiosity_score(project)
    
    return {
        "project": project,
        "curiosity_score": score,
        "gaps": gaps,
        "recommendation": "explore" if score > 0.5 else "consolidate"
    }

@app.get("/api/brain/agents/{project}")
async def get_agent_knowledge_map(project: str):
    """Mapa de conocimiento por agente y recomendaciones de sharing."""
    model = AgentBeliefModel()
    recommendations = await model.recommend_sharing(project)
    
    return {
        "project": project,
        "sharing_recommendations": recommendations
    }
```

---

## 4. Métricas de Impacto

| Capacidad | Antes | Con Curiosity+ToM | Beneficio |
|-----------|-------|-------------------|-----------|
| Gap detection | No existe | Proactivo (3 tipos) | Aprendizaje dirigido |
| Agent coordination | Aislado | Knowledge-aware | Menos duplicación |
| Knowledge sharing | Manual | Recomendado automáticamente | Eficiencia multi-agente |
| Proactive learning | Pasivo | Curiosity-driven | Cobertura completa |
| Agent reliability | No tracked | Per-agent scoring | Calidad de datos |

---

## 5. Referencias

1. Oguntola (2025) — "Theory of Mind in Multi-Agent Systems" — CMU-ML-25-118
2. arXiv:2508.00401 (2025) — "Theory of Mind Using Active Inference for Multi-Agent Cooperation"
3. Pathak et al. — "Curiosity-driven Exploration by Self-Supervised Prediction" (ICM)
4. Burda et al. — "Exploration by Random Network Distillation" (RND)
5. Wikipedia — "Intrinsic Motivation (AI)" — https://en.wikipedia.org/wiki/Intrinsic_motivation_(artificial_intelligence)
6. ScienceDirect (2025) — "Curiosity-driven exploration based on hierarchical vision transformer"
