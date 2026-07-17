import json
import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from backend.app.models.analysis import (
    AnalysisResult,
    AnalysisResultStatus,
    AnalysisTask,
    AnalysisTaskStatus,
    ReviewDecision,
    ReviewDecisionType,
)
from backend.app.models.document import Document, DocumentChunk
from backend.app.schemas.analysis import (
    AnalysisResultCreate,
    AnalysisTaskCreate,
    ReviewDecisionCreate,
)
from backend.app.services.analysis_tasks import (
    AnalysisCitationValidationError,
    AnalysisOutputValidationError,
    build_analysis_context_statement,
    build_deterministic_structured_analysis_result,
    build_structured_analysis_messages,
    create_analysis_result_for_task,
    create_review_decision_for_result,
    create_workspace_analysis_task,
    execute_analysis_task,
    get_analysis_result_for_task,
    get_review_decision_for_result,
    get_workspace_analysis_task,
    list_analysis_results_for_task,
    list_review_decisions_for_result,
    list_workspace_analysis_tasks,
    normalize_structured_analysis_output,
    parse_structured_analysis_response,
    validate_structured_analysis_result,
)
from backend.app.services.llms import (
    DeterministicLLMProvider,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMProviderName,
    LLMProviderResponseError,
    LLMResponse,
    LLMUsage,
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
        if (
            isinstance(instance, (AnalysisTask, AnalysisResult, ReviewDecision))
            and instance.id is None
        ):
            instance.id = uuid.uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = instance


class FakeStructuredLLMProvider(LLMProvider):
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[LLMMessage] = []
        self.temperature: float | None = None
        self.max_tokens: int | None = None

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        return LLMResponse(
            content=self.content,
            model="structured-test-model",
            provider=LLMProviderName.OPENAI,
            usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


class FakeFailingLLMProvider(LLMProvider):
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        raise LLMProviderError("provider unavailable")


def make_task(workspace_id: uuid.UUID | None = None) -> AnalysisTask:
    now = datetime.now(UTC)
    return AnalysisTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
        template_task_key="policy_requirements",
        name="Policy Requirement Extraction",
        task_type="extraction",
        status="pending",
        input_scope={},
        output_schema={"type": "object"},
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_result(workspace_id: uuid.UUID, task_id: uuid.UUID) -> AnalysisResult:
    now = datetime.now(UTC)
    return AnalysisResult(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        analysis_task_id=task_id,
        status=AnalysisResultStatus.AI_GENERATED.value,
        result={"requirements": []},
        citations=[],
        token_usage={},
        created_at=now,
        updated_at=now,
    )


def make_review_decision(
    workspace_id: uuid.UUID,
    analysis_result_id: uuid.UUID,
) -> ReviewDecision:
    now = datetime.now(UTC)
    return ReviewDecision(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        analysis_result_id=analysis_result_id,
        reviewer_id=uuid.uuid4(),
        decision=ReviewDecisionType.APPROVE.value,
        comment="Looks correct.",
        original_result={"requirements": []},
        edited_result=None,
        created_at=now,
    )


def make_document(workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        filename="policy.md",
        file_type="markdown",
        file_size=128,
        file_hash="hash",
        storage_path="/tmp/policy.md",
        status="completed",
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_chunk(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document: Document | None = None,
) -> DocumentChunk:
    now = datetime.now(UTC)
    effective_document = document or make_document(workspace_id, knowledge_base_id)
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=effective_document.id,
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        content="Hotel reimbursement requires an itemized receipt.",
        chunk_index=0,
        page_number=1,
        section_title="Hotel Reimbursement",
        token_count=8,
        chunk_metadata={},
        created_at=now,
        updated_at=now,
        document=effective_document,
    )


@pytest.mark.asyncio
async def test_list_workspace_analysis_tasks_returns_tasks() -> None:
    workspace_id = uuid.uuid4()
    task = make_task(workspace_id)
    session = FakeSession([FakeResult(items=[task])])

    tasks = await list_workspace_analysis_tasks(session, workspace_id)  # type: ignore[arg-type]

    assert tasks == [task]
    assert session.statements


@pytest.mark.asyncio
async def test_create_workspace_analysis_task_sets_pending_status() -> None:
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    session = FakeSession()

    task = await create_workspace_analysis_task(
        session,  # type: ignore[arg-type]
        workspace_id,
        owner_id,
        AnalysisTaskCreate(
            template_task_key="policy_requirements",
            name="Policy Requirement Extraction",
            task_type="extraction",
            output_schema={"type": "object"},
        ),
    )

    assert task.workspace_id == workspace_id
    assert task.created_by == owner_id
    assert task.status == "pending"
    assert session.added is task
    assert session.committed is True
    assert session.refreshed is task


@pytest.mark.asyncio
async def test_get_workspace_analysis_task_returns_task() -> None:
    workspace_id = uuid.uuid4()
    task = make_task(workspace_id)
    session = FakeSession([FakeResult(scalar=task)])

    result = await get_workspace_analysis_task(
        session,  # type: ignore[arg-type]
        workspace_id,
        task.id,
    )

    assert result is task
    assert session.statements


@pytest.mark.asyncio
async def test_create_analysis_result_for_task_persists_structured_result() -> None:
    workspace_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = FakeSession()

    result = await create_analysis_result_for_task(
        session,  # type: ignore[arg-type]
        workspace_id,
        task_id,
        AnalysisResultCreate(
            result={"requirements": [{"requirement": "Submit receipts"}]},
            citations=[{"document": "policy.md", "page": 1}],
            confidence=0.8,
            model="test-model",
            provider="local",
            token_usage={"total_tokens": 12},
        ),
    )

    assert result.workspace_id == workspace_id
    assert result.analysis_task_id == task_id
    assert result.status == "ai_generated"
    assert result.citations == [{"document": "policy.md", "page": 1}]
    assert session.added is result
    assert session.committed is True


@pytest.mark.asyncio
async def test_list_analysis_results_for_task_returns_results() -> None:
    workspace_id = uuid.uuid4()
    task_id = uuid.uuid4()
    result = make_result(workspace_id, task_id)
    session = FakeSession([FakeResult(items=[result])])

    results = await list_analysis_results_for_task(
        session,  # type: ignore[arg-type]
        workspace_id,
        task_id,
    )

    assert results == [result]
    assert session.statements


@pytest.mark.asyncio
async def test_get_analysis_result_for_task_returns_result() -> None:
    workspace_id = uuid.uuid4()
    task_id = uuid.uuid4()
    result = make_result(workspace_id, task_id)
    session = FakeSession([FakeResult(scalar=result)])

    fetched = await get_analysis_result_for_task(
        session,  # type: ignore[arg-type]
        workspace_id,
        task_id,
        result.id,
    )

    assert fetched is result
    assert session.statements


@pytest.mark.asyncio
async def test_create_review_decision_for_result_snapshots_original_result() -> None:
    workspace_id = uuid.uuid4()
    task_id = uuid.uuid4()
    reviewer_id = uuid.uuid4()
    result = make_result(workspace_id, task_id)
    result.result = {"requirements": [{"requirement": "Submit receipts"}]}
    session = FakeSession()

    decision = await create_review_decision_for_result(
        session,  # type: ignore[arg-type]
        workspace_id,
        result,
        reviewer_id,
        ReviewDecisionCreate(
            decision=ReviewDecisionType.APPROVE,
            comment="Evidence is sufficient.",
        ),
    )

    assert decision.workspace_id == workspace_id
    assert decision.analysis_result_id == result.id
    assert decision.reviewer_id == reviewer_id
    assert decision.decision == ReviewDecisionType.APPROVE.value
    assert decision.comment == "Evidence is sufficient."
    assert decision.original_result == result.result
    assert decision.edited_result is None
    assert session.added is decision
    assert session.committed is True


@pytest.mark.asyncio
async def test_list_review_decisions_for_result_returns_decisions() -> None:
    workspace_id = uuid.uuid4()
    analysis_result_id = uuid.uuid4()
    decision = make_review_decision(workspace_id, analysis_result_id)
    session = FakeSession([FakeResult(items=[decision])])

    decisions = await list_review_decisions_for_result(
        session,  # type: ignore[arg-type]
        workspace_id,
        analysis_result_id,
    )

    assert decisions == [decision]
    assert session.statements


@pytest.mark.asyncio
async def test_get_review_decision_for_result_returns_decision() -> None:
    workspace_id = uuid.uuid4()
    analysis_result_id = uuid.uuid4()
    decision = make_review_decision(workspace_id, analysis_result_id)
    session = FakeSession([FakeResult(scalar=decision)])

    fetched = await get_review_decision_for_result(
        session,  # type: ignore[arg-type]
        workspace_id,
        analysis_result_id,
        decision.id,
    )

    assert fetched is decision
    assert session.statements


def test_build_analysis_context_statement_filters_by_workspace_and_scope() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    document_id = uuid.uuid4()
    task = make_task(workspace_id)
    task.input_scope = {
        "knowledge_base_ids": [str(knowledge_base_id)],
        "document_ids": [str(document_id)],
        "limit": 3,
    }

    statement = build_analysis_context_statement(task)
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))

    assert workspace_id.hex in sql
    assert knowledge_base_id.hex in sql
    assert document_id.hex in sql
    assert "document_chunks.workspace_id" in sql
    assert "document_chunks.knowledge_base_id" in sql
    assert "document_chunks.document_id" in sql
    assert "LIMIT 3" in sql


