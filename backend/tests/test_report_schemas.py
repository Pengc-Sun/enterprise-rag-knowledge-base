import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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
    ReportExportRead,
    ReportPreviewRead,
    ReportRead,
    ReportSectionCreate,
    ReportSectionGenerateRequest,
    ReportSectionOrderItem,
    ReportSectionRead,
    ReportSectionReorderRequest,
    ReportSectionUpdate,
    ReportUpdate,
)


def test_report_create_accepts_title() -> None:
    report = ReportCreate(title="Policy Review Report")

    assert report.title == "Policy Review Report"


def test_report_create_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        ReportCreate(title="")


def test_report_update_accepts_partial_title_update() -> None:
    update = ReportUpdate(title="Updated Report")

    assert update.title == "Updated Report"


def test_report_read_serializes_model_status() -> None:
    now = datetime.now(UTC)
    report = Report(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        title="Policy Review Report",
        status=ReportStatus.READY.value,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )

    payload = ReportRead.model_validate(report)

    assert payload.id == report.id
    assert payload.status == ReportStatus.READY


def test_report_preview_read_accepts_markdown_payload() -> None:
    report_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    payload = ReportPreviewRead(
        report_id=report_id,
        workspace_id=workspace_id,
        title="Policy Review Report",
        status=ReportStatus.DRAFT,
        section_count=1,
        markdown="# Policy Review Report\n",
    )

    assert payload.report_id == report_id
    assert payload.workspace_id == workspace_id
    assert payload.status == ReportStatus.DRAFT
    assert payload.markdown == "# Policy Review Report\n"


def test_report_export_create_defaults_to_markdown() -> None:
    payload = ReportExportCreate()

    assert payload.format == ExportFormat.MARKDOWN


def test_report_export_read_serializes_model() -> None:
    now = datetime.now(UTC)
    export_job = ExportJob(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        format=ExportFormat.MARKDOWN.value,
        status=ExportJobStatus.COMPLETED.value,
        file_path=None,
        error_message=None,
        created_by=uuid.uuid4(),
        export_metadata={"markdown": "# Policy Review Report\n"},
        created_at=now,
        updated_at=now,
    )

    payload = ReportExportRead.model_validate(export_job)

    assert payload.id == export_job.id
    assert payload.format == ExportFormat.MARKDOWN
    assert payload.status == ExportJobStatus.COMPLETED
    assert payload.export_metadata["markdown"] == "# Policy Review Report\n"


def test_report_section_create_accepts_content_fields() -> None:
    section = ReportSectionCreate(title="Executive Summary")

    assert section.body_markdown == ""
    assert section.source_task_keys == []
    assert section.source_result_ids == []
    assert section.sort_order == 0


def test_report_section_generate_request_requires_analysis_results() -> None:
    with pytest.raises(ValidationError):
        ReportSectionGenerateRequest(analysis_result_ids=[])


def test_report_section_generate_request_accepts_generation_options() -> None:
    analysis_result_id = uuid.uuid4()

    payload = ReportSectionGenerateRequest(
        analysis_result_ids=[analysis_result_id],
        template_section_key="findings",
        title="Findings",
        sort_order=20,
    )

    assert payload.analysis_result_ids == [analysis_result_id]
    assert payload.template_section_key == "findings"
    assert payload.title == "Findings"
    assert payload.sort_order == 20


def test_report_section_update_accepts_partial_content_update() -> None:
    update = ReportSectionUpdate(body_markdown="Updated content", sort_order=30)

    assert update.body_markdown == "Updated content"
    assert update.sort_order == 30


def test_report_section_reorder_request_requires_sections() -> None:
    with pytest.raises(ValidationError):
        ReportSectionReorderRequest(sections=[])


def test_report_section_reorder_request_accepts_order_items() -> None:
    section_id = uuid.uuid4()

    payload = ReportSectionReorderRequest(
        sections=[ReportSectionOrderItem(section_id=section_id, sort_order=10)]
    )

    assert payload.sections[0].section_id == section_id
    assert payload.sections[0].sort_order == 10


def test_report_section_read_serializes_model() -> None:
    now = datetime.now(UTC)
    section = ReportSection(
        id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        template_section_key="summary",
        title="Executive Summary",
        body_markdown="Draft summary",
        source_task_keys=["policy_requirements"],
        source_result_ids=[str(uuid.uuid4())],
        sort_order=10,
        status=ReportSectionStatus.APPROVED.value,
        created_at=now,
        updated_at=now,
    )

    payload = ReportSectionRead.model_validate(section)

    assert payload.template_section_key == "summary"
    assert payload.status == ReportSectionStatus.APPROVED
    assert payload.source_task_keys == ["policy_requirements"]
