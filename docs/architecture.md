# Architecture Guide

This document describes the runtime architecture of Enterprise RAG Knowledge Base as implemented in the current codebase.

## Goals

The system is designed to provide a private, authenticated RAG workflow for enterprise documents:

- Users register, log in, and receive JWT access tokens.
- Users create knowledge bases and manage documents inside them.
- The v2.0 upgrade introduces workspaces as the top-level project boundary above knowledge bases.
- Uploaded files are parsed, chunked, embedded, and stored in PostgreSQL with pgvector.
- Queries use hybrid retrieval, reranking, and an LLM provider abstraction to generate grounded answers.
- Conversations persist messages and source citations for multi-turn chat.
- The frontend exposes the full workflow through React pages.

## High-Level Runtime

```text
Browser / React / Vite
        |
        | HTTP JSON + Server-Sent Events
        v
FastAPI backend
        |
        | SQLAlchemy async sessions
        v
PostgreSQL + pgvector

Supporting services:
        +-- Redis service dependency
        +-- local or mounted file storage
        +-- embedding provider abstraction
        +-- reranker provider abstraction
        +-- LLM provider abstraction
        +-- structured request and RAG logging
```

## Backend Layout

```text
backend/app/main.py                  FastAPI application, middleware, exception handlers
backend/app/api/v1/                  API router and endpoint modules
backend/app/api/dependencies/        Authentication dependencies
backend/app/core/                    Settings, logging, security, exception formatting
backend/app/db/                      SQLAlchemy base, async engine, session dependency
backend/app/models/                  SQLAlchemy ORM models
backend/app/schemas/                 Pydantic request and response schemas
backend/app/services/                Business logic and provider abstractions
backend/app/evaluation/              Retrieval metric utilities
backend/tests/                       Unit, integration, and API tests
```

`backend/app/main.py` wires the application together:

- Configures structured logging from settings.
- Adds request logging middleware.
- Adds permissive CORS for development.
- Mounts API v1 routes under `API_V1_PREFIX`, default `/api/v1`.
- Registers unified HTTP and validation exception handlers.
- Disposes the async database engine during application shutdown.

## Frontend Layout

```text
frontend/src/App.tsx                  Application routes
frontend/src/api/                     API client modules and shared types
frontend/src/auth/AuthContext.tsx     Token state and auth helpers
frontend/src/components/              Shared route protection component
frontend/src/pages/                   Login, register, dashboard, documents, chat pages
frontend/src/styles.css               Application styling
```

The frontend is a React + TypeScript + Vite app. It stores auth state through the auth context, protects authenticated routes, and calls the backend through typed API modules.

## Data Model

Main entities:

- `User`: registered account with unique email, username, hashed password, role, and active flag.
- `Workspace`: v2.0 project boundary with owner, slug, status, optional template, and member list.
- `WorkspaceMember`: v2.0 user-to-workspace role row with `owner`, `admin`, `editor`, `reviewer`, or `viewer`.
- `WorkspaceTemplate`: v2.0 reusable workspace definition with category, directory schema, analysis task schema, and report schema.
- `KnowledgeBase`: v1.0 user-owned collection for documents, conversations, and permissions. It remains the active document boundary until the Week 2 v2.0 migration attaches existing knowledge-base data to workspaces.
- `KnowledgeBaseMember`: user-to-knowledge-base permission row with `owner`, `editor`, or `viewer` permissions.
- `Document`: uploaded file metadata, hash, storage path, status, and creator.
- `DocumentChunk`: parsed content chunk with page, section, token count, JSON metadata, full-text vector, and pgvector embedding.
- `Conversation`: user conversation scoped to a knowledge base.
- `Message`: persisted user, assistant, or system message with source citations and optional token usage.
- `AuditLog`: workspace-scoped event record for key workspace, member, and document actions. It stores actor/resource IDs without cascading foreign keys so deletion does not erase the audit trail.

Important relationships:

