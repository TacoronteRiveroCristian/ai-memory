# AI Memory Brain

Un cerebro persistente para agentes de IA, inspirado en la neurociencia humana. No es una base de datos vectorial con un wrapper — es un sistema de memoria completo con **working memory**, **memoria duradera**, **consolidación offline** y **plasticidad**, diseñado para que múltiples agentes compartan conocimiento entre sesiones.

---

## La idea en 30 segundos

Cuando un humano trabaja en un proyecto, su cerebro:

1. **Percibe** — recibe información del entorno
2. **Retiene a corto plazo** — mantiene el contexto inmediato en memoria de trabajo
3. **Decide qué importa** — filtra ruido y guarda lo relevante
4. **Consolida durmiendo** — reorganiza y fortalece recuerdos importantes durante el sueño
5. **Recuerda por significado** — no busca por palabras exactas, sino por conceptos similares

Los agentes de IA no tienen nada de esto. Cada sesión empieza de cero. AI Memory Brain les da exactamente estas capacidades.

---

## Analogía con el cerebro humano

Cada componente del sistema tiene un equivalente neurológico:

```
┌─────────────────────────────────────────────────────────────────┐
│                    CEREBRO HUMANO  →  AI MEMORY BRAIN           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Corteza prefrontal          →  api-server (FastAPI + MCP)      │
│  (decisiones, control)          Organiza, prioriza, coordina    │
│                                                                 │
│  Hipocampo                   →  mem0                            │
│  (memoria reciente)             Captura experiencia inmediata   │
│                                                                 │
│  Corteza asociativa          →  Qdrant (vectores 1536-dim)      │
│  (memoria semántica)            Recuerda por significado         │
│                                                                 │
│  Memoria procedimental       →  PostgreSQL (13 tablas)          │
│  (hábitos, reglas)              Tareas, decisiones, errores     │
│                                                                 │
│  Sueño / consolidación       →  reflection-worker (cada 6h)    │
│  (reorganizar recuerdos)        DeepSeek razona y destila       │
│                                                                 │
│  Señales internas            →  Redis                           │
│  (neurotransmisores)            Caché, activación, heartbeat    │
│                                                                 │
│  El agente que trabaja       →  Claude, Cline, cualquier MCP   │
│  (la mente consciente)          client que se conecte           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Conceptos de plasticidad

El sistema implementa mecanismos de plasticidad neuronal reales:

| Concepto | Inspiración biológica | Implementación |
|----------|----------------------|----------------|
| **Decaimiento de Ebbinghaus** | Las memorias sin reforzar se debilitan | `stability_halflife` se duplica con cada acceso; las memorias no usadas decaen |
| **Activación propagada** | Recordar algo activa recuerdos relacionados | Acceder a una memoria refuerza sus vecinas vía Redis |
| **Valencia/Arousal** | Las emociones intensas fijan recuerdos | Errores = alto arousal, descubrimientos = valencia positiva |
| **Novedad** | Lo nuevo se recuerda mejor | Score de novedad relativo al conocimiento existente |
| **Extracción de esquemas** | El cerebro abstrae patrones de experiencias concretas | Detecta patrones abstractos entre múltiples memorias |

### El principio clave del diseño

> **Recordar es barato. Pensar es caro.**

Igual que un cerebro humano:
- **Percepción y acceso**: frecuente, rápido, bajo coste → embeddings de OpenAI + búsqueda vectorial
- **Consolidación profunda**: infrecuente, lenta, alto coste → DeepSeek razonando cada 6 horas

---

## Arquitectura

```
Agente (Claude/Cline/MCP client)
    │
    ▼
