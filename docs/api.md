# API Guide

This document describes the public HTTP API implemented by the FastAPI backend.

## Base URLs

Local backend:

```text
http://localhost:8000
```

Versioned API prefix:

```text
/api/v1
```

Interactive documentation:

```text
http://localhost:8000/docs
```

## Response Envelope

Successful responses use the shared `APIResponse` envelope:

```json
{
  "success": true,
  "message": "success",
  "data": {}
}
```

Failed responses use the same envelope and place details under `data.error`:

```json
{
  "success": false,
  "message": "Validation error",
  "data": {
    "error": {
      "code": "validation_error",
      "status_code": 422,
      "request_id": "...",
      "details": {}
    }
  }
}
```

Common error codes:

| HTTP status | Code |
| ---: | --- |
| 400 | `bad_request` |
| 401 | `unauthorized` |
| 403 | `forbidden` |
| 404 | `not_found` |
| 409 | `conflict` |
| 422 | `validation_error` |
| 429 | `rate_limited` |
| 500 | `internal_server_error` |
| 504 | `gateway_timeout` |

## Authentication

Protected endpoints require a bearer token:

```text
Authorization: Bearer <access_token>
```

The token is returned by the login endpoint and contains the user ID in the JWT `sub` claim.

## System Endpoints

### Root health

```text
GET /health
```

Checks that the FastAPI app is running.

### API health

```text
GET /api/v1/health
```

Returns service status, application name, and environment.

### Database health

```text
GET /api/v1/health/database
```

Runs a lightweight `SELECT 1` against PostgreSQL.

## Auth Endpoints

### Register

```text
POST /api/v1/auth/register
```

Request body:

```json
{
  "email": "user@example.com",
  "username": "demo_user",
  "password": "strong-password"
}
```

Behavior:

- Creates a user account.
- Hashes the password before storing it.
- Rejects duplicate email or username with `409 conflict`.

### Login

```text
POST /api/v1/auth/login
```

Request body:

```json
{
  "email": "user@example.com",
  "password": "strong-password"
}
```

Response data:

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

### Current user

```text
GET /api/v1/users/me
```

Requires authentication. Returns the active user represented by the bearer token.


## Workspace Endpoints

Workspace endpoints are part of the v2.0 upgrade branch and require authentication. A workspace is the new top-level project boundary for later v2.0 document, analysis, review, and report workflows.

### List workspace templates

```text
GET /api/v1/workspace-templates
```

Returns active built-in template definitions. The built-in categories are `general`,
`policy_review`, `it_support`, and `research_review`.

Each template includes:

- `directory_schema.directories`: logical workspace directories to create.
- `directory_schema.knowledge_bases`: default knowledge bases to create inside the workspace.
- `analysis_task_schema.tasks`: initial analysis task definitions with structured output schemas.
- `report_schema.sections`: initial report outline sections and their source task keys.

### Read workspace template

```text
GET /api/v1/workspace-templates/{template_id}
```

Returns one active template or `404 not_found` if the template does not exist or is inactive.

### Create workspace

```text
POST /api/v1/workspaces
```

Request body:

```json
{
  "name": "Policy Review",
  "slug": "policy-review",
  "description": "Review internal policy documents",
  "template_id": null
}
```

Behavior:

- Creates a workspace owned by the current user.
- Automatically creates an `owner` membership for the creator.
- Accepts optional `template_id`.
- If `template_id` is provided, the template must be active or the API returns `404`.
- Template creation currently instantiates:
  - workspace directories from `directory_schema.directories`
  - default knowledge bases from `directory_schema.knowledge_bases`
  - initial analysis tasks from `analysis_task_schema.tasks`
  - one draft report and report sections from `report_schema.sections`
- Requires a lowercase hyphenated slug.

### List workspaces

```text
GET /api/v1/workspaces
```

Lists workspaces the current user owns or belongs to.

### Read workspace

```text
GET /api/v1/workspaces/{workspace_id}
```

Requires workspace membership. Missing or inaccessible workspaces return `404 not_found`.

### Update workspace

```text
PATCH /api/v1/workspaces/{workspace_id}
```

Requires `owner` or `admin` role. Request body fields are optional:

```json
{
  "name": "Updated Policy Review",
  "slug": "updated-policy-review",
  "description": "Updated description",
  "status": "active"
}
```

