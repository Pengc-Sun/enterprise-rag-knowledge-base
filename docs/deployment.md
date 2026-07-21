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

Validate a complete fresh production-style install from empty Docker volumes:

```bash
FRONTEND_PORT=18080 APP_ENV_FILE=.env.production.example docker compose \
  --env-file .env.production.example \
  -p enterprise-rag-v2-day65-fresh \
  -f docker-compose.prod.yml up -d --build

curl -fsS http://127.0.0.1:18080/health
curl -fsS http://127.0.0.1:18080/api/v1/health

FRONTEND_PORT=18080 APP_ENV_FILE=.env.production.example docker compose \
  --env-file .env.production.example \
  -p enterprise-rag-v2-day65-fresh \
  -f docker-compose.prod.yml down -v --remove-orphans
```

Validate a Docker v1-to-v2 upgrade path from a seeded v1 database snapshot:

```bash
.venv/bin/python scripts/validate_docker_v1_upgrade.py --yes --json
```

The upgrade validation uses an isolated Compose project, seeds v1-style users, knowledge base,
member, document, chunk, conversation, and message rows at revision `0010`, runs the production
`migrate` service, verifies revision `0024`, starts backend/frontend health checks, validates
workspace backfill, and removes its isolated containers and volumes by default.

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
  Uploaded documents use `UPLOAD_DIR` and report exports use `EXPORT_DIR`; both should point under
  the persistent storage mount in Docker deployments.
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
- `storage-prod-data`: uploaded documents, generated report exports, and local storage.

Development named volume:

- `postgres-data`: development PostgreSQL files.

Do not delete these volumes unless you intentionally want to reset local state.

## Export Storage Persistence

Report exports are generated by the backend and stored on disk before the export job is marked
`completed`. The export job records the stored path in `export_jobs.file_path`, and downloads are
served through:

```text
GET /api/v1/workspaces/{workspace_id}/exports/{export_id}/download
```

The backend uses these environment variables:

```text
UPLOAD_DIR=storage/uploads
EXPORT_DIR=storage/exports
```

In Docker images, the application runs from `/app`, so the default relative paths resolve to
`/app/storage/uploads` and `/app/storage/exports`. Both paths are covered by the same persistent
storage mount:

```yaml
volumes:
  - storage-prod-data:/app/storage
```

For production-style Compose deployments, keep `UPLOAD_DIR` and `EXPORT_DIR` under `/app/storage`.
If either path points outside `/app/storage`, uploaded documents or generated exports may disappear
when the backend container is recreated.

Operational checks:

- Create a report export, then confirm `GET /exports/{export_id}` returns a non-empty `file_path`.
- Download the file through `GET /exports/{export_id}/download`.
- Restart or recreate the backend container.
- Confirm the same export still downloads successfully.
- Include `storage-prod-data` in backup/restore procedures together with PostgreSQL data.

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
- Confirm upload and export storage volumes are persistent.
- Confirm `UPLOAD_DIR` and `EXPORT_DIR` resolve under the mounted `/app/storage` path.
- Validate a fresh Docker install from empty volumes.
- Validate the Docker v1-to-v2 upgrade path with `scripts/validate_docker_v1_upgrade.py`.
- Confirm provider API keys, model names, base URLs, and embedding dimensions are configured if deterministic providers are not used.

## Current Deployment Scope

The current deployment target is Docker Compose. It is suitable for local validation, demos, and small single-host deployments. A production cloud deployment would still need managed secrets, TLS termination, backups, monitoring, rate limiting, and possibly a dedicated worker queue for document processing.
