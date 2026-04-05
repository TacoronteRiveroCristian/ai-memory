# Postgres Startup & Brain-UI Cascade Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent pgvector/postgres from failing to start on WSL2/Ubuntu due to stale `postmaster.pid`, and fix the brain-ui cascade failure that results from it.

**Architecture:** A bash entrypoint wrapper script is mounted read-only into the postgres container and set as its entrypoint. It removes any stale `postmaster.pid` and `postmaster.opts` files before handing off to the official postgres docker-entrypoint. The brain-ui `depends_on` is relaxed from `service_healthy` to `service_started` since it serves static files and does not need the backend to be healthy.

**Tech Stack:** Docker Compose, bash, pgvector/pgvector:pg16 image.

---

### Task 1: Create feature branch

**Files:**
- No files modified

- [ ] **Step 1: Create and switch to the fix branch**

```bash
git checkout -b fix/postgres-startup-brainui-cascade
```

Expected output:
```
Switched to a new branch 'fix/postgres-startup-brainui-cascade'
```

---

### Task 2: Add the postgres entrypoint wrapper script

**Files:**
- Create: `scripts/postgres-entrypoint.sh`

- [ ] **Step 1: Create the script**

Create `scripts/postgres-entrypoint.sh` with this exact content:

```bash
#!/bin/bash
set -e

# Remove stale postmaster files left by non-graceful shutdown (common on WSL2 and after power loss).
# Postgres refuses to start if postmaster.pid exists but the PID it references is not running.
PGDATA="${PGDATA:-/var/lib/postgresql/data}"

if [ -f "${PGDATA}/postmaster.pid" ]; then
    echo "[entrypoint] Removing stale postmaster.pid from ${PGDATA}"
    rm -f "${PGDATA}/postmaster.pid"
fi

if [ -f "${PGDATA}/postmaster.opts" ]; then
    echo "[entrypoint] Removing stale postmaster.opts from ${PGDATA}"
    rm -f "${PGDATA}/postmaster.opts"
fi

exec docker-entrypoint.sh "$@"
```

- [ ] **Step 2: Make the script executable**

```bash
chmod +x scripts/postgres-entrypoint.sh
```

- [ ] **Step 3: Verify the script is executable and has correct content**

```bash
ls -la scripts/postgres-entrypoint.sh
head -5 scripts/postgres-entrypoint.sh
```

Expected output (first line): `-rwxr-xr-x ...`

- [ ] **Step 4: Commit**

```bash
git add scripts/postgres-entrypoint.sh
git commit -m "fix: add postgres entrypoint wrapper to remove stale postmaster.pid"
```

---

### Task 3: Wire the entrypoint into docker-compose.yaml and tune postgres healthcheck

**Files:**
- Modify: `docker-compose.yaml` (postgres service — lines 21–54)

- [ ] **Step 1: Add entrypoint, volume mount, and start_period to the postgres service**

In `docker-compose.yaml`, the postgres service currently looks like this (abridged):

```yaml
  postgres:
    image: pgvector/pgvector:pg16
    container_name: ai-memory-postgres
    restart: unless-stopped
    shm_size: "64mb"
    networks:
      - backend
    ports:
      - "127.0.0.1:5434:5432"
    volumes:
      - ${AI_MEMORY_POSTGRES_VOLUME:-./volumes/postgres}:/var/lib/postgresql/data
      - ./config/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    environment:
      ...
    command: >
      postgres
        -c shared_buffers=128MB
        ...
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 10
```

Replace the postgres service block with (keep all environment vars and command flags unchanged, only adding `entrypoint`, a new volume line, and `start_period`):

```yaml
  postgres:
    image: pgvector/pgvector:pg16
    container_name: ai-memory-postgres
    restart: unless-stopped
    shm_size: "64mb"
    networks:
      - backend
    ports:
      - "127.0.0.1:5434:5432"
    entrypoint: ["/scripts/postgres-entrypoint.sh"]
    volumes:
      - ${AI_MEMORY_POSTGRES_VOLUME:-./volumes/postgres}:/var/lib/postgresql/data
      - ./config/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
      - ./scripts/postgres-entrypoint.sh:/scripts/postgres-entrypoint.sh:ro
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8"
    command: >
      postgres
        -c shared_buffers=128MB
        -c effective_cache_size=512MB
        -c work_mem=4MB
        -c maintenance_work_mem=32MB
        -c max_connections=50
        -c wal_buffers=8MB
        -c checkpoint_completion_target=0.9
        -c random_page_cost=1.1
        -c effective_io_concurrency=200
        -c synchronous_commit=off
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
```

