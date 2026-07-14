# Enterprise RAG Knowledge Base

Enterprise-oriented Retrieval-Augmented Generation knowledge base system.

This repository follows the 8-week development roadmap in `docs/development-roadmap.md`.

Current status: Week 7 testing, evaluation, logging, and reliability work is complete. The project now has broad backend tests, reproducible retrieval evaluation assets, structured request/RAG logs, and unified API error handling. See:

- `docs/development-roadmap.md`
- `docs/development-log/week-1.md`
- `docs/development-log/week-2.md`
- `evaluations/README.md`

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
- Frontend: React, TypeScript, Vite
- Database: PostgreSQL with pgvector
- Cache: Redis
- ORM: SQLAlchemy 2.0
- Migrations: Alembic
- Testing: Pytest
- Quality: Ruff, mypy
- Deployment: Docker Compose

## Local Development

Backend:

```bash
make install
make dev
```

Frontend:

```bash
cd frontend
pnpm install
pnpm dev
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
GET /api/v1/knowledge-bases/{knowledge_base_id}/documents
POST /api/v1/knowledge-bases/{knowledge_base_id}/documents
POST /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/reprocess
DELETE /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}
```

RAG endpoints:

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/query
POST /api/v1/knowledge-bases/{knowledge_base_id}/query/debug
```

Conversation endpoints:

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations
GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations
GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}
PATCH /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}
DELETE /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}
GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/messages
POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/chat
POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/chat/stream
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

## Week 4 Acceptance Status

- pgvector extension and embedding storage are configured for document chunks
- Chunk embedding status tracking, retry handling, and failure recording are implemented
- Configurable embedding provider abstraction is available, including deterministic local embeddings for development and tests
- Vector retrieval embeds user queries and returns top matching chunks within the selected knowledge base
- Configurable LLM provider abstraction is available, including deterministic local responses for development and tests
- Basic RAG query API answers questions using retrieved context
- Source citations include document name, page number, chunk ID, original text, and similarity score
- Insufficient context is handled with a safe response
- Pytest, Ruff, and mypy pass through `make check`

## Week 5 Acceptance Status

- PostgreSQL full-text search is configured for document chunks
- Hybrid retrieval combines vector search and keyword search
- Reciprocal Rank Fusion merges vector and keyword candidates
- Cross-encoder-style reranking abstraction is integrated into the retrieval pipeline
- Follow-up query rewriting uses conversation history to produce standalone questions
- Metadata filtering supports document IDs, file types, dates, departments, and permissions before generation
- Retrieval debug endpoint exposes vector score, keyword score, RRF score, rerank score, and final rank
- Retrieval, reranking, query rewriting, and debug behavior are covered by tests
- Pytest, Ruff, and mypy pass through `make check`

## Week 6 Acceptance Status

- Conversation and message persistence are implemented
- Multi-turn chat uses stored message history with configurable context limits
- Server-Sent Events stream answer tokens and emit metadata, source citations, completion, and error events
- React frontend supports registration, login, token-based route protection, and logout
- Frontend knowledge base management supports list, create, details, edit, and delete actions
- Frontend document management supports upload, list, processing status, chunk count, error display, reprocess, and delete actions
- Frontend chat supports conversation list, new conversation, streaming messages, stop generation, copy answer, source cards, and citation detail modal
- Week 6 acceptance flow is connected from login through knowledge base creation, document upload, and chat with citations
- Backend tests pass and frontend production build passes

## Week 7 Acceptance Status

- Core backend modules are covered by focused unit tests, including chunking, parsing, authentication, permissions, prompt construction, retrieval, reranking, query rewriting, streaming, and service behavior
- Document ingestion integration tests cover upload, parse, chunk, embed, retrieve, and generate flow
- End-to-end API tests cover register, login, knowledge base creation, document upload, RAG question answering, and source citation reads
- RAG evaluation dataset contains 40 labelled enterprise questions with expected answer, document, page, aliases, required terms, and metadata filters
- Retrieval evaluation metrics can be reproduced with Hit Rate@K, Recall@K, MRR@K, and nDCG@K across vector, hybrid, and hybrid-plus-reranker prediction files
- Structured JSON logging includes request IDs, user IDs, knowledge base IDs, query text, retrieved chunk IDs, retrieval/rerank/LLM/total latency, token usage, status, and error details
- API error responses use a unified error object with code, status code, request ID, and details
- LLM provider calls include bounded retry handling for transient failures, timeout handling, and rate-limit handling
- Evaluation documentation explains retrieval metric inputs and reliability/error semantics
- Pytest, Ruff, and mypy pass through `make check`

