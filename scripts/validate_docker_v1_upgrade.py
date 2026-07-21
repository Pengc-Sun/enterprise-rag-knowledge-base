#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPOSE_FILE = PROJECT_ROOT / "docker-compose.prod.yml"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env.production.example"
DEFAULT_PROJECT_NAME = "enterprise-rag-v2-docker-upgrade-validation"
DEFAULT_FRONTEND_PORT = 18081
V1_REVISION = "0010"
HEAD_REVISION = "0024"

SEED_OWNER_ID = uuid.UUID("24000000-0000-4000-8000-000000000001")
SEED_MEMBER_ID = uuid.UUID("24000000-0000-4000-8000-000000000002")
SEED_KNOWLEDGE_BASE_ID = uuid.UUID("24000000-0000-4000-8000-000000000003")
SEED_KNOWLEDGE_BASE_MEMBER_ID = uuid.UUID("24000000-0000-4000-8000-000000000004")
SEED_DOCUMENT_ID = uuid.UUID("24000000-0000-4000-8000-000000000005")
SEED_CHUNK_ID = uuid.UUID("24000000-0000-4000-8000-000000000006")
SEED_CONVERSATION_ID = uuid.UUID("24000000-0000-4000-8000-000000000007")
SEED_MESSAGE_ID = uuid.UUID("24000000-0000-4000-8000-000000000008")
SEED_OWNER_EMAIL = "docker-v1-upgrade-owner@example.com"
SEED_MEMBER_EMAIL = "docker-v1-upgrade-member@example.com"
SEED_WORKSPACE_SLUG = f"v1-default-{str(SEED_OWNER_ID).replace('-', '')}"


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


def compose_environment(*, env_file: Path, frontend_port: int) -> dict[str, str]:
    environment = os.environ.copy()
    environment["APP_ENV_FILE"] = env_file.as_posix()
    environment["FRONTEND_PORT"] = str(frontend_port)
    return environment


