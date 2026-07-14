# Security Guide

This document summarizes the current security model, controls, and remaining hardening work.

## Security Scope

The current project protects private knowledge bases through:

- JWT authentication.
- Active-user checks.
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

Knowledge base permissions use three roles:

| Permission | Access |
| --- | --- |
| `owner` | Full control, including delete. |
| `editor` | Read and write operations. |
| `viewer` | Read-only operations. |

Endpoint behavior:

- Knowledge base reads allow owner, editor, viewer.
- Knowledge base updates require owner or editor.
- Knowledge base delete requires owner.
- Document listing requires read access.
- Document upload, reprocess, and delete require write access.
- RAG query, retrieval debug, conversations, and chat require read access.

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

Isolation is enforced at the service and query layers:

- Knowledge base access checks include the current user ID and allowed permissions.
- Document routes always include `knowledge_base_id` and verify access before document lookup.
- Retrieval queries are scoped to a single `knowledge_base_id`.
- Conversations are scoped to both user and knowledge base.
- Metadata filters are applied inside retrieval query builders.

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
- Audit log UI or immutable audit trail.
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