- Deleting a user cascades owned knowledge bases, memberships, conversations, owned workspaces, and workspace memberships.
- Deleting a workspace cascades workspace memberships. Later v2.0 migration work will attach knowledge bases, documents, chunks, and conversations to workspaces.
- Deleting a knowledge base cascades members, documents, chunks, conversations, and messages.
- Deleting a document cascades its chunks and removes the stored upload file.
- Audit logs preserve workspace, actor, and resource IDs independently of resource deletion.

## Request Lifecycle

A typical API request follows this path:

1. `RequestLoggingMiddleware` binds or generates a request ID.
2. FastAPI routes the request through the v1 API router.
3. Protected endpoints call `get_current_active_user`.
4. Route handlers validate request bodies through Pydantic schemas.
5. Service functions execute business logic using an async SQLAlchemy session.
6. Responses are wrapped in `APIResponse` for successful calls.
7. Exceptions are converted into the unified error response format.
8. Middleware logs method, path, status, latency, and error details.

## Authentication and Authorization

Authentication uses bearer JWTs. Tokens contain the user ID in the `sub` claim and an expiration time in `exp`.

Authorization is enforced in service or endpoint logic through knowledge base and workspace permission checks:

- Knowledge-base read operations allow `owner`, `editor`, or `viewer`.
- Knowledge-base write operations allow `owner` or `editor`.
- Deleting a knowledge base requires `owner`.
- Workspace read operations allow `owner`, `admin`, `editor`, `reviewer`, or `viewer`.
- Workspace write and member-management operations allow `owner` or `admin`.
- Deleting a workspace requires `owner`.
- Workspace member endpoints cannot assign the `owner` role or modify/remove the workspace owner membership.

Unauthorized or missing resources intentionally return `404` for scoped access in many paths, which avoids leaking private resource existence.

## Document Ingestion Flow

```text
Upload file
  -> sanitize filename
  -> validate extension and MIME type
  -> stream to storage while hashing
  -> reject oversized file
  -> reject duplicate SHA-256 hash within knowledge base
  -> create Document row
  -> parse document text
  -> chunk parsed text
  -> replace DocumentChunk rows
  -> embed chunks
  -> mark embedding status per chunk
```

Supported upload types are PDF, DOCX, TXT, Markdown, and `.markdown`.

## RAG Query Flow

```text
Question + optional history + optional metadata filters
  -> optional query rewriting
  -> vector retrieval through embedding provider and pgvector cosine distance
  -> keyword retrieval through PostgreSQL full-text search
  -> Reciprocal Rank Fusion
  -> deterministic reranker abstraction
  -> prompt construction with selected context chunks
  -> LLM provider call
  -> answer, citations, model/provider metadata
  -> structured RAG log event
```

The RAG service logs retrieval latency, rerank latency, LLM latency, total latency, token usage, retrieved chunk IDs, status, and error details.

## Provider Abstractions

The backend includes provider abstraction layers for:

- Embeddings: deterministic local provider plus OpenAI-compatible remote providers for OpenAI, Qwen-compatible endpoints, and other compatible gateways such as OpenRouter.
- Reranking: deterministic cross-encoder-style reranker.
- LLMs: deterministic local provider and OpenAI-compatible providers for DeepSeek, Qwen, and OpenAI.

The deterministic providers make local development and CI reproducible without external API keys.

## Deployment Architecture

Development Compose starts:

- `backend`
- `postgres` using `pgvector/pgvector:pg16`
- `redis` using `redis:7-alpine`

Production-style Compose starts:

- `postgres` with named volume persistence
- `redis` with append-only persistence
- `migrate` one-shot Alembic upgrade service
- `backend` after database, Redis, and migration readiness
- `frontend` Nginx container after backend health is ready

## Observability

The current observability layer includes:

- Request ID propagation with `X-Request-ID`.
- Structured request logs.
- Structured RAG query logs.
- Unified error responses with request IDs.
- Health checks for application and database connectivity.

## Current Constraints

- Background document processing runs inside the request path rather than an external worker queue.
- Remote OpenAI-compatible embedding clients are implemented; deterministic embeddings remain the local default for development and CI.
- Production Compose is intended for validation and small deployments, not a managed cloud architecture.
