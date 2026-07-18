import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.report import ReportSectionStatus, ReportStatus


class ReportBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ReportCreate(ReportBase):
    pass


class ReportUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class ReportRead(ReportBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    status: ReportStatus
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportPreviewRead(BaseModel):
    report_id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    status: ReportStatus
    section_count: int
    markdown: str


class ReportSectionBase(BaseModel):
    template_section_key: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    body_markdown: str = ""
    source_task_keys: list[str] = Field(default_factory=list)
    source_result_ids: list[str] = Field(default_factory=list)
    sort_order: int = 0


class ReportSectionCreate(ReportSectionBase):
    pass


class ReportSectionUpdate(BaseModel):
    template_section_key: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body_markdown: str | None = None
    source_task_keys: list[str] | None = None
    source_result_ids: list[str] | None = None
    sort_order: int | None = None


class ReportSectionGenerateRequest(BaseModel):
    analysis_result_ids: list[uuid.UUID] = Field(min_length=1)
    template_section_key: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    sort_order: int = 0


class ReportSectionOrderItem(BaseModel):
    section_id: uuid.UUID
    sort_order: int


class ReportSectionReorderRequest(BaseModel):
    sections: list[ReportSectionOrderItem] = Field(min_length=1)


class ReportSectionRead(ReportSectionBase):
    id: uuid.UUID
    report_id: uuid.UUID
    workspace_id: uuid.UUID
    status: ReportSectionStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
