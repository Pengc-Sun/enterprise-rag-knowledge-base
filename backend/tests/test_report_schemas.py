import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.models.report import Report, ReportSection, ReportSectionStatus, ReportStatus
from backend.app.schemas.report import (
    ReportCreate,
    ReportRead,
    ReportSectionCreate,
    ReportSectionRead,
)


def test_report_create_accepts_title() -> None:
    report = ReportCreate(title="Policy Review Report")

    assert report.title == "Policy Review Report"


def test_report_create_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        ReportCreate(title="")


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


def test_report_section_create_accepts_content_fields() -> None:
    section = ReportSectionCreate(title="Executive Summary")

    assert section.body_markdown == ""
    assert section.source_task_keys == []
    assert section.source_result_ids == []
    assert section.sort_order == 0


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
