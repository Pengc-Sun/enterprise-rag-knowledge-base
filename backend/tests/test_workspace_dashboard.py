import uuid

import pytest

from backend.app.models.analysis import (
    AnalysisResultStatus,
    AnalysisTaskStatus,
    ReviewDecisionType,
)
from backend.app.models.document import DocumentStatus
from backend.app.models.report import ExportJobStatus, ReportStatus
from backend.app.services.workspace_dashboard import (
    build_status_metric,
    build_workspace_dashboard,
    complete_counts,
)


class FakeResult:
    def __init__(self, rows: list[tuple[str, int]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[str, int]]:
        return self.rows


class FakeSession:
    def __init__(self, results: list[FakeResult]) -> None:
        self.results = results
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_build_workspace_dashboard_returns_status_counts() -> None:
    workspace_id = uuid.uuid4()
    session = FakeSession(
        [
            FakeResult([(DocumentStatus.COMPLETED.value, 3), (DocumentStatus.FAILED.value, 1)]),
            FakeResult([(AnalysisTaskStatus.COMPLETED.value, 2)]),
            FakeResult(
                [
                    (AnalysisResultStatus.NEEDS_REVIEW.value, 4),
                    (AnalysisResultStatus.APPROVED.value, 2),
                ]
            ),
            FakeResult([(ReviewDecisionType.APPROVE.value, 2)]),
            FakeResult([(ReportStatus.DRAFT.value, 1), (ReportStatus.EXPORTED.value, 1)]),
            FakeResult([(ExportJobStatus.COMPLETED.value, 2)]),
        ]
    )

    dashboard = await build_workspace_dashboard(session, workspace_id)  # type: ignore[arg-type]

    assert dashboard.workspace_id == workspace_id
    assert dashboard.documents.total == 4
    assert dashboard.documents.by_status[DocumentStatus.COMPLETED.value] == 3
    assert dashboard.documents.by_status[DocumentStatus.UPLOADED.value] == 0
    assert dashboard.analysis_tasks.total == 2
    assert dashboard.reviews.total == 6
    assert dashboard.reviews.by_status[AnalysisResultStatus.NEEDS_REVIEW.value] == 4
    assert dashboard.reviews.by_decision[ReviewDecisionType.APPROVE.value] == 2
    assert dashboard.reports.total == 2
    assert dashboard.exports.total == 2
    assert len(session.statements) == 6


def test_build_status_metric_fills_missing_statuses() -> None:
    metric = build_status_metric({DocumentStatus.COMPLETED.value: 2}, DocumentStatus)

    assert metric.total == 2
    assert metric.by_status[DocumentStatus.COMPLETED.value] == 2
    assert metric.by_status[DocumentStatus.FAILED.value] == 0


def test_complete_counts_fills_missing_enum_values() -> None:
    counts = complete_counts({ReviewDecisionType.REJECT.value: 1}, ReviewDecisionType)

    assert counts[ReviewDecisionType.REJECT.value] == 1
    assert counts[ReviewDecisionType.APPROVE.value] == 0
