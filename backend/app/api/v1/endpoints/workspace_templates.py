import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.schemas.response import APIResponse, success_response
from backend.app.schemas.workspace import WorkspaceTemplateRead
from backend.app.services.workspace_templates import (
    get_active_workspace_template,
    list_active_workspace_templates,
)

router = APIRouter(prefix="/workspace-templates", tags=["workspace templates"])


@router.get("", response_model=APIResponse[list[WorkspaceTemplateRead]])
async def list_workspace_templates_endpoint(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[WorkspaceTemplateRead]]:
    templates = await list_active_workspace_templates(session)
    return success_response(
        [WorkspaceTemplateRead.model_validate(template) for template in templates]
    )


@router.get("/{template_id}", response_model=APIResponse[WorkspaceTemplateRead])
async def read_workspace_template_endpoint(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[WorkspaceTemplateRead]:
    template = await get_active_workspace_template(session, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace template not found",
        )
    return success_response(WorkspaceTemplateRead.model_validate(template))
