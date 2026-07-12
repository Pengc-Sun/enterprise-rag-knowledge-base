import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.schemas.document import DocumentRead
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.documents import (
    DocumentUploadError,
    FileTooLargeError,
    create_document_from_upload,
)
from backend.app.services.knowledge_bases import (
    WRITE_PERMISSIONS,
    get_knowledge_base_for_user,
)

router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}/documents", tags=["documents"])


@router.post("", response_model=APIResponse[DocumentRead], status_code=status.HTTP_201_CREATED)
async def upload_document_endpoint(
    knowledge_base_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile, File(...)],
) -> APIResponse[DocumentRead]:
    knowledge_base = await get_knowledge_base_for_user(
        session,
        knowledge_base_id,
        current_user.id,
        WRITE_PERMISSIONS,
    )
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    settings = get_settings()
    try:
        document = await create_document_from_upload(
            session,
            knowledge_base,
            current_user,
            file,
            settings.upload_dir,
            settings.max_upload_size_bytes,
        )
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=exc.message,
        ) from exc
    except DocumentUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

    return success_response(DocumentRead.model_validate(document), message="document uploaded")
