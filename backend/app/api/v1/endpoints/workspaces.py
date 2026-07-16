import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.db.session import get_db_session
from backend.app.models.audit import AuditAction, AuditResourceType
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, WorkspaceMember
from backend.app.schemas.response import APIResponse, success_response
from backend.app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberRead,
    WorkspaceMemberUpdate,
    WorkspaceRead,
    WorkspaceUpdate,
)
from backend.app.services.audit_logs import create_audit_log
from backend.app.services.users import get_user_by_id
from backend.app.services.workspaces import (
    MEMBER_MANAGEMENT_ROLES,
    OWNER_ROLES,
    READ_ROLES,
    WRITE_ROLES,
    WorkspaceMemberRoleError,
    WorkspaceOwnerMemberError,
    add_workspace_member,
    create_workspace,
    delete_workspace,
    get_workspace_for_user,
    get_workspace_member,
    list_workspace_members,
    list_workspaces_for_user,
    remove_workspace_member,
    update_workspace,
    update_workspace_member_role,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=APIResponse[WorkspaceRead], status_code=status.HTTP_201_CREATED)
async def create_workspace_endpoint(
    workspace_create: WorkspaceCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[WorkspaceRead]:
    workspace = await create_workspace(session, current_user.id, workspace_create)
    await create_audit_log(
        session,
        workspace_id=workspace.id,
        actor_user_id=current_user.id,
        action=AuditAction.WORKSPACE_CREATED,
        resource_type=AuditResourceType.WORKSPACE,
        resource_id=workspace.id,
        metadata={"name": workspace.name, "slug": workspace.slug},
    )
    return success_response(
        WorkspaceRead.model_validate(workspace),
        message="workspace created",
    )


@router.get("", response_model=APIResponse[list[WorkspaceRead]])
async def list_workspaces_endpoint(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[WorkspaceRead]]:
    workspaces = await list_workspaces_for_user(session, current_user.id)
    return success_response([WorkspaceRead.model_validate(item) for item in workspaces])


@router.get("/{workspace_id}", response_model=APIResponse[WorkspaceRead])
async def read_workspace_endpoint(
    workspace_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[WorkspaceRead]:
    workspace = await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    return success_response(WorkspaceRead.model_validate(workspace))


@router.patch("/{workspace_id}", response_model=APIResponse[WorkspaceRead])
async def update_workspace_endpoint(
    workspace_id: uuid.UUID,
    workspace_update: WorkspaceUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[WorkspaceRead]:
    workspace = await get_workspace_or_404(session, workspace_id, current_user.id, WRITE_ROLES)
    updated_workspace = await update_workspace(session, workspace, workspace_update)
    await create_audit_log(
        session,
        workspace_id=updated_workspace.id,
        actor_user_id=current_user.id,
        action=AuditAction.WORKSPACE_UPDATED,
        resource_type=AuditResourceType.WORKSPACE,
        resource_id=updated_workspace.id,
        metadata=workspace_update.model_dump(mode="json", exclude_unset=True),
    )
    return success_response(
        WorkspaceRead.model_validate(updated_workspace),
        message="workspace updated",
    )


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace_endpoint(
    workspace_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    workspace = await get_workspace_or_404(session, workspace_id, current_user.id, OWNER_ROLES)
    audit_metadata: dict[str, object] = {"name": workspace.name, "slug": workspace.slug}
    await delete_workspace(session, workspace)
    await create_audit_log(
        session,
        workspace_id=workspace.id,
        actor_user_id=current_user.id,
        action=AuditAction.WORKSPACE_DELETED,
        resource_type=AuditResourceType.WORKSPACE,
        resource_id=workspace.id,
        metadata=audit_metadata,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/members", response_model=APIResponse[list[WorkspaceMemberRead]])
async def list_workspace_members_endpoint(
    workspace_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[WorkspaceMemberRead]]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    members = await list_workspace_members(session, workspace_id)
    return success_response([WorkspaceMemberRead.model_validate(member) for member in members])


@router.post(
    "/{workspace_id}/members",
    response_model=APIResponse[WorkspaceMemberRead],
    status_code=status.HTTP_201_CREATED,
)
async def add_workspace_member_endpoint(
    workspace_id: uuid.UUID,
    member_create: WorkspaceMemberCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[WorkspaceMemberRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, MEMBER_MANAGEMENT_ROLES)
    if await get_user_by_id(session, member_create.user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        member = await add_workspace_member(
            session,
            workspace_id,
            member_create.user_id,
            member_create.role,
        )
    except WorkspaceMemberRoleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

    await create_audit_log(
        session,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        action=AuditAction.WORKSPACE_MEMBER_ADDED,
        resource_type=AuditResourceType.WORKSPACE_MEMBER,
        resource_id=member.id,
        metadata={"user_id": str(member.user_id), "role": member.role},
    )
    return success_response(
        WorkspaceMemberRead.model_validate(member),
        message="workspace member added",
    )


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=APIResponse[WorkspaceMemberRead],
)
async def update_workspace_member_endpoint(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    member_update: WorkspaceMemberUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[WorkspaceMemberRead]:
    workspace = await get_workspace_or_404(
        session,
        workspace_id,
        current_user.id,
        MEMBER_MANAGEMENT_ROLES,
    )
    member = await get_workspace_member_or_404(session, workspace_id, user_id)
    try:
        updated_member = await update_workspace_member_role(
            session,
            workspace,
            member,
            member_update.role,
        )
    except (WorkspaceMemberRoleError, WorkspaceOwnerMemberError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

    await create_audit_log(
        session,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        action=AuditAction.WORKSPACE_MEMBER_UPDATED,
        resource_type=AuditResourceType.WORKSPACE_MEMBER,
        resource_id=updated_member.id,
        metadata={"user_id": str(updated_member.user_id), "role": updated_member.role},
    )
    return success_response(
        WorkspaceMemberRead.model_validate(updated_member),
        message="workspace member updated",
    )


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_workspace_member_endpoint(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    workspace = await get_workspace_or_404(
        session,
        workspace_id,
        current_user.id,
        MEMBER_MANAGEMENT_ROLES,
    )
    member = await get_workspace_member_or_404(session, workspace_id, user_id)
    try:
        await remove_workspace_member(session, workspace, member)
    except WorkspaceOwnerMemberError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

    await create_audit_log(
        session,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        action=AuditAction.WORKSPACE_MEMBER_REMOVED,
        resource_type=AuditResourceType.WORKSPACE_MEMBER,
        resource_id=member.id,
        metadata={"user_id": str(member.user_id), "role": member.role},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def get_workspace_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    allowed_roles: frozenset[str],
) -> Workspace:
    workspace = await get_workspace_for_user(session, workspace_id, user_id, allowed_roles)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return workspace


async def get_workspace_member_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember:
    member = await get_workspace_member(session, workspace_id, user_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found",
        )
    return member
