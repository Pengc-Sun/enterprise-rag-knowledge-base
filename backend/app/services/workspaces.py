import uuid
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.workspace import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
)
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate

READ_ROLES = frozenset(
    {
        WorkspaceMemberRole.OWNER.value,
        WorkspaceMemberRole.ADMIN.value,
        WorkspaceMemberRole.EDITOR.value,
        WorkspaceMemberRole.REVIEWER.value,
        WorkspaceMemberRole.VIEWER.value,
    }
)
WRITE_ROLES = frozenset(
    {
        WorkspaceMemberRole.OWNER.value,
        WorkspaceMemberRole.ADMIN.value,
    }
)
OWNER_ROLES = frozenset({WorkspaceMemberRole.OWNER.value})


async def create_workspace(
    session: AsyncSession,
    owner_id: uuid.UUID,
    workspace_create: WorkspaceCreate,
) -> Workspace:
    workspace = Workspace(
        name=workspace_create.name,
        slug=workspace_create.slug,
        description=workspace_create.description,
        owner_id=owner_id,
        template_id=workspace_create.template_id,
    )
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceMemberRole.OWNER.value,
        )
    )
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def list_workspaces_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[Workspace]:
    membership_subquery = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == user_id
    )
    result = await session.execute(
        select(Workspace)
        .where(
            or_(
                Workspace.owner_id == user_id,
                Workspace.id.in_(membership_subquery),
            )
        )
        .order_by(Workspace.created_at.desc())
    )
    return list(result.scalars().all())


async def get_workspace_for_user(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    allowed_roles: frozenset[str] = READ_ROLES,
) -> Workspace | None:
    result = await session.execute(
        select(Workspace, WorkspaceMember.role)
        .outerjoin(
            WorkspaceMember,
            (WorkspaceMember.workspace_id == Workspace.id) & (WorkspaceMember.user_id == user_id),
        )
        .where(Workspace.id == workspace_id)
    )
    row = result.first()
    if row is None:
        return None

    workspace = cast(Workspace, row[0])
    role = cast(str | None, row[1])
    if workspace.owner_id == user_id:
        return workspace
    if role in allowed_roles:
        return workspace
    return None


async def update_workspace(
    session: AsyncSession,
    workspace: Workspace,
    workspace_update: WorkspaceUpdate,
) -> Workspace:
    update_data = workspace_update.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value

    for field, value in update_data.items():
        setattr(workspace, field, value)

    await session.commit()
    await session.refresh(workspace)
    return workspace


async def delete_workspace(session: AsyncSession, workspace: Workspace) -> None:
    await session.delete(workspace)
    await session.commit()
