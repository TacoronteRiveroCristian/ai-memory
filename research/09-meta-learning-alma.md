# ALMA: Meta-Aprendizaje de Diseños de Memoria para IA

## Resumen Ejecutivo

ALMA (2026) demuestra que los diseños de memoria para agentes IA pueden ser **descubiertos automáticamente** en vez de diseñados manualmente. Un Meta Agent busca sobre diseños expresados como código Python ejecutable, descubriendo arquitecturas que **superan consistentemente TODOS los baselines humanos** en 4 dominios. Implicación clave: la arquitectura de ai-memory debería evolucionar adaptativamente.

---

## 1. Paper y Contexto

### Referencia
**"Learning to Continually Learn via Meta-learning Agentic Memory Designs"**
- Yiming Xiong, Zhiqiang Hu, Jeff Clune
- arXiv:2602.07755 (Febrero 2026)
- **GitHub**: https://github.com/zksha/alma
- **Web**: https://yimingxiong.me/alma

### Motivación
> Los LLMs son sin estado por diseño. Los diseños de memoria humanos para agentes
> son subóptimos porque el espacio de diseño es demasiado grande para explorar manualmente.

---

## 2. Arquitectura del Framework

### Representación de Memoria: M = (U, D, R)
```
U = Update mechanism (cómo almacenar experiencias)
D = Database (estructura de almacenamiento)
R = Retrieval mechanism (cómo acceder al conocimiento)

Interfaces principales:
  general_update() → procesamiento secuencial de nuevas interacciones
  general_retrieve() → acceso a experiencia relevante
```

### Meta-Learning Loop (4 pasos iterativos)

```
CICLO:
┌─────────────────────────────────────────────────────┐
│ 1. SAMPLING                                          │
│    - Seleccionar hasta 5 diseños previos del archivo │
│    - Sin reemplazo (diversidad)                      │
│                                                      │
│ 2. REFLECTION & PLANNING                             │
│    - Meta Agent analiza logs de rendimiento           │
│    - Propone mejoras específicas                      │
│    - Identifica patrones de éxito/fracaso             │
│                                                      │
│ 3. IMPLEMENTATION                                    │
│    - Nuevo diseño codificado en Python               │
│    - Hasta 3 ciclos de debugging si hay errores      │
│    - Incluye DB schema + update + retrieval logic    │
│                                                      │
│ 4. EVALUATION & STORAGE                              │
│    - Test en entornos específicos del dominio        │
│    - Resultados + código → archivo (para futuros)    │
│    - Mejores diseños sirven de seed para iteración   │
└─────────────────────────────────────────────────────┘
```

### Estructura del Código
```
alma/
├── core/           # Módulos de implementación principal
├── envs_archive/   # Configuraciones por dominio
├── envs_docker/    # Entornos containerizados (ALFWorld, BALROG)
├── evals/          # Frameworks de evaluación
└── memo_archive/
    └── baseline/   # Almacenamiento de diseños de memoria
```

---

## 3. Diseños Descubiertos

### Hallazgo Principal
Los diseños descubiertos por ALMA **superan TODOS los baselines humanos** (MemGPT, Mem0, RAG estándar, etc.) en 4 dominios de toma de decisiones secuencial.

### Patrones Emergentes por Dominio

#### Tareas de Juego (ALFWorld)
```
Diseño descubierto: Relaciones espaciales de grano fino
- Almacena posiciones relativas de objetos
- Schema: "objeto X está en/sobre/dentro de Y"
- Retrieval: búsqueda por relación espacial + tipo de objeto
- Resultado: supera MemGPT en navegación espacial
```

#### Tareas de Razonamiento
```
Diseño descubierto: Estrategias abstractas por dominio
- No almacena hechos individuales → almacena REGLAS
- Schema: "cuando se ve patrón X, aplicar estrategia Y"
- Retrieval: matching de patrones + confianza
- Resultado: generalización superior a nuevos problemas
```

### Insight Clave
> El diseño óptimo de memoria depende del DOMINIO.
> No existe un "one-size-fits-all" — la memoria debe adaptarse
> al tipo de tarea que el agente realiza.

---

## 4. Implicaciones para ai-memory

### 4.1 Diseño Actual vs Descubrimiento Automático

```
ai-memory usa diseño fijo humano:
- 7 señales con pesos fijos (40% semantic, 20% domain, ...)
- Tiers de cascade fijos (0.92, 0.75, 0.55)
- Decay con halflife fijo (dobla con cada acceso)
- Relación tipos fijos (same_concept, extends, supports, ...)

ALMA sugiere:
- Los pesos deberían ser aprendidos del uso real
- Los thresholds deberían adaptarse por proyecto
- El decay rate debería ser específico al dominio
- Nuevos tipos de relación deberían emerger del uso
```

### 4.2 Propuesta: Mini-ALMA para ai-memory

