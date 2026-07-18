import uuid
from datetime import UTC, datetime

import pytest

from backend.app.models.analysis import AnalysisResult, AnalysisResultStatus, AnalysisTask
from backend.app.models.report import Report, ReportSection, ReportSectionStatus, ReportStatus
from backend.app.schemas.report import (
    ReportCreate,
    ReportSectionCreate,
    ReportSectionGenerateRequest,
)
from backend.app.services.reports import (
    ReportSectionGenerationError,
    create_report,
    create_report_section,
    generate_report_section_from_results,
    get_report_for_workspace,
    get_report_section_for_report,
    list_report_sections_for_report,
    list_reports_for_workspace,
)


class FakeScalarResult:
    def __init__(self, items: list[object]) -> None:
        self.items = items

    def all(self) -> list[object]:
        return self.items


class FakeResult:
    def __init__(self, items: list[object] | None = None, scalar: object | None = None) -> None:
        self.items = items or []
        self.scalar = scalar

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.items)

    def scalar_one_or_none(self) -> object | None:
        return self.scalar

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
        if isinstance(instance, (Report, ReportSection)) and instance.id is None:
            instance.id = uuid.uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = instance


def make_report(workspace_id: uuid.UUID) -> Report:
    now = datetime.now(UTC)
    return Report(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        title="Policy Review Report",
        status=ReportStatus.DRAFT.value,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_section(workspace_id: uuid.UUID, report_id: uuid.UUID) -> ReportSection:
    now = datetime.now(UTC)
    return ReportSection(
        id=uuid.uuid4(),
        report_id=report_id,
        workspace_id=workspace_id,
        template_section_key="summary",
        title="Executive Summary",
        body_markdown="Draft summary",
        source_task_keys=[],
        source_result_ids=[],
        sort_order=10,
        status=ReportSectionStatus.DRAFT.value,
        created_at=now,
        updated_at=now,
    )


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
    status: str = AnalysisResultStatus.APPROVED.value,
) -> AnalysisResult:
    now = datetime.now(UTC)
    return AnalysisResult(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        analysis_task_id=task_id,
        status=status,
        result={"finding": "Daily meal allowance is GBP 40."},
        citations=[{"document_title": "Policy", "page": 3, "chunk_id": "chunk-1"}],
        confidence=0.92,
        model="test-model",
        provider="test-provider",
        token_usage={},
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_reports_for_workspace_returns_reports() -> None:
    workspace_id = uuid.uuid4()
    report = make_report(workspace_id)
    session = FakeSession([FakeResult(items=[report])])

    reports = await list_reports_for_workspace(session, workspace_id)  # type: ignore[arg-type]

    assert reports == [report]
    assert session.statements


@pytest.mark.asyncio
async def test_get_report_for_workspace_returns_report() -> None:
    workspace_id = uuid.uuid4()
    report = make_report(workspace_id)
    session = FakeSession([FakeResult(scalar=report)])

    fetched = await get_report_for_workspace(
        session,  # type: ignore[arg-type]
        workspace_id,
        report.id,
    )

    assert fetched is report
    assert session.statements


@pytest.mark.asyncio
async def test_create_report_persists_report() -> None:
    workspace_id = uuid.uuid4()
    created_by = uuid.uuid4()
    session = FakeSession()

    report = await create_report(
        session,  # type: ignore[arg-type]
        workspace_id,
        created_by,
        ReportCreate(title="Policy Review Report"),
    )

    assert report.workspace_id == workspace_id
    assert report.created_by == created_by
    assert report.title == "Policy Review Report"
    assert report.status == ReportStatus.DRAFT.value
    assert session.added is report
    assert session.committed is True
    assert session.refreshed is report


@pytest.mark.asyncio
async def test_list_report_sections_for_report_returns_sections() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    section = make_section(workspace_id, report_id)
    session = FakeSession([FakeResult(items=[section])])

    sections = await list_report_sections_for_report(
        session,  # type: ignore[arg-type]
        workspace_id,
        report_id,
    )

    assert sections == [section]
    assert session.statements


@pytest.mark.asyncio
async def test_get_report_section_for_report_returns_section() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    section = make_section(workspace_id, report_id)
    session = FakeSession([FakeResult(scalar=section)])

    fetched = await get_report_section_for_report(
        session,  # type: ignore[arg-type]
        workspace_id,
        report_id,
        section.id,
    )

    assert fetched is section
    assert session.statements


@pytest.mark.asyncio
async def test_create_report_section_persists_section() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    session = FakeSession()

    section = await create_report_section(
        session,  # type: ignore[arg-type]
        workspace_id,
        report_id,
        ReportSectionCreate(
            title="Executive Summary",
            body_markdown="Draft summary",
            source_task_keys=["policy_requirements"],
            source_result_ids=[str(uuid.uuid4())],
            sort_order=10,
        ),
    )

    assert section.workspace_id == workspace_id
    assert section.report_id == report_id
    assert section.title == "Executive Summary"
    assert section.source_task_keys == ["policy_requirements"]
    assert section.status == ReportSectionStatus.DRAFT.value
    assert session.added is section
    assert session.committed is True


@pytest.mark.asyncio
async def test_generate_report_section_from_approved_results_persists_draft() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    task = make_analysis_task(workspace_id)
    analysis_result = make_analysis_result(workspace_id, task.id)
    session = FakeSession([FakeResult(items=[(analysis_result, task)])])

    section = await generate_report_section_from_results(
        session,  # type: ignore[arg-type]
        workspace_id,
        report_id,
        ReportSectionGenerateRequest(
            analysis_result_ids=[analysis_result.id],
            template_section_key="findings",
            sort_order=20,
        ),
    )

    assert section.workspace_id == workspace_id
    assert section.report_id == report_id
    assert section.title == "Policy Requirements"
    assert "Daily meal allowance is GBP 40" in section.body_markdown
    assert "Policy (page 3, chunk chunk-1)" in section.body_markdown
    assert section.source_task_keys == ["policy_requirements"]
    assert section.source_result_ids == [str(analysis_result.id)]
    assert section.sort_order == 20
    assert section.status == ReportSectionStatus.DRAFT.value
    assert session.added is section
    assert session.committed is True


@pytest.mark.asyncio
async def test_generate_report_section_rejects_missing_or_unapproved_results() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    session = FakeSession([FakeResult(items=[])])

    with pytest.raises(ReportSectionGenerationError):
        await generate_report_section_from_results(
            session,  # type: ignore[arg-type]
            workspace_id,
            report_id,
            ReportSectionGenerateRequest(analysis_result_ids=[uuid.uuid4()]),
        )

    assert session.added is None
    assert session.committed is False
