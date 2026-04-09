# /memory-roi — Informe de efectividad del AI Memory Brain

Ejecuta un análisis completo del valor y uso del MCP de memoria. Sigue estos pasos:

## Paso 1 — Ejecutar el script de métricas

Corre el script de medición contra el stack activo:

```bash
AI_MEMORY_BASE_URL=http://127.0.0.1:8050 python scripts/measure_effectiveness.py $ARGUMENTS
```

Si el stack no responde, informa al usuario que debe levantarlo con `make stack-up` y detente aquí.

## Paso 2 — Interpretar los resultados

Después de mostrar el output del script, añade una sección **"Mi interpretación"** con:

1. **¿Se está usando el MCP?**
   - Si `avg_activation_score < 0.04`: el MCP casi no se está invocando. Recomienda añadir `get_project_context` al inicio de cada sesión.
   - Si `avg_activation_score` entre 0.04 y 0.15: uso moderado. Sugiere usar `search_memory` más proactivamente.
   - Si `avg_activation_score > 0.15`: uso saludable. El cerebro está activo.

2. **¿Qué valor está aportando?**
   - Lista las memorias más calientes (si existen) y explica qué tipo de conocimiento representan.
   - Si hay `known_errors` con `occurrence_count > 1`: señala que esos errores se repitieron — sin el MCP no había protección.
   - Si hay schemas extraídos: explica que el sistema detectó patrones de alto nivel.

3. **¿Cómo mejorar la relación beneficio/esfuerzo?**
   - Si `orphan_memories > 0`: recomienda usar `link_memories` para conectarlas.
   - Si `bridges == 0` y hay múltiples proyectos: sugiere usar `bridge_projects`.
   - Si `last_nrem == null`: indica que la consolidación nunca ha corrido — ejecutar `make stack-up` para arrancar el worker.
   - Si `keyphrases_coverage < 80%`: hay memorias sin keyphrases, la búsqueda semántica es subóptima.

4. **Veredicto sobre ROI**
   - Basándote en el Brain Utilization Score, da un veredicto directo y honesto sobre si el MCP está justificando su uso.

## Paso 3 — Acciones opcionales

Pregunta al usuario si quiere que ejecutes alguna de estas acciones correctivas:
- `run_memory_reflection` para consolidar memorias pendientes
- `get_project_context(<proyecto>)` para ver el contexto actual de un proyecto concreto
- Revisar las memorias huérfanas y sugerir conexiones con `link_memories`

---

**Flags disponibles** (se pasan como `$ARGUMENTS`):
- `--project <nombre>` — filtrar análisis a un solo proyecto
- `--json` — salida en JSON (para automatización)

**Ejemplo de uso:**
```
/memory-roi
/memory-roi --project ai-memory
/memory-roi --json
```
