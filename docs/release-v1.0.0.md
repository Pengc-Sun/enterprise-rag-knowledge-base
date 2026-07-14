# v1.0.0 Release Notes

Release date: 2026-07-14

## Summary

Enterprise RAG Knowledge Base v1.0.0 is the first complete portfolio release of the project. It demonstrates an end-to-end enterprise RAG workflow with authentication, knowledge-base isolation, document ingestion, hybrid retrieval, reranking, streaming chat, source citations, evaluation assets, Docker deployment, CI, and project documentation.

## Release Highlights

- Full-stack app: FastAPI backend and React/Vite frontend.
- Private knowledge bases with owner/editor/viewer permissions.
- PDF, DOCX, TXT, and Markdown ingestion.
- Chunking, pgvector embeddings, PostgreSQL full-text search, hybrid retrieval, RRF, and reranking.
- RAG chat with citations and multi-turn conversation persistence.
- Streaming chat over Server-Sent Events.
- Retrieval debug endpoint exposing candidate scores and ranks.
- Reproducible retrieval evaluation with Hit Rate, Recall, MRR, and nDCG.
- Docker Compose development and production-style deployments.
- GitHub Actions CI for backend, frontend, and Docker build checks.
- Architecture, API, deployment, evaluation, security, screenshot, demo-data, and demo-video documentation.

## Verification Completed

| Check | Result |
| --- | --- |
| Backend tests | `185 passed, 1 warning` |
| Ruff | Passed |
| mypy | Passed, `94 source files` |
| Frontend typecheck | Passed |
| Frontend production build | Passed |
| Production Compose config | Passed |
| Production Docker build | Passed for backend and frontend |
| Retrieval evaluation | Passed and reproducible |
| Local secrets scan | No common real credential patterns found |

## Retrieval Evaluation Snapshot

| Strategy | Hit Rate@1 | MRR@1 | nDCG@1 |
| --- | ---: | ---: | ---: |
| vector | 0.750 | 0.750 | 0.750 |
| hybrid | 0.900 | 0.900 | 0.900 |
| hybrid_reranker | 1.000 | 1.000 | 1.000 |

Reproduce with:

```bash
.venv/bin/python scripts/run_retrieval_evaluation.py \
  --predictions evaluations/retrieval_predictions.jsonl \
  --json-output evaluations/retrieval_metrics.json
```

## GitHub Release Body

Use this body when publishing the GitHub release:

```markdown
# Enterprise RAG Knowledge Base v1.0.0

First complete portfolio release of a full-stack enterprise RAG knowledge base.

## Highlights

- FastAPI backend and React/Vite frontend
- JWT auth and protected frontend routes
- Knowledge-base CRUD with owner/editor/viewer permissions
- PDF, DOCX, TXT, and Markdown ingestion
- Chunking, pgvector embeddings, full-text search, hybrid retrieval, RRF, and reranking
- RAG chat with source citations and SSE streaming
- Retrieval debug endpoint and reproducible evaluation metrics
- Docker Compose dev and production-style deployment
- GitHub Actions CI for tests, lint, typecheck, frontend build, and Docker build
- Complete architecture, API, deployment, evaluation, security, screenshots, demo data, and demo video documentation

## Verification

- Backend tests: 185 passed
- Ruff: passed
- mypy: passed
- Frontend typecheck/build: passed
- Production Docker build: passed
- Retrieval evaluation reproduced
- Local secrets scan found no common real credential patterns

## Demo

Use `docs/demo-video.md` for the 2-3 minute demo flow. Demo data is in `docs/demo-data/`, and screenshots/diagrams are in `docs/screenshots/`.

## Known limitations

- Deterministic providers are the default for reproducible local demos.
- Synthetic evaluation data should be replaced with representative private documents for production benchmarking.
- Production Compose is a small-deployment reference, not a full managed cloud platform.
```

## Tagging Commands

Run after committing release prep changes:

```bash
git switch main
git pull origin main
git tag -a v1.0.0 -m "Enterprise RAG Knowledge Base v1.0.0"
git push origin v1.0.0
```

## Repository Topics

Suggested GitHub repository topics:

```text
rag
retrieval-augmented-generation
fastapi
react
typescript
postgresql
pgvector
sqlalchemy
alembic
llm
hybrid-search
reranking
docker
github-actions
enterprise-search
```

## Release Checklist

- [x] Run backend tests.
- [x] Run Ruff.
- [x] Run mypy.
- [x] Run frontend typecheck.
- [x] Run frontend build.
- [x] Validate production Docker Compose config.
- [x] Build production backend/frontend images.
- [x] Reproduce retrieval evaluation.
- [x] Run local secrets scan.
- [x] Update changelog.
- [x] Prepare release notes.
- [ ] Commit release prep changes.
- [ ] Push `main`.
- [ ] Create and push `v1.0.0` tag.
- [ ] Publish GitHub Release.
- [ ] Add repository topics.
- [ ] Attach demo video as a release asset if available.