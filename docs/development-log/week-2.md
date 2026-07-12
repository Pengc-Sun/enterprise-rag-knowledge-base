# Week 2 Development Log

## Goal

Implement user authentication, JWT-based current-user access, knowledge base CRUD, and permission foundations.

## Completed

- Added `users` table with email, username, hashed password, role, active state, and timestamps.
- Added Argon2 password hashing through `pwdlib`.
- Added user schemas for creation and read responses.
- Added email and username uniqueness checks.
- Added registration API at `POST /api/v1/auth/register`.
- Added login API at `POST /api/v1/auth/login`.
- Added JWT access token generation.
- Added current-user dependency from bearer token.
- Added inactive-user check.
- Added `/api/v1/users/me`.
- Added `knowledge_bases` table with owner relationship and visibility.
- Added knowledge base schemas, services, and CRUD APIs.
- Added `knowledge_base_members` table.
- Added owner, editor, and viewer permission model.
- Added owner/editor/viewer access checks to knowledge base CRUD.
- Added tests for authentication, JWT dependency handling, user services, knowledge base models, CRUD, and permission isolation.

## API Surface

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET /api/v1/users/me

POST /api/v1/knowledge-bases
GET /api/v1/knowledge-bases
GET /api/v1/knowledge-bases/{knowledge_base_id}
PATCH /api/v1/knowledge-bases/{knowledge_base_id}
DELETE /api/v1/knowledge-bases/{knowledge_base_id}
```

## Permission Rules

- Owner can read, update, and delete a knowledge base.
- Editor can read and update a knowledge base.
- Viewer can read a knowledge base.
- Non-members cannot read or modify private knowledge bases.
- Unauthorized or non-member knowledge base access returns `404 Knowledge base not found`.

## Verified

```bash
make check
make migrate-current
curl http://localhost:8000/docs
```

Manual acceptance flow verified against Docker services:

- Register owner, viewer, editor, and unrelated user.
- Log in each user and receive bearer JWT access tokens.
- Owner creates a private knowledge base.
- Owner can list and delete the knowledge base.
- Viewer can read the knowledge base.
- Viewer cannot update the knowledge base.
- Editor can update the knowledge base.
- Unrelated user cannot read the knowledge base.
- Deleted knowledge base returns 404.

Verification results:

- `make check`: passed
- `pytest`: 35 tests passed
- `ruff check .`: passed
- `mypy backend`: passed
- Swagger `/docs`: 200
- Alembic current revision: `0004 (head)`
- Docker services: backend, PostgreSQL, and Redis healthy

## Week 2 Acceptance Criteria

- Users can register and log in: done
- JWT authentication works: done
- Users can create knowledge bases: done
- Users cannot access unauthorized knowledge bases: done
- Permission tests pass: done

## Notes for Week 3

- Add document model and processing status.
- Add secure file upload endpoint.
- Validate file extension, MIME type, and file size.
- Save uploaded files under controlled storage paths.
- Begin parser support for PDF and TXT.
