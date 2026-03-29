# 🧠 Cerebro de Memoria Persistente para Agentes IA — Raspberry Pi 4 (8GB)

> Stack completo Docker Compose para ARM64, embeddings vía OpenAI, exposición con Cloudflare Tunnel

---

## 📊 Resumen ejecutivo: ¿Cabe en la Pi 4?

**Respuesta corta: SÍ**, con el stack LITE y embeddings vía OpenAI API. El stack completo con HuggingFace TEI (embeddings locales) **NO** — consume demasiada RAM.

| Servicio | RAM idle (ARM64) | RAM pico | Incluido en LITE |
|---|---|---|---|
| Qdrant | ~120 MB | ~400 MB | ✅ |
| PostgreSQL + pgvector | ~80 MB | ~200 MB | ✅ |
| Redis | ~15 MB | ~50 MB | ✅ |
| Mem0 API Server | ~150 MB | ~300 MB | ✅ |
| API Server MCP custom | ~100 MB | ~200 MB | ✅ |
| Nginx | ~5 MB | ~20 MB | ✅ |
| Cloudflared | ~30 MB | ~60 MB | ✅ |
| HuggingFace TEI (nomic) | ~550 MB | ~1.2 GB | ❌ Solo PC |
| **TOTAL LITE** | **~500 MB** | **~1.2 GB** | ✅ Cómodo en 8GB |
| **TOTAL FULL** | **~1 GB** | **~2.5 GB** | ✅ Cómodo en 16GB+ |

Con el stack LITE en la Pi 4 te quedan ~6GB libres para el SO y picos de carga. 🎉

---

## ⚠️ Compatibilidad ARM64 de cada imagen

| Imagen | ARM64 oficial | Notas |
|---|---|---|
| `qdrant/qdrant` | ✅ Sí | Soporte ARM64 desde v1.7+ |
| `pgvector/pgvector:pg16` | ✅ Sí | Multi-arch oficial |
| `redis:8-alpine` | ✅ Sí | Alpine es multi-arch siempre |
| `mem0/mem0-api-server` | ⚠️ Verificar | Si no hay ARM64, usar build local |
| `nginx:alpine` | ✅ Sí | Multi-arch |
| `cloudflare/cloudflared` | ✅ Sí | Arm64 disponible |
| `ghcr.io/huggingface/text-embeddings-inference:cpu-*` | ❌ Solo x86 | Solo para PC, no Pi |

> **Si `mem0/mem0-api-server` no tiene ARM64**: ver sección "Alternativa sin Mem0" al final.

---

## 💽 Paso 1: Boot desde SSD en Raspberry Pi 4

Esto es **crítico** — las bases de datos en SD card son lentas y la desgastan en semanas.

### Preparar el bootloader (solo Pi 4, diferente a Pi 5)

```bash
# En la Pi 4 con Raspberry Pi OS ya instalado en SD
sudo raspi-config
# → Advanced Options → Boot Order → USB Boot

# O directamente:
sudo -E rpi-eeprom-config --edit
# Cambiar BOOT_ORDER=0xf41  (USB primero, luego SD)
sudo reboot
```

### Clonar SD al SSD

```bash
# Instalar rpi-clone
sudo apt install git
git clone https://github.com/billw2/rpi-clone.git
cd rpi-clone
sudo cp rpi-clone /usr/local/sbin

# Conectar SSD por USB3 (aparecerá como /dev/sda normalmente)
lsblk  # confirmar device

# Clonar (reemplaza sda por tu device)
sudo rpi-clone sda
```

### Alternativa: instalar Ubuntu Server 64-bit directamente en SSD

```bash
# Desde Raspberry Pi Imager en tu PC:
# - OS: Other general-purpose OS → Ubuntu → Ubuntu Server 24.04 LTS (64-bit)
# - Storage: tu SSD (via adaptador USB)
# - Settings: SSH habilitado, usuario/pass, WiFi si necesario
```

### Optimizar SSD en Linux

```bash
# Habilitar TRIM periódico (importante para vida del SSD)
sudo systemctl enable fstrim.timer
sudo systemctl start fstrim.timer

# Verificar que está activo
sudo systemctl status fstrim.timer

# Configurar swappiness baja (para no desgastar SSD con swap excesivo)
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Configurar SWAP en SSD (recomendado: 4GB)

```bash
# Crear swap de 4GB en el SSD
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Hacer permanente
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 🏗️ Estructura de directorios del proyecto

```
~/ai-memory-brain/
├── docker-compose.lite.yml       # Para Raspberry Pi 4
├── docker-compose.full.yml       # Para PC x86_64
├── .env                          # Variables de entorno
├── config/
│   ├── nginx/
│   │   └── nginx.conf
│   ├── cloudflared/
│   │   └── config.yml
│   └── postgres/
│       └── init.sql
├── api-server/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py
└── scripts/
    ├── backup.sh
    ├── ingest_markdown.py
    ├── ingest_codebase.py
    └── health_check.sh
```

```bash
# Crear estructura
mkdir -p ~/ai-memory-brain/{config/{nginx,cloudflared,postgres},api-server,scripts}
cd ~/ai-memory-brain
```

---

## 🐳 COMPOSE A — LITE (Raspberry Pi 4, 8GB RAM, ARM64)

