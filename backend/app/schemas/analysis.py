import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.analysis import AnalysisResultStatus, AnalysisTaskStatus, ReviewDecisionType


class AnalysisTaskBase(BaseModel):
    template_task_key: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    task_type: str = Field(min_length=1, max_length=50)
    input_scope: dict[str, object] = Field(default_factory=dict)
    output_schema: dict[str, object] = Field(default_factory=dict)


class AnalysisTaskCreate(AnalysisTaskBase):
    pass


class AnalysisTaskRead(AnalysisTaskBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    status: AnalysisTaskStatus
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisResultBase(BaseModel):
    status: AnalysisResultStatus = AnalysisResultStatus.AI_GENERATED
    result: dict[str, object] = Field(default_factory=dict)
    citations: list[dict[str, object]] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    model: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=100)
    token_usage: dict[str, object] = Field(default_factory=dict)


class AnalysisResultCreate(AnalysisResultBase):
    pass


class AnalysisResultRead(AnalysisResultBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    analysis_task_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewDecisionBase(BaseModel):
    decision: ReviewDecisionType
    comment: str | None = Field(default=None, max_length=5000)
    edited_result: dict[str, object] | None = None


class ReviewDecisionCreate(ReviewDecisionBase):
    pass


class ReviewDecisionRead(ReviewDecisionBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    analysis_result_id: uuid.UUID
    reviewer_id: uuid.UUID | None
    original_result: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
