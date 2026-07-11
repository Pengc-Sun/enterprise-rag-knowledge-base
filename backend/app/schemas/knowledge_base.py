import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.knowledge_base import KnowledgeBaseVisibility


class KnowledgeBaseBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    visibility: KnowledgeBaseVisibility = KnowledgeBaseVisibility.PRIVATE


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    visibility: KnowledgeBaseVisibility | None = None


class KnowledgeBaseRead(KnowledgeBaseBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

