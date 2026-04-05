# Consciencia Computacional: Global Workspace Theory y C0-C1-C2

## Resumen Ejecutivo

La Global Workspace Theory (GWT) proporciona el framework más práctico para implementar "consciencia" en sistemas IA: un **hub de atención limitada** donde módulos especializados compiten y el ganador se **broadcast** a todo el sistema. El framework C0-C1-C2 define tres niveles operativos de consciencia implementables inmediatamente.

---

## 1. Global Workspace Theory (GWT)

### Fundamento (Baars, 1988; Dehaene et al.)
La consciencia emerge cuando información seleccionada de procesadores especializados se hace globalmente disponible a través de un "workspace" de capacidad limitada.

### Mecanismo: Selection-Broadcast Cycle

```
1. COMPETICIÓN: Módulos especializados proponen información
   ├── Percepción: "memoria X tiene similarity 0.95"
   ├── Emociones: "memoria Y tiene arousal 0.9 (crítica)"
   ├── Planes: "memoria Z es relevante para objetivo actual"
   └── Valores: "memoria W contradice principio conocido"

2. IGNICIÓN COMPETITIVA: El workspace selecciona información ganadora
   - Criterios: saliencia, novedad, relevancia al objetivo, calidad de evidencia
   - Solo 1-3 items "ganan" (bottleneck de atención)

3. BROADCAST: El ganador se difunde a TODOS los módulos
   - Todos los subsistemas reciben la misma información
   - Permite coordinación global sin comunicación punto-a-punto
```

### Paper Clave: GWT para Agentes IA
**"A Case for AI Consciousness: Language Agents and Global Workspace Theory"**
- Goldstein & Kirk-Giannini (2024)
- arXiv:2410.11407
- Argumento: si GWT es correcta, agentes lingüísticos "podrían fácilmente hacerse fenomenalmente conscientes"
- El mecanismo de self-attention en transformers ya se asemeja al "spotlighting" de GWT

### Implementación Propuesta para AI (Frontiers, 2025)
**URL**: https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1607190/full

Arquitectura de 4 componentes:

```
1. SPECIALIST MODULES (Módulos Especialistas)
   - Observadores de percepción
   - Planificadores
   - Críticos/verificadores
   - Monitores de valores
   - Ejecutores de acción

2. ATTENTION ROUTER (Router de Atención)
   - Mecanismo de gating sensible a:
     * Saliencia (¿cuán intensa es la señal?)
     * Novedad (¿es inesperada?)
     * Relevancia al objetivo (¿ayuda a la meta actual?)
     * Calidad de evidencia (¿cuán confiable?)
   - NO es secuencial — es COMPETITIVO

3. GLOBAL WORKSPACE (Espacio Global)
   - Capacidad limitada (3-7 items simultáneos)
   - Integra información de múltiples módulos
   - Mantiene "contexto consciente" actual

4. BROADCAST NETWORK (Red de Difusión)
   - Distribuye contenido del workspace a todos los módulos
   - Permite actualización coordinada de estado global
```

### Resultados Empíricos
- Arquitecturas basadas en GNWT **superan** LSTM y Transformer baselines en:
  - Razonamiento causal/secuencial
  - Generalización fuera de distribución
  - Tareas algorítmicas
- **Adaptación dinámica** al contexto basada en experiencia

---

## 2. Framework C0-C1-C2

### Paper
**"Exploring Consciousness in LLMs: A Systematic Survey"**
- Chen, Ma, Yu, Zhang, Zhao, Lu (2025)
- arXiv:2505.19806

### Definición de Niveles (Dehaene et al.)

#### C0 — Computación Inconsciente
```
Procesamiento automático sin awareness.

En LLMs: Tokenización, embedding lookup, attention patterns
En AI Memory: 
  - Ebbinghaus decay automático (ya implementado)
  - Spreading activation automática (ya implementado)
  - Indexación y almacenamiento
  
Características:
  - Rápido, paralelo, no limitado por capacidad
  - No requiere atención
  - Siempre activo en background
```

