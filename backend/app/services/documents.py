import hashlib
import re
import uuid
from contextlib import suppress
from pathlib import Path, PurePath

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document, DocumentChunk, DocumentStatus
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User
from backend.app.services.document_chunkers import ChunkingConfig, chunk_document
from backend.app.services.document_chunks import replace_document_chunks
from backend.app.services.document_parsers import DocumentParsingError, parse_document

CHUNK_SIZE_BYTES = 1024 * 1024
ALLOWED_MIME_TYPES_BY_EXTENSION: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".txt": frozenset({"text/plain"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".markdown": frozenset({"text/markdown", "text/plain"}),
    ".docx": frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
}


class DocumentUploadError(Exception):
    message = "Invalid document upload"


class InvalidFilenameError(DocumentUploadError):
    message = "Invalid filename"


class UnsupportedFileExtensionError(DocumentUploadError):
    message = "Unsupported file extension"


class UnsupportedMimeTypeError(DocumentUploadError):
    message = "Unsupported MIME type"


class FileTooLargeError(DocumentUploadError):
    message = "Uploaded file is too large"


class DuplicateDocumentError(DocumentUploadError):
    message = "Document already exists"


def sanitize_filename(filename: str | None) -> str:
    raw_filename = PurePath(filename or "").name
    if not raw_filename:
        raise InvalidFilenameError

    path = Path(raw_filename)
    extension = path.suffix.lower()
    if not extension:
        raise UnsupportedFileExtensionError

    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-")
    if not stem:
        stem = "document"

    return f"{stem[:200]}{extension}"


def validate_upload_type(filename: str, content_type: str | None) -> str:
    extension = Path(filename).suffix.lower()
    allowed_mime_types = ALLOWED_MIME_TYPES_BY_EXTENSION.get(extension)
    if allowed_mime_types is None:
        raise UnsupportedFileExtensionError

    normalized_content_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if normalized_content_type not in allowed_mime_types:
        raise UnsupportedMimeTypeError

    return extension.removeprefix(".")


async def create_document_from_upload(
    session: AsyncSession,
    knowledge_base: KnowledgeBase,
    current_user: User,
    upload_file: UploadFile,
    upload_dir: str,
    max_file_size_bytes: int,
) -> Document:
    sanitized_filename = sanitize_filename(upload_file.filename)
    file_type = validate_upload_type(sanitized_filename, upload_file.content_type)

    document_id = uuid.uuid4()
    storage_directory = Path(upload_dir) / str(knowledge_base.id)
    storage_directory.mkdir(parents=True, exist_ok=True)
    storage_path = storage_directory / f"{document_id}_{sanitized_filename}"

    digest = hashlib.sha256()
    file_size = 0

    try:
        with storage_path.open("xb") as output_file:
            while chunk := await upload_file.read(CHUNK_SIZE_BYTES):
                file_size += len(chunk)
                if file_size > max_file_size_bytes:
                    raise FileTooLargeError
                digest.update(chunk)
                output_file.write(chunk)
    except DocumentUploadError:
        storage_path.unlink(missing_ok=True)
        with suppress(OSError):
            storage_directory.rmdir()
        raise

    file_hash = digest.hexdigest()
    duplicate_document = await get_document_by_hash(session, knowledge_base.id, file_hash)
    if duplicate_document is not None:
        storage_path.unlink(missing_ok=True)
        with suppress(OSError):
            storage_directory.rmdir()
        raise DuplicateDocumentError

    document = Document(
        id=document_id,
        knowledge_base_id=knowledge_base.id,
        workspace_id=knowledge_base.workspace_id,
        filename=sanitized_filename,
        file_type=file_type,
        file_size=file_size,
        file_hash=file_hash,
        storage_path=storage_path.as_posix(),
        status=DocumentStatus.UPLOADED.value,
        created_by=current_user.id,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def get_document_by_hash(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    file_hash: str,
) -> Document | None:
    result = await session.execute(
        select(Document).where(
            Document.knowledge_base_id == knowledge_base_id,
            Document.file_hash == file_hash,
        )
    )
    return result.scalar_one_or_none()


async def get_document_for_knowledge_base(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document | None:
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.knowledge_base_id == knowledge_base_id,
        )
    )
    return result.scalar_one_or_none()


async def list_documents_for_knowledge_base(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
) -> list[tuple[Document, int]]:
    result = await session.execute(
        select(Document, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    return [(document, int(chunk_count)) for document, chunk_count in result.all()]


async def delete_document(session: AsyncSession, document: Document) -> None:
    storage_path = Path(document.storage_path)
    await session.delete(document)
    await session.commit()
    with suppress(OSError):
        storage_path.unlink(missing_ok=True)


async def reprocess_document(
    session: AsyncSession,
    document: Document,
    chunking_config: ChunkingConfig | None = None,
) -> Document:
    try:
        document.status = DocumentStatus.PARSING.value
        document.error_message = None
        await session.commit()

        parsed_document = parse_document(document)
        document.status = DocumentStatus.CHUNKING.value
        await session.commit()

        chunks = chunk_document(parsed_document, chunking_config)
        await replace_document_chunks(session, document, chunks)

        document.status = DocumentStatus.COMPLETED.value
        document.error_message = None
        await session.commit()
        await session.refresh(document)
        return document
    except DocumentParsingError as exc:
        document.status = DocumentStatus.FAILED.value
        document.error_message = exc.message
        await session.commit()
        await session.refresh(document)
        raise