```yaml
# docker-compose.lite.yml
name: ai-memory-lite

services:

  # ── Vector Database ──────────────────────────────────────
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    restart: unless-stopped
    networks: [backend]
    volumes:
      - /mnt/ssd/qdrant_data:/qdrant/storage  # SSD montado
    environment:
      QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}
      QDRANT__TELEMETRY_DISABLED: "true"
      QDRANT__STORAGE__ON_DISK_PAYLOAD: "true"  # Reduce RAM
      QDRANT__STORAGE__OPTIMIZERS__MEMMAP_THRESHOLD_KB: "20000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
        reservations:
          memory: 128M

  # ── PostgreSQL + pgvector ─────────────────────────────────
  postgres:
    image: pgvector/pgvector:pg16
    container_name: postgres
    restart: unless-stopped
    shm_size: "64mb"
    networks: [backend]
    volumes:
      - /mnt/ssd/postgres_data:/var/lib/postgresql/data
      - ./config/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-memoryuser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-memorydb}
      # Tuning para ARM/poca RAM
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
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-memoryuser}"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
        reservations:
          memory: 80M

  # ── Session Cache ─────────────────────────────────────────
  redis:
    image: redis:8-alpine
    container_name: redis
    restart: unless-stopped
    networks: [backend]
    volumes:
      - /mnt/ssd/redis_data:/data
    command: >
      redis-server
        --save 300 1
        --loglevel warning
        --requirepass ${REDIS_PASSWORD}
        --maxmemory 128mb
        --maxmemory-policy allkeys-lru
        --appendonly yes
        --appendfsync everysec
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 192M
          cpus: "0.5"
        reservations:
          memory: 15M

  # ── Mem0 Memory Orchestration ─────────────────────────────
  mem0:
    image: mem0/mem0-api-server:latest
    container_name: mem0
    restart: unless-stopped
    networks: [backend, frontend]
    environment:
      # OpenAI para embeddings (no necesita TEI local)
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      # Vector DB
      QDRANT_HOST: qdrant
      QDRANT_PORT: "6333"
      QDRANT_API_KEY: ${QDRANT_API_KEY}
      # History DB
      POSTGRES_HOST: postgres
      POSTGRES_PORT: "5432"
      POSTGRES_DB: ${POSTGRES_DB:-memorydb}
      POSTGRES_USER: ${POSTGRES_USER:-memoryuser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    depends_on:
      postgres: { condition: service_healthy }
      qdrant:   { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 20s
      timeout: 10s
      retries: 5
      start_period: 60s
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
        reservations:
          memory: 150M

  # ── MCP + REST API Server (custom Python) ─────────────────
  api-server:
    build:
      context: ./api-server
      dockerfile: Dockerfile
      platforms: [linux/arm64]
    container_name: api-server
    restart: unless-stopped
    networks: [frontend, backend]
    environment:
      QDRANT_HOST: qdrant
      QDRANT_PORT: "6333"
      QDRANT_API_KEY: ${QDRANT_API_KEY}
      POSTGRES_URL: "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"
      REDIS_URL: "redis://:${REDIS_PASSWORD}@redis:6379/0"
      MEM0_URL: "http://mem0:8000"
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      EMBEDDING_MODEL: "text-embedding-3-small"
      API_KEY: ${MEMORY_API_KEY}
      LOG_LEVEL: "INFO"
    depends_on:
      qdrant:   { condition: service_healthy }
      postgres: { condition: service_healthy }
      redis:    { condition: service_healthy }
      mem0:     { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8050/health"]
      interval: 20s
      timeout: 5s
      retries: 3
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 384M
          cpus: "1.5"
        reservations:
          memory: 100M

  # ── Reverse Proxy ─────────────────────────────────────────
  nginx:
    image: nginx:alpine
    container_name: nginx
    restart: unless-stopped
    networks: [frontend]
    volumes:
      - ./config/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on: [api-server]
    deploy:
      resources:
        limits:
          memory: 64M
          cpus: "0.25"

  # ── Cloudflare Tunnel ──────────────────────────────────────
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared
    restart: unless-stopped
    networks: [frontend]
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on: [nginx]
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: "0.25"

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # Sin acceso a internet para DBs

volumes: {}
# Nota: usamos bind mounts a /mnt/ssd/ en vez de named volumes
# para asegurar que todo va al SSD, no a la SD card
```

---

## 🖥️ COMPOSE B — FULL (PC x86_64, 16-32GB RAM)

```yaml
# docker-compose.full.yml
name: ai-memory-full

services:

  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    restart: unless-stopped
    networks: [backend]
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}
      QDRANT__TELEMETRY_DISABLED: "true"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
      interval: 10s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"

  postgres:
    image: pgvector/pgvector:pg16
    container_name: postgres
    restart: unless-stopped
    shm_size: "256mb"
    networks: [backend]
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./config/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-memoryuser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-memorydb}
    command: >
      postgres
        -c shared_buffers=512MB
        -c effective_cache_size=2GB
        -c work_mem=16MB
        -c maintenance_work_mem=128MB
        -c max_connections=100
        -c wal_buffers=32MB
        -c checkpoint_completion_target=0.9
        -c random_page_cost=1.1
        -c effective_io_concurrency=200
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-memoryuser}"]
      interval: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"

  redis:
    image: redis:8-alpine
    container_name: redis
    restart: unless-stopped
    networks: [backend]
    volumes:
      - redis_data:/data
    command: >
      redis-server
        --save 60 1
        --loglevel warning
        --requirepass ${REDIS_PASSWORD}
        --maxmemory 512mb
        --maxmemory-policy allkeys-lru
        --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 512M

  # ── Embeddings locales (SOLO x86_64, no ARM) ─────────────
  embeddings:
    image: ghcr.io/huggingface/text-embeddings-inference:cpu-1.2
    container_name: embeddings
    restart: unless-stopped
    platform: linux/amd64
    networks: [backend]
    volumes:
      - embedding_models:/data
    command: --model-id nomic-ai/nomic-embed-text-v1.5 --dtype float32
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/health"]
      interval: 30s
      start_period: 120s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"

  mem0:
    image: mem0/mem0-api-server:latest
    container_name: mem0
    restart: unless-stopped
    networks: [backend, frontend]
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      # Para usar embeddings locales TEI en vez de OpenAI:
      # OPENAI_API_BASE: http://embeddings:80/v1
      # EMBEDDING_MODEL: nomic-ai/nomic-embed-text-v1.5
      QDRANT_HOST: qdrant
      QDRANT_PORT: "6333"
      QDRANT_API_KEY: ${QDRANT_API_KEY}
      POSTGRES_HOST: postgres
      POSTGRES_PORT: "5432"
      POSTGRES_DB: ${POSTGRES_DB:-memorydb}
      POSTGRES_USER: ${POSTGRES_USER:-memoryuser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    depends_on:
      postgres:   { condition: service_healthy }
      qdrant:     { condition: service_healthy }
      embeddings: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 15s
      start_period: 60s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "2.0"

  api-server:
    build:
      context: ./api-server
      dockerfile: Dockerfile
    container_name: api-server
    restart: unless-stopped
    networks: [frontend, backend]
    environment:
      QDRANT_HOST: qdrant
      QDRANT_PORT: "6333"
      QDRANT_API_KEY: ${QDRANT_API_KEY}
      POSTGRES_URL: "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"
      REDIS_URL: "redis://:${REDIS_PASSWORD}@redis:6379/0"
      MEM0_URL: "http://mem0:8000"
      EMBEDDINGS_URL: "http://embeddings:80"  # TEI local
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      EMBEDDING_MODEL: "text-embedding-3-small"  # fallback si TEI falla
      API_KEY: ${MEMORY_API_KEY}
    depends_on:
      qdrant:     { condition: service_healthy }
      postgres:   { condition: service_healthy }
      redis:      { condition: service_healthy }
      mem0:       { condition: service_healthy }
      embeddings: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8050/health"]
      interval: 15s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "2.0"

  nginx:
    image: nginx:alpine
    container_name: nginx
    restart: unless-stopped
    networks: [frontend]
    volumes:
      - ./config/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on: [api-server]

  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared
    restart: unless-stopped
    networks: [frontend]
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on: [nginx]

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true

volumes:
  qdrant_data:
  postgres_data:
  redis_data:
  embedding_models:
```