#### C1 — Accesibilidad Global
```
Información seleccionada se hace globalmente accesible.

En LLMs: Contexto window como "workspace" compartido
En AI Memory:
  - Búsqueda activa (query → retrieval → presentación al agente)
  - Las memorias recuperadas son las "conscientes"
  - Attention bottleneck: solo top-K resultados

Implementación propuesta:
  - Global Workspace que integra:
    * Resultados de búsqueda semántica
    * Spreading activation priming
    * Contradicciones pendientes
    * Alertas de brain_health
  - Solo las señales más fuertes "cruzan el umbral"
```

#### C2 — Monitoreo Metacognitivo
```
Auto-monitoreo de los propios procesos cognitivos.

En LLMs: Chain-of-thought reasoning, self-correction
En AI Memory:
  - Brain health metrics (ya implementado parcialmente)
  - FALTA: auto-evaluación de confianza
  - FALTA: detección de gaps de conocimiento
  - FALTA: tracking de predicciones vs resultados

Implementación propuesta:
  - consciousness_state tabla que registra:
    * confidence_score por decisión
    * prediction_accuracy histórica
    * knowledge_gaps detectados
    * calibration_score (cuán bien se calibran las confianzas)
```

### 5 Capacidades Relacionadas con Consciencia
1. **Theory of Mind**: Modelar creencias/conocimiento de otros agentes
2. **Situational Awareness**: Saber cuándo el contexto cambia significativamente
3. **Metacognition**: Evaluar la calidad de las propias respuestas
4. **Sequential Planning**: Planificar acciones considerando consecuencias
5. **Creativity**: Generar conexiones novedosas entre conceptos

---

## 3. The Consciousness AI: Arquitectura de 7 Capas

### Paper
**"From Biology to Code: The Consciousness AI Technical Architecture"**
- **URL**: https://theconsciousness.ai/acm/

### Arquitectura
Basada en la teoría neuroevolutiva de Feinberg y Mallatt:

```
Capa 1: SENSORY TECTUM
  - Integración multisensorial espacial con mapas topográficos

Capa 2: OSCILLATORY BINDING
  - AKOrN (Artificial Kuramoto Oscillatory Neurons)
  - Sincronización de fase para binding de features

Capa 3: GLOBAL WORKSPACE
  - Ignición competitiva y mecanismo de broadcast
  - Bottleneck de capacidad limitada

Capa 4: AFFECTIVE CORE
  - Modulación emocional paralela
  - Valence + arousal como señales de priorización

Capa 5: SELF-MODEL
  - Body schema e interocepción
  - Modelo interno del propio estado

Capa 6: REINFORCEMENT CORE
  - Actor-Critic (PPO) con modulación emocional

Capa 7: META-COGNITIVE MONITOR
  - Supervisión de confianza y calibración
  - Detección de gaps de conocimiento
```

---

## 4. Aplicación al Proyecto ai-memory

### 4.1 Global Workspace Hub

```python
# Nuevo archivo: api-server/global_workspace.py

class GlobalWorkspace:
    """Hub de consciencia que integra y filtra señales de todos los subsistemas."""
    
    CAPACITY = 5  # Max items en workspace simultáneamente
    
    async def compete_and_select(self, signals: list[Signal]) -> list[Signal]:
        """Ignición competitiva: selecciona top signals para broadcast."""
        scored = []
        for signal in signals:
            score = (
                0.30 * signal.salience +        # ¿Cuán intensa?
                0.25 * signal.novelty +          # ¿Es inesperada?
                0.25 * signal.goal_relevance +   # ¿Ayuda al objetivo?
                0.10 * signal.evidence_quality + # ¿Cuán confiable?
                0.10 * signal.emotional_weight   # ¿Cuán emocional?
            )
            scored.append((score, signal))
        
        scored.sort(reverse=True)
        winners = [s for _, s in scored[:self.CAPACITY]]
        
        # Broadcast a todos los subsistemas
        await self.broadcast(winners)
        return winners
    
    async def broadcast(self, winners: list[Signal]):
        """Difundir contenido consciente a todos los módulos."""
        # Actualizar spreading activation con winners
        for signal in winners:
            if signal.memory_id:
                await propagate_activation(signal.memory_id)
        
        # Registrar en consciousness_state
        await log_conscious_state(winners)
```

