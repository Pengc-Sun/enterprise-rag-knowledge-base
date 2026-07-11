PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: help install test lint typecheck format check dev docker-up docker-down docker-logs migrate-up migrate-down migrate-current

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
	@echo "  make migrate-up       Apply Alembic migrations"
	@echo "  make migrate-down     Roll back one Alembic migration"
	@echo "  make migrate-current  Show current Alembic revision"

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

migrate-up:
	$(BIN)/alembic upgrade head

migrate-down:
	$(BIN)/alembic downgrade -1

migrate-current:
	$(BIN)/alembic current

