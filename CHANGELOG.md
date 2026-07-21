# Changelog

All notable changes to this project are documented in this file.

## [2.0.0] - 2026-07-21

### Added

- Workspace project boundary above knowledge bases, documents, chunks, conversations, analysis,
  review, reports, and exports.
- Workspace membership model with `owner`, `admin`, `editor`, `reviewer`, and `viewer` roles.
- Built-in workspace templates for general knowledge, policy review, IT support, and research
  review workflows.
- Template-driven workspace creation for directories, default knowledge bases, analysis tasks, and
  report outlines.
- v1.0 data migration into owner default workspaces with required `workspace_id` values on
  knowledge bases, documents, chunks, and conversations.
- Workspace-scoped knowledge-base, document, retrieval, RAG, conversation, chat, streaming, and
  compatibility routes.
- Workspace audit logs for key workspace, member, directory, document, and review actions.
- Structured analysis task and result APIs with JSON schema validation, normalized citations,
  provider metadata, and deterministic test behavior.
- Reviewer workflow for approving, editing, rejecting, or requesting changes to AI results while
  preserving the first original AI result snapshot.
- Review queue APIs and React review UI for reviewer decisions.
- Workspace-scoped report builder with manual sections, generated sections, ordering, Markdown
  preview, and approved-content-only source validation.
- Markdown, DOCX, and PDF report exports with persistent storage under
  `storage/exports/{workspace_id}/{export_id}/{filename}` and access-controlled downloads.
- Workspace dashboard metrics for documents, analysis tasks, review state, reports, and exports.
- React workspace experience covering workspace list/create/template selection, dashboard
  navigation, workspace knowledge bases, documents, chat, analysis, review, reports, exports, and
  members.
- Docker fresh-install validation and Docker v1-to-v2 upgrade validation scripts for release
  candidates.
- Final cross-workspace isolation regression tests for knowledge bases, retrieval, review queue,
  report source validation, and export lookup.
- v2 workspace workflow SVG documentation asset.

### Changed

- The frontend now starts from the workspace workflow while preserving legacy knowledge-base routes
  where a `workspace_id` query parameter is supplied.
- Report source validation now requires both the `AnalysisResult` row and its joined
  `AnalysisTask` row to belong to the same workspace.
- README, architecture, API, deployment, security, screenshot, and development-log documentation now
  describe the v2 workspace-based product.

### Verified

- Backend test suite: 458 passed, 1 skipped, 1 warning.
- Ruff: all checks passed.
- mypy: no issues found in 140 source files.
- Frontend TypeScript typecheck passed.
- Frontend production build passed.
- Production Docker fresh install from empty volumes passed through revision `0024`.
- Docker v1-to-v2 upgrade validation passed from revision `0010` to `0024` without seeded data loss.
- Cross-workspace isolation regression tests passed.
- SVG release documentation asset parses successfully.

### Known limitations

- The stable v1.0 line remains on `main` until the v2.0 branch or PR is approved and merged.
- Deterministic providers remain the default for reproducible local development and CI; real
  production use should configure external embedding and LLM providers.
- Production-style Docker Compose remains a small single-host deployment reference, not a complete
  managed cloud architecture.
- Background parsing and embedding still run in the application flow rather than a dedicated worker
  queue.

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
