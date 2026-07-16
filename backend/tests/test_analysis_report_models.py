import uuid

from backend.app.models.analysis import AnalysisTask, AnalysisTaskStatus
from backend.app.models.report import Report, ReportSection, ReportSectionStatus, ReportStatus


def test_analysis_task_status_values() -> None:
    assert AnalysisTaskStatus.PENDING.value == "pending"
    assert AnalysisTaskStatus.RUNNING.value == "running"
    assert AnalysisTaskStatus.COMPLETED.value == "completed"
    assert AnalysisTaskStatus.FAILED.value == "failed"


def test_report_status_values() -> None:
    assert ReportStatus.DRAFT.value == "draft"
    assert ReportStatus.READY.value == "ready"
    assert ReportStatus.EXPORTED.value == "exported"
    assert ReportSectionStatus.DRAFT.value == "draft"
    assert ReportSectionStatus.APPROVED.value == "approved"


def test_analysis_task_accepts_template_metadata() -> None:
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    task = AnalysisTask(
        workspace_id=workspace_id,
        template_task_key="policy_requirements",
        name="Policy Requirement Extraction",
        description="Extract policy requirements.",
        task_type="extraction",
        status=AnalysisTaskStatus.PENDING.value,
        input_scope={"template_task_key": "policy_requirements"},
        output_schema={"type": "object"},
        created_by=owner_id,
    )

    assert task.workspace_id == workspace_id
    assert task.template_task_key == "policy_requirements"
    assert task.status == "pending"
    assert task.created_by == owner_id


def test_report_section_relationship() -> None:
    workspace_id = uuid.uuid4()
    report = Report(
        workspace_id=workspace_id,
        title="Policy Review Report",
        status=ReportStatus.DRAFT.value,
        created_by=uuid.uuid4(),
    )
    section = ReportSection(
        report=report,
        workspace_id=workspace_id,
        template_section_key="requirements",
        title="Policy Requirements",
        body_markdown="",
        source_task_keys=["policy_requirements"],
        source_result_ids=[],
        sort_order=10,
        status=ReportSectionStatus.DRAFT.value,
    )

    assert section.report is report
    assert section in report.sections
    assert section.source_task_keys == ["policy_requirements"]
    assert section.source_result_ids == []

