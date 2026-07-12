import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.conversation import MessageRole


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=255)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class ConversationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1, max_length=20000)
    sources: list[dict[str, object]] = Field(default_factory=list)
    token_usage: dict[str, object] | None = None
    latency_ms: int | None = Field(default=None, ge=0)


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    sources: list[dict[str, object]]
    token_usage: dict[str, object] | None
    latency_ms: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
