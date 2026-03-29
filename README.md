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
./scripts/backup.sh
```
