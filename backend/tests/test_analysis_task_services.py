import uuid
from datetime import UTC, datetime

import pytest

from backend.app.models.analysis import AnalysisResult, AnalysisResultStatus, AnalysisTask
from backend.app.schemas.analysis import AnalysisResultCreate, AnalysisTaskCreate
from backend.app.services.analysis_tasks import (
    create_analysis_result_for_task,
    create_workspace_analysis_task,
    get_analysis_result_for_task,
    get_workspace_analysis_task,
    list_analysis_results_for_task,
    list_workspace_analysis_tasks,
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
        if isinstance(instance, (AnalysisTask, AnalysisResult)) and instance.id is None:
            instance.id = uuid.uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = instance


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

