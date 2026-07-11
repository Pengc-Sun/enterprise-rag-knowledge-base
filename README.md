# Enterprise RAG Knowledge Base

Enterprise-oriented Retrieval-Augmented Generation knowledge base system.

This repository follows the 8-week development roadmap in `docs/development-roadmap.md`.

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
