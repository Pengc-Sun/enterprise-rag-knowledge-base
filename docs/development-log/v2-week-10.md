# v2.0 Week 10 Development Log

## Goal

Harden the v2.0 branch for release, validate fresh installs and upgrade paths, finalize
documentation, and prepare the v2.0.0 release.

## Day 64 - Full Backend, Frontend, Migration, and Docker Checks

### Completed

- Ran the full backend quality gate through `make check`.
- Ran frontend TypeScript validation and production build.
- Verified Alembic has a single head revision.
- Validated production Docker Compose startup ordering and migrate-service dependencies.
- Validated development and production Compose configuration rendering.
- Built production backend, migrate, and frontend Docker images.
- Started Docker Desktop when the daemon was not initially available.
- Ran an isolated Docker migrate startup against a fresh Compose PostgreSQL volume.

### Verification Results

```bash
make check
cd frontend && pnpm typecheck && pnpm build
.venv/bin/alembic heads
.venv/bin/python scripts/validate_migration_startup.py --json
docker compose config
APP_ENV_FILE=.env.production.example docker compose --env-file .env.production.example -f docker-compose.prod.yml config
APP_ENV_FILE=.env.production.example docker compose --env-file .env.production.example -f docker-compose.prod.yml build backend frontend migrate
.venv/bin/python scripts/validate_migration_startup.py --run-docker-startup --json
```

- Backend: `ruff`, `mypy`, and `pytest` passed.
- Tests: 448 passed, 1 skipped.
- Frontend: `pnpm typecheck` and `pnpm build` passed.
- Alembic head: `0024 (head)`.
- Compose config: development and production configuration rendered successfully.
- Docker images: production backend, migrate, and frontend images built successfully.
- Docker migrate startup: isolated migrate service upgraded a fresh PostgreSQL database through
  `0024` and exited with code 0.

### Notes

- Local Alembic upgrade/downgrade round-trip was not run because no PostgreSQL service was listening
  on `localhost:5432` in the local shell environment.
- Day 65 will cover a full fresh Docker install from empty volumes.
- Day 66 will cover upgrade behavior from a v1.0 database snapshot.

## Day 65 - Fresh Docker Install From Empty Volumes

### Completed

- Started an isolated production Docker Compose stack from empty PostgreSQL, Redis, and storage
  volumes.
- Rebuilt the production backend, migrate, and frontend images from the current branch.
- Verified startup ordering: PostgreSQL and Redis became healthy before migrations, the migrate
  service completed before the backend, and the frontend started after the backend became healthy.
- Verified frontend and backend health endpoints through the exposed frontend port.
- Verified Alembic upgraded the empty database to revision `0024`.
- Verified built-in workspace templates were seeded into the fresh database.
- Ran a full API smoke test through the frontend proxy: register, login, list templates, create a
  template-backed Workspace, load the Workspace dashboard, and list Workspace knowledge bases.
- Fixed a template instantiation persistence bug where Workspace directories were attached in
  memory but not added to the SQLAlchemy session.

### Verification Results

```bash
FRONTEND_PORT=18080 APP_ENV_FILE=.env.production.example docker compose \
  --env-file .env.production.example \
  -p enterprise-rag-v2-day65-fresh \
  -f docker-compose.prod.yml down -v --remove-orphans

FRONTEND_PORT=18080 APP_ENV_FILE=.env.production.example docker compose \
  --env-file .env.production.example \
  -p enterprise-rag-v2-day65-fresh \
  -f docker-compose.prod.yml up -d --build

curl -fsS http://127.0.0.1:18080/health
curl -fsS http://127.0.0.1:18080/api/v1/health
```

- Docker services: backend, frontend, PostgreSQL, and Redis reached healthy status.
- Frontend health: `ok`.
- Backend health: `success=true`, `status=ok`, `environment=production`.
- Alembic version after fresh install: `0024`.
- Seeded workspace templates: `4`.
- Smoke test result: one new Workspace created from the General Knowledge Workspace template.
- Template-created records after smoke test: `3` directories, `1` knowledge base, `2` analysis
  tasks, `1` report, and `4` report sections.
- Container logs had no `SAWarning`, `ERROR`, `Traceback`, or exception matches after the fix.

### Notes

- The fresh install test uses the isolated Compose project
  `enterprise-rag-v2-day65-fresh` and port `18080` so it does not touch local development data.
- The isolated stack should be removed after verification with `docker compose down -v` using the
  same project name.

## Day 66 - Docker Upgrade From a v1.0 Database Snapshot

### Completed

- Added a repeatable Docker upgrade validation script for the v1.0-to-v2.0 database path.
- The script creates an isolated production Compose project, upgrades the database only to the
  v1.0 schema revision, seeds v1-style users, knowledge base, member, document, chunk,
  conversation, and message rows, then runs the current production `migrate` service.
- Verified the production migrate service upgrades the seeded v1 database from revision `0010` to
  revision `0024`.
- Verified the upgraded application can start backend and frontend services against the migrated
  database.
- Verified seeded v1 data is preserved and workspace backfill is complete.
- Added unit tests for the Docker upgrade validation script and its result checks.

### Verification Results

```bash
.venv/bin/python scripts/validate_docker_v1_upgrade.py --yes --json
```

- Seed revision: `0010`.
- Final Alembic revision: `0024`.
- Seeded users preserved: `2`.
- Seeded knowledge bases preserved: `1`.
- Seeded knowledge-base members preserved: `1`.
- Seeded documents preserved: `1`.
- Seeded document chunks preserved: `1`.
- Seeded conversations preserved: `1`.
- Seeded messages preserved: `1`.
- Seeded workspace templates after upgrade: `4`.
- Default workspace slug: `v1-default-24000000000040008000000000000001`.
- Workspace owner member role: `owner`.
- Migrated knowledge base, document, chunk, and conversation share the same workspace ID.
- Null `workspace_id` counts after upgrade are zero for knowledge bases, documents, chunks, and
  conversations.
- Backend and frontend services reached healthy status after the upgrade.

### Notes

- The validation uses the isolated Compose project
  `enterprise-rag-v2-docker-upgrade-validation` and frontend port `18081`.
- The script removes its isolated containers and volumes by default after validation.
