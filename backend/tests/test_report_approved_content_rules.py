import uuid
from datetime import UTC, datetime

import pytest

from backend.app.models.analysis import AnalysisResult, AnalysisResultStatus, AnalysisTask
from backend.app.models.report import ReportSection, ReportSectionStatus
from backend.app.schemas.report import (
    ReportSectionCreate,
    ReportSectionGenerateRequest,
    ReportSectionUpdate,
)
from backend.app.services.reports import (
    ReportSectionGenerationError,
    ReportSectionSourceError,
    create_report_section,
    generate_report_section_from_results,
    update_report_section,
    validate_report_section_source_results,
)


class FakeResult:
    def __init__(self, items: list[object] | None = None) -> None:
        self.items = items or []

    def all(self) -> list[object]:
        return self.items


class FakeSession:
    def __init__(self, results: list[FakeResult] | None = None) -> None:
        self.results = results or []
        self.statements: list[object] = []
        self.added: object | None = None
        self.committed = False
        self.refreshed: object | None = None

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return self.results.pop(0)

    def add(self, instance: object) -> None:
        self.added = instance
        if isinstance(instance, ReportSection) and instance.id is None:
            instance.id = uuid.uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = instance


def make_analysis_task(workspace_id: uuid.UUID) -> AnalysisTask:
    now = datetime.now(UTC)
    return AnalysisTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        template_task_key="policy_requirements",
        name="Policy Requirements",
        task_type="extraction",
        status="completed",
        input_scope={},
        output_schema={},
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_analysis_result(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    status: str,
) -> AnalysisResult:
    now = datetime.now(UTC)
    return AnalysisResult(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        analysis_task_id=task_id,
        status=status,
        result={"finding": "Approved policy finding."},
        citations=[{"document_title": "Policy", "page": 1}],
        confidence=0.91,
        model="test-model",
        provider="test-provider",
        token_usage={},
        created_at=now,
        updated_at=now,
    )


def make_section(
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    source_result_ids: list[str] | None = None,
) -> ReportSection:
    now = datetime.now(UTC)
    return ReportSection(
        id=uuid.uuid4(),
        report_id=report_id,
        workspace_id=workspace_id,
        template_section_key="requirements",
        title="Policy Requirements",
        body_markdown="Draft body",
        source_task_keys=["policy_requirements"],
        source_result_ids=source_result_ids or [],
        sort_order=10,
        status=ReportSectionStatus.DRAFT.value,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.parametrize(
    "status",
    [AnalysisResultStatus.APPROVED.value, AnalysisResultStatus.EDITED.value],
)
@pytest.mark.asyncio
async def test_report_sections_can_reference_approved_or_edited_results(status: str) -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    task = make_analysis_task(workspace_id)
    analysis_result = make_analysis_result(workspace_id, task.id, status)
    session = FakeSession([FakeResult(items=[(analysis_result, task)])])

    section = await create_report_section(
        session,  # type: ignore[arg-type]
        workspace_id,
        report_id,
        ReportSectionCreate(
            title="Policy Requirements",
            source_result_ids=[str(analysis_result.id)],
        ),
    )

    assert section.source_result_ids == [str(analysis_result.id)]
    assert session.added is section
    assert session.committed is True


@pytest.mark.parametrize(
    "status",
    [
        AnalysisResultStatus.AI_GENERATED.value,
        AnalysisResultStatus.NEEDS_REVIEW.value,
        AnalysisResultStatus.REJECTED.value,
    ],
)
@pytest.mark.asyncio
async def test_report_sections_reject_unapproved_source_result_statuses(status: str) -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    task = make_analysis_task(workspace_id)
    analysis_result = make_analysis_result(workspace_id, task.id, status)
    session = FakeSession([FakeResult(items=[])])

    with pytest.raises(ReportSectionSourceError):
        await create_report_section(
            session,  # type: ignore[arg-type]
            workspace_id,
            report_id,
            ReportSectionCreate(
                title="Policy Requirements",
                source_result_ids=[str(analysis_result.id)],
            ),
        )

    assert session.added is None
    assert session.committed is False


@pytest.mark.asyncio
async def test_generated_report_section_rejects_mixed_approved_and_unapproved_results() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    task = make_analysis_task(workspace_id)
    approved_result = make_analysis_result(
        workspace_id,
        task.id,
        AnalysisResultStatus.APPROVED.value,
    )
    unapproved_result = make_analysis_result(
        workspace_id,
        task.id,
        AnalysisResultStatus.NEEDS_REVIEW.value,
    )
    session = FakeSession([FakeResult(items=[(approved_result, task)])])

    with pytest.raises(ReportSectionGenerationError):
        await generate_report_section_from_results(
            session,  # type: ignore[arg-type]
            workspace_id,
            report_id,
            ReportSectionGenerateRequest(
                analysis_result_ids=[approved_result.id, unapproved_result.id]
            ),
        )

    assert session.added is None
    assert session.committed is False


@pytest.mark.asyncio
async def test_cross_workspace_source_results_are_rejected() -> None:
    workspace_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()
    task = make_analysis_task(other_workspace_id)
    other_workspace_result = make_analysis_result(
        other_workspace_id,
        task.id,
        AnalysisResultStatus.APPROVED.value,
    )
    session = FakeSession([FakeResult(items=[])])

    with pytest.raises(ReportSectionSourceError):
        await validate_report_section_source_results(
            session,  # type: ignore[arg-type]
            workspace_id,
            [str(other_workspace_result.id)],
        )


@pytest.mark.asyncio
async def test_update_report_section_can_clear_sources_without_rechecking_old_sources() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    old_source_id = str(uuid.uuid4())
    section = make_section(workspace_id, report_id, [old_source_id])
    session = FakeSession()

    updated_section = await update_report_section(
        session,  # type: ignore[arg-type]
        workspace_id,
        section,
        ReportSectionUpdate(source_result_ids=[]),
    )

    assert updated_section.source_result_ids == []
    assert session.statements == []
    assert session.committed is True


@pytest.mark.asyncio
async def test_update_report_section_preserves_sources_when_field_is_omitted() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    source_id = str(uuid.uuid4())
    section = make_section(workspace_id, report_id, [source_id])
    session = FakeSession()

    updated_section = await update_report_section(
        session,  # type: ignore[arg-type]
        workspace_id,
        section,
        ReportSectionUpdate(body_markdown="Updated body"),
    )

    assert updated_section.source_result_ids == [source_id]
    assert session.statements == []
    assert session.committed is True
