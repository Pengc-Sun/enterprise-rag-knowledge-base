# v2.0 Week 7 Development Log

## Goal

Build the report workflow on top of reviewed analysis results so formal report content only comes
from approved or reviewer-edited findings.

## Completed

- Added workspace-scoped report APIs for listing, creating, reading, and updating reports.
- Added workspace-scoped report section APIs for listing, creating, reading, updating, and ordering
  sections.
- Added draft section generation from approved analysis results.
- Enforced approved-content rules for report section sources:
  - `approved` analysis results can be referenced.
  - reviewer-`edited` analysis results can be referenced.
  - `ai_generated`, `needs_review`, and `rejected` analysis results are blocked.
  - cross-workspace analysis results are blocked even if approved.
- Added Markdown report preview without creating export artifacts.
- Added section reordering with same-report validation and duplicate-section rejection.
- Added focused approved-content rule tests for create, update, generate, clear-source, and
  cross-workspace cases.
- Updated API and architecture documentation for report workflow behavior.
- Added synthetic demo guidance for exercising the report workflow locally.

## Report Workflow

1. A workspace owner or admin creates a report.
2. An analysis task produces structured results with citations.
3. A reviewer approves a result or edits it into a reviewer-approved version.
4. A report section is generated from one or more approved or reviewer-edited results.
5. Owners or admins can edit section text, update source links, and reorder sections.
6. The report preview endpoint renders the current ordered sections as Markdown.

Unreviewed and rejected AI outputs remain visible in review workflows but cannot become formal
report sources.

## APIs Added

```text
GET   /api/v1/workspaces/{workspace_id}/reports
POST  /api/v1/workspaces/{workspace_id}/reports
GET   /api/v1/workspaces/{workspace_id}/reports/{report_id}
PATCH /api/v1/workspaces/{workspace_id}/reports/{report_id}
GET   /api/v1/workspaces/{workspace_id}/reports/{report_id}/preview
GET   /api/v1/workspaces/{workspace_id}/reports/{report_id}/sections
POST  /api/v1/workspaces/{workspace_id}/reports/{report_id}/sections
POST  /api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/generate
PATCH /api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/reorder
GET   /api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/{section_id}
PATCH /api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/{section_id}
```

## Approved-Content Rules

Report sections may only reference `AnalysisResult` records where:

- `workspace_id` matches the report workspace.
- `status` is `approved` or `edited`.

The same rule is enforced for manual section creation, source updates, and generated sections.

## Verified

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy backend
.venv/bin/alembic heads
git diff --check
```

Week 7 close-out verification after Day 48:

- `pytest`: 422 tests passed, 1 skipped
- `ruff check .`: passed
- `mypy backend`: passed
- Alembic head revision: `0023 (head)`
- `git diff --check`: passed
- Local `alembic current` requires a running PostgreSQL instance on `localhost:5432`

## Week 7 Acceptance Criteria

- Formal reports only include approved content: done.
- Rejected and unreviewed AI results are blocked from reports: done.
- Report preview can be generated from workspace-approved findings: done.

## Notes for Week 8

- Add Markdown export as a persistent export artifact.
- Add DOCX/PDF export paths.
- Add workspace dashboard metrics for project status, approved findings, reports, and exports.
