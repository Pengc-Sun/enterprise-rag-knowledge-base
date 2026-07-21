# v2.0.0 Release Notes

Release date: 2026-07-21

## Summary

Enterprise RAG Knowledge Base v2.0.0 upgrades the project from a knowledge-base chat application
into a workspace-based AI analysis platform. Workspaces are now the top-level project boundary for
documents, chunks, conversations, analysis tasks, AI results, reviewer decisions, formal reports,
and exports. The release adds template-created project structure, structured AI analysis with
citations, human review, approved-content-only reporting, Markdown/DOCX/PDF exports, a React
workspace UI, and Docker validation for both fresh installs and v1-to-v2 upgrades.

## Release Highlights

- Workspace CRUD with owner/admin/editor/reviewer/viewer membership roles.
- Built-in workspace templates for general knowledge, policy review, IT support, and research
  review workflows.
- Template-created directories, default knowledge bases, analysis tasks, and report outlines.
- v1.0 data migration into default owner workspaces without losing users, knowledge bases,
  documents, chunks, conversations, or messages.
- Workspace isolation across knowledge bases, documents, retrieval, RAG, conversations, chat,
  streaming, analysis tasks, review queue, reports, and exports.
- Structured AI analysis tasks with JSON schema validation, normalized citations, model/provider
  metadata, and deterministic provider behavior for tests.
- Reviewer workflow for approve, edit, reject, and request-changes decisions with original AI output
  snapshot preservation.
- Formal report builder that only uses approved or reviewer-edited analysis results from the same
  workspace.
- Markdown preview and Markdown, DOCX, and PDF export jobs with stored files and controlled
  downloads.
- Workspace dashboard metrics for document, analysis, review, report, and export status.
- React workspace frontend for templates, dashboard, knowledge bases, documents, chat, analysis,
  review, reports, exports, and members.
- Release hardening with full backend/frontend checks, Docker fresh-install validation, Docker
  v1-to-v2 upgrade validation, and final cross-workspace isolation regressions.

## Verification Completed

| Check | Result |
| --- | --- |
| Backend tests | `458 passed, 1 skipped, 1 warning` |
| Ruff | Passed |
| mypy | Passed, `140 source files` |
| Frontend typecheck | Passed |
| Frontend production build | Passed |
| Docker fresh install | Passed from empty volumes to Alembic `0024` |
| Docker v1-to-v2 upgrade | Passed from Alembic `0010` to `0024` |
| Cross-workspace isolation regressions | Passed |
| SVG release asset validation | Passed |

## Docker Validation Snapshot

Fresh install validation:

- Started isolated production Compose stack from empty PostgreSQL, Redis, and storage volumes.
- Verified backend, frontend, PostgreSQL, and Redis health.
- Verified backend `/api/v1/health` returned production `status=ok`.
- Verified Alembic revision `0024`.
- Verified `4` built-in workspace templates were seeded.
- Ran register, login, list templates, create template-backed workspace, dashboard, and
  knowledge-base smoke tests.

v1-to-v2 upgrade validation:

- Created isolated database at v1 schema revision `0010`.
- Seeded v1-style users, knowledge base, knowledge-base member, document, chunk, conversation, and
  message rows.
- Ran the production `migrate` service.
- Verified final Alembic revision `0024`.
- Verified seeded rows were preserved and migrated to one default owner workspace.
- Verified null `workspace_id` counts were zero for knowledge bases, documents, chunks, and
  conversations.

## GitHub Release Body

Use this body when publishing the GitHub release:

```markdown
# Enterprise RAG Knowledge Base v2.0.0

Workspace-based AI analysis platform release for enterprise RAG workflows.

## Highlights

- Workspace project boundary with owner/admin/editor/reviewer/viewer roles
- Built-in templates that create directories, knowledge bases, analysis tasks, and report outlines
- v1.0 data migration into default workspaces without losing knowledge-base data
- Workspace isolation across documents, chunks, conversations, retrieval, RAG, analysis, reports,
  and exports
- Structured AI analysis results with citations and schema validation
- Human review workflow with approve, edit, reject, and request-changes decisions
- Formal reports that only use approved or reviewer-edited content
- Markdown preview plus Markdown, DOCX, and PDF exports
- React workspace UI for templates, dashboard, documents, chat, analysis, review, reports, exports,
  and members
- Docker fresh-install and v1-to-v2 upgrade validation

## Verification

- Backend tests: 458 passed, 1 skipped
- Ruff: passed
- mypy: passed across 140 backend source files
- Frontend typecheck/build: passed
- Docker fresh install from empty volumes: passed through Alembic 0024
- Docker v1-to-v2 upgrade: passed from Alembic 0010 to 0024 without seeded data loss
- Final cross-workspace isolation regressions: passed

## Notes

- The stable v1.0 line remains available on `main` until the v2 branch is approved and merged.
- Deterministic providers remain the default for reproducible local demos and CI.
- Configure real embedding and LLM providers before using the system with production data.
- Production-style Docker Compose is a small-deployment reference, not a complete managed cloud
  platform.
```

## Version Bump

Completed before tagging v2.0.0:

- `pyproject.toml`: `version = "2.0.0"`
- `frontend/package.json`: `"version": "2.0.0"`
- `backend/app/main.py`: `version="2.0.0"`

## Tagging Commands

Run after the v2 branch is approved and merged into `main`:

```bash
git switch main
git pull origin main
git tag -a v2.0.0 -m "Enterprise RAG Knowledge Base v2.0.0"
git push origin v2.0.0
```

If publishing directly from the v2 branch before merging, verify the branch intentionally represents
the release source:

```bash
git switch feature/v2-workspaces
git pull origin feature/v2-workspaces
git tag -a v2.0.0 -m "Enterprise RAG Knowledge Base v2.0.0"
git push origin v2.0.0
```

## Repository Topics

Suggested GitHub repository topics:

```text
rag
retrieval-augmented-generation
workspace
ai-analysis
human-in-the-loop
fastapi
react
typescript
postgresql
pgvector
sqlalchemy
alembic
llm
hybrid-search
reranking
docker
github-actions
enterprise-search
document-ai
```

## Release Checklist

- [x] Run full backend tests.
- [x] Run Ruff.
- [x] Run mypy.
- [x] Run frontend typecheck.
- [x] Run frontend production build.
- [x] Validate Docker fresh install from empty volumes.
- [x] Validate Docker v1-to-v2 upgrade path.
- [x] Add final cross-workspace isolation regressions.
- [x] Refresh README, architecture, API, deployment, security, and screenshot docs.
- [x] Update changelog.
- [x] Prepare release notes.
- [x] Bump package, frontend, and OpenAPI versions to `2.0.0`.
- [x] Run final validation after the version bump.
- [ ] Commit release prep changes.
- [ ] Push `feature/v2-workspaces`.
- [ ] Open or update the v2 pull request into `main`.
- [ ] Merge v2 into `main` after review.
- [ ] Create and push the `v2.0.0` tag.
- [ ] Publish GitHub Release.
- [ ] Add or update repository topics.
- [ ] Attach demo video as a release asset if available.