def test_build_structured_analysis_messages_requires_json_and_includes_context() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    task = make_task(workspace_id)
    task.output_schema = {"type": "object", "required": ["summary", "findings"]}
    chunk = make_chunk(workspace_id, knowledge_base_id)

    messages = build_structured_analysis_messages(task, [chunk])

    assert [message.role for message in messages] == ["system", "user"]
    assert "Return only valid JSON" in messages[0].content
    assert "Markdown fences" in messages[0].content
    assert str(chunk.id) in messages[1].content
    assert "Expected output schema" in messages[1].content
    assert '"required": ["summary", "findings"]' in messages[1].content


def test_parse_structured_analysis_response_returns_json_object() -> None:
    payload = {"summary": "ok", "findings": [], "citations": [], "confidence": 0.7}

    parsed = parse_structured_analysis_response(json.dumps(payload))

    assert parsed == payload


@pytest.mark.parametrize("content", ["not-json", "[1, 2, 3]"])
def test_parse_structured_analysis_response_rejects_malformed_output(content: str) -> None:
    with pytest.raises(LLMProviderResponseError):
        parse_structured_analysis_response(content)


def test_validate_structured_analysis_result_accepts_matching_schema() -> None:
    result: dict[str, object] = {
        "requirements": [
            {
                "requirement": "Submit receipts",
                "evidence_required": "Itemized receipt",
                "priority": "high",
            }
        ],
        "citations": ["chunk-1"],
    }
    schema: dict[str, object] = {
        "type": "object",
        "required": ["requirements", "citations"],
        "properties": {
            "requirements": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["requirement", "evidence_required"],
                    "properties": {
                        "requirement": {"type": "string", "minLength": 1},
                        "evidence_required": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                },
            },
            "citations": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }

    validate_structured_analysis_result(result, schema)


