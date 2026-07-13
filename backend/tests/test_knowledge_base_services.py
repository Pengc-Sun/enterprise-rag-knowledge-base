import uuid
from datetime import UTC, datetime

import pytest

from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate
from backend.app.services.knowledge_bases import (
    OWNER_PERMISSIONS,
    READ_PERMISSIONS,
    WRITE_PERMISSIONS,
    get_knowledge_base_for_user,
    update_knowledge_base,
)


class FakePermissionResult:
    def __init__(self, row: tuple[KnowledgeBase, str | None] | None) -> None:
        self.row = row

    def first(self) -> tuple[KnowledgeBase, str | None] | None:
        return self.row


class FakePermissionSession:
    def __init__(self, row: tuple[KnowledgeBase, str | None] | None) -> None:
        self.row = row
        self.statement: object | None = None

    async def execute(self, statement: object) -> FakePermissionResult:
        self.statement = statement
        return FakePermissionResult(self.row)


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed = False

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = True


def make_knowledge_base() -> KnowledgeBase:
    now = datetime.now(UTC)
    return KnowledgeBase(
        id=uuid.uuid4(),
        name="Engineering Handbook",
        description="Internal docs",
        owner_id=uuid.uuid4(),
        visibility=KnowledgeBaseVisibility.PRIVATE.value,
        created_at=now,
        updated_at=now,
    )


def test_knowledge_base_create_schema_defaults_to_private() -> None:
    knowledge_base_create = KnowledgeBaseCreate(name="Engineering Handbook")

    assert knowledge_base_create.visibility == KnowledgeBaseVisibility.PRIVATE
    assert knowledge_base_create.description is None


@pytest.mark.asyncio
async def test_update_knowledge_base_updates_only_provided_fields() -> None:
    knowledge_base = make_knowledge_base()
    session = FakeSession()
    update = KnowledgeBaseUpdate(
        description="Updated docs",
        visibility=KnowledgeBaseVisibility.PUBLIC,
    )

    updated_knowledge_base = await update_knowledge_base(session, knowledge_base, update)  # type: ignore[arg-type]

    assert updated_knowledge_base is knowledge_base
    assert knowledge_base.name == "Engineering Handbook"
    assert knowledge_base.description == "Updated docs"
    assert knowledge_base.visibility == "public"
    assert session.committed is True
    assert session.refreshed is True


@pytest.mark.asyncio
async def test_get_knowledge_base_for_user_allows_owner_without_membership() -> None:
    knowledge_base = make_knowledge_base()
    session = FakePermissionSession((knowledge_base, None))

    result = await get_knowledge_base_for_user(
        session,  # type: ignore[arg-type]
        knowledge_base.id,
        knowledge_base.owner_id,
        OWNER_PERMISSIONS,
    )

    assert result is knowledge_base


@pytest.mark.asyncio
async def test_get_knowledge_base_for_user_denies_viewer_for_write_permissions() -> None:
    knowledge_base = make_knowledge_base()
    viewer_id = uuid.uuid4()
    session = FakePermissionSession((knowledge_base, "viewer"))

    result = await get_knowledge_base_for_user(
        session,  # type: ignore[arg-type]
        knowledge_base.id,
        viewer_id,
        WRITE_PERMISSIONS,
    )

    assert result is None
    assert "viewer" in READ_PERMISSIONS
    assert "viewer" not in WRITE_PERMISSIONS
