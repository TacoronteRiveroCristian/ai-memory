# AI Memory

Proyecto autocontenido para la stack de memoria:

- `docker-compose.yaml`
- `.env.example`
- `volumes/`
- `scripts/`
- `api-server/`, `mem0/`, `reflection-worker/`

Uso rápido:

```bash
cp .env.example .env
docker compose up -d
```

Comandos útiles:

```bash
docker compose ps
./scripts/health_check.sh
./scripts/smoke_test_local.sh
./scripts/backup.sh
```

Documentación útil:

- `docs/MCP_TOOLS.md`: qué hace cada tool MCP, cuándo usarla y cómo invocarla.
- `docs/CEREBRO_CONSCIENTE_SUPERDOCS.md`: arquitectura completa y funcionamiento del sistema.
