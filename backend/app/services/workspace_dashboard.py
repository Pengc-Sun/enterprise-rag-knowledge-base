import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.analysis import (
    AnalysisResult,
    AnalysisResultStatus,
    AnalysisTask,
    AnalysisTaskStatus,
    ReviewDecision,
    ReviewDecisionType,
)
from backend.app.models.document import Document, DocumentStatus
from backend.app.models.report import ExportJob, ExportJobStatus, Report, ReportStatus
from backend.app.schemas.workspace import (
    WorkspaceDashboardRead,
    WorkspaceDashboardReviewMetric,
    WorkspaceDashboardStatusMetric,
)


async def build_workspace_dashboard(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> WorkspaceDashboardRead:
    document_counts = await count_rows_by_value(
        session,
        workspace_id,
        Document.workspace_id,
        Document.status,
    )
    analysis_task_counts = await count_rows_by_value(
        session,
        workspace_id,
        AnalysisTask.workspace_id,
        AnalysisTask.status,
    )
    review_status_counts = await count_rows_by_value(
        session,
        workspace_id,
        AnalysisResult.workspace_id,
        AnalysisResult.status,
    )
    review_decision_counts = await count_rows_by_value(
        session,
        workspace_id,
        ReviewDecision.workspace_id,
        ReviewDecision.decision,
    )
    report_counts = await count_rows_by_value(
        session,
        workspace_id,
        Report.workspace_id,
        Report.status,
    )
    export_counts = await count_rows_by_value(
        session,
        workspace_id,
        ExportJob.workspace_id,
        ExportJob.status,
    )

    return WorkspaceDashboardRead(
        workspace_id=workspace_id,
        documents=build_status_metric(document_counts, DocumentStatus),
        analysis_tasks=build_status_metric(analysis_task_counts, AnalysisTaskStatus),
        reviews=WorkspaceDashboardReviewMetric(
            total=sum(review_status_counts.values()),
            by_status=complete_counts(review_status_counts, AnalysisResultStatus),
            by_decision=complete_counts(review_decision_counts, ReviewDecisionType),
        ),
        reports=build_status_metric(report_counts, ReportStatus),
        exports=build_status_metric(export_counts, ExportJobStatus),
    )


async def count_rows_by_value(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    workspace_column: Any,
    value_column: Any,
) -> dict[str, int]:
    result = await session.execute(
        select(value_column, func.count())
        .where(workspace_column == workspace_id)
        .group_by(value_column)
    )
    return {str(value): int(count) for value, count in result.all()}


def build_status_metric(
    counts: dict[str, int],
    status_enum: type[Any],
) -> WorkspaceDashboardStatusMetric:
    return WorkspaceDashboardStatusMetric(
        total=sum(counts.values()),
        by_status=complete_counts(counts, status_enum),
    )


def complete_counts(counts: dict[str, int], value_enum: type[Any]) -> dict[str, int]:
    return {str(item.value): counts.get(str(item.value), 0) for item in value_enum}
