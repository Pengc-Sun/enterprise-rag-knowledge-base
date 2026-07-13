import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db_session
from backend.app.models.document import Document
from backend.app.models.user import User
from backend.app.schemas.document import DocumentRead
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.document_embeddings import embed_document_chunks
from backend.app.services.document_parsers import DocumentParsingError
from backend.app.services.documents import (
    DocumentUploadError,
    DuplicateDocumentError,
    FileTooLargeError,
    create_document_from_upload,
    delete_document,
    get_document_for_knowledge_base,
    list_documents_for_knowledge_base,
    reprocess_document,
)
from backend.app.services.embeddings import create_embedding_provider
from backend.app.services.knowledge_bases import (
    READ_PERMISSIONS,
    WRITE_PERMISSIONS,
    get_knowledge_base_for_user,
)

router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}/documents", tags=["documents"])


async def process_document_for_retrieval(
    session: AsyncSession,
    document: Document,
    settings: Settings,
) -> tuple[Document, int]:
    processed_document = await reprocess_document(session, document)
    embedding_result = await embed_document_chunks(
        session,
        processed_document,
        create_embedding_provider(settings),
        settings.embedding_batch_size,
        settings.embedding_max_retries,
    )
    return processed_document, embedding_result.embedded_count + embedding_result.failed_count


def serialize_document(document: object, chunk_count: int = 0) -> DocumentRead:
    return DocumentRead.model_validate(document).model_copy(update={"chunk_count": chunk_count})


@router.get("", response_model=APIResponse[list[DocumentRead]])
async def list_documents_endpoint(
    knowledge_base_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[DocumentRead]]:
    knowledge_base = await get_knowledge_base_for_user(
        session,
        knowledge_base_id,
        current_user.id,
        READ_PERMISSIONS,
    )
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    documents = await list_documents_for_knowledge_base(session, knowledge_base.id)
    return success_response(
        [serialize_document(document, chunk_count) for document, chunk_count in documents]
    )


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
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except DocumentUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

    try:
        processed_document, chunk_count = await process_document_for_retrieval(
            session,
            document,
            settings,
        )
    except DocumentParsingError:
        return success_response(
            serialize_document(document),
            message="document uploaded but processing failed",
        )

    return success_response(
        serialize_document(processed_document, chunk_count),
        message="document uploaded and processed",
    )


@router.post(
    "/{document_id}/reprocess",
    response_model=APIResponse[DocumentRead],
)
async def reprocess_document_endpoint(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
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

    document = await get_document_for_knowledge_base(session, knowledge_base.id, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    settings = get_settings()
    try:
        processed_document, chunk_count = await process_document_for_retrieval(
            session,
            document,
            settings,
        )
    except DocumentParsingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

    return success_response(
        serialize_document(processed_document, chunk_count),
        message="document reprocessed",
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
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

    document = await get_document_for_knowledge_base(session, knowledge_base.id, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    await delete_document(session, document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