- [ ] **Step 2: Validate the YAML is well-formed**

```bash
docker compose config --quiet && echo "YAML OK"
```

Expected output: `YAML OK`

If it fails, check for indentation errors around the postgres service block.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yaml
git commit -m "fix: wire postgres entrypoint wrapper and add healthcheck start_period"
```

---

### Task 4: Relax brain-ui depends_on to break the cascade

**Files:**
- Modify: `docker-compose.yaml` (brain-ui service — lines 209–221)

- [ ] **Step 1: Change brain-ui depends_on condition**

In `docker-compose.yaml`, the brain-ui service currently has:

```yaml
  brain-ui:
    build:
      context: ./brain-ui
      args:
        VITE_API_URL: http://localhost:8050
        VITE_API_KEY: ${MEMORY_API_KEY}
    container_name: ai-memory-brain-ui
    restart: unless-stopped
    ports:
      - "3080:80"
    depends_on:
      api-server:
        condition: service_healthy
```

Change only the `condition` line:

```yaml
  brain-ui:
    build:
      context: ./brain-ui
      args:
        VITE_API_URL: http://localhost:8050
        VITE_API_KEY: ${MEMORY_API_KEY}
    container_name: ai-memory-brain-ui
    restart: unless-stopped
    ports:
      - "3080:80"
    depends_on:
      api-server:
        condition: service_started
```

- [ ] **Step 2: Validate YAML**

```bash
docker compose config --quiet && echo "YAML OK"
```

Expected output: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yaml
git commit -m "fix: relax brain-ui depends_on to service_started to prevent cascade failure"
```

---

### Task 5: Verify the fix end-to-end

**Files:**
- No files modified

- [ ] **Step 1: Bring the stack up**

```bash
make stack-up
```

Wait ~60 seconds for all services to initialize.

- [ ] **Step 2: Check all services are running and healthy**

```bash
docker ps --format "  {{.Names}}: {{.Status}}" | grep ai-memory
```

Expected: all services show `Up` and those with healthchecks show `(healthy)`. `ai-memory-postgres` must be `(healthy)`.

- [ ] **Step 3: Verify the API is reachable**

```bash
curl -s http://127.0.0.1:8050/health
```

Expected: `{"status":"ok"}` or similar JSON response.

- [ ] **Step 4: Verify the brain-ui is reachable**

```bash
curl -sI http://127.0.0.1:3080 | head -5
```

Expected: `HTTP/1.1 200 OK`

- [ ] **Step 5: Simulate a stale PID and verify postgres still starts**

```bash
# Bring stack down
make stack-down

# Create a fake stale PID file
touch volumes/postgres/postmaster.pid

# Bring stack back up
make stack-up

# Check postgres is healthy
docker ps --format "{{.Names}}: {{.Status}}" | grep postgres
```

Expected: `ai-memory-postgres: Up ... (healthy)` — the wrapper script removed the stale file.

- [ ] **Step 6: Clean up the fake PID if it still exists**

```bash
rm -f volumes/postgres/postmaster.pid
```

---

### Task 6: Open PR

- [ ] **Step 1: Push the branch**

```bash
git push -u origin fix/postgres-startup-brainui-cascade
```

- [ ] **Step 2: Create the PR**

```bash
gh pr create \
  --title "fix: postgres startup failure and brain-ui cascade on WSL2/Ubuntu" \
  --body "$(cat <<'EOF'
## Problem

- pgvector/postgres refuses to start after non-graceful shutdown (WSL2 PC restart, power loss) because a stale \`postmaster.pid\` is left in the data volume
- brain-ui never starts when postgres is unhealthy due to a depends_on cascade

## Solution

- Added \`scripts/postgres-entrypoint.sh\`: removes stale \`postmaster.pid\`/\`postmaster.opts\` before handing off to the official postgres entrypoint
- Added \`start_period: 30s\` to postgres healthcheck for reliable first-boot initialization
- Changed brain-ui \`depends_on\` from \`service_healthy\` to \`service_started\` (UI is static, no backend required to serve files)

## Test plan

- [ ] \`make stack-up\` brings all services to healthy
- [ ] Simulating stale PID (\`touch volumes/postgres/postmaster.pid && make stack-up\`) — postgres still starts
- [ ] Brain-UI reachable at http://localhost:3080

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