`status` can be `active` or `archived`.

### Delete workspace

```text
DELETE /api/v1/workspaces/{workspace_id}
```

Requires `owner` role. Returns `204 No Content`.

### List workspace directories

```text
GET /api/v1/workspaces/{workspace_id}/directories
```

Requires workspace membership. Lists logical directories created manually or from the selected
workspace template.

### Create workspace directory

```text
POST /api/v1/workspaces/{workspace_id}/directories
```

Requires `owner` or `admin` role. Request body:

```json
{
  "name": "Policies",
  "path": "policies",
  "description": "Policy documents",
  "parent_id": null,
  "sort_order": 10
}
```

`path` must be lowercase and may contain hyphenated path segments such as
`policies/reviewed`.

### Read workspace directory

```text
GET /api/v1/workspaces/{workspace_id}/directories/{directory_id}
```

Requires workspace membership. The directory must belong to the supplied workspace.

### Update workspace directory

```text
PATCH /api/v1/workspaces/{workspace_id}/directories/{directory_id}
```

Requires `owner` or `admin` role. Supports updating `name`, `path`, `description`,
`parent_id`, and `sort_order`. A directory cannot be its own parent.

### Delete workspace directory

```text
DELETE /api/v1/workspaces/{workspace_id}/directories/{directory_id}
```

Requires `owner` or `admin` role. Returns `204 No Content` on success.

### List workspace members

```text
GET /api/v1/workspaces/{workspace_id}/members
```

Requires workspace membership.

### Add workspace member

```text
POST /api/v1/workspaces/{workspace_id}/members
```

Requires `owner` or `admin` role. Request body:

```json
{
  "user_id": "00000000-0000-0000-0000-000000000000",
  "role": "reviewer"
}
```

Assignable roles are `admin`, `editor`, `reviewer`, and `viewer`. The `owner` role cannot be assigned through member endpoints.

### Update workspace member

```text
PATCH /api/v1/workspaces/{workspace_id}/members/{user_id}
```

Requires `owner` or `admin` role. The workspace owner membership cannot be modified through this endpoint.

### Remove workspace member

```text
DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}
```

Requires `owner` or `admin` role. The workspace owner membership cannot be removed through this endpoint. Returns `204 No Content` on success.

## Knowledge Base Endpoints

All knowledge base endpoints require authentication and workspace context. The v2 workspace-scoped
routes are preferred. The top-level routes remain available only when `workspace_id` is supplied as a
query parameter.

### Create knowledge base

```text
POST /api/v1/workspaces/{workspace_id}/knowledge-bases
POST /api/v1/knowledge-bases?workspace_id={workspace_id}
```

Request body:

```json
{
  "name": "Policy Library",
  "description": "Internal HR and travel policy documents"
}
```

Requires workspace owner/admin access. Creates a private knowledge base owned by the current user
inside the selected workspace.

### List knowledge bases

```text
GET /api/v1/workspaces/{workspace_id}/knowledge-bases
GET /api/v1/knowledge-bases?workspace_id={workspace_id}
```

Requires workspace membership. Lists knowledge bases in the selected workspace.

### Read knowledge base

```text
GET /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}
GET /api/v1/knowledge-bases/{knowledge_base_id}?workspace_id={workspace_id}
```

Requires workspace membership. The knowledge base must belong to the supplied workspace.

### Update knowledge base

```text
PATCH /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}
PATCH /api/v1/knowledge-bases/{knowledge_base_id}?workspace_id={workspace_id}
```

Requires workspace owner/admin access.

Request body fields are optional:

```json
{
  "name": "Updated Library",
  "description": "Updated description"
}
```

### Delete knowledge base

```text
DELETE /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}
DELETE /api/v1/knowledge-bases/{knowledge_base_id}?workspace_id={workspace_id}
```

Requires workspace owner access. Returns `204 No Content`.

## Document Endpoints

All document endpoints require authentication, workspace context, and a knowledge base that belongs
to the supplied workspace. The v2 workspace-scoped routes are preferred. The top-level routes remain
available only when `workspace_id` is supplied as a query parameter.

### List documents

```text
GET /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/documents
GET /api/v1/knowledge-bases/{knowledge_base_id}/documents?workspace_id={workspace_id}
```

