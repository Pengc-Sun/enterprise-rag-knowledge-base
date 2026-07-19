# v2.0 Week 8 Development Log

## Goal

Make reports portable through export files and expose workspace-level project status metrics.

## Completed

- Added export job tracking for workspace-scoped reports.
- Added Markdown export generation.
- Added DOCX export generation through `python-docx`.
- Added PDF export generation through a server-side ReportLab renderer.
- Wrote generated Markdown, DOCX, and PDF artifacts to export storage.
- Added access-controlled export download endpoint.
- Added `EXPORT_DIR` configuration for development and production-style deployments.
- Added workspace dashboard metrics for document, analysis task, review, report, and export status.
- Revalidated report section source results at export time so exports only include currently
  `approved` or reviewer-`edited` analysis results.
- Added focused tests for export status reads, export downloads, approved-only export gating, and
  dashboard counts.
- Updated API, architecture, and deployment documentation for export storage and dashboard metrics.

## APIs Added

```text
POST /api/v1/workspaces/{workspace_id}/reports/{report_id}/exports
GET  /api/v1/workspaces/{workspace_id}/exports/{export_id}
GET  /api/v1/workspaces/{workspace_id}/exports/{export_id}/download
GET  /api/v1/workspaces/{workspace_id}/dashboard
```

## Export Storage

Exports are written under:

```text
storage/exports/{workspace_id}/{export_id}/{filename}
```

The production-style Docker stack persists this path through `storage-prod-data:/app/storage`.
`UPLOAD_DIR` and `EXPORT_DIR` should stay under `/app/storage` in Docker deployments so container
recreation does not remove uploaded documents or generated exports.

## Dashboard Metrics

The workspace dashboard returns simple status-card counts for:

- documents by document status
- analysis tasks by task status
- review results by analysis result status
- review decisions by decision type
- reports by report status
- exports by export job status

Charts and richer timeline analytics are intentionally left for later frontend/dashboard work.

## Verified

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy backend
.venv/bin/alembic heads
git diff --check
```

Week 8 close-out verification after Day 55:

- `pytest`: 448 tests passed, 1 skipped
- `ruff check .`: passed
- `mypy backend`: passed
- Alembic head revision: `0024 (head)`
- `git diff --check`: passed
- Local `alembic current` requires a running PostgreSQL instance on `localhost:5432`

## Week 8 Acceptance Criteria

- Reports can be exported as Markdown, DOCX, and PDF: done.
- Exported reports include citations from approved report sections: done.
- Workspace dashboard shows document, task, review, report, and export status: done.
- Export artifacts are stored under persistent Docker storage paths: done.
