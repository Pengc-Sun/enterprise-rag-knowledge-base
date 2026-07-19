import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.workspace import (
    WorkspaceMemberRole,
    WorkspaceStatus,
    WorkspaceTemplateCategory,
)

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
DIRECTORY_PATH_PATTERN = r"^[a-z0-9]+(?:[-/][a-z0-9]+)*$"


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


class WorkspaceDashboardStatusMetric(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)


class WorkspaceDashboardReviewMetric(WorkspaceDashboardStatusMetric):
    by_decision: dict[str, int] = Field(default_factory=dict)


class WorkspaceDashboardRead(BaseModel):
    workspace_id: uuid.UUID
    documents: WorkspaceDashboardStatusMetric
    analysis_tasks: WorkspaceDashboardStatusMetric
    reviews: WorkspaceDashboardReviewMetric
    reports: WorkspaceDashboardStatusMetric
    exports: WorkspaceDashboardStatusMetric


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


class WorkspaceDirectoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1, max_length=500, pattern=DIRECTORY_PATH_PATTERN)
    description: str | None = Field(default=None, max_length=5000)
    parent_id: uuid.UUID | None = None
    sort_order: int = 0


class WorkspaceDirectoryCreate(WorkspaceDirectoryBase):
    pass


class WorkspaceDirectoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    path: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        pattern=DIRECTORY_PATH_PATTERN,
    )
    description: str | None = Field(default=None, max_length=5000)
    parent_id: uuid.UUID | None = None
    sort_order: int | None = None


class WorkspaceDirectoryRead(WorkspaceDirectoryBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
