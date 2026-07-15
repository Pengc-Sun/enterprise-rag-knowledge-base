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
MEMBER_MANAGEMENT_ROLES = WRITE_ROLES
DEFAULT_WORKSPACE_NAME = "Default Workspace"
DEFAULT_WORKSPACE_DESCRIPTION = (
    "Auto-created for v1-compatible knowledge-base flows."
)
DEFAULT_WORKSPACE_SLUG_PREFIX = "v1-default-"

ASSIGNABLE_MEMBER_ROLES = frozenset(
    {
        WorkspaceMemberRole.ADMIN.value,
        WorkspaceMemberRole.EDITOR.value,
        WorkspaceMemberRole.REVIEWER.value,
        WorkspaceMemberRole.VIEWER.value,
    }
)


class WorkspaceMemberRoleError(ValueError):
    message = "Workspace owner role cannot be managed through member endpoints"


class WorkspaceOwnerMemberError(ValueError):
    message = "Workspace owner membership cannot be modified through member endpoints"


def default_workspace_slug_for_user(user_id: uuid.UUID) -> str:
    return f"{DEFAULT_WORKSPACE_SLUG_PREFIX}{str(user_id).replace('-', '')}"


async def get_default_workspace_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Workspace | None:
    result = await session.execute(
        select(Workspace).where(
            Workspace.owner_id == user_id,
            Workspace.slug == default_workspace_slug_for_user(user_id),
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_default_workspace_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Workspace:
    existing_workspace = await get_default_workspace_for_user(session, user_id)
    if existing_workspace is not None:
        return existing_workspace

    workspace = Workspace(
        name=DEFAULT_WORKSPACE_NAME,
        slug=default_workspace_slug_for_user(user_id),
        description=DEFAULT_WORKSPACE_DESCRIPTION,
        owner_id=user_id,
    )
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user_id,
            role=WorkspaceMemberRole.OWNER.value,
        )
    )
    await session.commit()
    await session.refresh(workspace)
    return workspace


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


async def list_workspace_members(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[WorkspaceMember]:
    result = await session.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    return list(result.scalars().all())


async def get_workspace_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember | None:
    result = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def add_workspace_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: WorkspaceMemberRole,
) -> WorkspaceMember:
    role_value = validate_assignable_member_role(role)
    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role_value,
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def update_workspace_member_role(
    session: AsyncSession,
    workspace: Workspace,
    member: WorkspaceMember,
    role: WorkspaceMemberRole,
) -> WorkspaceMember:
    ensure_not_workspace_owner(workspace, member)
    member.role = validate_assignable_member_role(role)
    await session.commit()
    await session.refresh(member)
    return member


async def remove_workspace_member(
    session: AsyncSession,
    workspace: Workspace,
    member: WorkspaceMember,
) -> None:
    ensure_not_workspace_owner(workspace, member)
    await session.delete(member)
    await session.commit()


def validate_assignable_member_role(role: WorkspaceMemberRole) -> str:
    role_value = role.value
    if role_value not in ASSIGNABLE_MEMBER_ROLES:
        raise WorkspaceMemberRoleError
    return role_value


def ensure_not_workspace_owner(workspace: Workspace, member: WorkspaceMember) -> None:
    if member.user_id == workspace.owner_id or member.role == WorkspaceMemberRole.OWNER.value:
        raise WorkspaceOwnerMemberError
