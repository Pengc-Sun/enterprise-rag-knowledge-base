# v2.0 Week 6 Development Log

## Goal

Add human review before AI conclusions can become formal report material.

## Completed

- Added `review_decisions` persistence with reviewer, decision, comment, original result, edited
  result, and creation timestamp.
- Added review schemas and workspace-scoped review decision APIs.
- Implemented review actions:
  - `approve` sets the analysis result status to `approved`
  - `edit` requires `edited_result`, replaces the active result payload, and sets status `edited`
  - `reject` sets status `rejected`
  - `request_changes` sets status `needs_review`
- Preserved the first original AI result snapshot across later reviewer edits.
- Added `REVIEW_ROLES` so workspace owner, admin, and reviewer can create review decisions.
- Added review queue list/filter API for reviewer worklists.
- Added tests for reviewer permissions, review queue permissions, and review state transitions.
- Added `review_decision.created` audit logging for successful review decisions.
- Updated API, architecture, security, README, and upgrade-plan documentation.

## Review Workflow

1. A workspace owner or admin runs an analysis task.
2. The backend stores a structured `AnalysisResult` with citations and `needs_review` status.
3. A reviewer opens the review queue, optionally filtering by result status, task, or task type.
4. The reviewer approves, edits, rejects, or requests changes.
5. The decision is stored as a `ReviewDecision`.
6. Successful decisions write an `AuditLog` record with action `review_decision.created`.
7. Later report workflows should only use approved or reviewer-edited content.

## APIs Added

```text
GET  /api/v1/workspaces/{workspace_id}/analysis-tasks/review-queue
GET  /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/results/{analysis_result_id}/review-decisions
POST /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/results/{analysis_result_id}/review-decisions
GET  /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/results/{analysis_result_id}/review-decisions/{review_decision_id}
```

## Audit Logging

Successful review decision creation writes:

```text
action: review_decision.created
resource_type: review_decision
resource_id: review_decision.id
metadata: analysis_task_id, analysis_result_id, decision
```

Denied review access and invalid review payloads do not create audit records.

## Verified

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy backend
.venv/bin/alembic heads
git diff --check
```

Week 6 close-out verification after Day 42:

- `pytest`: 370 tests passed, 1 skipped
- `ruff check .`: passed
- `mypy backend`: passed
- Alembic head revision: `0023 (head)`
- `git diff --check`: passed
- Local `alembic current` requires a running PostgreSQL instance on `localhost:5432`

## Week 6 Acceptance Criteria

- Reviewers can approve, edit, or reject AI conclusions: done.
- Reviewer edits are versioned against original AI output: done.
- Rejected results cannot be used by reports: queued for Week 7 approved-content enforcement.

## Notes for Week 7

- Build report APIs on top of approved or reviewer-edited analysis results.
- Block rejected and unreviewed results from report sections.
- Add Markdown preview and report section editing after approved-content rules are in place.