def test_validate_structured_analysis_result_rejects_schema_mismatch() -> None:
    result: dict[str, object] = {
        "requirements": [{"requirement": "Submit receipts"}],
        "citations": [{"chunk_id": "chunk-1"}],
    }
    schema: dict[str, object] = {
        "type": "object",
        "required": ["requirements", "citations"],
        "properties": {
            "requirements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["requirement", "evidence_required"],
                    "properties": {
                        "requirement": {"type": "string"},
                        "evidence_required": {"type": "string"},
                    },
                },
            },
            "citations": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }

    with pytest.raises(AnalysisOutputValidationError):
        validate_structured_analysis_result(result, schema)


@pytest.mark.asyncio
async def test_execute_analysis_task_retrieves_workspace_chunks_and_creates_result() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    task = make_task(workspace_id)
    task.input_scope = {"knowledge_base_ids": [str(knowledge_base_id)], "limit": 2}
    chunk = make_chunk(workspace_id, knowledge_base_id)
    session = FakeSession([FakeResult(items=[chunk])])

    result = await execute_analysis_task(session, task)  # type: ignore[arg-type]

    assert task.status == AnalysisTaskStatus.COMPLETED.value
    assert result.workspace_id == workspace_id
    assert result.analysis_task_id == task.id
    assert result.status == AnalysisResultStatus.NEEDS_REVIEW.value
    assert result.provider == "local"
    assert result.model == "workspace-scoped-retrieval"
    assert result.result["chunk_count"] == 1
    result_findings = cast(list[dict[str, object]], result.result["findings"])
    result_finding_citations = cast(list[dict[str, object]], result_findings[0]["citations"])
    assert result_finding_citations[0]["chunk_id"] == str(chunk.id)
    assert result.citations[0]["chunk_id"] == str(chunk.id)
    assert result.citations[0]["document_name"] == "policy.md"
    assert result.citations[0]["quote"] == chunk.content
    assert session.added is result
    assert session.committed is True
    assert session.refreshed is result


def test_normalize_structured_analysis_output_requires_each_finding_citation() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    chunk = make_chunk(workspace_id, knowledge_base_id)
    structured_result: dict[str, object] = {
        "findings": [{"claim": "Hotel receipt required."}],
        "citations": [{"chunk_id": str(chunk.id)}],
    }

    with pytest.raises(AnalysisCitationValidationError):
        normalize_structured_analysis_output(structured_result, [chunk])


