# Design: Fix Postgres Startup & Brain-UI Cascade on WSL2/Ubuntu

**Date:** 2026-04-05  
**Status:** Approved

## Problem

Two related issues occur every time the stack is started on WSL2 (and occasionally on native Ubuntu after unclean shutdown):

1. **Postgres (pgvector) does not start** — Docker Desktop on WSL2 stops containers non-gracefully on Windows restart, leaving a stale `postmaster.pid` file inside `./volumes/postgres/`. On the next `docker compose up`, postgres detects the PID file, checks that the PID is not running (new container), and refuses to start. This is a recurring problem on every PC restart.

2. **Brain-UI is not accessible** — `brain-ui` has a `depends_on: api-server: condition: service_healthy`, and `api-server` has `depends_on: postgres: condition: service_healthy`. Postgres failure cascades: postgres unhealthy → api-server never becomes healthy → brain-ui never starts. The UI is a static SPA served by nginx and does not require the backend to be healthy to serve its files.

## Chosen Approach: Option A — Entrypoint Wrapper + Healthcheck Tuning + Cascade Fix

### 1. Postgres stale PID cleanup

Add a custom entrypoint script `scripts/postgres-entrypoint.sh` that:
- Removes `postmaster.pid` (and `postmaster.opts`) from `$PGDATA` if they exist
- Then hands off to the official `docker-entrypoint.sh postgres` with all original args

Mount this script into the postgres container and set it as the entrypoint. The existing `command:` block (with tuning flags) is preserved unchanged.

This fix is host-OS agnostic — it runs inside the container and works identically on WSL2 and native Ubuntu.

### 2. Postgres healthcheck start_period

Add `start_period: 30s` to the postgres healthcheck. On first boot (empty volume), postgres runs `initdb` which takes longer than on subsequent starts. The start_period prevents false-negative health failures during initialization.

### 3. Brain-UI depends_on relaxed

Change `brain-ui` depends_on `api-server` condition from `service_healthy` to `service_started`. The UI is static HTML/JS/CSS served by nginx — it can be served independently of backend health. The browser-side JS will show appropriate error states if the API is unreachable.

## Files Changed

| File | Change |
|------|--------|
| `scripts/postgres-entrypoint.sh` | New — removes stale PID then execs official entrypoint |
| `docker-compose.yaml` | Add entrypoint + start_period to postgres; relax brain-ui depends_on |

## Non-goals

- No changes to postgres data storage model (bind mounts kept as-is)
- No changes to postgres tuning parameters
- No changes to brain-ui nginx config or VITE env vars
- No named volume migration (Option B)

## Testing

After the fix:
1. `make stack-up` should bring all services to healthy on a fresh start
2. Simulate stale PID: `touch volumes/postgres/postmaster.pid && make stack-up` — postgres should still start
3. Brain-UI reachable at `http://localhost:3080` even before api-server is fully healthy
