# v2.0 Week 4 Development Log

## Goal

Make workspace templates create real project structure when a workspace is created.

## Completed

- Expanded built-in template definitions for `general`, `policy_review`, `it_support`, and
  `research_review`.
- Added structured template schemas for:
  - workspace directories
  - default workspace knowledge bases
  - initial analysis tasks
  - draft report sections
- Added `workspace_directories` table, model, service functions, schemas, and workspace-scoped
  APIs.
- Added directory parent-child support and per-workspace directory path uniqueness.
- Added directory audit actions for create, update, and delete.
- Updated workspace creation so an active `template_id` is validated before creation.
- Implemented template-driven directory instantiation during workspace creation.
- Implemented template-driven default knowledge-base creation and owner permissions.
- Added `analysis_tasks`, `reports`, and `report_sections` tables and models.
- Implemented template-driven initial analysis task creation.
- Implemented template-driven draft report and report section creation.
- Added tests for template definitions, workspace directory services and APIs, template
  instantiation, nested directory parent links, migration structure, and model behavior.
- Updated README and API documentation with current template behavior.

## Template Instantiation Behavior

When `POST /api/v1/workspaces` receives an active `template_id`, workspace creation now creates:

- the workspace row
- the creator's workspace `owner` membership
- template directories from `directory_schema.directories`
- default knowledge bases from `directory_schema.knowledge_bases`
- knowledge-base owner memberships for the creator
- initial analysis tasks from `analysis_task_schema.tasks`
- one draft report and report sections from `report_schema.sections`

If `template_id` is missing, workspace creation keeps the simple workspace-only behavior. If
`template_id` points to a missing or inactive template, the API returns `404`.

## APIs Added

```text
GET    /api/v1/workspaces/{workspace_id}/directories
POST   /api/v1/workspaces/{workspace_id}/directories
GET    /api/v1/workspaces/{workspace_id}/directories/{directory_id}
PATCH  /api/v1/workspaces/{workspace_id}/directories/{directory_id}
DELETE /api/v1/workspaces/{workspace_id}/directories/{directory_id}
```

Read operations require workspace membership. Write operations require `owner` or `admin`.

## Migrations

- `0018`: update built-in workspace template schemas.
- `0019`: create `workspace_directories`.
- `0020`: add default knowledge-base definitions to built-in templates.
- `0021`: create `analysis_tasks`, `reports`, and `report_sections`.

## Verified

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy backend
.venv/bin/alembic current
git diff --check
```

Week 4 close-out verification after Day 28:

- `pytest`: 307 tests passed, 1 skipped
- `ruff check .`: passed
- `mypy backend`: passed
- Alembic current revision: `0021 (head)`
- Alembic upgrade/downgrade round trips through `0018`, `0019`, `0020`, and `0021`: passed
- `git diff --check`: passed

## Week 4 Acceptance Criteria

- Workspace creation can choose a template: done.
- Template creates directories, analysis tasks, and report outline: done.
- Different templates create different task definitions: done.

## Notes for Week 5

- Build the analysis task engine around the `analysis_tasks` table.
- Add `analysis_results` persistence and structured AI output validation.
- Add APIs for listing, reading, and running analysis tasks.
- Keep all task and result access scoped by workspace.

