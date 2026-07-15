#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPOSE_FILE = PROJECT_ROOT / "docker-compose.prod.yml"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env.production.example"
DEFAULT_PROJECT_NAME = "enterprise-rag-v2-migration-validation"
EXPECTED_MIGRATION_COMMAND = ["alembic", "upgrade", "head"]


def normalize_command(command: Any) -> list[str]:
    if isinstance(command, list):
        return [str(part) for part in command]
    if isinstance(command, str):
        return shlex.split(command)
    return []


def docker_compose_base_command(
    *,
    compose_file: Path = DEFAULT_COMPOSE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
    project_name: str = DEFAULT_PROJECT_NAME,
) -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        env_file.as_posix(),
        "-p",
        project_name,
        "-f",
        compose_file.as_posix(),
    ]


def run_command(
    command: list[str],
    *,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=capture_output,
        text=True,
        cwd=PROJECT_ROOT,
    )


def load_compose_config(
    *,
    compose_file: Path = DEFAULT_COMPOSE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
    project_name: str = DEFAULT_PROJECT_NAME,
) -> dict[str, Any]:
    command = docker_compose_base_command(
        compose_file=compose_file,
        env_file=env_file,
        project_name=project_name,
    ) + ["config", "--format", "json"]
    result = run_command(command, capture_output=True)
    return json.loads(result.stdout)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def service_dependency_condition(service: dict[str, Any], dependency: str) -> str | None:
    depends_on = service.get("depends_on", {})
    if isinstance(depends_on, dict):
        dependency_config = depends_on.get(dependency, {})
        if isinstance(dependency_config, dict):
            condition = dependency_config.get("condition")
            return str(condition) if condition is not None else None
    return None


def validate_migration_startup_config(config: dict[str, Any]) -> dict[str, Any]:
    services = config.get("services", {})
    require(isinstance(services, dict), "Compose config must contain a services mapping")

    for service_name in ("postgres", "redis", "migrate", "backend", "frontend"):
        require(service_name in services, f"Missing Compose service: {service_name}")

    postgres = services["postgres"]
    redis = services["redis"]
    migrate = services["migrate"]
    backend = services["backend"]
    frontend = services["frontend"]

    require(postgres.get("image") == "pgvector/pgvector:pg16", "PostgreSQL must use pgvector")
    require("healthcheck" in postgres, "PostgreSQL must define a healthcheck")
    require("healthcheck" in redis, "Redis must define a healthcheck")
    require(
        normalize_command(migrate.get("command")) == EXPECTED_MIGRATION_COMMAND,
        "migrate service must run alembic upgrade head",
    )
    require(migrate.get("restart") == "no", "migrate service must be one-shot restart: no")
    require(
        service_dependency_condition(migrate, "postgres") == "service_healthy",
        "migrate service must wait for healthy PostgreSQL",
    )
    require(
        service_dependency_condition(backend, "postgres") == "service_healthy",
        "backend service must wait for healthy PostgreSQL",
    )
    require(
        service_dependency_condition(backend, "redis") == "service_healthy",
        "backend service must wait for healthy Redis",
    )
    require(
        service_dependency_condition(backend, "migrate") == "service_completed_successfully",
        "backend service must wait for migrate to complete successfully",
    )
    require(
        service_dependency_condition(frontend, "backend") == "service_healthy",
        "frontend service must wait for healthy backend",
    )

    return {
        "migrate_command": normalize_command(migrate.get("command")),
        "migrate_waits_for_postgres": True,
        "backend_waits_for_migrate": True,
        "frontend_waits_for_backend": True,
    }


def alembic_command() -> str:
    local_alembic = PROJECT_ROOT / ".venv" / "bin" / "alembic"
    if local_alembic.exists():
        return local_alembic.as_posix()
    return "alembic"


def alembic_current() -> str:
    result = run_command([alembic_command(), "current"], capture_output=True)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def validate_alembic_upgrade_downgrade() -> dict[str, str]:
    run_command([alembic_command(), "upgrade", "head"])
    before = alembic_current()
    require("(head)" in before, f"Expected Alembic to start at head, got {before!r}")

    try:
        run_command([alembic_command(), "downgrade", "-1"])
        after_downgrade = alembic_current()
        require("(head)" not in after_downgrade, "Alembic downgrade did not move off head")
        run_command([alembic_command(), "upgrade", "head"])
        after_upgrade = alembic_current()
        require(
            "(head)" in after_upgrade,
            f"Expected Alembic to return to head, got {after_upgrade!r}",
        )
    finally:
        run_command([alembic_command(), "upgrade", "head"])

    return {
        "before": before,
        "after_downgrade": after_downgrade,
        "after_upgrade": after_upgrade,
    }


def validate_docker_migration_startup(
    *,
    compose_file: Path = DEFAULT_COMPOSE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
    project_name: str = DEFAULT_PROJECT_NAME,
) -> None:
    base_command = docker_compose_base_command(
        compose_file=compose_file,
        env_file=env_file,
        project_name=project_name,
    )
    run_command(base_command + ["down", "-v", "--remove-orphans"])
    try:
        run_command(base_command + ["up", "--build", "--exit-code-from", "migrate", "migrate"])
    finally:
        run_command(base_command + ["down", "-v", "--remove-orphans"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate v2 migration safety: production Compose startup ordering, "
            "Alembic upgrade/downgrade, and optional Docker migration startup."
        )
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Allow local Alembic upgrade/downgrade validation against the configured database.",
    )
    parser.add_argument(
        "--run-docker-startup",
        action="store_true",
        help="Start an isolated production Compose project and verify the migrate service exits 0.",
    )
    parser.add_argument(
        "--compose-file",
        type=Path,
        default=DEFAULT_COMPOSE_FILE,
        help="Production Compose file to validate.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Environment file used by production Compose.",
    )
    parser.add_argument(
        "--project-name",
        default=DEFAULT_PROJECT_NAME,
        help="Isolated Docker Compose project name for optional startup validation.",
    )
    parser.add_argument("--json", action="store_true", help="Print validation details as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    compose_config = load_compose_config(
        compose_file=args.compose_file,
        env_file=args.env_file,
        project_name=args.project_name,
    )
    result: dict[str, Any] = {
        "compose": validate_migration_startup_config(compose_config),
    }

    if args.yes:
        result["alembic"] = validate_alembic_upgrade_downgrade()
    else:
        result["alembic"] = "skipped; pass --yes to run database-mutating validation"

    if args.run_docker_startup:
        validate_docker_migration_startup(
            compose_file=args.compose_file,
            env_file=args.env_file,
            project_name=args.project_name,
        )
        result["docker_migration_startup"] = "passed"
    else:
        result["docker_migration_startup"] = "skipped; pass --run-docker-startup to start Docker"

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Migration startup validation passed")
        print(f"compose_migrate_command={' '.join(result['compose']['migrate_command'])}")
        print(f"alembic={result['alembic']}")
        print(f"docker_migration_startup={result['docker_migration_startup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