┌─────────────────────────────────────────────┐
│           api-server (FastAPI + MCP, :8050)  │
│           "Corteza prefrontal"               │
│                                              │
│  REST API  ◄──►  MCP Tools  ◄──►  Auth      │
└────┬──────────┬──────────┬──────────┬───────┘
     │          │          │          │
     ▼          ▼          ▼          ▼
  Qdrant    PostgreSQL   Redis      mem0
  (:6333)   (:5434)      (:6379)   (:8000)
  vectores  estructura   caché     working
  1536-dim  13 tablas    señales   memory

        │                            │
        └────────────┬───────────────┘
                     ▼
          ┌─────────────────────┐
          │  reflection-worker  │
          │  "Sueño" cada 6h   │
          │  DeepSeek razona    │
          │  Promueve memorias  │
          └─────────────────────┘

UI (opcional):
  brain-ui (:3080) — Visualización de grafo en tiempo real
```

### Flujo de una sesión completa

```
1. INICIO  →  get_project_context()     // El agente "se despierta" con contexto
               ├─ tareas activas
               ├─ decisiones recientes
               ├─ working memory (mem0)
               └─ búsqueda semántica (Qdrant)

2. TRABAJO →  store_memory()            // Guarda hallazgos importantes
              store_decision()           // Registra decisiones de arquitectura
              store_error()              // Documenta errores encontrados
              update_task_state()        // Actualiza progreso

3. CIERRE  →  record_session_summary()  // Resume toda la sesión
               ├─ Se guarda en PostgreSQL
               ├─ Se envía a mem0 (working memory)
               └─ Se marca para consolidación

4. SUEÑO   →  reflection-worker         // Cada 6h, DeepSeek consolida
               ├─ Lee sesiones pendientes
               ├─ Consulta working memory
               ├─ Razona y extrae conclusiones
               ├─ Promueve memorias duraderas
               └─ Detecta contradicciones
```

---

## Inicio rápido

### Prerrequisitos

- Docker y Docker Compose
- Claves de API: **OpenAI** (embeddings) y **DeepSeek** (razonamiento)

### Instalación

```bash
# 1. Clonar y configurar
git clone <repo-url> && cd ai-memory
cp .env.example .env

# 2. Editar .env con tus claves reales
#    OPENAI_API_KEY=sk-...
#    DEEPSEEK_API_KEY=...
#    MEMORY_API_KEY=<tu-clave-para-la-API>
#    (cambiar también POSTGRES_PASSWORD, REDIS_PASSWORD, QDRANT_API_KEY)

# 3. Levantar todo
make stack-up          # docker compose up -d --build

# 4. Verificar que todo está sano
make health
```

### Conectar un agente via MCP

En `.mcp.json` de tu agente (ej. Claude Code):

```json
{
  "mcpServers": {
    "memoryBrain": {
      "type": "sse",
      "url": "http://localhost:8050/mcp",
      "headers": {
        "X-API-Key": "${MEMORY_API_KEY}"
      }
    }
  }
}
```

Para Claude Code, carga la variable de entorno antes de iniciar:

```bash
source .env && claude
```

### Ver la UI del cerebro

```bash
# La UI se levanta automáticamente con make stack-up en el puerto 3080
# Abrir: http://localhost:3080
```

---

## MCP Tools disponibles

### Memoria explícita

| Tool | Descripción |
|------|-------------|
| `store_memory` | Guarda una memoria duradera (Qdrant + PostgreSQL) |
| `search_memory` | Búsqueda semántica por significado |
| `get_project_context` | Rehidrata contexto completo de un proyecto |
| `delete_memory` | Elimina una memoria por ID |

### Tareas y decisiones

| Tool | Descripción |
|------|-------------|
| `update_task_state` | Cambia estado de una tarea (active/done/blocked/cancelled) |
| `list_active_tasks` | Lista tareas activas de un proyecto |
| `store_decision` | Registra una decisión con rationale y alternativas |
| `store_error` | Documenta un error y su solución |

### Sesiones y reflexión

| Tool | Descripción |
|------|-------------|
| `record_session_summary` | Cierra una sesión con resumen estructurado |
| `run_memory_reflection` | Lanza consolidación manual (sin esperar 6h) |
| `get_reflection_status` | Estado del reflection worker |

### Observabilidad

| Tool | Descripción |
|------|-------------|
| `list_recent_consolidations` | Qué consolidó el worker y cuándo |
| `list_contradictions` | Conflictos detectados entre memorias |
| `get_brain_activity` | Timeline de actividad cerebral (últimas N horas) |

### Relaciones

| Tool | Descripción |
|------|-------------|
| `link_memories` | Conecta dos memorias con un tipo de relación |
| `bridge_projects` | Crea puente entre dos proyectos |

---

## Comandos útiles

```bash
# Stack
make stack-up                     # Levantar todo (incluye UI)
make stack-down                   # Apagar todo
make health                       # Verificar salud de servicios
make smoke                        # Smoke test E2E