Requires workspace membership. Returns documents with chunk counts.

### Upload document

```text
POST /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/documents
POST /api/v1/knowledge-bases/{knowledge_base_id}/documents?workspace_id={workspace_id}
Content-Type: multipart/form-data
```

Form field:

```text
file=<uploaded file>
```

Requires workspace owner/admin access.

Supported file types:

- `.pdf` with `application/pdf`
- `.docx` with `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `.txt` with `text/plain`
- `.md` or `.markdown` with `text/markdown` or `text/plain`

Behavior:

- Sanitizes the filename.
- Streams the file to storage.
- Rejects files larger than `MAX_UPLOAD_SIZE_BYTES`.
- Rejects duplicate SHA-256 hashes within the same knowledge base.
- Parses, chunks, and embeds the document during upload.

### Read document

```text
GET /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/documents/{document_id}
GET /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}?workspace_id={workspace_id}
```

Requires workspace membership. The document must belong to the supplied workspace and knowledge
base.

### Reprocess document

```text
POST /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/documents/{document_id}/reprocess
POST /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/reprocess?workspace_id={workspace_id}
```

Requires workspace owner/admin access. Re-parses the stored file, replaces chunks, and re-embeds
them.

### Delete document

```text
DELETE /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/documents/{document_id}
DELETE /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}?workspace_id={workspace_id}
```

Requires workspace owner/admin access. Deletes the database row and stored file. Returns
`204 No Content`.

## RAG Endpoints

RAG endpoints require authentication, workspace context, and a knowledge base that belongs to the
supplied workspace. Retrieval candidates are filtered by both `workspace_id` and
`knowledge_base_id`.

### Query knowledge base

```text
POST /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/query
POST /api/v1/knowledge-bases/{knowledge_base_id}/query?workspace_id={workspace_id}
```

Requires workspace membership.

Request body:

```json
{
  "question": "What is the maximum meal allowance?",
  "history": [
    {"role": "user", "content": "Ask only about travel policy"}
  ],
  "filters": {
    "document_ids": [],
    "file_types": ["pdf"],
    "created_after": null,
    "created_before": null,
    "departments": [],
    "permissions": []
  }
}
```

Response data includes:

- `answer`
- `rewritten_question`
- `question_was_rewritten`
- `model`
- `provider`
- `context_chunk_count`
- `context_chunk_ids`
- `sources`

Source citations include document name, page number, chunk ID, original text, and similarity score.

### Retrieval debug

```text
POST /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/query/debug
POST /api/v1/knowledge-bases/{knowledge_base_id}/query/debug?workspace_id={workspace_id}
```

Requires workspace membership. Returns retrieval internals without generating an answer.

Debug candidates include:

- chunk ID
- document ID and name
- chunk index
- page number
- section title
- content preview
- vector rank and score
- keyword rank and score
- RRF score
- rerank score
- final rank

## Conversation Endpoints

Conversations are scoped to a workspace and knowledge base. Every conversation and message
operation validates workspace membership first, then validates that the knowledge base and
conversation belong to that workspace.

### Create conversation

```text
POST /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/conversations
POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations?workspace_id={workspace_id}
```

Request body:

```json
{
  "title": "Travel policy questions"
}
```

### List conversations

```text
GET /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/conversations
GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations?workspace_id={workspace_id}
```

### Read conversation

```text
GET /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}
GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}?workspace_id={workspace_id}
```

### Update conversation

```text
PATCH /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}
PATCH /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}?workspace_id={workspace_id}
```

Request body:

```json
{
  "title": "Updated title"
}
```

### Delete conversation

```text
DELETE /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}
DELETE /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}?workspace_id={workspace_id}
```

Returns `204 No Content`.

### List messages

```text
GET /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/messages
GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/messages?workspace_id={workspace_id}
```

### Chat

```text
POST /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/chat
POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/chat?workspace_id={workspace_id}
```

Request body:

```json
{
  "question": "Can I claim hotel laundry?",
  "filters": {
    "document_ids": [],
    "file_types": [],
    "departments": [],
    "permissions": []
  }
}
```

Stores both the user message and assistant message.

### Streaming chat

```text
POST /api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/chat/stream
POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/chat/stream?workspace_id={workspace_id}
```

Uses Server-Sent Events. The stream can emit token, metadata, source, completion, and error events.

## Analysis and Review Endpoints

Analysis task endpoints are workspace-scoped and require authentication. They turn retrieved
workspace evidence into structured AI output, then route that output through human review before it
can be used by report workflows.

### List analysis tasks

```text
GET /api/v1/workspaces/{workspace_id}/analysis-tasks
```

Requires workspace read access.

### Create analysis task

```text
POST /api/v1/workspaces/{workspace_id}/analysis-tasks
```

Requires workspace owner or admin.

### Run analysis task

```text
POST /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/run
```

Requires workspace owner or admin. Successful runs persist an `AnalysisResult` with status
`needs_review` and normalized citations.

### Review queue

```text
GET /api/v1/workspaces/{workspace_id}/analysis-tasks/review-queue
```

Requires workspace owner, admin, or reviewer. Optional filters:

- `status`: one of `ai_generated`, `needs_review`, `approved`, `edited`, or `rejected`
- `analysis_task_id`: restrict queue items to one task
- `task_type`: restrict queue items by task type
- `limit` and `offset`: bounded pagination

Without a `status` filter, the queue returns `ai_generated` and `needs_review` results.

### Create review decision

```text
POST /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/results/{analysis_result_id}/review-decisions
```

Requires workspace owner, admin, or reviewer.

Request body:

```json
{
  "decision": "edit",
  "comment": "Clarified the requirement wording.",
  "edited_result": {
    "summary": "Updated reviewer-approved summary",
    "findings": []
  }
}
```

Supported decisions:

- `approve`: marks the analysis result `approved`
- `edit`: requires `edited_result`, replaces the active structured result, and marks it `edited`
- `reject`: marks the analysis result `rejected`
- `request_changes`: marks the analysis result `needs_review`

Each decision persists a `ReviewDecision` row with the original AI output snapshot and any reviewer
edit. Successful review decisions also create an `AuditLog` record with action
`review_decision.created`.

## Report Endpoints

Report endpoints are workspace-scoped and require authentication. Day 43 provides the base report
and section API surface; later report workflow days add approved-content generation, preview,
editing, ordering, and exports.

### List reports

```text
GET /api/v1/workspaces/{workspace_id}/reports
```

Requires workspace read access.

### Create report

```text
POST /api/v1/workspaces/{workspace_id}/reports
```

Requires workspace owner or admin. New reports are created as `draft`.

Request body:

```json
{
  "title": "Policy Review Report"
}
```

### Read report

```text
GET /api/v1/workspaces/{workspace_id}/reports/{report_id}
```

Requires workspace read access.

### List report sections

```text
GET /api/v1/workspaces/{workspace_id}/reports/{report_id}/sections
```

Requires workspace read access.

### Create report section

```text
POST /api/v1/workspaces/{workspace_id}/reports/{report_id}/sections
```

Requires workspace owner or admin. New sections are created as `draft`.

Request body:

```json
{
  "template_section_key": "requirements",
  "title": "Policy Requirements",
  "body_markdown": "",
  "source_task_keys": ["policy_requirements"],
  "source_result_ids": [],
  "sort_order": 10
}
```

### Read report section

```text
GET /api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/{section_id}
```

Requires workspace read access.

## Permission Summary

| Operation | Required permission |
| --- | --- |
| Read/list knowledge bases | workspace owner, admin, editor, reviewer, viewer |
| Create/update knowledge base | workspace owner or admin |
| Delete knowledge base | workspace owner |
| List/read documents | workspace owner, admin, editor, reviewer, viewer |
| Upload/reprocess/delete documents | workspace owner or admin |
| RAG query and debug | workspace owner, admin, editor, reviewer, viewer |
| Conversations and chat | workspace owner, admin, editor, reviewer, viewer |
| List review queue | workspace owner, admin, reviewer |
| Create review decision | workspace owner, admin, reviewer |
| List/read reports and sections | workspace owner, admin, editor, reviewer, viewer |
| Create reports and sections | workspace owner or admin |

## API Testing

Backend API behavior is covered by tests under `backend/tests/`, including auth, knowledge bases, documents, RAG queries, conversations, streaming, analysis tasks, review decisions, unified errors, and end-to-end flows.