def run_command(
    command: list[str],
    *,
    capture_output: bool = False,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=capture_output,
        input=input_text,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def seed_v1_snapshot_sql() -> str:
    return f"""
    insert into users (id, email, username, hashed_password, role, is_active)
    values
        (
            '{SEED_OWNER_ID}',
            '{SEED_OWNER_EMAIL}',
            'docker_v1_upgrade_owner',
            'hashed',
            'user',
            true
        ),
        (
            '{SEED_MEMBER_ID}',
            '{SEED_MEMBER_EMAIL}',
            'docker_v1_upgrade_member',
            'hashed',
            'user',
            true
        );

    insert into knowledge_bases (id, name, description, owner_id, visibility)
    values (
        '{SEED_KNOWLEDGE_BASE_ID}',
        'Docker v1 Upgrade Knowledge Base',
        'Seeded before the v2 workspace migration.',
        '{SEED_OWNER_ID}',
        'private'
    );

    insert into knowledge_base_members (id, knowledge_base_id, user_id, permission)
    values (
        '{SEED_KNOWLEDGE_BASE_MEMBER_ID}',
        '{SEED_KNOWLEDGE_BASE_ID}',
        '{SEED_MEMBER_ID}',
        'viewer'
    );

    insert into documents (
        id, knowledge_base_id, filename, file_type, file_size, file_hash,
        storage_path, status, created_by
    )
    values (
        '{SEED_DOCUMENT_ID}',
        '{SEED_KNOWLEDGE_BASE_ID}',
        'docker_v1_upgrade_policy.md',
        'md',
        256,
        'sha256:docker-v1-upgrade-policy',
        'knowledge-bases/docker-v1-upgrade-policy.md',
        'completed',
        '{SEED_OWNER_ID}'
    );

    insert into document_chunks (
        id, document_id, knowledge_base_id, content, chunk_index, page_number,
        section_title, token_count, embedding_status, metadata
    )
    values (
        '{SEED_CHUNK_ID}',
        '{SEED_DOCUMENT_ID}',
        '{SEED_KNOWLEDGE_BASE_ID}',
        'Docker v1 upgrade policy content must remain available after migration.',
        0,
        1,
        'Upgrade Policy',
        10,
        'pending',
        '{{}}'::jsonb
    );

    insert into conversations (id, user_id, knowledge_base_id, title)
    values (
        '{SEED_CONVERSATION_ID}',
        '{SEED_OWNER_ID}',
        '{SEED_KNOWLEDGE_BASE_ID}',
        'Docker v1 upgrade conversation'
    );

    insert into messages (id, conversation_id, role, content, sources)
    values (
        '{SEED_MESSAGE_ID}',
        '{SEED_CONVERSATION_ID}',
        'user',
        'Will this v1 conversation survive the upgrade?',
        '[]'::jsonb
    );
    """


def verification_sql() -> str:
    return f"""
    select jsonb_build_object(
        'alembic_version', (select version_num from alembic_version),
        'seed_revision', '{V1_REVISION}',
        'head_revision', '{HEAD_REVISION}',
        'owner_users', (
            select count(*) from users
            where id in ('{SEED_OWNER_ID}', '{SEED_MEMBER_ID}')
        ),
        'knowledge_bases', (
            select count(*) from knowledge_bases where id = '{SEED_KNOWLEDGE_BASE_ID}'
        ),
        'knowledge_base_members', (
            select count(*) from knowledge_base_members
            where id = '{SEED_KNOWLEDGE_BASE_MEMBER_ID}'
        ),
        'documents', (
            select count(*) from documents where id = '{SEED_DOCUMENT_ID}'
        ),
        'document_chunks', (
            select count(*) from document_chunks where id = '{SEED_CHUNK_ID}'
        ),
        'conversations', (
            select count(*) from conversations where id = '{SEED_CONVERSATION_ID}'
        ),
        'messages', (
            select count(*) from messages where id = '{SEED_MESSAGE_ID}'
        ),
        'workspace_templates', (
            select count(*) from workspace_templates
        ),
        'workspace_slug', (
            select w.slug
            from knowledge_bases kb
            join workspaces w on w.id = kb.workspace_id
            where kb.id = '{SEED_KNOWLEDGE_BASE_ID}'
        ),
        'workspace_member_role', (
            select wm.role
            from knowledge_bases kb
            join workspace_members wm
              on wm.workspace_id = kb.workspace_id
             and wm.user_id = kb.owner_id
            where kb.id = '{SEED_KNOWLEDGE_BASE_ID}'
        ),
        'workspace_ids_match', (
            select count(distinct workspace_id) = 1
            from (
                select workspace_id from knowledge_bases where id = '{SEED_KNOWLEDGE_BASE_ID}'
                union all
                select workspace_id from documents where id = '{SEED_DOCUMENT_ID}'
                union all
                select workspace_id from document_chunks where id = '{SEED_CHUNK_ID}'
                union all
                select workspace_id from conversations where id = '{SEED_CONVERSATION_ID}'
            ) workspace_rows
        ),
        'null_workspace_counts', jsonb_build_object(
            'knowledge_bases', (select count(*) from knowledge_bases where workspace_id is null),
            'documents', (select count(*) from documents where workspace_id is null),
            'document_chunks', (select count(*) from document_chunks where workspace_id is null),
            'conversations', (select count(*) from conversations where workspace_id is null)
        )
    )::text;
    """


def psql_command(
    base_command: list[str],
    *,
    database: str,
    user: str,
    sql: str,
    env: dict[str, str],
) -> str:
    result = run_command(
        base_command
        + [
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            user,
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
        ],
        capture_output=True,
        input_text=sql,
        env=env,
    )
    return result.stdout.strip()


def wait_for_postgres(
    base_command: list[str],
    *,
    database: str,
    user: str,
    env: dict[str, str],
    timeout_seconds: int = 90,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = subprocess.run(
            base_command + ["exec", "-T", "postgres", "pg_isready", "-U", user, "-d", database],
            check=False,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            env=env,
        )
        if result.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError("Timed out waiting for PostgreSQL to become ready")


def wait_for_frontend_health(*, frontend_port: int, timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{frontend_port}/health",
                timeout=3,
            ) as response:
                if response.read().decode("utf-8").strip() == "ok":
                    return
        except OSError:
            time.sleep(2)
    raise RuntimeError("Timed out waiting for frontend health endpoint")


def validate_upgrade_result(result: dict[str, Any]) -> None:
    expected_counts = {
        "owner_users": 2,
        "knowledge_bases": 1,
        "knowledge_base_members": 1,
        "documents": 1,
        "document_chunks": 1,
        "conversations": 1,
        "messages": 1,
        "workspace_templates": 4,
    }
    for key, expected in expected_counts.items():
        if result.get(key) != expected:
            raise RuntimeError(f"Expected {key}={expected}, got {result.get(key)!r}")

    if result.get("alembic_version") != HEAD_REVISION:
        raise RuntimeError(
            f"Expected Alembic revision {HEAD_REVISION}, "
            f"got {result.get('alembic_version')!r}"
        )
    if result.get("workspace_slug") != SEED_WORKSPACE_SLUG:
        raise RuntimeError(f"Unexpected workspace slug: {result.get('workspace_slug')!r}")
    if result.get("workspace_member_role") != "owner":
        raise RuntimeError(
            f"Unexpected workspace member role: {result.get('workspace_member_role')!r}"
        )
    if result.get("workspace_ids_match") is not True:
        raise RuntimeError("Workspace IDs do not match across migrated v1 rows")

    null_workspace_counts = result.get("null_workspace_counts")
    if not isinstance(null_workspace_counts, dict):
        raise RuntimeError("Missing null workspace count details")
    for table_name, count in null_workspace_counts.items():
        if count != 0:
            raise RuntimeError(f"Expected no null workspace IDs in {table_name}, got {count!r}")


def validate_docker_v1_upgrade(
    *,
    compose_file: Path = DEFAULT_COMPOSE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
    project_name: str = DEFAULT_PROJECT_NAME,
    frontend_port: int = DEFAULT_FRONTEND_PORT,
    postgres_db: str = "enterprise_rag",
    postgres_user: str = "enterprise_rag",
    keep_containers: bool = False,
) -> dict[str, Any]:
    base_command = docker_compose_base_command(
        compose_file=compose_file,
        env_file=env_file,
        project_name=project_name,
    )
    env = compose_environment(env_file=env_file, frontend_port=frontend_port)

    run_command(base_command + ["down", "-v", "--remove-orphans"], env=env)
    try:
        run_command(base_command + ["build", "migrate", "backend", "frontend"], env=env)
        run_command(base_command + ["up", "-d", "postgres", "redis"], env=env)
        wait_for_postgres(base_command, database=postgres_db, user=postgres_user, env=env)

        run_command(
            base_command
            + ["run", "--rm", "--no-deps", "migrate", "alembic", "upgrade", V1_REVISION],
            env=env,
        )
        psql_command(
            base_command,
            database=postgres_db,
            user=postgres_user,
            sql=seed_v1_snapshot_sql(),
            env=env,
        )

        run_command(base_command + ["up", "--exit-code-from", "migrate", "migrate"], env=env)
        run_command(base_command + ["up", "-d", "backend", "frontend"], env=env)
        wait_for_frontend_health(frontend_port=frontend_port)

        verification_output = psql_command(
            base_command,
            database=postgres_db,
            user=postgres_user,
            sql=verification_sql(),
            env=env,
        )
        result = json.loads(verification_output)
        validate_upgrade_result(result)
        return result
    finally:
        if not keep_containers:
            run_command(base_command + ["down", "-v", "--remove-orphans"], env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Docker v1.0-to-v2.0 upgrade path. The command creates an isolated "
            "production Compose database at the v1 schema revision, seeds v1 data, runs the "
            "current production migrate service, starts the app, verifies migrated data, and "
            "cleans up the isolated volumes."
        )
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm that Docker containers and volumes may be created and removed.",
    )
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE_FILE)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--project-name", default=DEFAULT_PROJECT_NAME)
    parser.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    parser.add_argument("--postgres-db", default="enterprise_rag")
    parser.add_argument("--postgres-user", default="enterprise_rag")
    parser.add_argument(
        "--keep-containers",
        action="store_true",
        help="Leave the isolated Compose project running for manual debugging.",
    )
    parser.add_argument("--json", action="store_true", help="Print validation details as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.yes:
        print("Refusing to create and remove Docker volumes without --yes.")
        return 2

    result = validate_docker_v1_upgrade(
        compose_file=args.compose_file,
        env_file=args.env_file,
        project_name=args.project_name,
        frontend_port=args.frontend_port,
        postgres_db=args.postgres_db,
        postgres_user=args.postgres_user,
        keep_containers=args.keep_containers,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Docker v1-to-v2 upgrade validation passed")
        print(f"alembic_version={result['alembic_version']}")
        print(f"workspace_slug={result['workspace_slug']}")
        print(f"workspace_templates={result['workspace_templates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