# Testing (modo determinista — sin llamadas a APIs externas)
make stack-test-up                # Stack en modo test
make test-deterministic           # Ejecutar tests
make eval-deterministic           # Benchmark de latencia y recall
make brain-check                  # Suite completa E2E

# Demo (datos de ejemplo preconfigurados)
make demo-up && make demo-seed    # Levantar con datos de ejemplo
make demo-check                   # Validar dataset de demo
make demo-down                    # Apagar demo

# Heartbeat monitor (opcional)
make heartbeat-fast               # Monitor acelerado (desarrollo)
make heartbeat-prod               # Monitor producción
make heartbeat-status             # Ver estado
```

---

## Brain UI — Visualización del cerebro

La UI (`brain-ui/`) es una SPA React + TypeScript que visualiza el cerebro como un grafo interactivo usando `react-force-graph-2d`. Permite:

- Ver memorias como nodos conectados por relaciones semánticas
- Filtrar por proyecto, tipo de memoria, keywords
- Inspeccionar detalles de cada memoria
- Monitorear salud del sistema
- Eliminar proyectos completos

### Desarrollo local de la UI

```bash
cd brain-ui
npm install
npm run dev    # Vite dev server en :5173
```

Necesita `VITE_API_URL` y `VITE_API_KEY` en las variables de entorno (o en `.env` dentro de `brain-ui/`).

---

## Troubleshooting

### La UI no se ve / página en blanco

**Causa más común: la API key no se pasó durante el build de Docker.**

La UI necesita `VITE_API_KEY` en tiempo de **build** (no de runtime), porque Vite la embebe en el JavaScript estático. Si la variable estaba vacía cuando se construyó la imagen, todas las llamadas a la API fallarán con 401.

```bash
# 1. Verificar que .env tiene MEMORY_API_KEY configurado
grep MEMORY_API_KEY .env

# 2. Reconstruir la UI con las variables correctas
docker compose build --no-cache brain-ui
docker compose up -d brain-ui

# 3. Verificar en el navegador (F12 → Console) que no hay errores 401
```

### La UI carga pero no muestra nodos

- **No hay memorias todavía**: El grafo necesita memorias almacenadas. Usa `make demo-seed` para cargar datos de ejemplo, o empieza a usar las tools MCP para guardar memorias.
- **Proyecto incorrecto**: Asegúrate de seleccionar el proyecto correcto en el selector superior.
- **API no accesible**: Verifica que `api-server` está corriendo: `curl http://localhost:8050/health`

### Los contenedores arrancan pero `/ready` devuelve `false`

El cerebro está **desplegado pero no despierto**. Ocurre cuando las claves de API son placeholder:

```bash
# Verificar que las claves son reales (no "change-me" ni "sk-placeholder")
grep -E "OPENAI_API_KEY|DEEPSEEK_API_KEY" .env

# Tras corregir, reiniciar:
make stack-down && make stack-up
```

### `mem0` tarda mucho o falla

- `mem0` depende de OpenAI para embeddings y DeepSeek para extracción. Si alguno está caído o lento, la working memory se degrada.
- El timeout de ingesta es configurable: `MEM0_INGEST_TIMEOUT_SECONDS` (default: 90s).
- **La sesión nunca se pierde** aunque mem0 falle — el resumen se guarda en PostgreSQL igualmente.