---

## ⚙️ Archivos de configuración

### `.env`

```env
# OpenAI
OPENAI_API_KEY=sk-proj-...

# Bases de datos
POSTGRES_USER=memoryuser
POSTGRES_PASSWORD=CAMBIA_ESTO_password_muy_seguro
POSTGRES_DB=memorydb

# Servicios internos
QDRANT_API_KEY=CAMBIA_ESTO_qdrant_key_32chars
REDIS_PASSWORD=CAMBIA_ESTO_redis_password

# API pública
MEMORY_API_KEY=CAMBIA_ESTO_api_key_para_agentes

# Cloudflare
CLOUDFLARE_TUNNEL_TOKEN=eyJhI...tu_tunnel_token_aqui
```

### `config/postgres/init.sql`

```sql
-- Habilitar extensiones
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Tabla de proyectos
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de tareas (estado de workflows)
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    state VARCHAR(50) DEFAULT 'pending',  -- pending, active, blocked, done, cancelled
    priority INTEGER DEFAULT 5,
    agent_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Tabla de decisiones/contexto de proyecto
CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    context TEXT,
    decision TEXT NOT NULL,
    rationale TEXT,
    alternatives TEXT,
    agent_id VARCHAR(100),
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de errores conocidos
CREATE TABLE IF NOT EXISTS known_errors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id),
    error_signature VARCHAR(500),
    description TEXT NOT NULL,
    solution TEXT,
    occurrence_count INTEGER DEFAULT 1,
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

-- Tabla de memoria episódica (log de acciones importantes)
CREATE TABLE IF NOT EXISTS memory_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id),
    agent_id VARCHAR(100) NOT NULL,
    action_type VARCHAR(100),  -- code_change, decision, error_fix, refactor, etc.
    summary TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    importance FLOAT DEFAULT 0.5,
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_log_project ON memory_log(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_log_agent ON memory_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_log_created ON memory_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_known_errors_sig ON known_errors USING gin(to_tsvector('english', error_signature));

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### `config/nginx/nginx.conf`

```nginx
worker_processes auto;
events { worker_connections 512; }

http {
    # Rate limiting zones
    limit_req_zone $binary_remote_addr zone=api:10m rate=20r/m;
    limit_req_zone $binary_remote_addr zone=mcp:10m rate=60r/m;
    limit_conn_zone $binary_remote_addr zone=conn:10m;

    # Logging
    log_format main '$remote_addr - $request "$status" $body_bytes_sent';
    access_log /var/log/nginx/access.log main;

    # Gzip
    gzip on;
    gzip_types application/json text/plain;

    # Auth map (API key validation)
    map $http_x_api_key $api_key_valid {
        default 0;
        "${MEMORY_API_KEY}" 1;  # Nginx no expande env vars así, ver nota abajo
    }

    server {
        listen 80;

        # Security headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header X-XSS-Protection "1; mode=block";

        # Health check público (sin auth)
        location /health {
            proxy_pass http://api-server:8050/health;
            access_log off;
        }

        # MCP endpoint (SSE - requiere config especial)
        location /mcp {
            limit_req zone=mcp burst=20 nodelay;
            limit_conn conn 10;

            proxy_pass http://api-server:8050;
            proxy_http_version 1.1;

            # SSE requirements
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 86400s;
            proxy_set_header Connection '';
            chunked_transfer_encoding off;

            # Forward headers
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-API-Key $http_x_api_key;
        }

        # REST API general
        location /api/ {
            limit_req zone=api burst=10 nodelay;

            proxy_pass http://api-server:8050/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-API-Key $http_x_api_key;
            proxy_read_timeout 30s;
        }

        # Mem0 API (si quieres acceso directo)
        location /mem0/ {
            limit_req zone=api burst=5 nodelay;
            proxy_pass http://mem0:8000/;
            proxy_set_header Host $host;
        }
    }
}
```

### `config/cloudflared/config.yml`

```yaml
tunnel: TU_TUNNEL_ID
credentials-file: /etc/cloudflared/credentials.json

ingress:
  # MCP + API principal
  - hostname: memory.tudominio.com
    service: http://nginx:80

  # Qdrant UI (solo para acceso admin, proteger con Cloudflare Access)
  - hostname: qdrant.tudominio.com
    service: http://qdrant:6333

  # Catch-all
  - service: http_status:404
```

---

## 🐍 Servidor MCP Python completo

### `api-server/Dockerfile`

```dockerfile
FROM python:3.12-slim

# Optimizado para ARM64
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencias sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8050

