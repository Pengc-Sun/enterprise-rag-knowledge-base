import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.workspace import WorkspaceDirectory
from backend.app.schemas.workspace import WorkspaceDirectoryCreate, WorkspaceDirectoryUpdate


class WorkspaceDirectoryParentError(ValueError):
    message = "Parent directory not found"


class WorkspaceDirectorySelfParentError(ValueError):
    message = "Directory cannot be its own parent"


async def list_workspace_directories(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[WorkspaceDirectory]:
    result = await session.execute(
        select(WorkspaceDirectory)
        .where(WorkspaceDirectory.workspace_id == workspace_id)
        .order_by(WorkspaceDirectory.sort_order.asc(), WorkspaceDirectory.name.asc())
    )
    return list(result.scalars().all())


async def get_workspace_directory(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    directory_id: uuid.UUID,
) -> WorkspaceDirectory | None:
    result = await session.execute(
        select(WorkspaceDirectory).where(
            WorkspaceDirectory.id == directory_id,
            WorkspaceDirectory.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def create_workspace_directory(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    directory_create: WorkspaceDirectoryCreate,
) -> WorkspaceDirectory:
    if directory_create.parent_id is not None:
        await ensure_parent_directory_exists(session, workspace_id, directory_create.parent_id)

    directory = WorkspaceDirectory(
        workspace_id=workspace_id,
        parent_id=directory_create.parent_id,
        name=directory_create.name,
        path=directory_create.path,
        description=directory_create.description,
        sort_order=directory_create.sort_order,
    )
    session.add(directory)
    await session.commit()
    await session.refresh(directory)
    return directory


async def update_workspace_directory(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    directory: WorkspaceDirectory,
    directory_update: WorkspaceDirectoryUpdate,
) -> WorkspaceDirectory:
    update_data = directory_update.model_dump(exclude_unset=True)
    if "parent_id" in update_data and update_data["parent_id"] is not None:
        parent_id = update_data["parent_id"]
        if parent_id == directory.id:
            raise WorkspaceDirectorySelfParentError
        await ensure_parent_directory_exists(session, workspace_id, parent_id)

    for field, value in update_data.items():
        setattr(directory, field, value)

    await session.commit()
    await session.refresh(directory)
    return directory


async def delete_workspace_directory(
    session: AsyncSession,
    directory: WorkspaceDirectory,
) -> None:
    await session.delete(directory)
    await session.commit()


async def ensure_parent_directory_exists(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    parent_id: uuid.UUID,
) -> None:
    parent = await get_workspace_directory(session, workspace_id, parent_id)
    if parent is None:
        raise WorkspaceDirectoryParentError

