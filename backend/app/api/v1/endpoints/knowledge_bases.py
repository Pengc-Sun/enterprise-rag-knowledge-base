import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.db.session import get_db_session
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User
from backend.app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
)
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.knowledge_bases import (
    create_knowledge_base,
    delete_knowledge_base,
    get_knowledge_base_for_owner,
    list_knowledge_bases_for_owner,
    update_knowledge_base,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge bases"])


@router.post("", response_model=APIResponse[KnowledgeBaseRead], status_code=status.HTTP_201_CREATED)
async def create_knowledge_base_endpoint(
    knowledge_base_create: KnowledgeBaseCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[KnowledgeBaseRead]:
    knowledge_base = await create_knowledge_base(
        session,
        current_user.id,
        knowledge_base_create,
    )
    return success_response(
        KnowledgeBaseRead.model_validate(knowledge_base),
        message="knowledge base created",
    )


@router.get("", response_model=APIResponse[list[KnowledgeBaseRead]])
async def list_knowledge_bases_endpoint(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[KnowledgeBaseRead]]:
    knowledge_bases = await list_knowledge_bases_for_owner(session, current_user.id)
    return success_response([KnowledgeBaseRead.model_validate(item) for item in knowledge_bases])


@router.get("/{knowledge_base_id}", response_model=APIResponse[KnowledgeBaseRead])
async def read_knowledge_base_endpoint(
    knowledge_base_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[KnowledgeBaseRead]:
    knowledge_base = await get_knowledge_base_or_404(session, knowledge_base_id, current_user.id)
    return success_response(KnowledgeBaseRead.model_validate(knowledge_base))


@router.patch("/{knowledge_base_id}", response_model=APIResponse[KnowledgeBaseRead])
async def update_knowledge_base_endpoint(
    knowledge_base_id: uuid.UUID,
    knowledge_base_update: KnowledgeBaseUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[KnowledgeBaseRead]:
    knowledge_base = await get_knowledge_base_or_404(session, knowledge_base_id, current_user.id)
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
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    knowledge_base = await get_knowledge_base_or_404(session, knowledge_base_id, current_user.id)
    await delete_knowledge_base(session, knowledge_base)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def get_knowledge_base_or_404(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> KnowledgeBase:
    knowledge_base = await get_knowledge_base_for_owner(session, knowledge_base_id, owner_id)
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )
    return knowledge_base
