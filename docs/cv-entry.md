# CV Entry

Use this file as a concise project description for a resume, portfolio, or interview discussion.

## One-Line Summary

Built a full-stack Enterprise RAG Knowledge Base with FastAPI, React, PostgreSQL/pgvector, hybrid retrieval, reranking, streaming chat, source citations, Docker deployment, CI, and reproducible evaluation.

## Resume Bullet Options

- Built an enterprise RAG knowledge base with FastAPI, React, PostgreSQL/pgvector, SQLAlchemy async, Alembic, Docker Compose, and GitHub Actions CI.
- Implemented authenticated multi-tenant knowledge bases with JWT auth, owner/editor/viewer permissions, document ingestion, chunking, embeddings, hybrid retrieval, reranking, and cited RAG answers.
- Added streaming multi-turn chat with persisted conversations, source citation inspection, retrieval debug tooling, structured logs, unified API errors, and provider retry/timeout handling.
- Created reproducible RAG evaluation assets with 40 labelled synthetic questions and metrics including Hit Rate@K, Recall@K, MRR@K, and nDCG@K.
- Packaged the project for portfolio review with production-style Docker deployment, CI checks, architecture/API/deployment/security documentation, screenshots, demo data, and release notes.

## Interview Talking Points

- Why hybrid retrieval was used instead of vector-only retrieval.
- How Reciprocal Rank Fusion combines vector and keyword candidates.
- How reranking changes final context selection.
- How knowledge base permissions isolate private documents.
- How source citations help users verify generated answers.
- How deterministic providers make tests and demos reproducible.
- What would change for production: managed secrets, CORS allowlist, TLS, rate limits, malware scanning, worker queue, monitoring, backups, and real provider integrations.

## Suggested Repository Description

```text
Full-stack enterprise RAG knowledge base with FastAPI, React, PostgreSQL/pgvector, hybrid retrieval, reranking, streaming chat, citations, Docker, CI, and evaluation metrics.
```
