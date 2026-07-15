# v2.0 Week 2 Development Log

## Goal

Migrate v1.0 knowledge-base data into workspaces without data loss and verify both local
Alembic migration paths and Docker startup migration paths.

## Completed

- Added nullable `workspace_id` columns to knowledge bases, documents, document chunks, and
  conversations.
- Added a default-workspace migration for existing v1.0 knowledge-base owners.
- Backfilled knowledge bases, documents, chunks, and conversations into owner default workspaces.
- Made `workspace_id` required after backfill and added foreign keys plus indexes.
- Updated models, schemas, and services to persist and expose workspace IDs.
- Kept v1 knowledge-base creation working by assigning new knowledge bases to the user's default
  workspace.
- Added seeded v1.0 migration validation for users, knowledge bases, documents, chunks,
  conversations, and messages.
- Added migration startup validation for production Compose ordering, Alembic downgrade/upgrade,
  and optional real Docker migrate startup.

## Verification Commands

```bash
make validate-workspace-migration
make validate-migration-startup
make validate-docker-migration-startup
```

## Verified

- Seeded v1.0 data migrates into one default workspace and preserves messages.
- Alembic can downgrade from `0016` to `0015` and upgrade back to `0016 (head)`.
- Production Compose config runs `alembic upgrade head` in a one-shot `migrate` service.
- Backend startup waits for PostgreSQL, Redis, and successful migration completion.
- Docker fresh-install migration startup was validated with an isolated Compose project and volume.

## Week 2 Acceptance Criteria

- Existing v1.0 users, knowledge bases, documents, chunks, conversations, and messages remain
  accessible: verified with seeded migration validation.
- Every knowledge base, document, chunk, and conversation has a valid `workspace_id`: done.
- New Docker installs migrate successfully: verified with `make validate-docker-migration-startup`.
- Upgraded databases migrate successfully: verified with seeded migration and Alembic round-trip
  validation.

## Notes for Week 3

- Require explicit workspace context on knowledge-base, document, retrieval, and chat APIs.
- Add negative tests for cross-workspace data access.
- Keep v1 compatibility only where it is intentional and covered by tests.
