import uuid
from datetime import UTC, datetime

import pytest

from backend.app.models.workspace import WorkspaceDirectory
from backend.app.schemas.workspace import WorkspaceDirectoryCreate, WorkspaceDirectoryUpdate
from backend.app.services.workspace_directories import (
    WorkspaceDirectoryParentError,
    WorkspaceDirectorySelfParentError,
    create_workspace_directory,
    delete_workspace_directory,
    get_workspace_directory,
    list_workspace_directories,
    update_workspace_directory,
)


class FakeScalarResult:
    def __init__(self, items: list[WorkspaceDirectory]) -> None:
        self.items = items

    def all(self) -> list[WorkspaceDirectory]:
        return self.items


class FakeResult:
    def __init__(
        self,
        items: list[WorkspaceDirectory] | None = None,
        scalar: WorkspaceDirectory | None = None,
    ) -> None:
        self.items = items or []
        self.scalar = scalar

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.items)

    def scalar_one_or_none(self) -> WorkspaceDirectory | None:
        return self.scalar


class FakeSession:
    def __init__(self, results: list[FakeResult] | None = None) -> None:
        self.results = results or []
        self.statements: list[object] = []
        self.added: object | None = None
        self.deleted: object | None = None
        self.committed = False
        self.refreshed: object | None = None

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return self.results.pop(0)

    def add(self, instance: object) -> None:
        self.added = instance
        if isinstance(instance, WorkspaceDirectory) and instance.id is None:
            instance.id = uuid.uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = instance

    async def delete(self, instance: object) -> None:
        self.deleted = instance


def make_directory(
    workspace_id: uuid.UUID | None = None,
    directory_id: uuid.UUID | None = None,
) -> WorkspaceDirectory:
    now = datetime.now(UTC)
    return WorkspaceDirectory(
        id=directory_id or uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
        name="Papers",
        path="papers",
        description="Research papers",
        sort_order=10,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_workspace_directories_returns_ordered_directories() -> None:
    workspace_id = uuid.uuid4()
    directory = make_directory(workspace_id)
    session = FakeSession([FakeResult(items=[directory])])

    directories = await list_workspace_directories(session, workspace_id)  # type: ignore[arg-type]

    assert directories == [directory]
    assert session.statements


@pytest.mark.asyncio
async def test_get_workspace_directory_filters_by_workspace() -> None:
    workspace_id = uuid.uuid4()
    directory = make_directory(workspace_id)
    session = FakeSession([FakeResult(scalar=directory)])

    result = await get_workspace_directory(
        session,  # type: ignore[arg-type]
        workspace_id,
        directory.id,
    )

    assert result is directory
    assert session.statements


@pytest.mark.asyncio
async def test_create_workspace_directory_validates_parent_directory() -> None:
    workspace_id = uuid.uuid4()
    parent = make_directory(workspace_id)
    session = FakeSession([FakeResult(scalar=parent)])

    directory = await create_workspace_directory(
        session,  # type: ignore[arg-type]
        workspace_id,
        WorkspaceDirectoryCreate(
            name="Reviewed Papers",
            path="papers/reviewed",
            parent_id=parent.id,
            sort_order=20,
        ),
    )

    assert directory.workspace_id == workspace_id
    assert directory.parent_id == parent.id
    assert session.added is directory
    assert session.committed is True
    assert session.refreshed is directory


@pytest.mark.asyncio
async def test_create_workspace_directory_rejects_missing_parent() -> None:
    session = FakeSession([FakeResult(scalar=None)])

    with pytest.raises(WorkspaceDirectoryParentError):
        await create_workspace_directory(
            session,  # type: ignore[arg-type]
            uuid.uuid4(),
            WorkspaceDirectoryCreate(
                name="Reviewed Papers",
                path="papers/reviewed",
                parent_id=uuid.uuid4(),
            ),
        )


@pytest.mark.asyncio
async def test_update_workspace_directory_rejects_self_parent() -> None:
    workspace_id = uuid.uuid4()
    directory = make_directory(workspace_id)
    session = FakeSession()

    with pytest.raises(WorkspaceDirectorySelfParentError):
        await update_workspace_directory(
            session,  # type: ignore[arg-type]
            workspace_id,
            directory,
            WorkspaceDirectoryUpdate(parent_id=directory.id),
        )

    assert session.committed is False


@pytest.mark.asyncio
async def test_update_workspace_directory_applies_fields() -> None:
    workspace_id = uuid.uuid4()
    directory = make_directory(workspace_id)
    session = FakeSession()

    result = await update_workspace_directory(
        session,  # type: ignore[arg-type]
        workspace_id,
        directory,
        WorkspaceDirectoryUpdate(
            name="Evidence Tables",
            path="evidence-tables",
            description="Structured evidence",
            sort_order=30,
        ),
    )

    assert result is directory
    assert directory.name == "Evidence Tables"
    assert directory.path == "evidence-tables"
    assert directory.description == "Structured evidence"
    assert directory.sort_order == 30
    assert session.committed is True
    assert session.refreshed is directory


@pytest.mark.asyncio
async def test_delete_workspace_directory_deletes_and_commits() -> None:
    directory = make_directory()
    session = FakeSession()

    await delete_workspace_directory(session, directory)  # type: ignore[arg-type]

    assert session.deleted is directory
    assert session.committed is True

