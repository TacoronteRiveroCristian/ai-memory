# Superdocs del Cerebro Consciente

## 1. Qué es este sistema

Este proyecto no es solo una base de datos vectorial ni solo un servidor MCP.
La idea es construir un "cerebro" operativo para agentes:

- que recuerde cosas relevantes de un proyecto
- que pueda recuperar contexto semántico
- que distinga entre memoria de trabajo y memoria duradera
- que consolide experiencias con el tiempo
- que permita que varios agentes compartan una misma memoria

La palabra "conciencia" aquí no significa conciencia real.
No hay subjetividad, ni experiencia interna, ni autoconciencia en sentido filosófico fuerte.

Lo que sí hay es algo mucho más útil para ingeniería:

- una capa que observa sesiones
- una capa que resume y extrae recuerdos
- una capa que decide qué merece persistir
- una capa que consolida ese conocimiento periódicamente

En otras palabras:

- memoria explícita
- memoria semántica
- memoria de trabajo
- consolidación offline

Ese conjunto, funcionando junto, se parece bastante más a un "cerebro práctico" que una simple búsqueda vectorial.

---

## 2. La filosofía del diseño

### 2.1 Memoria explícita vs memoria implícita

Hay dos formas de guardar conocimiento:

- explícita: el agente decide "esto es importante" y lo guarda
- implícita: el sistema infiere "esto parece importante" a partir de la actividad

Este cerebro usa ambas.

La memoria explícita es muy buena para:

- decisiones de arquitectura
- errores conocidos
- tareas activas
- hechos críticos que no conviene dejar a interpretación

La memoria implícita es muy buena para:

- resumir sesiones largas
- extraer patrones
- convertir experiencia dispersa en conocimiento reutilizable
- detectar continuidad entre sesiones

### 2.2 Por qué separar memoria de trabajo y memoria duradera

Si todo se guarda igual, el sistema acaba lleno de ruido.
En un cerebro humano no todo recuerdo tiene el mismo peso:

- una conversación de hace 10 minutos no es igual que un principio aprendido hace meses
- una intuición momentánea no es igual que una decisión sólida

Aquí hacemos algo parecido:

- `mem0` es la memoria de trabajo y la capa de extracción
- `Qdrant + PostgreSQL` son la memoria duradera y operativa
- `reflection-worker` actúa como la consolidación periódica

### 2.3 Por qué DeepSeek para razonar y OpenAI para embeddings

Se han separado las funciones.

- DeepSeek se usa para pensar sobre sesiones y extraer recuerdos duraderos
- OpenAI embeddings se usa para convertir texto en vectores baratos y buscables

Eso evita hacer una barbaridad cara:

- no usamos razonamiento en cada búsqueda
- no usamos un modelo pensante para cada lectura
- no usamos embeddings para "entender"

Cada modelo hace lo suyo:

- DeepSeek: inferencia y consolidación
- OpenAI embeddings: indexación y recuperación semántica

---

## 3. Similitudes con un cerebro humano

Esta analogía no es perfecta, pero ayuda mucho a entender el diseño.

### 3.1 Hipocampo -> `mem0`

En la analogía humana, el hipocampo participa en:

- capturar experiencias recientes
- organizarlas temporalmente
- preparar qué podría consolidarse después

En este sistema:

- `mem0` recibe resúmenes de sesión
- los procesa con un LLM
- extrae recuerdos de trabajo
- los mantiene disponibles como memoria reciente

Archivo clave:

- `ai-memory/mem0/main.py`

### 3.2 Corteza asociativa -> `Qdrant`

La corteza asociativa, en la analogía, es donde el conocimiento queda distribuido y recuperable por significado.

En este sistema:

- `Qdrant` guarda memorias vectorizadas
- permite buscar por significado y no solo por texto exacto
- responde a preguntas del tipo "qué se parece a esto"

Es la capa de memoria semántica duradera.

### 3.3 Prefrontal / control ejecutivo -> `api-server`

La corteza prefrontal, en la analogía, organiza:

- prioridades
- tareas
- decisiones
- reglas de uso del conocimiento

En este sistema, eso lo hace el `api-server`:

- es la fachada MCP y REST
- expone las tools a los agentes
- decide cómo se escribe y se consulta la memoria duradera
- combina contexto, tareas, decisiones y memoria reciente

