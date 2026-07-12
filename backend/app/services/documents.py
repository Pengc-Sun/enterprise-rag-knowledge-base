import hashlib
import re
import uuid
from contextlib import suppress
from pathlib import Path, PurePath

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document, DocumentStatus
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User

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

    document = Document(
        id=document_id,
        knowledge_base_id=knowledge_base.id,
        filename=sanitized_filename,
        file_type=file_type,
        file_size=file_size,
        file_hash=digest.hexdigest(),
        storage_path=storage_path.as_posix(),
        status=DocumentStatus.UPLOADED.value,
        created_by=current_user.id,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document