def test_normalize_structured_analysis_output_persists_normalized_citations() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    chunk = make_chunk(workspace_id, knowledge_base_id)
    structured_result: dict[str, object] = {
        "findings": [
            {
                "claim": "Hotel receipt required.",
                "citations": [{"chunk_id": str(chunk.id), "quote": "receipt required"}],
            }
        ],
        "citations": [str(chunk.id)],
    }

    normalized_result, normalized_citations = normalize_structured_analysis_output(
        structured_result,
        [chunk],
    )

    findings = cast(list[dict[str, object]], normalized_result["findings"])
    finding_citations = cast(list[dict[str, object]], findings[0]["citations"])
    finding_citation = finding_citations[0]
    assert finding_citation["chunk_id"] == str(chunk.id)
    assert finding_citation["document_id"] == str(chunk.document_id)
    assert finding_citation["document_name"] == "policy.md"
    assert finding_citation["knowledge_base_id"] == str(chunk.knowledge_base_id)
    assert finding_citation["page_number"] == 1
    assert finding_citation["section_title"] == "Hotel Reimbursement"
    assert finding_citation["quote"] == "receipt required"
    assert normalized_result["citations"] == normalized_citations
    assert normalized_citations[0]["chunk_id"] == str(chunk.id)


def test_build_deterministic_structured_analysis_result_matches_task_schema() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    task = make_task(workspace_id)
    task.template_task_key = "policy_requirements"
    task.output_schema = {
        "type": "object",
        "required": ["requirements", "citations"],
        "properties": {
            "requirements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["requirement", "evidence_required"],
                    "properties": {
                        "requirement": {"type": "string"},
                        "evidence_required": {"type": "string"},
                    },
                },
            },
            "citations": {"type": "array", "items": {"type": "string"}},
        },
    }
    chunk = make_chunk(workspace_id, knowledge_base_id)

    structured_result = build_deterministic_structured_analysis_result(task, [chunk])

    validate_structured_analysis_result(structured_result, task.output_schema)
    requirements = cast(list[dict[str, object]], structured_result["requirements"])
    requirement = requirements[0]
    assert "Deterministic requirement" in cast(str, requirement["requirement"])
    assert "Deterministic evidence_required" in cast(str, requirement["evidence_required"])
    assert requirement["citations"] == [str(chunk.id)]
    assert structured_result["citations"] == [str(chunk.id)]


@pytest.mark.asyncio
async def test_execute_analysis_task_uses_deterministic_structured_provider() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    task = make_task(workspace_id)
    task.output_schema = {
        "type": "object",
        "required": ["requirements", "citations"],
        "properties": {
            "requirements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["requirement", "evidence_required"],
                    "properties": {
                        "requirement": {"type": "string"},
                        "evidence_required": {"type": "string"},
                    },
                },
            },
            "citations": {"type": "array", "items": {"type": "string"}},
        },
    }
    chunk = make_chunk(workspace_id, knowledge_base_id)
    session = FakeSession([FakeResult(items=[chunk])])

    result = await execute_analysis_task(
        session,  # type: ignore[arg-type]
        task,
        llm_provider=DeterministicLLMProvider(model="deterministic-analysis"),
    )

    assert task.status == AnalysisTaskStatus.COMPLETED.value
    assert result.status == AnalysisResultStatus.NEEDS_REVIEW.value
    assert result.provider == "deterministic"
    assert result.model == "deterministic-analysis"
    requirements = cast(list[dict[str, object]], result.result["requirements"])
    requirement_citations = cast(list[dict[str, object]], requirements[0]["citations"])
    assert requirement_citations[0]["chunk_id"] == str(chunk.id)
    assert result.citations[0]["chunk_id"] == str(chunk.id)
    assert result.citations[0]["document_name"] == "policy.md"
    assert session.added is result