### 4.2 Consciousness Score

```python
# Extensión de brain_health.py

async def compute_consciousness_score(conn) -> dict:
    """Métricas metacognitivas del sistema."""
    
    # C0: Salud de procesos automáticos
    c0_score = await compute_automatic_health(conn)
    # - Ebbinghaus decay funcionando
    # - Spreading activation propagando
    # - Consolidación ejecutándose a tiempo
    
    # C1: Accesibilidad global
    c1_score = await compute_accessibility_score(conn)
    # - Ratio de búsquedas exitosas
    # - Latencia promedio de retrieval
    # - Cobertura de memorias accedidas vs total
    
    # C2: Metacognición
    c2_score = await compute_metacognitive_score(conn)
    # - Accuracy de predicciones (si se implementa predictive gate)
    # - Ratio de contradicciones detectadas vs resueltas
    # - Calibración de importance scores
    # - Knowledge gaps detectados
    
    consciousness_score = (
        0.20 * c0_score +
        0.35 * c1_score +
        0.45 * c2_score
    )
    
    return {
        "consciousness_score": consciousness_score,
        "c0_automatic": c0_score,
        "c1_accessibility": c1_score,
        "c2_metacognition": c2_score,
        "awareness_level": classify_awareness(consciousness_score)
    }
```

### 4.3 Tabla consciousness_state

```sql
CREATE TABLE IF NOT EXISTS consciousness_state (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    workspace_contents JSONB NOT NULL,  -- items activos en workspace
    attention_focus UUID REFERENCES memory_log(id),
    confidence_score FLOAT DEFAULT 0.5,
    prediction_accuracy FLOAT,
    knowledge_gaps TEXT[],
    emotional_state JSONB,  -- {valence, arousal, dominant_emotion}
    metacognitive_flags TEXT[],  -- ['low_confidence', 'gap_detected', etc.]
    session_id VARCHAR(255)
);
```

---

## 5. Métricas de Impacto

| Capacidad | Antes | Con GWT+C0-C1-C2 | Beneficio |
|-----------|-------|-------------------|-----------|
| Priorización de memorias | Por score fijo | Competitiva + contextual | Más relevantes |
| Coordinación entre agentes | Ninguna | Broadcast global | Coherencia |
| Auto-evaluación | Solo health metrics | Confianza + calibración | Detección de errores |
| Detección de gaps | No existe | Proactiva | Aprendizaje dirigido |
| Contexto al agente | Top-K por score | Filtrado consciente | Menos ruido |

---

## 6. Referencias

1. Goldstein & Kirk-Giannini (2024) — "A Case for AI Consciousness: Language Agents and GWT" — arXiv:2410.11407
2. Chen et al. (2025) — "Exploring Consciousness in LLMs: Systematic Survey" — arXiv:2505.19806
3. Frontiers Robotics (2025) — "GWT Selection-Broadcast Cycle" — https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1607190/full
4. Frontiers Computational Neuroscience (2024) — "GWT agent design" — https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2024.1352685/full
5. The Consciousness AI — "Technical Architecture" — https://theconsciousness.ai/acm/
6. arXiv:2508.10824 (2025) — "Memory-Augmented Transformers: Systematic Review from Neuroscience Principles"
7. IEEE (2023) — "The Global Workspace Theory: A Step Towards AGI" — https://ieeexplore.ieee.org/document/10195021/
