# AI Memory Brain — Plugin para Claude Code

Conecta Claude Code a AI Memory Brain para que **todos tus proyectos** tengan memoria persistente entre sesiones, automaticamente.

## Que instala

| Archivo | Destino | Funcion |
|---------|---------|---------|
| Hook de ingestion | `~/.claude/hooks/ingest-turn.sh` | Envia cada turno al cerebro (fire-and-forget) |
| MCP server | `~/.claude/.mcp.json` | Conecta las tools del cerebro en todo proyecto |
| Hook Stop | `~/.claude/settings.json` | Dispara la ingestion al final de cada turno |
| Protocolo | `~/.claude/CLAUDE.md` | Ensena al agente cuando y como guardar memorias |
| Env var | `~/.bashrc` o `~/.zshrc` | Exporta `MEMORY_API_KEY` para autenticacion |

Todo se instala a nivel de **usuario** (`~/.claude/`), no de proyecto. Un solo `install.sh` y todos tus proyectos quedan conectados.

## Prerrequisitos

- **Claude Code** instalado
- **AI Memory Brain** corriendo y accesible (ver README del proyecto raiz)
- **jq** instalado (`sudo apt install jq` / `brew install jq`)
- Tu `MEMORY_API_KEY` (la que pusiste en `.env` del proyecto ai-memory)

## Instalacion

```bash
# Desde la raiz del proyecto ai-memory:
./plugin/claude-code/install.sh <URL_DEL_CEREBRO> <TU_API_KEY>

# Ejemplo (Raspberry Pi en red local):
./plugin/claude-code/install.sh http://192.168.1.156:8050 mi-clave-secreta

# Ejemplo (misma maquina):
./plugin/claude-code/install.sh http://localhost:8050 mi-clave-secreta
```

Despues de instalar:

```bash
# Cargar la variable de entorno (o abrir una terminal nueva)
source ~/.bashrc

# Abrir Claude Code en cualquier proyecto
cd ~/mis-proyectos/mi-app
claude
# -> memoryBrain aparece en el panel MCP automaticamente
```

## Verificar que funciona

1. Abre Claude Code en cualquier proyecto
2. Comprueba que `memoryBrain` aparece conectado en el panel MCP
3. Pide al agente: "que contexto tienes de este proyecto?"
   - Deberia llamar a `get_project_context`
4. Trabaja normalmente — el agente guardara memorias proactivamente
5. En la UI del cerebro (`http://<IP>:3080`) veras los nodos aparecer

## Desinstalacion

```bash
./plugin/claude-code/uninstall.sh
```

Elimina el hook, el MCP server, el bloque de protocolo del CLAUDE.md y la entrada de settings.json. No toca los datos del cerebro ni la variable `MEMORY_API_KEY`.

## Instalacion manual (sin script)

Si prefieres hacerlo a mano o el script no funciona en tu sistema:

### 1. MCP server (`~/.claude/.mcp.json`)

Crea o edita el archivo y anade:

```json
{
  "mcpServers": {
    "memoryBrain": {
      "type": "http",
      "url": "http://<IP>:8050/mcp",
      "headers": {
        "X-API-Key": "<TU_API_KEY>"
      }
    }
  }
}
```

### 2. Hook de ingestion (`~/.claude/hooks/ingest-turn.sh`)

Copia `plugin/claude-code/hooks/ingest-turn.sh` a `~/.claude/hooks/` y hazlo ejecutable:

```bash
mkdir -p ~/.claude/hooks
cp plugin/claude-code/hooks/ingest-turn.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/ingest-turn.sh
```

Edita la linea `API_URL=` para que apunte a tu cerebro.

### 3. Hook en settings (`~/.claude/settings.json`)

Anade el hook `Stop` (merge con tu config existente):

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/ingest-turn.sh"
          }
        ]
      }
    ]
  }
}
```

### 4. Protocolo en CLAUDE.md (`~/.claude/CLAUDE.md`)

Copia el contenido de `plugin/claude-code/SKILL.md` al final de tu `~/.claude/CLAUDE.md`.

### 5. Variable de entorno

```bash
echo 'export MEMORY_API_KEY="<TU_API_KEY>"' >> ~/.bashrc
source ~/.bashrc
```

## Que hace cada pieza

### Hook de ingestion (pasivo)

Cada vez que Claude Code termina un turno, el hook captura el mensaje del usuario, la respuesta del agente y las tools usadas, y lo envia al endpoint `/ingest_turn`. El cerebro decide si merece ser guardado usando un clasificador (DeepSeek). Es **fire-and-forget**: si el cerebro no responde, el hook no bloquea.

### Protocolo MCP (activo)

Las `serverInstructions` del MCP server le dicen al agente cuando guardar proactivamente: decisiones, errores, patrones, tareas. El `CLAUDE.md` refuerza esto con ejemplos y calibracion de importancia.

### Tres capas complementarias

| Capa | Mecanismo | Alcance |
|------|-----------|---------|
| **serverInstructions** | Campo `instructions` del MCP | Todos los clientes MCP |
| **CLAUDE.md** | Instrucciones de usuario | Solo Claude Code |
| **Hook Stop** | Shell script fire-and-forget | Solo Claude Code |

La primera capa funciona con cualquier cliente MCP (Cline, custom agents, etc.). Las otras dos son especificas de Claude Code.

## Troubleshooting

### memoryBrain no aparece en el panel MCP

- Verifica que `MEMORY_API_KEY` esta exportada: `echo $MEMORY_API_KEY`
- Verifica que el cerebro responde: `curl http://<IP>:8050/health`
- Revisa `~/.claude/.mcp.json` — debe tener la entrada `memoryBrain`

### El hook no envia turnos

- Revisa el log: `cat ~/.claude/ai-memory-ingest.log`
- Verifica que jq esta instalado: `which jq`
- Verifica que el hook es ejecutable: `ls -la ~/.claude/hooks/ingest-turn.sh`

### "Project not found" en el cerebro

Normal si es la primera vez que usas ese proyecto. El cerebro crea el proyecto automaticamente cuando guardas la primera memoria.
