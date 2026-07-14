# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - 2026-07-14

### Added

- Full-stack Enterprise RAG Knowledge Base application with FastAPI backend and React/Vite frontend.
- JWT authentication, protected frontend routes, user registration, login, and current-user API.
- Knowledge base CRUD with owner, editor, and viewer permission model.
- Document upload, filename sanitization, MIME validation, size limits, duplicate SHA-256 detection, parsing, chunking, reprocessing, and deletion.
- PostgreSQL async SQLAlchemy persistence, Alembic migrations, pgvector embeddings, and full-text search vectors.
- Deterministic local embedding, reranker, and LLM providers for reproducible development and CI.
- Hybrid retrieval with vector search, keyword search, Reciprocal Rank Fusion, metadata filters, and reranking.
- RAG answer generation with source citations, insufficient-context handling, and retrieval debug API.
- Conversation and message persistence with multi-turn chat and Server-Sent Events streaming responses.
- React workflows for auth, knowledge base management, document management, chat, source cards, and citation detail display.
- Unified API response envelope and standardized error responses with request IDs.
- Structured request and RAG logs, provider timeout/rate-limit handling, bounded retries, and evaluation-friendly error semantics.
- RAG evaluation dataset, synthetic prediction file, retrieval metrics, and reproducible evaluation command.
- Docker Compose development stack and production-style stack with PostgreSQL, Redis, Alembic migration, backend, Nginx frontend, health checks, and named volumes.
- GitHub Actions CI for backend tests, Ruff, mypy, frontend typecheck/build, and production Docker image build.
- Project documentation covering architecture, API, deployment, evaluation, security, screenshots, demo data, and demo video script.

### Verified

- Backend test suite: 185 passed, 1 warning.
- Ruff: all checks passed.
- mypy: no issues found in 94 source files.
- Frontend TypeScript typecheck passed.
- Frontend production build passed.
- Production Docker Compose config validated.
- Production backend and frontend Docker images built.
- Retrieval evaluation reproduced for vector, hybrid, and hybrid-reranker strategies.
- Local secrets scan found no common real credential patterns; only example environment files are tracked.

### Known limitations

- Deterministic providers are intended for local development, testing, and demo use; real production use should configure external embedding and LLM providers.
- Synthetic evaluation data is not a substitute for a production benchmark on representative private documents.
- Document processing currently runs in the application flow rather than a dedicated worker queue.
- Production-style Docker Compose is suitable for demos and small deployments, not a complete managed cloud platform.
- A final demo video file should be attached as a GitHub Release asset rather than committed to git.
