# v2.0 Week 5 Development Log

## Goal

Add workspace-scoped analysis tasks that produce structured, cited AI output.

## Completed

- Added `analysis_tasks` and `analysis_results` persistence.
- Added schemas and APIs for listing, creating, reading, running, and storing analysis results.
- Implemented workspace-scoped task execution using retrieved `DocumentChunk` evidence.
- Added strict JSON prompting for structured analysis output.
- Parsed provider responses as JSON before persistence.
- Validated structured output against task schemas.
- Required normalized citations for findings.
- Persisted model, provider, confidence, token usage, result payload, and citation metadata.
- Added deterministic structured provider behavior for repeatable tests.
- Added provider failure handling so invalid or failed model output does not become report input.
- Added tests for successful analysis, malformed JSON, missing citations, schema mismatch, and provider failures.

## Analysis Behavior

Running an analysis task now:

1. Marks the task as running.
2. Retrieves only chunks in the task workspace.
3. Builds structured JSON analysis messages.
4. Calls the configured provider or deterministic test provider.
5. Parses and validates the response.
6. Normalizes citations to source chunk IDs.
7. Stores an `AnalysisResult` with status `needs_review`.

Malformed, uncited, or schema-invalid output is rejected before result persistence.

## APIs Added

```text
GET  /api/v1/workspaces/{workspace_id}/analysis-tasks
POST /api/v1/workspaces/{workspace_id}/analysis-tasks
GET  /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}
POST /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/run
GET  /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/results
POST /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/results
GET  /api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/results/{analysis_result_id}
```

## Verified

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy backend
.venv/bin/alembic heads
git diff --check
```

## Week 5 Acceptance Criteria

- Different templates can run different AI analysis tasks: done.
- AI output is saved as structured JSON with citations: done.
- Invalid or uncited model output does not become usable report content: done.

## Notes for Week 6

- Add review decisions for human approval and rejection.
- Preserve the original AI result when reviewers edit output.
- Add reviewer-only permissions and review queue APIs.