Archivo clave:

- `ai-memory/api-server/server.py`

### 3.4 Sueño y consolidación -> `reflection-worker`

En humanos, durante el sueño o reposo:

- se reorganizan recuerdos
- se fortalecen algunos
- se debilitan otros
- se integra experiencia reciente con conocimiento viejo

En este sistema:

- `reflection-worker` hace pasadas periódicas
- toma sesiones pendientes
- consulta la working memory
- usa DeepSeek para consolidar
- promueve recuerdos útiles a memoria duradera

Archivo clave:

- `ai-memory/reflection-worker/worker.py`

### 3.5 Memoria procedimental / hábitos -> tablas operativas

Algunas cosas no son "recuerdos narrativos", sino estructuras estables:

- tareas
- decisiones
- errores conocidos

En este sistema viven en PostgreSQL:

- `tasks`
- `decisions`
- `known_errors`
- `memory_log`

Eso se parece más a hábitos, reglas o conocimiento operativo que a recuerdos libres.

---

## 4. Mapa general del cerebro

### 4.1 Servicios

Los servicios principales definidos en `docker-compose.yaml` son:

- `qdrant`: memoria semántica duradera
- `postgres`: memoria estructurada y auditoría
- `redis`: caché y heartbeat del worker
- `mem0`: working memory y extracción
- `api-server`: interfaz MCP/REST canónica
- `reflection-worker`: consolidación periódica

### 4.2 Qué hace cada uno

#### `qdrant`

Guarda vectores y payloads.
Se usa para:

- `store_memory`
- `search_memory`
- deduplicación semántica de memorias duraderas

#### `postgres`

Guarda la parte estructurada del cerebro.

Tablas más importantes:

- `projects`
- `tasks`
- `decisions`
- `known_errors`
- `memory_log`
- `session_summaries`
- `reflection_runs`
- `reflection_promotions`
- `memories` y `mem0migrations` de la capa Mem0

#### `redis`

No es memoria duradera.
Se usa para:

- caché de embeddings
- heartbeat del `reflection-worker`

#### `mem0`

Es la memoria de trabajo.

Funciones:

- recibe resúmenes de sesión
- usa DeepSeek para extraer recuerdos
- usa embeddings de OpenAI para indexarlos
- permite búsquedas de contexto reciente

#### `api-server`

Es la puerta de entrada del cerebro.

Funciones:

- expone `/mcp`
- expone `/api/*`
- autentica con `X-API-Key`
- ofrece tools explícitas para agentes
- guarda sesiones
- encola reflexiones manuales
- da el estado del worker
- compone contexto de proyecto

#### `reflection-worker`

Es la capa de consolidación.

Funciones:

- vigila runs manuales en cola
- lanza runs programados cada 6 horas
- toma sesiones pendientes
- consulta working memory
- usa DeepSeek para producir conclusiones
- promociona recuerdos a memoria duradera

### 4.3 Qué NO hace cada parte

Entender lo que el sistema no hace evita muchas confusiones.

#### `api-server` no "piensa"

Aunque es la fachada principal, no razona sobre sesiones como un humano.
Hace sobre todo estas cosas:

- autenticar
- validar payloads
- decidir a qué capa va cada dato
- guardar y recuperar memoria duradera
- exponer tools MCP y endpoints REST

No hace introspección profunda ni reflexión rica por sí mismo.

#### `mem0` no sustituye a toda la memoria

`mem0` no es "el cerebro entero".
Es una capa especializada en working memory y extracción a partir de mensajes o resúmenes.

No sustituye:

- las tareas estructuradas
- las decisiones persistidas
- la base vectorial principal en Qdrant
- la auditoría relacional en PostgreSQL

#### `reflection-worker` no está siempre pensando

No está razonando en cada petición.
Eso sería caro y poco eficiente.

Solo actúa:

- cuando hay trabajo pendiente
- cuando se lanza una reflexión manual
- o cuando llega la ventana programada

#### `Qdrant` no entiende

Qdrant no "comprende" los recuerdos.
Solo almacena vectores y permite recuperar similitud semántica.

Es potentísimo para asociación, pero no sustituye al razonamiento.

