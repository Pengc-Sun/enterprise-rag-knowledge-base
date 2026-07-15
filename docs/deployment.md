# Deployment Guide

This document describes how to run Enterprise RAG Knowledge Base locally and with the production-style Docker Compose stack.

## Prerequisites

Required tools:

- Docker and Docker Compose
- Python 3.11
- Node.js 22 or compatible current LTS
- pnpm through Corepack
- Make

Optional for local source development:

- PostgreSQL with pgvector
- Redis

## Environment Files

Development example:

```bash
cp .env.example .env
```

Production-style example:

```bash
cp .env.production.example .env.production
```

Before using production-style settings outside local validation, change at least:

- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- provider API keys, if non-deterministic providers are enabled

Do not commit `.env` files.

### OpenRouter Chat and Embeddings

OpenRouter uses OpenAI-compatible API paths. Configure it through the existing `openai` provider setting and the OpenRouter base URL:

```bash
LLM_PROVIDER=openai
LLM_MODEL=tencent/hy3:free
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=<your-openrouter-key>

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=<openrouter-embedding-model>
EMBEDDING_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_API_KEY=<your-openrouter-key>
EMBEDDING_DIMENSION=<model-output-dimension>
```

`tencent/hy3:free` is a chat model configuration. Embeddings must use a model that supports the `/embeddings` endpoint. If you change the embedding model or dimension after documents were uploaded, re-upload or reprocess documents so stored vectors use the same dimension and model.

## Development Docker Stack

Start the development stack:

```bash
make docker-up
```

Stop it:

```bash
make docker-down
```

Follow logs:

```bash
make docker-logs
```

The development stack starts:

- backend on `http://localhost:8000`
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`

The backend container uses `.env.example` and depends on healthy PostgreSQL and Redis services.

## Local Source Backend

If you want to run FastAPI directly on macOS instead of inside the backend container, start only dependencies first:

```bash
docker compose up -d postgres redis
```

Then configure `.env` for localhost service access if needed:

```text
DATABASE_URL=postgresql+asyncpg://enterprise_rag:enterprise_rag@localhost:5432/enterprise_rag
REDIS_URL=redis://localhost:6379/0
```

Install and run:

```bash
make install
make migrate-up
make dev
```

Do not run the Docker backend and `make dev` at the same time because both bind port `8000`.

## Frontend Development

Run the frontend development server:

```bash
cd frontend
corepack enable
pnpm install
pnpm dev
```

Build the frontend:

```bash
cd frontend
pnpm typecheck
pnpm build
```

## Database Migrations

Apply migrations:

```bash
make migrate-up
```

Roll back one revision:

```bash
make migrate-down
```

Show current revision:

```bash
make migrate-current
```

Migrations are stored in `alembic/`. The production-style Compose stack runs `alembic upgrade head` in the `migrate` one-shot service before starting the backend.

## Production-Style Docker Stack

Validate Compose configuration:

```bash
make docker-prod-config PROD_ENV=.env.production
```

Validate migration startup ordering and Alembic downgrade/upgrade:

```bash
make validate-migration-startup
```

Validate the real Docker migrate service against an isolated fresh database:

```bash
make validate-docker-migration-startup
```

Build and start:

```bash
make docker-prod-up PROD_ENV=.env.production
```

Follow logs:

```bash
make docker-prod-logs PROD_ENV=.env.production
```

Stop:

```bash
make docker-prod-down
```

The production-style stack starts:

- `postgres`: `pgvector/pgvector:pg16` with `postgres-prod-data` volume.
- `redis`: `redis:7-alpine` with append-only persistence and `redis-prod-data` volume.
- `migrate`: one-shot Alembic upgrade service.
- `backend`: FastAPI backend with `storage-prod-data` mounted at `/app/storage`.
- `frontend`: Nginx-served React build, exposing `${FRONTEND_PORT:-8080}`.

Default production-style URL:

```text
http://localhost:8080
```

Backend API requests are proxied by the frontend container through `/api/v1`.

## Startup Ordering

The production-style Compose file uses health-based ordering:

1. PostgreSQL must be healthy.
2. Redis must be healthy.
3. Alembic migration must complete successfully.
4. Backend starts and becomes healthy.
5. Frontend starts after backend health is ready.

This avoids the most common race conditions during container startup.

## Persistent Volumes

Production-style named volumes:

- `postgres-prod-data`: database files.
- `redis-prod-data`: Redis append-only data.
- `storage-prod-data`: uploaded documents and local storage.

Development named volume:

- `postgres-data`: development PostgreSQL files.

Do not delete these volumes unless you intentionally want to reset local state.

## Health Checks

Application health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health
```

Database health:

```bash
curl http://localhost:8000/api/v1/health/database
```

Production-style frontend health is checked inside the frontend container through Nginx.

## CI/CD

GitHub Actions runs on push to `main` and pull requests. The CI workflow covers:

- backend pytest
- Ruff lint
- mypy typecheck
- frontend typecheck and production build
- production Docker image build

The workflow file is `.github/workflows/ci.yml`.

## Deployment Checklist

Before sharing or deploying:

- Replace all example secrets.
- Confirm `.env` is not tracked by git.
- Run `make docker-prod-config PROD_ENV=.env.production`.
- Run `make check`.
- Run frontend `pnpm typecheck` and `pnpm build`.
- Confirm GitHub Actions passes.
- Confirm upload storage volume is persistent.
- Confirm provider API keys, model names, base URLs, and embedding dimensions are configured if deterministic providers are not used.

## Current Deployment Scope

The current deployment target is Docker Compose. It is suitable for local validation, demos, and small single-host deployments. A production cloud deployment would still need managed secrets, TLS termination, backups, monitoring, rate limiting, and possibly a dedicated worker queue for document processing.
