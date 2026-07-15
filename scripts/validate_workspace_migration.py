#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from collections.abc import Awaitable
from pathlib import Path
from typing import Any, TypeVar

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from backend.app.db.session import AsyncSessionLocal, engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
BASE_REVISION = "0013"

SEED_USER_ID = uuid.UUID("23000000-0000-4000-8000-000000000013")
SEED_KNOWLEDGE_BASE_ID = uuid.UUID("23000000-0000-4000-8000-000000000023")
SEED_DOCUMENT_ID = uuid.UUID("23000000-0000-4000-8000-000000000033")
SEED_CHUNK_ID = uuid.UUID("23000000-0000-4000-8000-000000000043")
SEED_CONVERSATION_ID = uuid.UUID("23000000-0000-4000-8000-000000000053")
SEED_MESSAGE_ID = uuid.UUID("23000000-0000-4000-8000-000000000063")
SEED_EMAIL = "workspace-migration-seed@example.com"
SEED_USERNAME = "workspace_migration_seed"
DEFAULT_WORKSPACE_SLUG_PREFIX = "v1-default-"

T = TypeVar("T")


def default_workspace_slug_for_seed_user() -> str:
    return f"{DEFAULT_WORKSPACE_SLUG_PREFIX}{str(SEED_USER_ID).replace('-', '')}"


def seeded_v1_ids() -> dict[str, str]:
    return {
        "user_id": str(SEED_USER_ID),
        "knowledge_base_id": str(SEED_KNOWLEDGE_BASE_ID),
        "document_id": str(SEED_DOCUMENT_ID),
        "chunk_id": str(SEED_CHUNK_ID),
        "conversation_id": str(SEED_CONVERSATION_ID),
        "message_id": str(SEED_MESSAGE_ID),
    }


def alembic_config() -> Config:
    return Config(ALEMBIC_INI.as_posix())


def run_downgrade_to_seed_base() -> None:
    command.downgrade(alembic_config(), BASE_REVISION)


def run_upgrade_to_head() -> None:
    command.upgrade(alembic_config(), "head")


async def cleanup_seed_data() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("delete from knowledge_bases where id = :knowledge_base_id"),
            {"knowledge_base_id": SEED_KNOWLEDGE_BASE_ID},
        )
        await session.execute(
            text("delete from workspaces where slug = :slug"),
            {"slug": default_workspace_slug_for_seed_user()},
        )
        await session.execute(
            text("delete from users where id = :user_id or email = :email"),
            {"user_id": SEED_USER_ID, "email": SEED_EMAIL},
        )
        await session.commit()


