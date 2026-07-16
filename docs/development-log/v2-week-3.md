# v2.0 Week 3 Development Log

## Goal

Make workspace isolation enforceable across knowledge bases, documents, retrieval, RAG, and
conversation paths, then verify the behavior with negative tests and full regression checks.

## Completed

- Updated knowledge-base APIs to require explicit workspace context.
- Added workspace-scoped knowledge-base routes under
  `/api/v1/workspaces/{workspace_id}/knowledge-bases`.
- Updated document list, upload, detail, reprocess, and delete flows to validate workspace
  membership before nested resource access.
- Added workspace-scoped document routes under
  `/api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/documents`.
- Updated vector, keyword, and hybrid retrieval queries to filter by both `workspace_id` and
  `knowledge_base_id`.
- Updated RAG query and retrieval debug endpoints to require workspace context.
- Updated conversations and messages to validate workspace membership and ownership before
  reading, writing, chatting, or streaming.
- Added workspace-scoped conversation routes under
  `/api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/conversations`.
- Added cross-workspace negative tests for documents, retrieval chunks, conversations, and RAG
  queries.
- Added `audit_logs` table, model, service, and migration `0017`.
- Added audit logging for workspace create/update/delete, workspace member changes, and document
  upload/reprocess/delete actions.
- Updated architecture and security docs to describe workspace isolation and audit logging.

## Isolation Guarantees

- Workspace access is checked before any nested knowledge-base, document, conversation, RAG, or
  retrieval operation.
- Top-level compatibility routes must receive `workspace_id` as a query parameter.
- Workspace-scoped routes are preferred for new v2.0 clients.
- Knowledge bases are fetched by `(workspace_id, knowledge_base_id)`.
- Documents are fetched by `(workspace_id, knowledge_base_id, document_id)`.
- Conversations are fetched by `(workspace_id, knowledge_base_id, conversation_id, user_id)`.
- Retrieval candidates are selected from `document_chunks` only when both `workspace_id` and
  `knowledge_base_id` match the current request.
- Cross-workspace access returns `404` before lower-level reads, writes, retrieval, or LLM calls.
- Audit logs preserve workspace, actor, action, resource, and metadata for key workspace and
  document write actions.

## Verified

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy backend
.venv/bin/alembic current
```

Week 3 close-out verification after Day 21:

- `pytest`: 277 tests passed, 1 skipped
- `ruff check .`: passed
- `mypy backend`: passed
- Alembic current revision: `0017 (head)`
- Alembic `0017` upgrade/downgrade round trip: passed
- `git diff --check`: passed

## Week 3 Acceptance Criteria

- Workspace A cannot read, retrieve, upload into, or chat with Workspace B data: done.
- Retrieval never returns chunks from another workspace: done.
- Automated tests cover cross-workspace isolation: done.

## Notes for Week 4

- Start template instantiation work.
- Add workspace directory model, service, and APIs.
- Create template-driven default directories, analysis tasks, and report structure.
- Keep all new template resources scoped by workspace.
