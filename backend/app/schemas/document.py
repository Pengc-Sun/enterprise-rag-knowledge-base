import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.models.document import DocumentStatus


class DocumentRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    file_hash: str
    storage_path: str
    status: DocumentStatus
    error_message: str | None
    chunk_count: int = 0
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