async def seed_v1_data() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                insert into users (id, email, username, hashed_password, role, is_active)
                values (:id, :email, :username, 'hashed', 'user', true)
                """
            ),
            {"id": SEED_USER_ID, "email": SEED_EMAIL, "username": SEED_USERNAME},
        )
        await session.execute(
            text(
                """
                insert into knowledge_bases (id, name, owner_id, visibility)
                values (:id, 'Seeded v1 Knowledge Base', :owner_id, 'private')
                """
            ),
            {"id": SEED_KNOWLEDGE_BASE_ID, "owner_id": SEED_USER_ID},
        )
        await session.execute(
            text(
                """
                insert into documents (
                    id, knowledge_base_id, filename, file_type, file_size, file_hash,
                    storage_path, status, created_by
                )
                values (
                    :id, :knowledge_base_id, 'seeded_policy.md', 'md', 120,
                    'sha256:workspace-migration-seed',
                    'knowledge-bases/workspace-migration-seed/seeded_policy.md',
                    'completed', :created_by
                )
                """
            ),
            {
                "id": SEED_DOCUMENT_ID,
                "knowledge_base_id": SEED_KNOWLEDGE_BASE_ID,
                "created_by": SEED_USER_ID,
            },
        )
        await session.execute(
            text(
                """
                insert into document_chunks (
                    id, document_id, knowledge_base_id, content, chunk_index, page_number,
                    section_title, token_count, embedding_status, metadata
                )
                values (
                    :id, :document_id, :knowledge_base_id,
                    'Seeded policy content for workspace migration.', 0, 1,
                    'Seeded Policy', 6, 'pending', '{}'::jsonb
                )
                """
            ),
            {
                "id": SEED_CHUNK_ID,
                "document_id": SEED_DOCUMENT_ID,
                "knowledge_base_id": SEED_KNOWLEDGE_BASE_ID,
            },
        )
        await session.execute(
            text(
                """
                insert into conversations (id, user_id, knowledge_base_id, title)
                values (:id, :user_id, :knowledge_base_id, 'Seeded migration chat')
                """
            ),
            {
                "id": SEED_CONVERSATION_ID,
                "user_id": SEED_USER_ID,
                "knowledge_base_id": SEED_KNOWLEDGE_BASE_ID,
            },
        )
        await session.execute(
            text(
                """
                insert into messages (id, conversation_id, role, content, sources)
                values (:id, :conversation_id, 'user', 'Is this migrated?', '[]'::jsonb)
                """
            ),
            {"id": SEED_MESSAGE_ID, "conversation_id": SEED_CONVERSATION_ID},
        )
        await session.commit()


async def verify_seeded_data_migrated() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                text(
                    """
                    select
                        w.id as workspace_id,
                        w.slug as workspace_slug,
                        wm.role as workspace_member_role,
                        kb.workspace_id as knowledge_base_workspace_id,
                        d.workspace_id as document_workspace_id,
                        dc.workspace_id as chunk_workspace_id,
                        c.workspace_id as conversation_workspace_id,
                        (select count(*) from messages where id = :message_id) as message_count
                    from knowledge_bases kb
                    join documents d on d.id = :document_id
                    join document_chunks dc on dc.id = :chunk_id
                    join conversations c on c.id = :conversation_id
                    join workspaces w on w.id = kb.workspace_id
                    join workspace_members wm on wm.workspace_id = w.id and wm.user_id = kb.owner_id
                    where kb.id = :knowledge_base_id
                    """
                ),
                {
                    "knowledge_base_id": SEED_KNOWLEDGE_BASE_ID,
                    "document_id": SEED_DOCUMENT_ID,
                    "chunk_id": SEED_CHUNK_ID,
                    "conversation_id": SEED_CONVERSATION_ID,
                    "message_id": SEED_MESSAGE_ID,
                },
            )
        ).mappings().one()

    workspace_values = [
        row["workspace_id"],
        row["knowledge_base_workspace_id"],
        row["document_workspace_id"],
        row["chunk_workspace_id"],
        row["conversation_workspace_id"],
    ]
    all_workspace_ids_match = len(set(workspace_values)) == 1 and workspace_values[0] is not None
    result = {
        "workspace_id": str(row["workspace_id"]),
        "workspace_slug": row["workspace_slug"],
        "workspace_member_role": row["workspace_member_role"],
        "all_workspace_ids_match": all_workspace_ids_match,
        "message_count": row["message_count"],
    }
    if row["workspace_slug"] != default_workspace_slug_for_seed_user():
        raise RuntimeError(f"Unexpected workspace slug: {row['workspace_slug']}")
    if row["workspace_member_role"] != "owner":
        raise RuntimeError(f"Unexpected workspace member role: {row['workspace_member_role']}")
    if not all_workspace_ids_match:
        raise RuntimeError("Seeded v1 rows do not share one workspace_id")
    if row["message_count"] != 1:
        raise RuntimeError("Seeded message was not preserved")
    return result


async def dispose_engine() -> None:
    await engine.dispose()


def run_async(coro: Awaitable[T]) -> T:
    async def runner() -> T:
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the v1-to-v2 workspace migration using seeded v1 rows. "
            "This command downgrades the configured database to revision 0013, "
            "seeds v1 data, upgrades to head, verifies workspace backfill, and cleans up."
        )
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm that the configured database may be downgraded/upgraded for validation.",
    )
    parser.add_argument(
        "--keep-seed-data",
        action="store_true",
        help="Leave seeded rows in the database after successful validation.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print validation details as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.yes:
        print("Refusing to mutate the database without --yes.")
        return 2

    try:
        run_async(cleanup_seed_data())
        run_downgrade_to_seed_base()
        run_async(cleanup_seed_data())
        run_async(seed_v1_data())
        run_upgrade_to_head()
        result = run_async(verify_seeded_data_migrated())
        if args.json:
            print(json.dumps({"seeded_ids": seeded_v1_ids(), "result": result}, indent=2))
        else:
            print("Workspace migration validation passed")
            print(f"workspace_id={result['workspace_id']}")
            print(f"workspace_slug={result['workspace_slug']}")
            print(f"message_count={result['message_count']}")
        if not args.keep_seed_data:
            run_async(cleanup_seed_data())
        return 0
    finally:
        run_async(dispose_engine())


if __name__ == "__main__":
    raise SystemExit(main())
