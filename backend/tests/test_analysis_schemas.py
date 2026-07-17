import pytest
from pydantic import ValidationError

from backend.app.models.analysis import AnalysisResultStatus, ReviewDecisionType
from backend.app.schemas.analysis import (
    AnalysisResultCreate,
    AnalysisTaskCreate,
    ReviewDecisionCreate,
)


def test_analysis_task_create_accepts_structured_payload() -> None:
    task = AnalysisTaskCreate(
        template_task_key="policy_requirements",
        name="Policy Requirement Extraction",
        description="Extract policy requirements.",
        task_type="extraction",
        input_scope={"knowledge_base_keys": ["policies"]},
        output_schema={"type": "object"},
    )

    assert task.template_task_key == "policy_requirements"
    assert task.input_scope == {"knowledge_base_keys": ["policies"]}


def test_analysis_result_create_accepts_structured_output() -> None:
    result = AnalysisResultCreate(
        status=AnalysisResultStatus.NEEDS_REVIEW,
        result={"requirements": [{"requirement": "Submit receipts"}]},
        citations=[{"document": "policy.md", "page": 1}],
        confidence=0.75,
        model="test-model",
        provider="local",
        token_usage={"total_tokens": 12},
    )

    assert result.status == AnalysisResultStatus.NEEDS_REVIEW
    assert result.citations[0]["document"] == "policy.md"


def test_analysis_result_create_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        AnalysisResultCreate(result={}, confidence=1.5)


def test_review_decision_create_accepts_edit_payload() -> None:
    decision = ReviewDecisionCreate(
        decision=ReviewDecisionType.EDIT,
        comment="Clarify the requirement.",
        edited_result={"requirements": [{"requirement": "Submit itemized receipts"}]},
    )

    assert decision.decision == ReviewDecisionType.EDIT
    assert decision.edited_result == {
        "requirements": [{"requirement": "Submit itemized receipts"}]
    }


def test_review_decision_create_rejects_unknown_decision() -> None:
    with pytest.raises(ValidationError):
        ReviewDecisionCreate.model_validate({"decision": "unknown"})
