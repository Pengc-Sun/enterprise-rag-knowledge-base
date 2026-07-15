PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
PROD_ENV ?= .env.production.example

.PHONY: help install test lint typecheck format check dev docker-up docker-down docker-logs docker-prod-up docker-prod-down docker-prod-logs docker-prod-config migrate-up migrate-down migrate-current validate-workspace-migration validate-migration-startup validate-docker-migration-startup eval-retrieval

help:
	@echo "Available commands:"
	@echo "  make install          Create .venv and install development dependencies"
	@echo "  make test             Run pytest"
	@echo "  make lint             Run Ruff lint checks"
	@echo "  make typecheck        Run mypy"
	@echo "  make format           Format code and apply safe Ruff fixes"
	@echo "  make check            Run lint, typecheck, and tests"
	@echo "  make dev              Start the FastAPI development server"
	@echo "  make docker-up        Build and start Docker services"
	@echo "  make docker-down      Stop Docker services"
	@echo "  make docker-logs      Follow Docker service logs"
	@echo "  make docker-prod-up   Build and start production Docker services"
	@echo "  make docker-prod-down Stop production Docker services"
	@echo "  make docker-prod-logs Follow production Docker service logs"
	@echo "  make docker-prod-config Validate production Docker Compose config"
	@echo "  make migrate-up       Apply Alembic migrations"
	@echo "  make migrate-down     Roll back one Alembic migration"
	@echo "  make migrate-current  Show current Alembic revision"
	@echo "  make validate-workspace-migration Validate seeded v1-to-v2 workspace migration"
	@echo "  make validate-migration-startup Validate Alembic round trip and Docker startup ordering"
	@echo "  make validate-docker-migration-startup Validate real Docker migrate startup"
	@echo "  make eval-retrieval   Evaluate retrieval prediction metrics"

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)

install: $(BIN)/python
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

test:
	$(BIN)/pytest

lint:
	$(BIN)/ruff check .

typecheck:
	$(BIN)/mypy backend

format:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

check: lint typecheck test

dev:
	$(BIN)/uvicorn backend.app.main:app --reload

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f


docker-prod-up:
	APP_ENV_FILE=$(PROD_ENV) docker compose --env-file $(PROD_ENV) -f docker-compose.prod.yml up -d --build

docker-prod-down:
	docker compose -f docker-compose.prod.yml down

docker-prod-logs:
	APP_ENV_FILE=$(PROD_ENV) docker compose --env-file $(PROD_ENV) -f docker-compose.prod.yml logs -f

docker-prod-config:
	APP_ENV_FILE=$(PROD_ENV) docker compose --env-file $(PROD_ENV) -f docker-compose.prod.yml config

migrate-up:
	$(BIN)/alembic upgrade head

migrate-down:
	$(BIN)/alembic downgrade -1

migrate-current:
	$(BIN)/alembic current

validate-workspace-migration:
	$(BIN)/python scripts/validate_workspace_migration.py --yes

validate-migration-startup:
	$(BIN)/python scripts/validate_migration_startup.py --yes

validate-docker-migration-startup:
	$(BIN)/python scripts/validate_migration_startup.py --yes --run-docker-startup

# Usage: make eval-retrieval PREDICTIONS=evaluations/retrieval_predictions.jsonl
eval-retrieval:
	$(BIN)/python scripts/run_retrieval_evaluation.py --predictions $(PREDICTIONS)
