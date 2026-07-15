import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.workspace import (
    WorkspaceMemberRole,
    WorkspaceStatus,
    WorkspaceTemplateCategory,
)

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class WorkspaceTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    category: WorkspaceTemplateCategory = WorkspaceTemplateCategory.GENERAL
    version: str = Field(default="1.0", min_length=1, max_length=50)
    is_active: bool = True
    directory_schema: dict[str, object] = Field(default_factory=dict)
    analysis_task_schema: dict[str, object] = Field(default_factory=dict)
    report_schema: dict[str, object] = Field(default_factory=dict)


class WorkspaceTemplateCreate(WorkspaceTemplateBase):
    pass


class WorkspaceTemplateRead(WorkspaceTemplateBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=SLUG_PATTERN)
    description: str | None = Field(default=None, max_length=5000)
    template_id: uuid.UUID | None = None


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100, pattern=SLUG_PATTERN)
    description: str | None = Field(default=None, max_length=5000)
    status: WorkspaceStatus | None = None


class WorkspaceRead(WorkspaceBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    status: WorkspaceStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberBase(BaseModel):
    user_id: uuid.UUID
    role: WorkspaceMemberRole = WorkspaceMemberRole.VIEWER


class WorkspaceMemberCreate(WorkspaceMemberBase):
    pass


class WorkspaceMemberUpdate(BaseModel):
    role: WorkspaceMemberRole


class WorkspaceMemberRead(WorkspaceMemberBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
