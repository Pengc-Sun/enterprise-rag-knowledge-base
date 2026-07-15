import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db_session
from backend.app.models.document import Document
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
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
    get_document_for_workspace_knowledge_base,
    list_documents_for_workspace_knowledge_base,
    reprocess_document,
)
from backend.app.services.embeddings import create_embedding_provider
from backend.app.services.knowledge_bases import (
    get_knowledge_base_for_workspace,
)
from backend.app.services.workspaces import (
    READ_ROLES,
    WRITE_ROLES,
    get_workspace_for_user,
)

router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}/documents", tags=["documents"])
workspace_router = APIRouter(
    prefix="/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/documents",
    tags=["documents"],
)


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
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[DocumentRead]]:
    return await list_documents_in_workspace(
        workspace_id,
        knowledge_base_id,
        current_user,
        session,
    )


@workspace_router.get("", response_model=APIResponse[list[DocumentRead]])
async def list_workspace_documents_endpoint(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[DocumentRead]]:
    return await list_documents_in_workspace(
        workspace_id,
        knowledge_base_id,
        current_user,
        session,
    )


async def list_documents_in_workspace(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> APIResponse[list[DocumentRead]]:
    knowledge_base = await get_knowledge_base_or_404(
        session,
        workspace_id,
        knowledge_base_id,
        current_user.id,
        READ_ROLES,
    )
    documents = await list_documents_for_workspace_knowledge_base(
        session,
        workspace_id,
        knowledge_base.id,
    )
    return success_response(
        [serialize_document(document, chunk_count) for document, chunk_count in documents]
    )


@router.post("", response_model=APIResponse[DocumentRead], status_code=status.HTTP_201_CREATED)
async def upload_document_endpoint(
    knowledge_base_id: uuid.UUID,
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile, File(...)],
) -> APIResponse[DocumentRead]:
    return await upload_document_to_workspace(
        workspace_id,
        knowledge_base_id,
        current_user,
        session,
        file,
    )


@workspace_router.post(
    "",
    response_model=APIResponse[DocumentRead],
    status_code=status.HTTP_201_CREATED,
)
async def upload_workspace_document_endpoint(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile, File(...)],
) -> APIResponse[DocumentRead]:
    return await upload_document_to_workspace(
        workspace_id,
        knowledge_base_id,
        current_user,
        session,
        file,
    )


async def upload_document_to_workspace(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
    file: UploadFile,
) -> APIResponse[DocumentRead]:
    knowledge_base = await get_knowledge_base_or_404(
        session,
        workspace_id,
        knowledge_base_id,
        current_user.id,
        WRITE_ROLES,
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


@router.get("/{document_id}", response_model=APIResponse[DocumentRead])
async def read_document_endpoint(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[DocumentRead]:
    return await read_document_in_workspace(
        workspace_id,
        knowledge_base_id,
        document_id,
        current_user,
        session,
    )


@workspace_router.get("/{document_id}", response_model=APIResponse[DocumentRead])
async def read_workspace_document_endpoint(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[DocumentRead]:
    return await read_document_in_workspace(
        workspace_id,
        knowledge_base_id,
        document_id,
        current_user,
        session,
    )


async def read_document_in_workspace(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> APIResponse[DocumentRead]:
    await get_knowledge_base_or_404(
        session,
        workspace_id,
        knowledge_base_id,
        current_user.id,
        READ_ROLES,
    )
    document = await get_document_or_404(session, workspace_id, knowledge_base_id, document_id)
    return success_response(serialize_document(document))


@router.post(
    "/{document_id}/reprocess",
    response_model=APIResponse[DocumentRead],
)
async def reprocess_document_endpoint(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[DocumentRead]:
    return await reprocess_document_in_workspace(
        workspace_id,
        knowledge_base_id,
        document_id,
        current_user,
        session,
    )


@workspace_router.post(
    "/{document_id}/reprocess",
    response_model=APIResponse[DocumentRead],
)
async def reprocess_workspace_document_endpoint(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[DocumentRead]:
    return await reprocess_document_in_workspace(
        workspace_id,
        knowledge_base_id,
        document_id,
        current_user,
        session,
    )


async def reprocess_document_in_workspace(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> APIResponse[DocumentRead]:
    await get_knowledge_base_or_404(
        session,
        workspace_id,
        knowledge_base_id,
        current_user.id,
        WRITE_ROLES,
    )
    document = await get_document_or_404(session, workspace_id, knowledge_base_id, document_id)

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
    workspace_id: Annotated[uuid.UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    return await delete_document_in_workspace(
        workspace_id,
        knowledge_base_id,
        document_id,
        current_user,
        session,
    )


@workspace_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace_document_endpoint(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    return await delete_document_in_workspace(
        workspace_id,
        knowledge_base_id,
        document_id,
        current_user,
        session,
    )


async def delete_document_in_workspace(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> Response:
    await get_knowledge_base_or_404(
        session,
        workspace_id,
        knowledge_base_id,
        current_user.id,
        WRITE_ROLES,
    )
    document = await get_document_or_404(session, workspace_id, knowledge_base_id, document_id)
    await delete_document(session, document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def get_knowledge_base_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    user_id: uuid.UUID,
    allowed_roles: frozenset[str],
) -> KnowledgeBase:
    await get_workspace_or_404(session, workspace_id, user_id, allowed_roles)
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


async def get_document_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document:
    document = await get_document_for_workspace_knowledge_base(
        session,
        workspace_id,
        knowledge_base_id,
        document_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document
