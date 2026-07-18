import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.report import ReportSectionStatus, ReportStatus


class ReportBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ReportCreate(ReportBase):
    pass


class ReportRead(ReportBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    status: ReportStatus
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportSectionBase(BaseModel):
    template_section_key: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    body_markdown: str = ""
    source_task_keys: list[str] = Field(default_factory=list)
    source_result_ids: list[str] = Field(default_factory=list)
    sort_order: int = 0


class ReportSectionCreate(ReportSectionBase):
    pass


class ReportSectionRead(ReportSectionBase):
    id: uuid.UUID
    report_id: uuid.UUID
    workspace_id: uuid.UUID
    status: ReportSectionStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
