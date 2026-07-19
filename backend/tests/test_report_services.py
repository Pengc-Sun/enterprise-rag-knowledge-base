import uuid
from base64 import b64decode
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.app.models.analysis import AnalysisResult, AnalysisResultStatus, AnalysisTask
from backend.app.models.report import (
    ExportFormat,
    ExportJob,
    ExportJobStatus,
    Report,
    ReportSection,
    ReportSectionStatus,
    ReportStatus,
)
from backend.app.schemas.report import (
    ReportCreate,
    ReportExportCreate,
    ReportPreviewRead,
    ReportSectionCreate,
    ReportSectionGenerateRequest,
    ReportSectionOrderItem,
    ReportSectionReorderRequest,
    ReportSectionUpdate,
    ReportUpdate,
)
from backend.app.services.reports import (
    ReportSectionGenerationError,
    ReportSectionOrderingError,
    ReportSectionSourceError,
    build_report_preview,
    create_report,
    create_report_export,
    create_report_section,
    generate_report_section_from_results,
    get_export_job_for_workspace,
    get_report_for_workspace,
    get_report_section_for_report,
    list_report_sections_for_report,
    list_reports_for_workspace,
    render_report_docx,
    render_report_pdf,
    render_report_preview_markdown,
    reorder_report_sections,
    update_report,
    update_report_section,
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
        if isinstance(instance, (Report, ReportSection, ExportJob)) and instance.id is None:
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
async def test_update_report_persists_partial_updates() -> None:
    workspace_id = uuid.uuid4()
    report = make_report(workspace_id)
    session = FakeSession()

    updated_report = await update_report(
        session,  # type: ignore[arg-type]
        report,
        ReportUpdate(title="Updated Policy Review Report"),
    )

    assert updated_report is report
    assert report.title == "Updated Policy Review Report"
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
async def test_build_report_preview_returns_ordered_markdown() -> None:
    workspace_id = uuid.uuid4()
    report = make_report(workspace_id)
    first_section = make_section(workspace_id, report.id)
    first_section.title = "Executive Summary"
    first_section.body_markdown = "Approved summary."
    second_section = make_section(workspace_id, report.id)
    second_section.title = "Findings"
    second_section.body_markdown = "Approved findings."
    session = FakeSession([FakeResult(items=[first_section, second_section])])

    preview = await build_report_preview(
        session,  # type: ignore[arg-type]
        workspace_id,
        report,
    )

    assert preview.report_id == report.id
    assert preview.workspace_id == workspace_id
    assert preview.title == "Policy Review Report"
    assert preview.status == ReportStatus.DRAFT
    assert preview.section_count == 2
    assert preview.markdown == (
        "# Policy Review Report\n\n"
        "## Executive Summary\n\n"
        "Approved summary.\n\n"
        "## Findings\n\n"
        "Approved findings.\n"
    )


@pytest.mark.asyncio
async def test_get_export_job_for_workspace_returns_export_job() -> None:
    workspace_id = uuid.uuid4()
    export_job = ExportJob(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        report_id=uuid.uuid4(),
        format=ExportFormat.MARKDOWN.value,
        status=ExportJobStatus.COMPLETED.value,
        file_path=None,
        error_message=None,
        created_by=uuid.uuid4(),
        export_metadata={"markdown": "# Report\n"},
    )
    session = FakeSession([FakeResult(scalar=export_job)])

    fetched = await get_export_job_for_workspace(
        session,  # type: ignore[arg-type]
        workspace_id,
        export_job.id,
    )

    assert fetched is export_job
    assert session.statements


@pytest.mark.asyncio
async def test_create_report_export_persists_completed_markdown_job(tmp_path: Path) -> None:
    workspace_id = uuid.uuid4()
    report = make_report(workspace_id)
    created_by = uuid.uuid4()
    section = make_section(workspace_id, report.id)
    section.title = "Executive Summary"
    section.body_markdown = "Approved summary."
    session = FakeSession([FakeResult(items=[section])])

    export_job = await create_report_export(
        session,  # type: ignore[arg-type]
        workspace_id,
        report,
        created_by,
        ReportExportCreate(format=ExportFormat.MARKDOWN),
        tmp_path.as_posix(),
    )

    assert export_job.workspace_id == workspace_id
    assert export_job.report_id == report.id
    assert export_job.format == ExportFormat.MARKDOWN.value
    assert export_job.status == ExportJobStatus.COMPLETED.value
    assert export_job.created_by == created_by
    assert export_job.file_path is not None
    assert Path(export_job.file_path).read_text(encoding="utf-8") == (
        "# Policy Review Report\n\n## Executive Summary\n\nApproved summary.\n"
    )
    assert export_job.error_message is None
    assert export_job.export_metadata["section_count"] == 1
    assert export_job.export_metadata["markdown"] == (
        "# Policy Review Report\n\n## Executive Summary\n\nApproved summary.\n"
    )
    assert report.status == ReportStatus.EXPORTED.value
    assert session.added is export_job
    assert session.committed is True


@pytest.mark.asyncio
async def test_create_report_export_persists_completed_docx_job(tmp_path: Path) -> None:
    workspace_id = uuid.uuid4()
    report = make_report(workspace_id)
    created_by = uuid.uuid4()
    section = make_section(workspace_id, report.id)
    section.title = "Executive Summary"
    section.body_markdown = "Approved summary."
    session = FakeSession([FakeResult(items=[section])])

    export_job = await create_report_export(
        session,  # type: ignore[arg-type]
        workspace_id,
        report,
        created_by,
        ReportExportCreate(format=ExportFormat.DOCX),
        tmp_path.as_posix(),
    )

    assert export_job.format == ExportFormat.DOCX.value
    assert export_job.status == ExportJobStatus.COMPLETED.value
    assert export_job.export_metadata["content_type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert export_job.export_metadata["filename"] == "policy-review-report.docx"
    docx_bytes = b64decode(str(export_job.export_metadata["docx_base64"]))
    assert docx_bytes.startswith(b"PK")
    assert export_job.file_path is not None
    assert Path(export_job.file_path).read_bytes() == docx_bytes
    assert report.status == ReportStatus.EXPORTED.value
    assert session.added is export_job
    assert session.committed is True


@pytest.mark.asyncio
async def test_create_report_export_persists_completed_pdf_job(tmp_path: Path) -> None:
    workspace_id = uuid.uuid4()
    report = make_report(workspace_id)
    created_by = uuid.uuid4()
    section = make_section(workspace_id, report.id)
    section.title = "Executive Summary"
    section.body_markdown = "Approved summary."
    session = FakeSession([FakeResult(items=[section])])

    export_job = await create_report_export(
        session,  # type: ignore[arg-type]
        workspace_id,
        report,
        created_by,
        ReportExportCreate(format=ExportFormat.PDF),
        tmp_path.as_posix(),
    )

    assert export_job.format == ExportFormat.PDF.value
    assert export_job.status == ExportJobStatus.COMPLETED.value
    assert export_job.export_metadata["content_type"] == "application/pdf"
    assert export_job.export_metadata["filename"] == "policy-review-report.pdf"
    pdf_bytes = b64decode(str(export_job.export_metadata["pdf_base64"]))
    assert pdf_bytes.startswith(b"%PDF")
    assert export_job.file_path is not None
    assert Path(export_job.file_path).read_bytes() == pdf_bytes
    assert report.status == ReportStatus.EXPORTED.value
    assert session.added is export_job
    assert session.committed is True


def test_render_report_docx_returns_docx_bytes() -> None:
    preview = ReportPreviewRead(
        report_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        title="Policy Review Report",
        status=ReportStatus.DRAFT,
        section_count=1,
        markdown="# Policy Review Report\n\n## Executive Summary\n\nApproved summary.\n",
    )

    docx_bytes = render_report_docx(preview)

    assert docx_bytes.startswith(b"PK")
    assert len(docx_bytes) > 1000


def test_render_report_pdf_returns_pdf_bytes() -> None:
    preview = ReportPreviewRead(
        report_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        title="Policy Review Report",
        status=ReportStatus.DRAFT,
        section_count=1,
        markdown="# Policy Review Report\n\n## Executive Summary\n\nApproved summary.\n",
    )

    pdf_bytes = render_report_pdf(preview)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_render_report_preview_markdown_handles_empty_sections() -> None:
    workspace_id = uuid.uuid4()
    report = make_report(workspace_id)

    markdown = render_report_preview_markdown(report, [])

    assert markdown == "# Policy Review Report\n\n_No report sections yet._\n"


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
async def test_create_report_section_accepts_approved_source_results() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    task = make_analysis_task(workspace_id)
    analysis_result = make_analysis_result(workspace_id, task.id)
    session = FakeSession([FakeResult(items=[(analysis_result, task)])])

    section = await create_report_section(
        session,  # type: ignore[arg-type]
        workspace_id,
        report_id,
        ReportSectionCreate(
            title="Executive Summary",
            body_markdown="Draft summary",
            source_result_ids=[str(analysis_result.id), str(analysis_result.id)],
        ),
    )

    assert section.source_result_ids == [str(analysis_result.id)]
    assert session.added is section
    assert session.committed is True


@pytest.mark.asyncio
async def test_create_report_section_rejects_invalid_source_result_id() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    session = FakeSession()

    with pytest.raises(ReportSectionSourceError):
        await create_report_section(
            session,  # type: ignore[arg-type]
            workspace_id,
            report_id,
            ReportSectionCreate(
                title="Executive Summary",
                source_result_ids=["not-a-uuid"],
            ),
        )

    assert session.added is None
    assert session.committed is False


@pytest.mark.asyncio
async def test_create_report_section_rejects_unapproved_source_results() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    session = FakeSession([FakeResult(items=[])])

    with pytest.raises(ReportSectionSourceError):
        await create_report_section(
            session,  # type: ignore[arg-type]
            workspace_id,
            report_id,
            ReportSectionCreate(
                title="Executive Summary",
                source_result_ids=[str(uuid.uuid4())],
            ),
        )

    assert session.added is None
    assert session.committed is False


@pytest.mark.asyncio
async def test_update_report_section_persists_content_updates() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    section = make_section(workspace_id, report_id)
    session = FakeSession()

    updated_section = await update_report_section(
        session,  # type: ignore[arg-type]
        workspace_id,
        section,
        ReportSectionUpdate(
            title="Updated Summary",
            body_markdown="Updated body",
            sort_order=30,
        ),
    )

    assert updated_section is section
    assert section.title == "Updated Summary"
    assert section.body_markdown == "Updated body"
    assert section.sort_order == 30
    assert session.committed is True
    assert session.refreshed is section


@pytest.mark.asyncio
async def test_update_report_section_validates_source_results() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    section = make_section(workspace_id, report_id)
    session = FakeSession([FakeResult(items=[])])

    with pytest.raises(ReportSectionSourceError):
        await update_report_section(
            session,  # type: ignore[arg-type]
            workspace_id,
            section,
            ReportSectionUpdate(source_result_ids=[str(uuid.uuid4())]),
        )

    assert session.committed is False


@pytest.mark.asyncio
async def test_reorder_report_sections_updates_sort_order() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    first_section = make_section(workspace_id, report_id)
    second_section = make_section(workspace_id, report_id)
    session = FakeSession([FakeResult(items=[first_section, second_section])])

    sections = await reorder_report_sections(
        session,  # type: ignore[arg-type]
        workspace_id,
        report_id,
        ReportSectionReorderRequest(
            sections=[
                ReportSectionOrderItem(section_id=first_section.id, sort_order=20),
                ReportSectionOrderItem(section_id=second_section.id, sort_order=10),
            ]
        ),
    )

    assert first_section.sort_order == 20
    assert second_section.sort_order == 10
    assert [section.id for section in sections] == [second_section.id, first_section.id]
    assert session.committed is True


@pytest.mark.asyncio
async def test_reorder_report_sections_rejects_duplicate_ids() -> None:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    section_id = uuid.uuid4()
    session = FakeSession()

    with pytest.raises(ReportSectionOrderingError):
        await reorder_report_sections(
            session,  # type: ignore[arg-type]
            workspace_id,
            report_id,
            ReportSectionReorderRequest(
                sections=[
                    ReportSectionOrderItem(section_id=section_id, sort_order=10),
                    ReportSectionOrderItem(section_id=section_id, sort_order=20),
                ]
            ),
        )

    assert session.committed is False


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