```python
# Concepto: auto-optimizar parámetros del sistema basándose en feedback

class MemoryDesignOptimizer:
    """Mini-ALMA: optimiza parámetros de memoria basándose en uso real."""
    
    # Parámetros optimizables
    TUNABLE_PARAMS = {
        'cascade_tier1_threshold': 0.92,  # Default
        'cascade_tier2_threshold': 0.75,
        'cascade_tier3_threshold': 0.55,
        'signal_weights': {
            'semantic': 0.40, 'domain': 0.20,
            'lexical': 0.12, 'emotional': 0.10,
            'importance': 0.08, 'temporal': 0.05,
            'type_compat': 0.05
        },
        'search_score_weights': {
            'semantic_relevance': 0.50,
            'relation_weight': 0.20,
            'recency_frequency': 0.20,
            'tag_overlap': 0.10
        },
        'decay_base_halflife': 1.0,
        'novelty_threshold': 0.3,
    }
    
    async def evaluate_design(self, project: str, params: dict) -> float:
        """Evalúa un set de parámetros basándose en métricas históricas."""
        # Métricas:
        # 1. Search precision: ¿las memorias recuperadas fueron útiles?
        # 2. Retention rate: ¿las memorias importantes sobreviven?
        # 3. Schema quality: ¿los schemas generalizaron correctamente?
        # 4. Contradiction resolution: ¿se resolvieron a tiempo?
        
        search_precision = await compute_search_precision(project)
        retention = await compute_retention_rate(project)
        schema_quality = await compute_schema_usefulness(project)
        
        return 0.4 * search_precision + 0.3 * retention + 0.3 * schema_quality
    
    async def optimize_for_project(self, project: str):
        """Optimiza parámetros para un proyecto específico."""
        current_score = await self.evaluate_design(project, self.TUNABLE_PARAMS)
        
        # Simple hill-climbing (ALMA usa Meta Agent LLM, pero podemos empezar simple)
        for param_name, current_value in self.TUNABLE_PARAMS.items():
            if isinstance(current_value, float):
                # Probar ±10%
                for delta in [-0.1, 0.1]:
                    trial = {**self.TUNABLE_PARAMS, param_name: current_value * (1 + delta)}
                    trial_score = await self.evaluate_design(project, trial)
                    if trial_score > current_score:
                        self.TUNABLE_PARAMS[param_name] = trial[param_name]
                        current_score = trial_score
        
        # Guardar configuración optimizada por proyecto
        await save_project_params(project, self.TUNABLE_PARAMS)
```

### 4.3 Domain-Adaptive Memory Types

```python
# ALMA descubrió que diferentes dominios necesitan diferentes schemas
# Propuesta: detectar el dominio del proyecto y adaptar

DOMAIN_MEMORY_PROFILES = {
    'software_development': {
        'priority_types': ['error', 'decision', 'pattern'],
        'cascade_weights': {'lexical': 0.20, 'semantic': 0.35},  # Más lexical
        'schema_interval': 10,  # Schemas cada 10 memorias
    },
    'research': {
        'priority_types': ['insight', 'reference', 'hypothesis'],
        'cascade_weights': {'semantic': 0.50, 'importance': 0.15},  # Más semántico
        'schema_interval': 5,  # Schemas más frecuentes
    },
    'operations': {
        'priority_types': ['incident', 'runbook', 'config'],
        'cascade_weights': {'temporal': 0.15, 'arousal': 0.15},  # Más temporal
        'schema_interval': 20,  # Schemas menos frecuentes
    }
}
```

---

## 5. Tabla de Almacenamiento Propuesta

```sql
-- Archivo de diseños de memoria probados
CREATE TABLE IF NOT EXISTS memory_design_archive (
    id SERIAL PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    design_params JSONB NOT NULL,  -- Parámetros del diseño
    evaluation_score FLOAT,
    evaluation_metrics JSONB,  -- {precision, retention, schema_quality}
    generation INT DEFAULT 0,  -- Iteración de optimización
    parent_design_id INT REFERENCES memory_design_archive(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Parámetros activos por proyecto
CREATE TABLE IF NOT EXISTS active_memory_design (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    design_id INT REFERENCES memory_design_archive(id),
    params JSONB NOT NULL,
    activated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Métricas de Impacto

| Aspecto | Diseño Fijo | Con Mini-ALMA | Beneficio |
|---------|-------------|---------------|-----------|
| Cascade thresholds | Fijos globales | Adaptados por proyecto | Más preciso |
| Signal weights | 40/20/12/10/8/5/5 | Optimizados por dominio | Mejores relaciones |
| Schema frequency | Cada deep_sleep | Adaptada al volumen | Más oportuno |
| Decay rate | Uniforme | Por dominio + importancia | Menos pérdida |
| Tipo de relaciones | 6 tipos fijos | Emergentes del uso | Más expresivos |

---

## 7. Referencias

1. Xiong, Hu, Clune (2026) — "Learning to Continually Learn via Meta-learning Agentic Memory Designs" — arXiv:2602.07755
2. **GitHub**: https://github.com/zksha/alma
3. **Web**: https://yimingxiong.me/alma
