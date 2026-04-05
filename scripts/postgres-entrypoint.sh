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
