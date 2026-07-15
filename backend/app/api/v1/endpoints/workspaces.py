import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.response import APIResponse, success_response
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from backend.app.services.workspaces import (
    OWNER_ROLES,
    READ_ROLES,
    WRITE_ROLES,
    create_workspace,
    delete_workspace,
    get_workspace_for_user,
    list_workspaces_for_user,
    update_workspace,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=APIResponse[WorkspaceRead], status_code=status.HTTP_201_CREATED)
async def create_workspace_endpoint(
    workspace_create: WorkspaceCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[WorkspaceRead]:
    workspace = await create_workspace(session, current_user.id, workspace_create)
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
    await delete_workspace(session, workspace)
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