@pytest.mark.asyncio
async def test_execute_analysis_task_persists_structured_llm_json_result() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    task = make_task(workspace_id)
    chunk = make_chunk(workspace_id, knowledge_base_id)
    response_payload = {
        "summary": "Hotel receipts are required.",
        "findings": [{"title": "Receipt required", "citations": [{"chunk_id": str(chunk.id)}]}],
        "citations": [{"chunk_id": str(chunk.id), "page_number": 1}],
        "confidence": 0.82,
    }
    llm_provider = FakeStructuredLLMProvider(json.dumps(response_payload))
    session = FakeSession([FakeResult(items=[chunk])])

    result = await execute_analysis_task(
        session,  # type: ignore[arg-type]
        task,
        llm_provider=llm_provider,
        temperature=0.0,
        max_tokens=512,
    )

    assert task.status == AnalysisTaskStatus.COMPLETED.value
    assert result.status == AnalysisResultStatus.NEEDS_REVIEW.value
    assert result.result["summary"] == response_payload["summary"]
    result_findings = cast(list[dict[str, object]], result.result["findings"])
    result_finding_citations = cast(list[dict[str, object]], result_findings[0]["citations"])
    assert result_finding_citations[0]["chunk_id"] == str(chunk.id)
    assert result.citations[0]["chunk_id"] == str(chunk.id)
    assert result.citations[0]["document_name"] == "policy.md"
    assert result.citations[0]["quote"] == chunk.content
    assert result.confidence == 0.82
    assert result.provider == "openai"
    assert result.model == "structured-test-model"
    assert result.token_usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert llm_provider.temperature == 0.0
    assert llm_provider.max_tokens == 512
    assert "Return only valid JSON" in llm_provider.messages[0].content
    assert session.added is result


@pytest.mark.asyncio
async def test_execute_analysis_task_rejects_uncited_findings_without_result() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    task = make_task(workspace_id)
    chunk = make_chunk(workspace_id, knowledge_base_id)
    response_payload = {
        "summary": "Hotel receipts are required.",
        "findings": [{"title": "Receipt required"}],
        "citations": [{"chunk_id": str(chunk.id)}],
        "confidence": 0.82,
    }
    llm_provider = FakeStructuredLLMProvider(json.dumps(response_payload))
    session = FakeSession([FakeResult(items=[chunk])])

    with pytest.raises(AnalysisCitationValidationError):
        await execute_analysis_task(
            session,  # type: ignore[arg-type]
            task,
            llm_provider=llm_provider,
        )

    assert task.status == AnalysisTaskStatus.FAILED.value
    assert session.added is None
    assert session.committed is True


@pytest.mark.asyncio
async def test_execute_analysis_task_rejects_malformed_json_without_result() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    task = make_task(workspace_id)
    chunk = make_chunk(workspace_id, knowledge_base_id)
    llm_provider = FakeStructuredLLMProvider("not-json")
    session = FakeSession([FakeResult(items=[chunk])])

    with pytest.raises(LLMProviderResponseError):
        await execute_analysis_task(
            session,  # type: ignore[arg-type]
            task,
            llm_provider=llm_provider,
        )

    assert task.status == AnalysisTaskStatus.FAILED.value
    assert session.added is None
    assert session.committed is True


@pytest.mark.asyncio
async def test_execute_analysis_task_marks_provider_failure_failed_without_result() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    task = make_task(workspace_id)
    chunk = make_chunk(workspace_id, knowledge_base_id)
    session = FakeSession([FakeResult(items=[chunk])])

    with pytest.raises(LLMProviderError):
        await execute_analysis_task(
            session,  # type: ignore[arg-type]
            task,
            llm_provider=FakeFailingLLMProvider(),
        )

    assert task.status == AnalysisTaskStatus.FAILED.value
    assert session.added is None
    assert session.committed is True


@pytest.mark.asyncio
async def test_execute_analysis_task_rejects_schema_mismatch_without_result() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    task = make_task(workspace_id)
    task.output_schema = {
        "type": "object",
        "required": ["requirements", "citations"],
        "properties": {
            "requirements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["requirement", "evidence_required"],
                    "properties": {
                        "requirement": {"type": "string"},
                        "evidence_required": {"type": "string"},
                    },
                },
            },
            "citations": {"type": "array", "items": {"type": "string"}},
        },
    }
    chunk = make_chunk(workspace_id, knowledge_base_id)
    response_payload = {
        "requirements": [
            {
                "requirement": "Submit receipts",
                "citations": [{"chunk_id": str(chunk.id)}],
            }
        ],
        "citations": ["chunk-1"],
    }
    llm_provider = FakeStructuredLLMProvider(json.dumps(response_payload))
    session = FakeSession([FakeResult(items=[chunk])])

    with pytest.raises(AnalysisOutputValidationError):
        await execute_analysis_task(
            session,  # type: ignore[arg-type]
            task,
            llm_provider=llm_provider,
        )

    assert task.status == AnalysisTaskStatus.FAILED.value
    assert session.added is None
    assert session.committed is True
