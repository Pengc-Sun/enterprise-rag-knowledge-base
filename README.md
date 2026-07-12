# Enterprise RAG Knowledge Base

Enterprise-oriented Retrieval-Augmented Generation knowledge base system.

This repository follows the 8-week development roadmap in `docs/development-roadmap.md`.

Current status: Week 3 document ingestion pipeline is complete. See:

- `docs/development-log/week-1.md`
- `docs/development-log/week-2.md`

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

Document endpoints:

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/documents
POST /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/reprocess
```

Supported upload types: PDF, DOCX, TXT, Markdown. Duplicate uploads are rejected by SHA-256 hash within the same knowledge base.

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

## Week 2 Acceptance Status

- Users can register and log in
- JWT authentication works
- `/api/v1/users/me` returns the authenticated user
- Users can create knowledge bases
- Knowledge base owner/editor/viewer permissions are enforced
- Unauthorized users cannot access private knowledge bases
- Pytest, Ruff, and mypy pass through `make check`

## Week 3 Acceptance Status

- PDF, DOCX, TXT, and Markdown files can be uploaded
- Uploaded files are validated by extension, MIME type, size, and sanitized filename
- Duplicate documents are rejected by SHA-256 hash within each knowledge base
- PDF, DOCX, TXT, and Markdown parsing is covered by tests
- Recursive, token-aware, overlap-aware, and section-aware chunking is implemented
- Chunks are stored with document, knowledge base, page, section, token count, and JSON metadata
- Documents can be reprocessed to replace stored chunks
- Pytest, Ruff, and mypy pass through `make check`
