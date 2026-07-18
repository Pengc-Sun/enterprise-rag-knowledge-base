# Security Guide

This document summarizes the current security model, controls, and remaining hardening work.

## Security Scope

The current project protects private workspaces and knowledge bases through:

- JWT authentication.
- Active-user checks.
- Workspace membership checks.
- Workspace-scoped resource lookups.
- Knowledge-base-scoped permissions.
- Upload validation.
- Unified error handling.
- Request IDs and structured logging for traceability.

It is not yet a fully hardened production deployment. Additional controls are listed in the hardening checklist below.

## Authentication

Users register with email, username, and password. Passwords are hashed through `pwdlib.PasswordHash.recommended()` before storage.

Login returns a JWT access token:

- `sub`: user ID.
- `exp`: expiration timestamp.
- signing key: `JWT_SECRET_KEY`.
- algorithm: `JWT_ALGORITHM`, default `HS256`.

Protected endpoints require:

```text
Authorization: Bearer <access_token>
```

Invalid, expired, missing, or malformed tokens return `401 unauthorized`.

## Authorization

Workspace membership is the v2.0 top-level authorization boundary:

| Role | Access |
| --- | --- |
| `owner` | Full workspace control, including delete. |
| `admin` | Workspace write and member-management operations. |
| `editor` | Workspace read and future content-editing workflows. |
| `reviewer` | Workspace read access plus review queue and review decision workflows. |
| `viewer` | Workspace read-only operations. |

Knowledge base permissions remain available for v1.0 compatibility:

| Permission | Access |
| --- | --- |
| `owner` | Full control, including delete. |
| `editor` | Read and write operations. |
| `viewer` | Read-only operations. |

Endpoint behavior:

- Workspace-scoped knowledge base reads allow workspace owner, admin, editor, reviewer, or viewer.
- Workspace-scoped knowledge base create/update require workspace owner or admin.
- Workspace-scoped knowledge base delete requires workspace owner.
- Document listing requires workspace read access.
- Document upload, reprocess, and delete require workspace owner or admin.
- Review queue listing and review decision creation require workspace owner, admin, or reviewer.
- Workspace creation, workspace updates, member changes, directory changes, document write actions,
  and successful review decisions create database audit log records.
- RAG query, retrieval debug, conversations, and chat require workspace read access.

For scoped resources, unauthorized access generally returns `404 Knowledge base not found` or resource-specific `404`, which avoids confirming whether private resources exist.

## Upload Security

Upload controls are implemented before document persistence:

- Filename is reduced to the basename through `PurePath`.
- Filename characters outside `A-Z`, `a-z`, `0-9`, `.`, `_`, and `-` are replaced with `_`.
- The sanitized stem is capped at 200 characters.
- Files without an allowed extension are rejected.
- MIME type must match the extension allowlist.
- File content is streamed in 1 MiB chunks.
- Upload size is capped by `MAX_UPLOAD_SIZE_BYTES`.
- SHA-256 hash is computed while streaming.
- Duplicate files are rejected within the same knowledge base.
- Failed uploads remove the partially written file.

Allowed types:

| Extension | MIME types |
| --- | --- |
| `.pdf` | `application/pdf` |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.txt` | `text/plain` |
| `.md`, `.markdown` | `text/markdown`, `text/plain` |

## Data Isolation

Isolation is enforced at the API, service, and query layers:

- Workspace access is checked before nested knowledge-base, document, conversation, RAG, or retrieval operations.
- Workspace-scoped routes include `workspace_id` in the path.
- Top-level compatibility routes require `workspace_id` as a query parameter.
- Knowledge bases are resolved by `(workspace_id, knowledge_base_id)`.
- Documents are resolved by `(workspace_id, knowledge_base_id, document_id)`.
- Conversations are resolved by `(workspace_id, knowledge_base_id, conversation_id, user_id)`.
- Retrieval queries are scoped to both `workspace_id` and `knowledge_base_id`.
- Retrieval cannot return chunks from another workspace.
- Metadata filters are applied inside retrieval query builders.
- Cross-workspace access returns `404` before lower-level document reads, retrieval, chat, or LLM calls.

## Error Handling

All application errors are returned through a consistent envelope:

```json
{
  "success": false,
  "message": "...",
  "data": {
    "error": {
      "code": "...",
      "status_code": 400,
      "request_id": "...",
      "details": {}
    }
  }
}
```

This prevents raw tracebacks from being returned to clients and gives support workflows a request ID for log correlation.

## Logging and Privacy

The request middleware logs:

- method
- path
- status
- total latency
- error string when present
- request ID

The RAG service logs:

- user ID
- knowledge base ID
- rewritten query
- retrieved chunk IDs
- retrieval, rerank, LLM, and total latencies
- token usage
- status and error details

Operational caution:

- Do not log provider API keys.
- Avoid logging uploaded document bodies outside the RAG context needed for debugging.
- Treat query text as potentially sensitive enterprise data.
- Use access-controlled log storage in any shared deployment.

## Secrets

Never commit:

- `.env`
- provider API keys
- real database passwords
- production JWT secrets
- user data or uploaded enterprise documents

Before any non-local deployment, rotate:

- `JWT_SECRET_KEY`
- `POSTGRES_PASSWORD`
- provider API keys

Example files contain placeholder values only.

## Network and CORS

The FastAPI app currently allows all origins, methods, headers, and credentials. This is acceptable for development, but production should restrict CORS to known frontend origins.

Production-style Docker currently exposes only the frontend port by default. The backend is reached internally by the frontend proxy.

## Provider Security

Remote LLM and embedding providers use bearer API keys in HTTP `Authorization` headers. The OpenAI-compatible LLM provider applies:

- request timeout
- bounded retries
- exponential retry backoff
- specific handling for `429` and timeout failures

When enabling remote providers:

- store keys only in environment variables or a secret manager
- verify base URLs and model names
- monitor provider errors and rate limits
- avoid sending documents that should not leave the deployment boundary

## Current Gaps

The following controls are not yet fully implemented:

- Production CORS allowlist.
- TLS termination instructions.
- Rate limiting for public endpoints.
- Account lockout or login throttling.
- Password reset and email verification.
- Virus or malware scanning for uploads.
- Dedicated background worker isolation for parsing and embedding.
- Audit log UI and immutable audit log storage.
- Centralized secret manager integration.
- Automated dependency vulnerability scanning.

## Hardening Checklist

Before production use:

- Replace all placeholder secrets.
- Restrict CORS to the deployed frontend origin.
- Put the app behind TLS.
- Add API rate limiting.
- Add upload malware scanning if external users can upload files.
- Add database backups and restore tests.
- Add monitoring and alerting for error rates, latency, disk usage, and queue depth if workers are introduced.
- Add dependency scanning in CI.
- Review log retention and access policies.
- Confirm uploaded file storage is encrypted at rest in the target environment.