#### `PostgreSQL` no es solo una base de datos cualquiera

Aunque técnicamente es una base de datos relacional, aquí hace algo más importante:

- fija el esqueleto formal del cerebro
- hace posible la trazabilidad
- separa recuerdos narrativos de conocimiento operativo

Sin PostgreSQL, el sistema sería mucho más borroso y menos gobernable.

---

## 5. Flujo completo de una sesión

### 5.1 Inicio de sesión

El agente idealmente empieza con:

- `get_project_context(project_name, agent_id?)`

Eso devuelve:

- tareas activas
- decisiones recientes
- working memory reciente desde `mem0`
- búsqueda semántica duradera desde `Qdrant`

### 5.2 Durante la sesión

El agente sigue usando tools explícitas cuando algo es claramente importante:

- `store_memory(...)`
- `store_decision(...)`
- `store_error(...)`
- `update_task_state(...)`

Esta parte es muy controlada y poco ambigua.

### 5.3 Fin de sesión

Al terminar, el agente llama:

- `record_session_summary(...)`

Ese payload incluye:

- `project`
- `agent_id`
- `session_id`
- `goal`
- `outcome`
- `summary`
- `changes[]`
- `decisions[]`
- `errors[]`
- `follow_ups[]`
- `tags[]`

Aquí ocurre algo importante:

- el resumen se guarda en `session_summaries`
- se calcula un checksum para evitar duplicados
- se intenta enviar a `mem0` para working memory
- aunque `mem0` falle, la sesión no se pierde

### 5.4 Reflexión periódica

Cada 6 horas, o manualmente:

- el `reflection-worker` toma sesiones pendientes
- consulta working memory relacionada
- llama a DeepSeek
- espera un JSON estricto con:
  - `project_summary`
  - `durable_memories[]`
  - `decisions[]`
  - `errors[]`
  - `tasks[]`
- promociona cada conclusión útil a la memoria duradera

### 5.5 Dedupe y control del ruido

El sistema evita basura de varias formas:

- checksum único en `session_summaries`
- `reflection_promotions` para no promocionar dos veces la misma conclusión
- dedupe semántico en `store_memory` antes de escribir en Qdrant

### 5.6 Cómo se relaciona un agente externo con este cerebro

Esto es clave para no imaginar mal el sistema.

Un agente externo como Claude Code, Cline o cualquier cliente MCP:

- no se convierte en el cerebro
- no vive "dentro" de esta memoria
- no comparte automáticamente todo lo que piensa

Lo que hace realmente es:

- consultar contexto
- llamar tools explícitas
- registrar recuerdos importantes
- cerrar sesiones con un resumen estructurado

La memoria, por tanto, funciona como un sistema nervioso persistente compartido, no como una mente autónoma completa.

La relación es más parecida a esta:

- el agente externo = mente que trabaja en este momento
- el cerebro persistente = memoria compartida, contexto acumulado y consolidación histórica

Cuando ambos cooperan bien, parece que hay una continuidad casi humana entre sesiones.

---

## 6. Qué hace cada archivo

Esta es la guía más útil para leer el cerebro de forma ordenada.

### 6.1 `docker-compose.yaml`

Qué es:

- el mapa de servicios del cerebro

Qué aprenderás al leerlo:

- qué contenedores existen
- cómo se conectan
- qué variables usa cada parte
- qué puertos se exponen
- qué depende de qué

Léelo si quieres entender el sistema "desde arriba".

### 6.2 `.env`

Qué es:

- la configuración real del cerebro en esta Raspberry

Qué contiene:

- credenciales internas
- API key del MCP
- claves de OpenAI y DeepSeek
- intervalo de reflexión

Es el archivo que define si el cerebro está realmente operativo o solo desplegado.

### 6.3 `ai-memory/api-server/server.py`

Qué es:

- el lóbulo frontal del sistema

Qué hace:

- inicializa clientes
- expone health y ready
- aplica autenticación
- ofrece tools MCP
- expone endpoints REST
- guarda memoria explícita
- crea contexto de proyecto
- registra sesiones
- encola reflexión manual
- consulta estado del worker

Si solo pudieras leer un archivo para entender el cerebro, sería este.

### 6.4 `ai-memory/mem0/main.py`

