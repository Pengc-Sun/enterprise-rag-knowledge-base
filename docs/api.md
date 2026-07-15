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

Returns active built-in template definitions. Week 1 seeds these categories: `general`, `policy_review`, `it_support`, and `research_review`. Each template includes directory, analysis task, and report schemas for later v2.0 instantiation work.

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
- Accepts optional `template_id`; Week 1 stores the selected template, while full template instantiation is scheduled for a later v2.0 week.
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

All knowledge base endpoints require authentication.

### Create knowledge base

```text
POST /api/v1/knowledge-bases
```

Request body:

```json
{
  "name": "Policy Library",
  "description": "Internal HR and travel policy documents"
}
```

Creates a private knowledge base owned by the current user.

### List knowledge bases

```text
GET /api/v1/knowledge-bases
```

Lists knowledge bases visible to the current user.

### Read knowledge base

```text
GET /api/v1/knowledge-bases/{knowledge_base_id}
```

Requires read permission.

### Update knowledge base

```text
PATCH /api/v1/knowledge-bases/{knowledge_base_id}
```

Requires write permission.

Request body fields are optional:

```json
{
  "name": "Updated Library",
  "description": "Updated description"
}
```

### Delete knowledge base

```text
DELETE /api/v1/knowledge-bases/{knowledge_base_id}
```

Requires owner permission. Returns `204 No Content`.

## Document Endpoints

All document endpoints are scoped to a knowledge base and require authentication.

### List documents

```text
GET /api/v1/knowledge-bases/{knowledge_base_id}/documents
```

Requires read permission. Returns documents with chunk counts.

### Upload document

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/documents
Content-Type: multipart/form-data
```

Form field:

```text
file=<uploaded file>
```

Requires write permission.

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

### Reprocess document

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/reprocess
```

Requires write permission. Re-parses the stored file, replaces chunks, and re-embeds them.

### Delete document

```text
DELETE /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}
```

Requires write permission. Deletes the database row and stored file. Returns `204 No Content`.

## RAG Endpoints

### Query knowledge base

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/query
```

Requires read permission.

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
POST /api/v1/knowledge-bases/{knowledge_base_id}/query/debug
```

Requires read permission. Returns retrieval internals without generating an answer.

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

Conversations are scoped to a knowledge base and require read access to that knowledge base.

### Create conversation

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations
```

Request body:

```json
{
  "title": "Travel policy questions"
}
```

### List conversations

```text
GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations
```

### Read conversation

```text
GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}
```

### Update conversation

```text
PATCH /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}
```

Request body:

```json
{
  "title": "Updated title"
}
```

### Delete conversation

```text
DELETE /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}
```

Returns `204 No Content`.

### List messages

```text
GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/messages
```

### Chat

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/chat
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
POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}/chat/stream
```

Uses Server-Sent Events. The stream can emit token, metadata, source, completion, and error events.

## Permission Summary

| Operation | Required permission |
| --- | --- |
| Read knowledge base | owner, editor, viewer |
| Update knowledge base | owner, editor |
| Delete knowledge base | owner |
| List/upload/reprocess/delete documents | read for list, write for changes |
| RAG query and debug | owner, editor, viewer |
| Conversations and chat | owner, editor, viewer |

## API Testing

Backend API behavior is covered by tests under `backend/tests/`, including auth, knowledge bases, documents, RAG queries, conversations, streaming, unified errors, and end-to-end flows.
