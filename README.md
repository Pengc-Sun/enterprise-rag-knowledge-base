# Enterprise RAG Knowledge Base

Enterprise-oriented Retrieval-Augmented Generation knowledge base system.

This repository follows the 8-week development roadmap in `docs/development-roadmap.md`.

Current status: Week 1 backend foundation is complete. See `docs/development-log/week-1.md`.

## Goals

- User registration and JWT authentication
- Multiple knowledge bases
- PDF, DOCX, TXT, and Markdown ingestion
- Chunking, embedding, pgvector storage, and hybrid retrieval
- Reranking, streaming chat responses, and source citations
- Docker-based local development
- Automated tests, linting, type checking, and CI

## Stack

- Backend: Python, FastAPI
- Database: PostgreSQL with pgvector
- Cache: Redis
- ORM: SQLAlchemy 2.0
- Migrations: Alembic
- Testing: Pytest
- Quality: Ruff, mypy
- Deployment: Docker Compose

## Local Development

```bash
make install
make dev
```

Health check:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health/database
```

Swagger:

```text
http://localhost:8000/docs
```

Auth endpoints:

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET /api/v1/users/me
```

Knowledge base endpoints:

```text
POST /api/v1/knowledge-bases
GET /api/v1/knowledge-bases
GET /api/v1/knowledge-bases/{knowledge_base_id}
PATCH /api/v1/knowledge-bases/{knowledge_base_id}
DELETE /api/v1/knowledge-bases/{knowledge_base_id}
```

## Docker

```bash
make docker-up
make docker-down
```

## Database Migrations

```bash
make migrate-up
make migrate-down
make migrate-current
```

## Quality Checks

```bash
make test
make lint
make typecheck
make check
```

## Week 1 Acceptance Status

- Docker Compose starts backend, PostgreSQL with pgvector, and Redis
- `/health` returns success
- `/api/v1/health/database` validates PostgreSQL connectivity
- Swagger is available at `/docs`
- Alembic upgrade and downgrade are verified
- Pytest, Ruff, and mypy pass through `make check`
