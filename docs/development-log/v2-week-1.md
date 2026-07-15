# v2.0 Week 1 Development Log

## Goal

Add workspace as the top-level v2.0 project boundary without breaking the existing v1.0 knowledge-base, document, retrieval, and chat flows.

## Completed

- Created the `feature/v2-workspaces` branch for isolated v2.0 development.
- Added `Workspace`, `WorkspaceMember`, and `WorkspaceTemplate` SQLAlchemy models.
- Added workspace statuses, member roles, and template categories.
- Added Pydantic schemas for workspace create/update/read, member create/update/read, and template read payloads.
- Added Alembic migration `0011` for workspace tables, indexes, foreign keys, and uniqueness constraints.
- Added Alembic migration `0012` to seed built-in workspace templates.
- Seeded `general`, `policy_review`, `it_support`, and `research_review` template definitions.
- Implemented workspace CRUD service functions.
- Implemented workspace CRUD API endpoints under `/api/v1/workspaces`.
- Implemented workspace member list, add, update, and remove service functions.
- Implemented workspace member API endpoints under `/api/v1/workspaces/{workspace_id}/members`.
- Protected owner membership from member-management endpoints.
- Prevented assigning `owner` role through member endpoints.
- Implemented workspace template list/detail service functions.
- Implemented template API endpoints under `/api/v1/workspace-templates`.
- Added backend tests for workspace schemas, models, services, endpoints, template APIs, and access-control boundaries.
- Updated README, API, architecture, and upgrade-plan documentation for Week 1.

## API Surface Added

```text
GET    /api/v1/workspace-templates
GET    /api/v1/workspace-templates/{template_id}
POST   /api/v1/workspaces
GET    /api/v1/workspaces
GET    /api/v1/workspaces/{workspace_id}
PATCH  /api/v1/workspaces/{workspace_id}
DELETE /api/v1/workspaces/{workspace_id}
GET    /api/v1/workspaces/{workspace_id}/members
POST   /api/v1/workspaces/{workspace_id}/members
PATCH  /api/v1/workspaces/{workspace_id}/members/{user_id}
DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}
```

## Verified

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy backend
```

Verification results after Day 7 documentation updates:

- `pytest`: 237 tests passed
- `ruff check .`: passed
- `mypy backend`: passed
- `git diff --check`: passed

## Week 1 Acceptance Criteria

- A user can create multiple workspaces: done.
- Workspace owner membership is created automatically: done.
- Users only see workspaces they own or belong to: done.
- Template APIs return active template definitions: done.

## Notes for Week 2

- Add nullable `workspace_id` columns to v1.0 data tables.
- Backfill existing owner data into default workspaces.
- Verify migration upgrade and downgrade without data loss.
- Prepare services for explicit workspace context.