### El reflection-worker no consolida

```bash
# Ver logs del worker
docker logs ai-memory-reflection-worker --tail 50

# Verificar heartbeat
make heartbeat-status

# Lanzar reflexión manual (sin esperar 6h)
# Usa la tool MCP: run_memory_reflection(project="tu-proyecto")
```

Causas comunes:
- `DEEPSEEK_API_KEY` inválida → el worker arranca pero no puede razonar
- No hay sesiones pendientes → nada que consolidar
- El worker está reiniciándose → revisar `docker compose ps`

### CORS: la UI en desarrollo no puede hablar con la API

Si usas `npm run dev` (puerto 5173) y la API está en 8050, el navegador bloqueará las peticiones por CORS. Opciones:

1. **Usar la UI dockerizada** (recomendado): `docker compose up -d brain-ui` → acceder en `:3080`
2. **Configurar VITE_API_URL** apuntando al proxy correcto

### Los tests fallan con "Connection refused"

Los tests necesitan la stack de test corriendo:

```bash
# Levantar stack en modo test
make stack-test-up

# Esperar a que esté healthy
make health

# Ahora sí, ejecutar tests
make test-deterministic
```

### Quiero reiniciar el cerebro desde cero

```bash
# Parar todo
make stack-down

# Borrar volúmenes de datos
rm -rf volumes/postgres volumes/qdrant volumes/redis volumes/mem0

# Levantar de nuevo (PostgreSQL recreará el schema)
make stack-up
```

---

## Modo de test determinista

Para desarrollo y CI, el sistema soporta un modo sin llamadas a APIs externas:

- **`AI_MEMORY_TEST_MODE=true`**: timestamps congelados, embeddings basados en hash (sin OpenAI), razonamiento heurístico (sin DeepSeek)
- Los tests sin marca `@pytest.mark.live` corren en este modo
- CI está configurada en `.github/workflows/deterministic-brain-ci.yml`

---

## Variables de entorno principales

| Variable | Descripción | Default |
|----------|-------------|---------|
| `MEMORY_API_KEY` | Clave de autenticación para la API | (requerida) |
| `OPENAI_API_KEY` | Clave para embeddings | (requerida) |
| `DEEPSEEK_API_KEY` | Clave para razonamiento/consolidación | (requerida) |
| `POSTGRES_PASSWORD` | Password de PostgreSQL | (requerida) |
| `REDIS_PASSWORD` | Password de Redis | (requerida) |
| `QDRANT_API_KEY` | Clave de Qdrant | (requerida) |
| `REFLECTION_INTERVAL_SECONDS` | Intervalo de consolidación | `21600` (6h) |
| `AI_MEMORY_TEST_MODE` | Modo determinista sin APIs externas | `false` |
| `VITE_API_BASE_URL` | URL de la API para la UI | `http://127.0.0.1:8050` |
| `INGEST_ENABLED` | Ingestión pasiva de turnos | `true` |

Ver `.env.example` para la lista completa.

---

## Documentación adicional

| Documento | Contenido |
|-----------|-----------|
| [`docs/MCP_TOOLS.md`](docs/MCP_TOOLS.md) | Guía detallada de cada tool MCP con ejemplos |
| [`docs/CEREBRO_CONSCIENTE_SUPERDOCS.md`](docs/CEREBRO_CONSCIENTE_SUPERDOCS.md) | Arquitectura completa, filosofía de diseño y analogías neurocientíficas |
| [`CLAUDE.md`](CLAUDE.md) | Instrucciones para agentes que trabajan con este código |
| [`CHANGELOG.md`](CHANGELOG.md) | Historial de cambios |

---

## Umbrales de rendimiento (CI)

| Endpoint | P95 máximo |
|----------|-----------|
| `structured_search` | 250ms |
| `project_context` | 2500ms |
| `plasticity_session` | 1500ms |
| `graph_subgraph` | 900ms |

---

## Licencia

Proyecto privado.