CMD ["python", "server.py"]
```

### `api-server/requirements.txt`

```
mcp[cli]>=1.5.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
qdrant-client>=1.12.0
asyncpg>=0.30.0
redis>=5.2.0
openai>=1.58.0
mem0ai>=0.1.0
httpx>=0.27.0
pydantic>=2.10.0
python-dotenv>=1.0.0
```

### `api-server/server.py`

```python
"""
AI Memory Brain - MCP + REST API Server
Compatible con Claude Code, Codex CLI, Cursor, Cline y VSCode agents
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Any

import asyncpg
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from openai import AsyncOpenAI
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, SearchRequest,
    PayloadSchemaType
)

# ── Configuración ──────────────────────────────────────────

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

QDRANT_HOST       = os.environ["QDRANT_HOST"]
QDRANT_PORT       = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_API_KEY    = os.environ["QDRANT_API_KEY"]
POSTGRES_URL      = os.environ["POSTGRES_URL"]
REDIS_URL         = os.environ["REDIS_URL"]
OPENAI_API_KEY    = os.environ["OPENAI_API_KEY"]
EMBEDDING_MODEL   = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
API_KEY           = os.environ["API_KEY"]
COLLECTION_NAME   = "memories"
VECTOR_DIM        = 1536  # text-embedding-3-small

# ── Clientes globales ──────────────────────────────────────

qdrant: Optional[AsyncQdrantClient] = None
pg_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None
openai_client: Optional[AsyncOpenAI] = None

# ── FastAPI App ────────────────────────────────────────────

app = FastAPI(title="AI Memory Brain", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── MCP Server ─────────────────────────────────────────────

mcp = FastMCP("AIMemoryBrain")

# ── Helpers ────────────────────────────────────────────────

async def get_embedding(text: str) -> list[float]:
    """Genera embedding via OpenAI API."""
    cache_key = f"embed:{hash(text)}"
    
    # Check cache
    if redis_client:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    
    response = await openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL
    )
    embedding = response.data[0].embedding
    
    # Cache por 1 hora
    if redis_client:
        await redis_client.setex(cache_key, 3600, json.dumps(embedding))
    
    return embedding


def verify_api_key(x_api_key: str = Header(None)) -> bool:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ── Inicialización DB ──────────────────────────────────────

async def init_qdrant():
    """Crea la colección Qdrant si no existe."""
    global qdrant
    qdrant = AsyncQdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY,
    )
    
    collections = await qdrant.get_collections()
    names = [c.name for c in collections.collections]
    
    if COLLECTION_NAME not in names:
        await qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_DIM,
                distance=Distance.COSINE,
                on_disk=True,  # Importante para Pi 4 con SSD
            )
        )
        # Crear índices de payload para filtrado rápido
        for field in ["project_id", "agent_id", "memory_type", "tags"]:
            await qdrant.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        logger.info(f"Colección '{COLLECTION_NAME}' creada en Qdrant")
    else:
        logger.info(f"Colección '{COLLECTION_NAME}' ya existe")


# ── MCP Tools ──────────────────────────────────────────────

@mcp.tool()
async def store_memory(
    content: str,
    project: str,
    memory_type: str = "general",
    tags: str = "",
    importance: float = 0.7,
    agent_id: str = "unknown"
) -> str:
    """
    Almacena una nueva memoria persistente.
    
    Args:
        content: El contenido a recordar (decisión, error, contexto, etc.)
        project: Nombre del proyecto al que pertenece
        memory_type: Tipo de memoria: 'decision', 'error', 'architecture', 
                     'context', 'task', 'general'
        tags: Tags separados por comas (ej: "python,fastapi,auth")
        importance: Importancia de 0.0 a 1.0 (default: 0.7)
        agent_id: ID del agente que almacena (ej: 'claude-code', 'codex')
    
    Returns:
        Confirmación con el ID de la memoria almacenada
    """
    try:
        embedding = await get_embedding(content)
        memory_id = str(uuid.uuid4())
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]
        
        payload = {
            "content": content,
            "project_id": project,
            "agent_id": agent_id,
            "memory_type": memory_type,
            "tags": tags_list,
            "importance": importance,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "access_count": 0,
        }
        
        await qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(id=memory_id, vector=embedding, payload=payload)]
        )
        
        # También registrar en PostgreSQL para historial
        if pg_pool:
            async with pg_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO memory_log 
                    (id, project_id, agent_id, action_type, summary, importance, tags)
                    VALUES ($1, 
                        (SELECT id FROM projects WHERE name=$2 LIMIT 1),
                        $3, $4, $5, $6, $7)
                    ON CONFLICT DO NOTHING
                """, uuid.UUID(memory_id), project, agent_id,
                    memory_type, content[:500], importance, tags_list)
        
        logger.info(f"Memoria almacenada: {memory_id} | proyecto={project}")
        return f"✅ Memoria almacenada con ID: {memory_id}\nProyecto: {project} | Tipo: {memory_type}"
    
    except Exception as e:
        logger.error(f"Error almacenando memoria: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def search_memory(
    query: str,
    project: Optional[str] = None,
    memory_type: Optional[str] = None,
    limit: int = 8
) -> str:
    """
    Busca memorias relevantes por similitud semántica.
    
    Args:
        query: Descripción de lo que buscas en lenguaje natural
        project: Filtrar por proyecto específico (opcional)
        memory_type: Filtrar por tipo: 'decision', 'error', 'architecture', etc.
        limit: Número máximo de resultados (default: 8)
    
    Returns:
        Lista de memorias relevantes con score de relevancia
    """
    try:
        embedding = await get_embedding(query)
        
        # Construir filtros
        conditions = []
        if project:
            conditions.append(FieldCondition(
                key="project_id", match=MatchValue(value=project)
            ))
        if memory_type:
            conditions.append(FieldCondition(
                key="memory_type", match=MatchValue(value=memory_type)
            ))
        
        search_filter = Filter(must=conditions) if conditions else None
        
        results = await qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=embedding,
            query_filter=search_filter,
            limit=limit,
            with_payload=True,
            score_threshold=0.4,
        )
        
        if not results:
            return f"No encontré memorias relevantes para: '{query}'"
        
        output = [f"🔍 {len(results)} memorias relevantes para '{query}':\n"]
        for i, r in enumerate(results, 1):
            p = r.payload
            output.append(
                f"\n{'─'*50}\n"
                f"**[{i}] Score: {r.score:.3f}** | Tipo: {p.get('memory_type','?')} | "
                f"Proyecto: {p.get('project_id','?')}\n"
                f"{p.get('content','')}\n"
                f"Tags: {', '.join(p.get('tags', []))} | "
                f"Creado: {p.get('created_at','?')[:10]}"
            )
        
        return "\n".join(output)
    
    except Exception as e:
        logger.error(f"Error buscando memorias: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_project_context(project_name: str) -> str:
    """
    Recupera el contexto completo de un proyecto: memorias recientes,
    tareas activas, decisiones de arquitectura y errores conocidos.
    
    Args:
        project_name: Nombre del proyecto
    
    Returns:
        Resumen completo del estado del proyecto
    """
    try:
        output = [f"📁 CONTEXTO DEL PROYECTO: {project_name}\n{'='*50}"]
        
        # 1. Tareas activas desde PostgreSQL
        if pg_pool:
            async with pg_pool.acquire() as conn:
                tasks = await conn.fetch("""
                    SELECT t.title, t.state, t.priority, t.description, t.agent_id
                    FROM tasks t
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.name = $1 AND t.state NOT IN ('done', 'cancelled')
                    ORDER BY t.priority DESC, t.created_at DESC
                    LIMIT 10
                """, project_name)
                
                if tasks:
                    output.append("\n📋 TAREAS ACTIVAS:")
                    for t in tasks:
                        output.append(
                            f"  [{t['state'].upper()}] {t['title']} "
                            f"(prioridad: {t['priority']}, agente: {t['agent_id']})"
                        )
                
                # Decisiones recientes
                decisions = await conn.fetch("""
                    SELECT d.title, d.decision, d.rationale, d.created_at
                    FROM decisions d
                    JOIN projects p ON d.project_id = p.id
                    WHERE p.name = $1
                    ORDER BY d.created_at DESC
                    LIMIT 5
                """, project_name)
                
                if decisions:
                    output.append("\n🏛️ DECISIONES RECIENTES:")
                    for d in decisions:
                        output.append(
                            f"  • {d['title']}: {d['decision']}\n"
                            f"    Rationale: {d['rationale'] or 'N/A'}"
                        )
        
        # 2. Memorias semánticas del proyecto (Qdrant)
        embedding = await get_embedding(f"context architecture overview {project_name}")
        results = await qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=embedding,
            query_filter=Filter(must=[
                FieldCondition(key="project_id", match=MatchValue(value=project_name))
            ]),
            limit=5,
            with_payload=True,
            score_threshold=0.3,
        )
        
        if results:
            output.append("\n🧠 MEMORIAS RELEVANTES:")
            for r in results:
                output.append(f"  • [{r.payload.get('memory_type','?')}] {r.payload.get('content','')[:200]}")
        
        if len(output) == 1:
            output.append("\n⚠️ No hay contexto registrado para este proyecto todavía.")
            output.append("Usa store_memory para empezar a registrar contexto.")
        
        return "\n".join(output)
    
    except Exception as e:
        logger.error(f"Error obteniendo contexto: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def update_task_state(
    task_title: str,
    project: str,
    new_state: str,
    details: str = "",
    agent_id: str = "unknown"
) -> str:
    """
    Crea o actualiza el estado de una tarea en el proyecto.
    
    Args:
        task_title: Título de la tarea
        project: Nombre del proyecto
        new_state: Estado: 'pending', 'active', 'blocked', 'done', 'cancelled'
        details: Detalles adicionales o motivo del cambio
        agent_id: Agente que realiza el cambio
    
    Returns:
        Confirmación del cambio de estado
    """
    valid_states = ['pending', 'active', 'blocked', 'done', 'cancelled']
    if new_state not in valid_states:
        return f"❌ Estado inválido. Usa uno de: {', '.join(valid_states)}"
    
    try:
        if not pg_pool:
            return "❌ Base de datos no disponible"
        
        async with pg_pool.acquire() as conn:
            # Asegurar que el proyecto existe
            project_id = await conn.fetchval("""
                INSERT INTO projects (name) VALUES ($1)
                ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name
                RETURNING id
            """, project)
            
            # Upsert de la tarea
            task_id = await conn.fetchval("""
                INSERT INTO tasks (project_id, title, state, description, agent_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
                RETURNING id
            """, project_id, task_title, new_state, details, agent_id)
            
            if not task_id:
                # La tarea ya existe, actualizar
                await conn.execute("""
                    UPDATE tasks SET state=$1, description=COALESCE(NULLIF($2,''), description),
                    agent_id=$3, completed_at=CASE WHEN $1='done' THEN NOW() ELSE NULL END
                    WHERE title=$4 AND project_id=$5
                """, new_state, details, agent_id, task_title, project_id)
        
        state_emoji = {'pending':'⏳','active':'🔄','blocked':'🚫','done':'✅','cancelled':'❌'}
        return f"{state_emoji.get(new_state,'•')} Tarea '{task_title}' → {new_state.upper()}\nProyecto: {project}"
    
    except Exception as e:
        logger.error(f"Error actualizando tarea: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_active_tasks(project: Optional[str] = None) -> str:
    """
    Lista todas las tareas activas (no completadas ni canceladas).
    
    Args:
        project: Filtrar por proyecto (opcional, muestra todos si no se especifica)
    
    Returns:
        Lista de tareas activas con su estado y proyecto
    """
    try:
        if not pg_pool:
            return "❌ Base de datos no disponible"
        
        async with pg_pool.acquire() as conn:
            if project:
                rows = await conn.fetch("""
                    SELECT t.title, t.state, t.priority, t.agent_id, p.name as project
                    FROM tasks t JOIN projects p ON t.project_id=p.id
                    WHERE p.name=$1 AND t.state NOT IN ('done','cancelled')
                    ORDER BY t.priority DESC, t.created_at
                """, project)
            else:
                rows = await conn.fetch("""
                    SELECT t.title, t.state, t.priority, t.agent_id, p.name as project
                    FROM tasks t JOIN projects p ON t.project_id=p.id
                    WHERE t.state NOT IN ('done','cancelled')
                    ORDER BY p.name, t.priority DESC, t.created_at
                    LIMIT 50
                """)
        
        if not rows:
            return "✅ No hay tareas activas" + (f" en proyecto '{project}'" if project else "")
        
        output = [f"📋 {len(rows)} tareas activas" + (f" — {project}" if project else "") + ":\n"]
        current_project = None
        for r in rows:
            if not project and r['project'] != current_project:
                current_project = r['project']
                output.append(f"\n📁 {current_project}:")
            
            state_emoji = {'pending':'⏳','active':'🔄','blocked':'🚫'}
            output.append(
                f"  {state_emoji.get(r['state'],'•')} [{r['state']}] {r['title']} "
                f"(p:{r['priority']})"
            )
        
        return "\n".join(output)
    
    except Exception as e:
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def store_decision(
    title: str,
    decision: str,
    project: str,
    rationale: str = "",
    alternatives: str = "",
    tags: str = "",
    agent_id: str = "unknown"
) -> str:
    """
    Registra una decisión de arquitectura o técnica importante.
    
    Args:
        title: Título corto de la decisión (ej: "Usar Redis para caché de sesión")
        decision: La decisión tomada
        project: Proyecto al que pertenece
        rationale: Por qué se tomó esta decisión
        alternatives: Alternativas consideradas y por qué se descartaron
        tags: Tags separados por comas
        agent_id: Agente que registra la decisión
    """
    try:
        if not pg_pool:
            return "❌ Base de datos no disponible"
        
        async with pg_pool.acquire() as conn:
            project_id = await conn.fetchval("""
                INSERT INTO projects (name) VALUES ($1)
                ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name
                RETURNING id
            """, project)
            
            tags_list = [t.strip() for t in tags.split(",") if t.strip()]
            
            await conn.execute("""
                INSERT INTO decisions 
                (project_id, title, decision, rationale, alternatives, agent_id, tags)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
            """, project_id, title, decision, rationale, alternatives, agent_id, tags_list)
        
        # También en Qdrant para búsqueda semántica
        content = f"DECISIÓN: {title}\n{decision}\nRationale: {rationale}"
        await store_memory(content, project, "decision", tags, 0.9, agent_id)
        
        return f"🏛️ Decisión registrada: '{title}'\nProyecto: {project}"
    
    except Exception as e:
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def store_error(
    error_description: str,
    solution: str,
    project: str,
    error_signature: str = "",
    tags: str = ""
) -> str:
    """
    Registra un error conocido y su solución para evitar repetirlo.
    
    Args:
        error_description: Descripción del error encontrado
        solution: Cómo se resolvió
        project: Proyecto donde ocurrió
        error_signature: Fragmento del mensaje de error para identificarlo (opcional)
        tags: Tags separados por comas (ej: "docker,networking,dns")
    """
    try:
        if pg_pool:
            async with pg_pool.acquire() as conn:
                project_id = await conn.fetchval("""
                    INSERT INTO projects (name) VALUES ($1)
                    ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name
                    RETURNING id
                """, project)
                
                tags_list = [t.strip() for t in tags.split(",") if t.strip()]
                
                await conn.execute("""
                    INSERT INTO known_errors 
                    (project_id, error_signature, description, solution, tags)
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT DO NOTHING
                """, project_id, error_signature or error_description[:100],
                    error_description, solution, tags_list)
        
        # También en Qdrant con alta importancia
        content = f"ERROR CONOCIDO: {error_description}\nSOLUCIÓN: {solution}"
        await store_memory(content, project, "error", tags, 0.95)
        
        return f"🐛 Error registrado en proyecto '{project}'\nSolución guardada para referencia futura"
    
    except Exception as e:
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def delete_memory(memory_id: str) -> str:
    """Elimina una memoria específica por su ID UUID."""
    try:
        await qdrant.delete(
            collection_name=COLLECTION_NAME,
            points_selector=[memory_id]
        )
        return f"🗑️ Memoria {memory_id} eliminada"
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ── REST API Endpoints ─────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/stats")
async def stats(auth: bool = Depends(verify_api_key)):
    """Estadísticas del sistema de memoria."""
    info = await qdrant.get_collection(COLLECTION_NAME)
    return {
        "vectors_count": info.vectors_count,
        "indexed_vectors": info.indexed_vectors_count,
        "collection": COLLECTION_NAME,
    }


# ── Startup/Shutdown ───────────────────────────────────────

@app.on_event("startup")
async def startup():
    global pg_pool, redis_client, openai_client
    
    logger.info("Iniciando AI Memory Brain...")
    
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    # PostgreSQL pool
    pg_pool = await asyncpg.create_pool(
        POSTGRES_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("✅ PostgreSQL conectado")
    
    # Redis
    redis_client = aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
    await redis_client.ping()
    logger.info("✅ Redis conectado")
    
    # Qdrant
    await init_qdrant()
    logger.info("✅ Qdrant conectado")
    
    logger.info("🚀 AI Memory Brain listo!")


@app.on_event("shutdown")
async def shutdown():
    if pg_pool:
        await pg_pool.close()
    if redis_client:
        await redis_client.close()
    if qdrant:
        await qdrant.close()


# ── Montar MCP en FastAPI ──────────────────────────────────

# El servidor MCP se monta en /mcp
mcp_app = mcp.get_asgi_app()
app.mount("/mcp", mcp_app)


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8050,
        log_level="info",
        workers=1,  # Un worker en Pi 4 (ARM)
    )
```

---

## 🌱 Alimentar la base de datos

### Script de ingesta desde Obsidian/Markdown

```python
# scripts/ingest_markdown.py
"""
Ingesta batch de archivos Markdown (Obsidian vault, documentación, etc.)
Uso: python ingest_markdown.py --vault /path/to/vault --project mi-proyecto
"""

import argparse
import asyncio
import json
import re
from pathlib import Path
import httpx

API_URL = "http://localhost:8050"  # o tu URL de Cloudflare
API_KEY = "tu-memory-api-key"

async def store_memory(client: httpx.AsyncClient, content: str, project: str, 
                        memory_type: str, tags: list, importance: float = 0.7):
    """Llama al MCP tool store_memory via REST."""
    # El servidor MCP expone los tools también via endpoint REST
    response = await client.post(
        f"{API_URL}/api/memories",
        headers={"X-API-Key": API_KEY},
        json={
            "content": content,
            "project": project,
            "memory_type": memory_type,
            "tags": ", ".join(tags),
            "importance": importance,
            "agent_id": "ingest-script"
        }
    )
    return response.json()


def extract_obsidian_tags(content: str) -> list[str]:
    """Extrae tags de formato Obsidian (#tag o frontmatter tags:)."""
    tags = re.findall(r'#([a-zA-Z0-9_/-]+)', content)
    # Frontmatter tags
    fm_match = re.search(r'^tags:\s*\[(.*?)\]', content, re.MULTILINE)
    if fm_match:
        fm_tags = [t.strip().strip('"\'') for t in fm_match.group(1).split(',')]
        tags.extend(fm_tags)
    return list(set(tags))


def chunk_document(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Divide texto en chunks con overlap para mejor recuperación."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 50:  # Ignorar chunks muy cortos
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


async def ingest_vault(vault_path: str, project: str, extensions: list = None):
    extensions = extensions or ['.md', '.txt']
    vault = Path(vault_path)
    files = []
    for ext in extensions:
        files.extend(vault.rglob(f"*{ext}"))
    
    print(f"📚 Encontrados {len(files)} archivos en {vault_path}")
    
    async with httpx.AsyncClient(timeout=30) as client:
        ingested = 0
        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                if len(content.strip()) < 50:
                    continue
                
                tags = extract_obsidian_tags(content)
                tags.append(file_path.parent.name)  # Carpeta como tag
                
                # Determinar tipo de memoria por carpeta/nombre
                memory_type = "general"
                name_lower = str(file_path).lower()
                if any(k in name_lower for k in ['decision', 'adr', 'architecture']):
                    memory_type = "decision"
                elif any(k in name_lower for k in ['error', 'bug', 'fix', 'troubleshoot']):
                    memory_type = "error"
                elif any(k in name_lower for k in ['readme', 'overview', 'intro']):
                    memory_type = "architecture"
                
                chunks = chunk_document(content)
                
                for i, chunk in enumerate(chunks):
                    context = f"[{file_path.name}{'#'+str(i) if len(chunks)>1 else ''}]\n{chunk}"
                    await store_memory(client, context, project, memory_type, tags)
                    await asyncio.sleep(0.1)  # Rate limit OpenAI embeddings
                
                ingested += 1
                if ingested % 10 == 0:
                    print(f"  ✅ {ingested}/{len(files)} archivos procesados")
                    
            except Exception as e:
                print(f"  ⚠️ Error en {file_path}: {e}")
    
    print(f"\n🎉 Ingesta completada: {ingested} archivos → proyecto '{project}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True, help="Ruta al vault de Obsidian")
    parser.add_argument("--project", required=True, help="Nombre del proyecto")
    args = parser.parse_args()
    
    asyncio.run(ingest_vault(args.vault, args.project))
```

### Script de ingesta de código fuente

```python
# scripts/ingest_codebase.py
"""
Analiza un repositorio y extrae conocimiento estructural.
Uso: python ingest_codebase.py --repo /path/to/repo --project mi-app
"""

import asyncio
import subprocess
from pathlib import Path
import httpx

API_URL = "http://localhost:8050"
API_KEY = "tu-memory-api-key"

IGNORAR_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'dist', 'build', '.pytest_cache'}
IGNORAR_EXTS = {'.pyc', '.pyo', '.min.js', '.lock', '.sum'}
CODE_EXTS = {'.py', '.js', '.ts', '.go', '.rs', '.java', '.rb', '.php', '.cs', '.cpp', '.c'}

async def ingest_repo(repo_path: str, project: str):
    repo = Path(repo_path)
    
    async with httpx.AsyncClient(timeout=60) as client:
        
        # 1. README y documentación
        for readme in repo.glob("README*"):
            content = readme.read_text(errors='ignore')
            await client.post(f"{API_URL}/api/memories",
                headers={"X-API-Key": API_KEY},
                json={"content": f"README DEL PROYECTO:\n{content[:2000]}", 
                      "project": project, "memory_type": "architecture",
                      "importance": 0.95, "agent_id": "ingest-codebase"})
        
        # 2. Estructura del proyecto (árbol de directorios)
        tree = subprocess.run(
            ['find', repo_path, '-type', 'f', '-not', '-path', '*/.git/*'],
            capture_output=True, text=True
        ).stdout
        structure = "\n".join(sorted(
            line.replace(repo_path, '').lstrip('/')
            for line in tree.strip().split('\n')
            if not any(d in line for d in IGNORAR_DIRS)
            and not any(line.endswith(e) for e in IGNORAR_EXTS)
        ))
        await client.post(f"{API_URL}/api/memories",
            headers={"X-API-Key": API_KEY},
            json={"content": f"ESTRUCTURA DEL PROYECTO {project}:\n{structure[:3000]}",
                  "project": project, "memory_type": "architecture",
                  "importance": 0.9, "agent_id": "ingest-codebase"})
        
        # 3. Archivos de configuración importantes
        config_files = ['docker-compose.yml', 'Dockerfile', 'pyproject.toml',
                        'package.json', 'requirements.txt', '.env.example']
        for cf in config_files:
            path = repo / cf
            if path.exists():
                content = path.read_text(errors='ignore')[:1500]
                await client.post(f"{API_URL}/api/memories",
                    headers={"X-API-Key": API_KEY},
                    json={"content": f"CONFIG [{cf}]:\n{content}",
                          "project": project, "memory_type": "architecture",
                          "tags": "config,infrastructure", "importance": 0.85,
                          "agent_id": "ingest-codebase"})
                await asyncio.sleep(0.2)
        
        print(f"✅ Repositorio '{project}' ingestado")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    asyncio.run(ingest_repo(args.repo, args.project))
```

---

## 🤖 Cómo instruir a los agentes para usar la memoria

### CLAUDE.md / AGENTS.md (poner en la raíz del proyecto)

```markdown
# 🧠 Memory Brain Integration

Tienes acceso al servidor MCP `memory-brain` con las siguientes herramientas:

## Cuándo DEBES usar la memoria (obligatorio):

1. **Al inicio de cada sesión:** Llama `get_project_context("NOMBRE_PROYECTO")` 
   para cargar el contexto del proyecto antes de empezar.

2. **Al encontrar un error nuevo:** Llama `store_error(...)` con la descripción 
   y solución. Esto evita repetir el mismo diagnóstico en futuras sesiones.

3. **Al tomar decisiones de arquitectura:** Llama `store_decision(...)` con el 
   título, la decisión y el razonamiento.

4. **Al completar una tarea:** Llama `update_task_state(title, project, "done")`.

5. **Al encontrar información relevante del proyecto:** Llama `store_memory(...)`.

6. **Al final de cada sesión:** Llama `record_session_summary(...)` con:
   proyecto, agent_id, session_id, goal, outcome, summary, changes, decisions,
   errors, follow_ups y tags.

## Cuándo usar `search_memory`:

- Antes de implementar algo nuevo, busca si ya existe una decisión previa.
- Si encuentras un error, busca si ya se resolvió antes.
- Para obtener contexto sobre tecnologías usadas en el proyecto.
- Tras empezar una sesión, combina `get_project_context(...)` con la memoria
  reciente para saber qué estaba pasando antes de retomar.

## Naming conventions:

- Proyecto: nombre-en-kebab-case (ej: "datadis-sdk", "ems-platform")
- Agent ID: usa siempre el mismo (ej: "claude-code-cristian")
- Memory types: decision | error | architecture | context | task | general
```

---

## 🔧 Configuración de clientes MCP

### Claude Code (`~/.claude.json`)

```json
{
  "mcpServers": {
    "memory-brain": {
      "type": "http",
      "url": "https://memory.tudominio.com/mcp",
      "headers": {
        "X-API-Key": "tu-memory-api-key"
      }
    }
  }
}
```

### OpenAI Codex CLI (`~/.codex/config.toml`)

```toml
[mcp_servers.memory-brain]
url = "https://memory.tudominio.com/mcp"
headers = { "X-API-Key" = "tu-memory-api-key" }
startup_timeout_sec = 15
tool_timeout_sec = 30
enabled = true
```

### Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "memory-brain": {
      "url": "https://memory.tudominio.com/mcp",
      "headers": { "X-API-Key": "tu-memory-api-key" }
    }
  }
}
```

### Cline (VSCode settings)

```json
{
  "cline.mcpServers": {
    "memory-brain": {
      "url": "https://memory.tudominio.com/mcp",
      "headers": { "X-API-Key": "tu-memory-api-key" },
      "autoApprove": ["search_memory", "get_project_context", "list_active_tasks"]
    }
  }
}
```

---

## 🛡️ Scripts de mantenimiento

### Backup (`scripts/backup.sh`)

```bash
#!/bin/bash
# Backup diario de Qdrant + PostgreSQL
BACKUP_DIR="/mnt/ssd/backups/$(date +%Y%m%d_%H%M)"
mkdir -p "$BACKUP_DIR"

echo "📦 Backup iniciado: $BACKUP_DIR"

# Backup Qdrant (snapshot via API)
curl -s -X POST "http://localhost:6333/collections/memories/snapshots" \
  -H "api-key: $QDRANT_API_KEY" | jq -r '.result.name' > /tmp/snap_name.txt
SNAP=$(cat /tmp/snap_name.txt)
curl -s "http://localhost:6333/collections/memories/snapshots/$SNAP" \
  -H "api-key: $QDRANT_API_KEY" -o "$BACKUP_DIR/qdrant_memories.snapshot"

# Backup PostgreSQL
docker exec postgres pg_dump -U memoryuser memorydb | \
  gzip > "$BACKUP_DIR/postgres_memorydb.sql.gz"

# Eliminar backups de más de 7 días
find /mnt/ssd/backups -type d -mtime +7 -exec rm -rf {} + 2>/dev/null

echo "✅ Backup completado en $BACKUP_DIR"
```

```bash
# Añadir al crontab (backup diario a las 3am)
(crontab -l; echo "0 3 * * * /bin/bash ~/ai-memory-brain/scripts/backup.sh") | crontab -
```

### Monitoreo de temperatura y recursos

```bash
# scripts/health_check.sh
#!/bin/bash
echo "=== AI Memory Brain — Estado $(date) ==="

# Temperatura CPU (crítico en Pi 4)
TEMP=$(vcgencmd measure_temp 2>/dev/null | grep -oP '\d+\.\d+')
echo "🌡️  CPU Temp: ${TEMP:-N/A}°C $([ "${TEMP%%.*}" -gt 70 ] 2>/dev/null && echo '⚠️ ALTA' || echo '✅')"

# RAM
free -h | awk '/^Mem:/ {printf "💾 RAM: %s usado de %s (libre: %s)\n", $3, $2, $4}'

# Disco SSD
df -h /mnt/ssd | awk 'NR==2 {printf "💽 SSD: %s usado de %s (%s lleno)\n", $3, $2, $5}'

# Estado contenedores
echo ""
echo "🐳 Contenedores:"
docker ps --format "  {{.Names}}: {{.Status}}" | grep -E "qdrant|postgres|redis|mem0|api-server"

# Health check API
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8050/health)
echo ""
echo "🔗 API Health: $HTTP_CODE $([ "$HTTP_CODE" = "200" ] && echo '✅' || echo '❌')"
```

---

## 🌡️ Consejos de estabilidad para Raspberry Pi 4

**Temperatura:** El Pi 4 hace throttling a 80°C y se apaga a 85°C. Con carga sostenida de Docker:
- **Imprescindible:** Disipador pasivo + ventilador o caja con ventilación activa (ej: Argon ONE M.2)
- Monitorear con: `watch -n 5 vcgencmd measure_temp`
- El throttling se detecta con: `vcgencmd get_throttled` (0x0 = todo bien)

**Alimentación:** Usar **fuente oficial de 5V/3A** con cable USB-C corto. Alimentación insuficiente causa resets aleatorios que pueden corromper las BBDDs.

**Watchdog automático:** El Pi 4 tiene watchdog hardware:
```bash
echo 'dtparam=watchdog=on' | sudo tee -a /boot/config.txt
sudo apt install watchdog
echo 'watchdog-device = /dev/watchdog' | sudo tee -a /etc/watchdog.conf
echo 'max-load-1 = 24' | sudo tee -a /etc/watchdog.conf
sudo systemctl enable watchdog && sudo systemctl start watchdog
```

**Docker restart policy:** Todos los servicios tienen `restart: unless-stopped` — si la Pi se reinicia (corte de luz), los contenedores suben solos.

---

## 🚀 Secuencia de arranque completa

```bash
# 1. Montar el SSD
sudo mkdir -p /mnt/ssd
# Añadir a /etc/fstab:
# /dev/sda1 /mnt/ssd ext4 defaults,noatime 0 2

# 2. Crear directorios de datos en SSD
sudo mkdir -p /mnt/ssd/{qdrant_data,postgres_data,redis_data,backups}
sudo chown -R 1000:1000 /mnt/ssd/

# 3. Clonar el proyecto
git clone https://github.com/tuuser/ai-memory-brain ~/ai-memory-brain
cd ~/ai-memory-brain
cp .env.example .env
nano .env  # Rellenar todos los valores

# 4. Build del servidor custom
docker build -t ai-memory-api-server ./api-server --platform linux/arm64

# 5. Arrancar (primera vez, puede tardar 5-10 min descargando imágenes)
docker compose -f docker-compose.lite.yml up -d

# 6. Ver logs de arranque
docker compose -f docker-compose.lite.yml logs -f --tail=50

# 7. Verificar que todo está OK
bash scripts/health_check.sh

# 8. Ingestar tu Obsidian vault
python scripts/ingest_markdown.py \
  --vault /ruta/a/tu/obsidian \
  --project "personal-knowledge"
```