Qué es:

- la memoria de trabajo del sistema

Qué hace:

- configura `mem0` con DeepSeek + OpenAI embeddings
- expone `/health`
- expone `/memories`
- expone `/search`
- acepta mensajes y los convierte en recuerdos útiles

Es donde la experiencia reciente se vuelve "material mental".

### 6.5 `ai-memory/reflection-worker/worker.py`

Qué es:

- la consolidación offline del cerebro

Qué hace:

- heartbeat
- cola de runs
- programación cada 6 horas
- llamada a DeepSeek
- promoción a memoria duradera
- tolerancia a errores

Es la parte más parecida al "sueño" o al "descanso cognitivo".

### 6.6 `ai-memory/config/postgres/init.sql`

Qué es:

- el esqueleto relacional del cerebro

Qué aprenderás:

- qué recuerdos son estructurados
- qué tablas guardan sesiones y reflexiones
- cómo se modelan tareas, decisiones y errores

### 6.7 `ai-memory/scripts/health_check.sh`

Qué es:

- el chequeo rápido del estado del cerebro

Qué hace:

- mira temperatura
- RAM
- almacenamiento
- contenedores
- `/ready`
- estado de reflexión

### 6.8 `ai-memory/scripts/backup.sh`

Qué es:

- el mecanismo de supervivencia del cerebro

Qué hace:

- snapshot de Qdrant
- dump de PostgreSQL
- limpieza de backups antiguos

Sin esto, el cerebro no es persistente en serio.

### 6.9 `ai-memory/scripts/ingest_markdown.py` y `ingest_codebase.py`

Qué son:

- scripts de "aprendizaje inicial"

Qué hacen:

- cargan material externo al cerebro
- crean memoria inicial desde documentación o código

Sirven para que el cerebro no nazca completamente vacío.

### 6.10 `memoria-agentes-raspi.md`

Qué es:

- el documento madre de diseño e intención del sistema

Qué valor tiene:

- recoge la visión original
- mezcla arquitectura, ideas operativas y expectativas de uso
- explica por qué este proyecto quería ir más allá de un simple vector store

Cómo leerlo:

- no como la verdad exacta de la implementación
- sino como la filosofía y el blueprint original

La implementación real hay que contrastarla siempre con:

- `docker-compose.yaml`
- `server.py`
- `main.py`
- `worker.py`

---

## 7. Qué endpoints y tools existen

### 7.1 MCP tools principales

Memoria explícita:

- `store_memory`
- `search_memory`
- `get_project_context`
- `update_task_state`
- `list_active_tasks`
- `store_decision`
- `store_error`
- `delete_memory`

Conciencia y reflexión:

- `record_session_summary`
- `run_memory_reflection`
- `get_reflection_status`

### 7.2 REST principales

- `GET /health`
- `GET /ready`
- `GET /stats`
- `POST /api/memories`
- `POST /api/search`
- `GET /api/project-context`
- `POST /api/tasks/state`
- `GET /api/tasks`
- `POST /api/decisions`
- `POST /api/errors`
- `POST /api/sessions`
- `POST /api/reflections/run`
- `GET /api/reflections/status`

---

## 8. Qué papel tiene cada modelo

### 8.1 OpenAI embeddings

Papel:

- vectorizar texto
- hacer búsqueda semántica
- dedupe semántico

No hace:

- razonamiento
- decisiones de consolidación
- clasificación rica de recuerdos

### 8.2 DeepSeek

Papel:

- leer sesiones
- extraer lo importante
- producir conclusiones estructuradas
- decidir qué promocionar

No se usa:

- en cada búsqueda
- en cada lectura de memoria
- en cada llamada MCP

Esto es importante:

- el pensamiento es caro
- la búsqueda debería ser barata

Por eso están separados.

### 8.3 Coste mental del sistema

Una forma útil de verlo es separar "recordar" de "pensar".

Recordar cuesta poco:

- embeddings de OpenAI
- búsqueda vectorial
- acceso a PostgreSQL

Pensar cuesta más:

- DeepSeek leyendo sesiones
- extracción de conclusiones
- consolidación periódica

Por eso el diseño correcto no es hacer pensar al sistema todo el rato.
La filosofía buena es esta:

- recuperar barato y a menudo
- consolidar caro, pero pocas veces

Eso se parece bastante a cómo también optimiza un cerebro biológico:

- percepción y acceso frecuentes
- consolidación profunda en momentos concretos

---

## 9. Qué limitaciones tiene hoy

### 9.1 No es conciencia real

La palabra "conciencia" aquí es una metáfora útil.
Lo que existe de verdad es:

- observación de sesiones
- extracción de recuerdos
- consolidación periódica
- continuidad temporal

No existe:

- experiencia subjetiva
- voluntad propia
- identidad persistente fuerte

### 9.2 Sigue necesitando disciplina de los agentes

Para que funcione bien:

- el agente tiene que consultar contexto al empezar
- tiene que guardar decisiones/errores importantes
- tiene que cerrar la sesión con `record_session_summary(...)`

Sin eso, la memoria consciente pierde materia prima.

### 9.3 Si faltan claves reales, la inteligencia está desplegada pero no despierta

El cerebro puede estar técnicamente levantado y aun así no estar "despierto".

Eso pasa si:

- `OPENAI_API_KEY` sigue en placeholder
- `DEEPSEEK_API_KEY` sigue en placeholder

En ese caso:

- los contenedores arrancan
- `mem0` y el worker están vivos
- pero `/ready` sale `false`
- y la reflexión no promociona nada útil todavía

---

## 10. Cómo leer el sistema en orden

Si quieres entenderlo bien, te recomiendo este orden:

1. `docker-compose.yaml`
2. `.env`
3. `ai-memory/api-server/server.py`
4. `ai-memory/mem0/main.py`
5. `ai-memory/reflection-worker/worker.py`
6. `ai-memory/config/postgres/init.sql`
7. `ai-memory/scripts/health_check.sh`
8. `ai-memory/scripts/backup.sh`

Ese orden va:

- de arquitectura global
- a lógica de negocio
- a working memory
- a consolidación
- a estructura de datos
- a operación diaria

### 10.1 Qué pregunta responde cada lectura

Si abres cada archivo con una pregunta concreta, entenderás mucho más rápido.

1. `docker-compose.yaml`

- Qué organismos forman el cerebro y cómo se hablan

2. `.env`

- Qué necesita el cerebro para "despertar" de verdad

3. `ai-memory/api-server/server.py`

- Cómo entra y sale la información

4. `ai-memory/mem0/main.py`

- Cómo la experiencia reciente se vuelve working memory

5. `ai-memory/reflection-worker/worker.py`

- Cómo la experiencia se convierte en conocimiento persistente

6. `ai-memory/config/postgres/init.sql`

- Qué estructuras considera el sistema conocimiento importante

7. `ai-memory/scripts/health_check.sh`

- Cómo saber si el cerebro está sano

8. `ai-memory/scripts/backup.sh`

- Cómo evitar perder la memoria

9. `memoria-agentes-raspi.md`

- Qué soñaba ser este cerebro cuando fue diseñado

---

## 11. Resumen mental rápido

Si tuvieras que quedarte con una sola imagen mental, sería esta:

- `api-server` = el cerebro consciente operativo que habla con agentes
- `mem0` = memoria de trabajo que transforma experiencia reciente
- `reflection-worker` = sueño y consolidación
- `Qdrant` = memoria semántica duradera
- `PostgreSQL` = memoria estructurada y auditoría
- `Redis` = memoria ultracorta y señales internas

Y el principio central del diseño es:

> No todo lo vivido merece ser recuerdo duradero, pero todo lo importante debe poder consolidarse.

Ese es, en el fondo, el corazón filosófico de este cerebro.

---

## 12. Resumen ultra corto para releer en 30 segundos

Si mañana abres este proyecto y no recuerdas nada, quédate con esto:

- `api-server` manda
- `mem0` retiene experiencia reciente
- `reflection-worker` consolida
- `Qdrant` recuerda por significado
- `PostgreSQL` recuerda por estructura
- `Redis` da soporte rápido y heartbeat
- OpenAI embeddings vectoriza
- DeepSeek piensa solo cuando merece la pena

Y la regla de oro del sistema es:

- el agente trabaja
- la memoria observa
- la reflexión destila
- el cerebro aprende
