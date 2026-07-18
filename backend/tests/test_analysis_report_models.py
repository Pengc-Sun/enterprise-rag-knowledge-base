import uuid

from backend.app.models.analysis import (
    AnalysisResult,
    AnalysisResultStatus,
    AnalysisTask,
    AnalysisTaskStatus,
    ReviewDecision,
    ReviewDecisionType,
)
from backend.app.models.report import (
    ExportFormat,
    ExportJob,
    ExportJobStatus,
    Report,
    ReportSection,
    ReportSectionStatus,
    ReportStatus,
)


def test_analysis_task_status_values() -> None:
    assert AnalysisTaskStatus.PENDING.value == "pending"
    assert AnalysisTaskStatus.RUNNING.value == "running"
    assert AnalysisTaskStatus.COMPLETED.value == "completed"
    assert AnalysisTaskStatus.FAILED.value == "failed"


def test_analysis_result_status_values() -> None:
    assert AnalysisResultStatus.AI_GENERATED.value == "ai_generated"
    assert AnalysisResultStatus.NEEDS_REVIEW.value == "needs_review"
    assert AnalysisResultStatus.APPROVED.value == "approved"
    assert AnalysisResultStatus.EDITED.value == "edited"
    assert AnalysisResultStatus.REJECTED.value == "rejected"
    assert ReviewDecisionType.APPROVE.value == "approve"
    assert ReviewDecisionType.EDIT.value == "edit"
    assert ReviewDecisionType.REJECT.value == "reject"
    assert ReviewDecisionType.REQUEST_CHANGES.value == "request_changes"


def test_report_status_values() -> None:
    assert ReportStatus.DRAFT.value == "draft"
    assert ReportStatus.READY.value == "ready"
    assert ReportStatus.EXPORTED.value == "exported"
    assert ReportSectionStatus.DRAFT.value == "draft"
    assert ReportSectionStatus.APPROVED.value == "approved"
    assert ExportFormat.MARKDOWN.value == "markdown"
    assert ExportFormat.DOCX.value == "docx"
    assert ExportFormat.PDF.value == "pdf"
    assert ExportJobStatus.PENDING.value == "pending"
    assert ExportJobStatus.RUNNING.value == "running"
    assert ExportJobStatus.COMPLETED.value == "completed"
    assert ExportJobStatus.FAILED.value == "failed"


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


def test_analysis_result_relationship() -> None:
    workspace_id = uuid.uuid4()
    task = AnalysisTask(
        workspace_id=workspace_id,
        template_task_key="policy_requirements",
        name="Policy Requirement Extraction",
        task_type="extraction",
        status=AnalysisTaskStatus.PENDING.value,
        input_scope={},
        output_schema={"type": "object"},
        created_by=uuid.uuid4(),
    )
    result = AnalysisResult(
        workspace_id=workspace_id,
        analysis_task=task,
        status=AnalysisResultStatus.AI_GENERATED.value,
        result={"requirements": []},
        citations=[{"document": "policy.md", "page": 1}],
        confidence=0.82,
        model="test-model",
        provider="local",
        token_usage={"total_tokens": 42},
    )

    assert result.analysis_task is task
    assert result in task.results
    assert result.status == "ai_generated"
    assert result.citations == [{"document": "policy.md", "page": 1}]


def test_review_decision_relationship() -> None:
    workspace_id = uuid.uuid4()
    task = AnalysisTask(
        workspace_id=workspace_id,
        template_task_key="policy_requirements",
        name="Policy Requirement Extraction",
        task_type="extraction",
        status=AnalysisTaskStatus.PENDING.value,
        input_scope={},
        output_schema={"type": "object"},
        created_by=uuid.uuid4(),
    )
    result = AnalysisResult(
        workspace_id=workspace_id,
        analysis_task=task,
        status=AnalysisResultStatus.NEEDS_REVIEW.value,
        result={"requirements": []},
        citations=[],
        token_usage={},
    )
    decision = ReviewDecision(
        workspace_id=workspace_id,
        analysis_result=result,
        reviewer_id=uuid.uuid4(),
        decision=ReviewDecisionType.APPROVE.value,
        comment="Looks correct.",
        original_result=result.result,
        edited_result=None,
    )

    assert decision.analysis_result is result
    assert decision in result.review_decisions
    assert decision.original_result == {"requirements": []}


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


def test_export_job_relationship() -> None:
    workspace_id = uuid.uuid4()
    report = Report(
        workspace_id=workspace_id,
        title="Policy Review Report",
        status=ReportStatus.EXPORTED.value,
        created_by=uuid.uuid4(),
    )
    export_job = ExportJob(
        workspace_id=workspace_id,
        report=report,
        format=ExportFormat.MARKDOWN.value,
        status=ExportJobStatus.COMPLETED.value,
        file_path=None,
        error_message=None,
        created_by=uuid.uuid4(),
        export_metadata={"markdown": "# Policy Review Report\n"},
    )

    assert export_job.report is report
    assert export_job.format == "markdown"
    assert export_job.status == "completed"
    assert export_job.export_metadata["markdown"] == "# Policy Review Report\n"
