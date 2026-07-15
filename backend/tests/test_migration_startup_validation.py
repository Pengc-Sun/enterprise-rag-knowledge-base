import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def load_script() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "validate_migration_startup.py"
    spec = importlib.util.spec_from_file_location("validate_migration_startup", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def production_compose_config() -> dict[str, object]:
    return {
        "services": {
            "postgres": {
                "image": "pgvector/pgvector:pg16",
                "healthcheck": {"test": ["CMD-SHELL", "pg_isready"]},
            },
            "redis": {
                "image": "redis:7-alpine",
                "healthcheck": {"test": ["CMD", "redis-cli", "ping"]},
            },
            "migrate": {
                "command": ["alembic", "upgrade", "head"],
                "restart": "no",
                "depends_on": {
                    "postgres": {"condition": "service_healthy", "required": True},
                },
            },
            "backend": {
                "depends_on": {
                    "postgres": {"condition": "service_healthy", "required": True},
                    "redis": {"condition": "service_healthy", "required": True},
                    "migrate": {"condition": "service_completed_successfully", "required": True},
                },
            },
            "frontend": {
                "depends_on": {
                    "backend": {"condition": "service_healthy", "required": True},
                },
            },
        },
    }


def test_migration_startup_config_requires_migrate_before_backend() -> None:
    script = load_script()

    result = script.validate_migration_startup_config(production_compose_config())

    assert result["migrate_command"] == ["alembic", "upgrade", "head"]
    assert result["migrate_waits_for_postgres"] is True
    assert result["backend_waits_for_migrate"] is True
    assert result["frontend_waits_for_backend"] is True


def test_migration_startup_config_rejects_backend_race_condition() -> None:
    script = load_script()
    config = production_compose_config()
    services = config["services"]
    assert isinstance(services, dict)
    backend = services["backend"]
    assert isinstance(backend, dict)
    backend["depends_on"] = {
        "postgres": {"condition": "service_healthy", "required": True},
        "redis": {"condition": "service_healthy", "required": True},
    }

    with pytest.raises(RuntimeError, match="backend service must wait for migrate"):
        script.validate_migration_startup_config(config)


def test_docker_compose_base_command_uses_isolated_project_and_env_file() -> None:
    script = load_script()

    command = script.docker_compose_base_command(
        compose_file=Path("docker-compose.prod.yml"),
        env_file=Path(".env.production.example"),
        project_name="migration-test",
    )

    assert command == [
        "docker",
        "compose",
        "--env-file",
        ".env.production.example",
        "-p",
        "migration-test",
        "-f",
        "docker-compose.prod.yml",
    ]
