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
