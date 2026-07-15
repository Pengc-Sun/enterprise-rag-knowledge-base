import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.db.session import get_db_session
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
)
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.knowledge_bases import (
    OWNER_PERMISSIONS,
    READ_PERMISSIONS,
    WRITE_PERMISSIONS,
    create_knowledge_base,
    delete_knowledge_base,
    get_knowledge_base_for_workspace,
    list_knowledge_bases_for_workspace,
    update_knowledge_base,
)
from backend.app.services.workspaces import (
    OWNER_ROLES,
    READ_ROLES,
    WRITE_ROLES,
    get_workspace_for_user,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge bases"])
workspace_router = APIRouter(
    prefix="/workspaces/{workspace_id}/knowledge-bases",
    tags=["knowledge bases"],
)


@router.post("", response_model=APIResponse[KnowledgeBaseRead], status_code=status.HTTP_201_CREATED)
async def create_knowledge_base_endpoint(
    knowledge_base_create: KnowledgeBaseCreate,
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[KnowledgeBaseRead]:
    workspace = await get_workspace_or_404(session, workspace_id, current_user.id, WRITE_ROLES)
    return await create_knowledge_base_in_workspace(
        knowledge_base_create,
        workspace,
        current_user,
        session,
    )


@workspace_router.post(
    "",
    response_model=APIResponse[KnowledgeBaseRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_knowledge_base_endpoint(
    workspace_id: uuid.UUID,
    knowledge_base_create: KnowledgeBaseCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[KnowledgeBaseRead]:
    workspace = await get_workspace_or_404(session, workspace_id, current_user.id, WRITE_ROLES)
    return await create_knowledge_base_in_workspace(
        knowledge_base_create,
        workspace,
        current_user,
        session,
    )


async def create_knowledge_base_in_workspace(
    knowledge_base_create: KnowledgeBaseCreate,
    workspace: Workspace,
    current_user: User,
    session: AsyncSession,
) -> APIResponse[KnowledgeBaseRead]:
    knowledge_base = await create_knowledge_base(
        session,
        current_user.id,
        workspace.id,
        knowledge_base_create,
    )
    return success_response(
        KnowledgeBaseRead.model_validate(knowledge_base),
        message="knowledge base created",
    )


@router.get("", response_model=APIResponse[list[KnowledgeBaseRead]])
async def list_knowledge_bases_endpoint(
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[KnowledgeBaseRead]]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    knowledge_bases = await list_knowledge_bases_for_workspace(session, workspace_id)
    return success_response([KnowledgeBaseRead.model_validate(item) for item in knowledge_bases])


@workspace_router.get("", response_model=APIResponse[list[KnowledgeBaseRead]])
async def list_workspace_knowledge_bases_endpoint(
    workspace_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[KnowledgeBaseRead]]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    knowledge_bases = await list_knowledge_bases_for_workspace(session, workspace_id)
    return success_response([KnowledgeBaseRead.model_validate(item) for item in knowledge_bases])


@router.get("/{knowledge_base_id}", response_model=APIResponse[KnowledgeBaseRead])
async def read_knowledge_base_endpoint(
    knowledge_base_id: uuid.UUID,
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[KnowledgeBaseRead]:
    return await read_knowledge_base_in_workspace(
        workspace_id,
        knowledge_base_id,
        current_user,
        session,
    )


@workspace_router.get("/{knowledge_base_id}", response_model=APIResponse[KnowledgeBaseRead])
async def read_workspace_knowledge_base_endpoint(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[KnowledgeBaseRead]:
    return await read_knowledge_base_in_workspace(
        workspace_id,
        knowledge_base_id,
        current_user,
        session,
    )


async def read_knowledge_base_in_workspace(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> APIResponse[KnowledgeBaseRead]:
    knowledge_base = await get_knowledge_base_or_404(
        session,
        workspace_id,
        knowledge_base_id,
        current_user.id,
        READ_PERMISSIONS,
    )
    return success_response(KnowledgeBaseRead.model_validate(knowledge_base))


@router.patch("/{knowledge_base_id}", response_model=APIResponse[KnowledgeBaseRead])
async def update_knowledge_base_endpoint(
    knowledge_base_id: uuid.UUID,
    knowledge_base_update: KnowledgeBaseUpdate,
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[KnowledgeBaseRead]:
    return await update_knowledge_base_in_workspace(
        workspace_id,
        knowledge_base_id,
        knowledge_base_update,
        current_user,
        session,
    )


@workspace_router.patch("/{knowledge_base_id}", response_model=APIResponse[KnowledgeBaseRead])
async def update_workspace_knowledge_base_endpoint(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    knowledge_base_update: KnowledgeBaseUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[KnowledgeBaseRead]:
    return await update_knowledge_base_in_workspace(
        workspace_id,
        knowledge_base_id,
        knowledge_base_update,
        current_user,
        session,
    )


async def update_knowledge_base_in_workspace(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    knowledge_base_update: KnowledgeBaseUpdate,
    current_user: User,
    session: AsyncSession,
) -> APIResponse[KnowledgeBaseRead]:
    knowledge_base = await get_knowledge_base_or_404(
        session,
        workspace_id,
        knowledge_base_id,
        current_user.id,
        WRITE_PERMISSIONS,
    )
    updated_knowledge_base = await update_knowledge_base(
        session,
        knowledge_base,
        knowledge_base_update,
    )
    return success_response(
        KnowledgeBaseRead.model_validate(updated_knowledge_base),
        message="knowledge base updated",
    )


@router.delete("/{knowledge_base_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base_endpoint(
    knowledge_base_id: uuid.UUID,
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    return await delete_knowledge_base_in_workspace(
        workspace_id,
        knowledge_base_id,
        current_user,
        session,
    )


@workspace_router.delete("/{knowledge_base_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace_knowledge_base_endpoint(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    return await delete_knowledge_base_in_workspace(
        workspace_id,
        knowledge_base_id,
        current_user,
        session,
    )


async def delete_knowledge_base_in_workspace(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> Response:
    knowledge_base = await get_knowledge_base_or_404(
        session,
        workspace_id,
        knowledge_base_id,
        current_user.id,
        OWNER_PERMISSIONS,
    )
    await delete_knowledge_base(session, knowledge_base)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def get_knowledge_base_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    user_id: uuid.UUID,
    allowed_permissions: frozenset[str],
) -> KnowledgeBase:
    if allowed_permissions == OWNER_PERMISSIONS:
        workspace_roles = OWNER_ROLES
    elif allowed_permissions == WRITE_PERMISSIONS:
        workspace_roles = WRITE_ROLES
    else:
        workspace_roles = READ_ROLES
    await get_workspace_or_404(session, workspace_id, user_id, workspace_roles)
    knowledge_base = await get_knowledge_base_for_workspace(
        session,
        knowledge_base_id,
        workspace_id,
    )
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )
    return knowledge_base


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
