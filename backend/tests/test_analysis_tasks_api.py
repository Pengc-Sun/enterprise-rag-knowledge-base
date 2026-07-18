import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.api.v1.endpoints import analysis_tasks as analysis_task_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.analysis import (
    AnalysisResult,
    AnalysisResultStatus,
    AnalysisTask,
    ReviewDecision,
    ReviewDecisionType,
)
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import Workspace
from backend.app.services.analysis_tasks import (
    AnalysisOutputValidationError,
    ReviewDecisionValidationError,
)
from backend.app.services.llms import LLMProviderTimeoutError
from backend.app.services.workspaces import READ_ROLES, REVIEW_ROLES, WRITE_ROLES


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="analyst@example.com",
        username="analyst",
        hashed_password="hashed",
        role=UserRole.USER.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_workspace(owner_id: uuid.UUID) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        id=uuid.uuid4(),
        name="Policy Review",
        slug="policy-review",
        owner_id=owner_id,
        created_at=now,
        updated_at=now,
    )


def make_task(workspace_id: uuid.UUID, created_by: uuid.UUID) -> AnalysisTask:
    now = datetime.now(UTC)
    return AnalysisTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        template_task_key="policy_requirements",
        name="Policy Requirement Extraction",
        description="Extract requirements.",
        task_type="extraction",
        status="pending",
        input_scope={},
        output_schema={"type": "object"},
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def make_result(workspace_id: uuid.UUID, task_id: uuid.UUID) -> AnalysisResult:
    now = datetime.now(UTC)
    return AnalysisResult(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        analysis_task_id=task_id,
        status="ai_generated",
        result={"requirements": []},
        citations=[{"document": "policy.md", "page": 1}],
        confidence=0.9,
        model="test-model",
        provider="local",
        token_usage={"total_tokens": 10},
        created_at=now,
        updated_at=now,
    )


def make_review_decision(
    workspace_id: uuid.UUID,
    analysis_result_id: uuid.UUID,
    reviewer_id: uuid.UUID,
) -> ReviewDecision:
    now = datetime.now(UTC)
    return ReviewDecision(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        analysis_result_id=analysis_result_id,
        reviewer_id=reviewer_id,
        decision=ReviewDecisionType.APPROVE.value,
        comment="Looks correct.",
        original_result={"requirements": []},
        edited_result=None,
        created_at=now,
    )


def override_db_session() -> AsyncSession:
    return cast(AsyncSession, object())


def set_overrides(user: User) -> None:
    def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_active_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_db_session


def clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_list_analysis_tasks_requires_workspace_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace_id = uuid.uuid4()

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> None:
        return None

    async def fake_list_workspace_analysis_tasks(
        session: AsyncSession,
        workspace_id: uuid.UUID,
    ) -> list[AnalysisTask]:
        pytest.fail("tasks must not be listed when workspace access is denied")

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "list_workspace_analysis_tasks",
        fake_list_workspace_analysis_tasks,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace_id}/analysis-tasks")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found"


def test_create_analysis_task_returns_created_task(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task = make_task(workspace.id, user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == WRITE_ROLES
        return workspace

    async def fake_create_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        created_by: uuid.UUID,
        task_create: object,
    ) -> AnalysisTask:
        assert workspace_id == workspace.id
        assert created_by == user.id
        return task

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "create_workspace_analysis_task",
        fake_create_workspace_analysis_task,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/analysis-tasks",
            json={
                "template_task_key": "policy_requirements",
                "name": "Policy Requirement Extraction",
                "task_type": "extraction",
                "output_schema": {"type": "object"},
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["workspace_id"] == str(workspace.id)
    assert body["data"]["template_task_key"] == "policy_requirements"


def test_read_analysis_task_returns_404_for_cross_workspace_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task_id = uuid.uuid4()

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == READ_ROLES
        return workspace

    async def fake_get_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> None:
        return None

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_analysis_task",
        fake_get_workspace_analysis_task,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace.id}/analysis-tasks/{task_id}")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Analysis task not found"


def test_create_analysis_result_returns_structured_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task = make_task(workspace.id, user.id)
    result = make_result(workspace.id, task.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == WRITE_ROLES
        return workspace

    async def fake_get_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> AnalysisTask:
        return task

    async def fake_create_analysis_result_for_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
        result_create: object,
    ) -> AnalysisResult:
        assert workspace_id == workspace.id
        assert analysis_task_id == task.id
        return result

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_analysis_task",
        fake_get_workspace_analysis_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "create_analysis_result_for_task",
        fake_create_analysis_result_for_task,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/analysis-tasks/{task.id}/results",
            json={
                "result": {"requirements": []},
                "citations": [{"document": "policy.md", "page": 1}],
                "confidence": 0.9,
                "model": "test-model",
                "provider": "local",
                "token_usage": {"total_tokens": 10},
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["analysis_task_id"] == str(task.id)
    assert body["data"]["citations"][0]["document"] == "policy.md"


def test_run_analysis_task_returns_execution_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task = make_task(workspace.id, user.id)
    expected_task = task
    result = make_result(workspace.id, task.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> AnalysisTask:
        return task

    async def fake_execute_analysis_task(
        session: AsyncSession,
        task: AnalysisTask,
        **kwargs: object,
    ) -> AnalysisResult:
        assert task is expected_task
        assert kwargs["llm_provider"] is not None
        assert kwargs["temperature"] == 0.0
        assert kwargs["max_tokens"] == 1024
        return result

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_analysis_task",
        fake_get_workspace_analysis_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "execute_analysis_task",
        fake_execute_analysis_task,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/analysis-tasks/{task.id}/run"
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "analysis task executed"
    assert body["data"]["id"] == str(result.id)


def test_run_analysis_task_returns_error_for_schema_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task = make_task(workspace.id, user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> AnalysisTask:
        return task

    async def fake_execute_analysis_task(
        session: AsyncSession,
        task: AnalysisTask,
        **kwargs: object,
    ) -> AnalysisResult:
        raise AnalysisOutputValidationError

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_analysis_task",
        fake_get_workspace_analysis_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "execute_analysis_task",
        fake_execute_analysis_task,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/analysis-tasks/{task.id}/run"
        )
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert response.json()["message"] == "AI analysis output did not match the task schema"


def test_run_analysis_task_maps_provider_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task = make_task(workspace.id, user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> AnalysisTask:
        return task

    async def fake_execute_analysis_task(
        session: AsyncSession,
        task: AnalysisTask,
        **kwargs: object,
    ) -> AnalysisResult:
        raise LLMProviderTimeoutError

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_analysis_task",
        fake_get_workspace_analysis_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "execute_analysis_task",
        fake_execute_analysis_task,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/analysis-tasks/{task.id}/run"
        )
    finally:
        clear_overrides()

    assert response.status_code == 504
    assert response.json()["message"] == "LLM provider request timed out"


def test_create_review_decision_returns_created_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task = make_task(workspace.id, user.id)
    result = make_result(workspace.id, task.id)
    decision = make_review_decision(workspace.id, result.id, user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == REVIEW_ROLES
        return workspace

    async def fake_get_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> AnalysisTask:
        return task

    async def fake_get_analysis_result_for_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
        analysis_result_id: uuid.UUID,
    ) -> AnalysisResult:
        return result

    async def fake_create_review_decision_for_result(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_result: AnalysisResult,
        reviewer_id: uuid.UUID,
        decision_create: object,
    ) -> ReviewDecision:
        assert workspace_id == workspace.id
        assert analysis_result is result
        assert reviewer_id == user.id
        return decision

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_analysis_task",
        fake_get_workspace_analysis_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_analysis_result_for_task",
        fake_get_analysis_result_for_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "create_review_decision_for_result",
        fake_create_review_decision_for_result,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/analysis-tasks/{task.id}"
            f"/results/{result.id}/review-decisions",
            json={"decision": "approve", "comment": "Looks correct."},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "review decision created"
    assert body["data"]["analysis_result_id"] == str(result.id)
    assert body["data"]["decision"] == "approve"
    assert body["data"]["reviewer_id"] == str(user.id)


def test_list_review_queue_returns_filtered_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task = make_task(workspace.id, user.id)
    result = make_result(workspace.id, task.id)
    result.status = AnalysisResultStatus.NEEDS_REVIEW.value

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == REVIEW_ROLES
        return workspace

    async def fake_list_review_queue_results(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        *,
        status: AnalysisResultStatus | None = None,
        analysis_task_id: uuid.UUID | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[AnalysisResult, AnalysisTask]]:
        assert workspace_id == workspace.id
        assert status == AnalysisResultStatus.NEEDS_REVIEW
        assert analysis_task_id == task.id
        assert task_type == "extraction"
        assert limit == 10
        assert offset == 5
        return [(result, task)]

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "list_review_queue_results",
        fake_list_review_queue_results,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/workspaces/{workspace.id}/analysis-tasks/review-queue",
            params={
                "status": "needs_review",
                "analysis_task_id": str(task.id),
                "task_type": "extraction",
                "limit": "10",
                "offset": "5",
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["analysis_result"]["id"] == str(result.id)
    assert body["data"][0]["analysis_result"]["status"] == "needs_review"
    assert body["data"][0]["analysis_task"]["id"] == str(task.id)
    assert body["data"][0]["analysis_task"]["name"] == task.name


def test_list_review_queue_requires_reviewer_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace_id = uuid.uuid4()

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> None:
        assert allowed_roles == REVIEW_ROLES
        return None

    async def fake_list_review_queue_results(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        *,
        status: AnalysisResultStatus | None = None,
        analysis_task_id: uuid.UUID | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[AnalysisResult, AnalysisTask]]:
        pytest.fail("review queue must not be listed when review access is denied")

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "list_review_queue_results",
        fake_list_review_queue_results,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/workspaces/{workspace_id}/analysis-tasks/review-queue"
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found"


def test_create_review_decision_requires_reviewer_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace_id = uuid.uuid4()
    task_id = uuid.uuid4()
    result_id = uuid.uuid4()

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> None:
        assert allowed_roles == REVIEW_ROLES
        return None

    async def fake_get_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> AnalysisTask:
        pytest.fail("analysis task must not be loaded when review access is denied")

    async def fake_get_analysis_result_for_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
        analysis_result_id: uuid.UUID,
    ) -> AnalysisResult:
        pytest.fail("analysis result must not be loaded when review access is denied")

    async def fake_create_review_decision_for_result(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_result: AnalysisResult,
        reviewer_id: uuid.UUID,
        decision_create: object,
    ) -> ReviewDecision:
        pytest.fail("review decision must not be created when review access is denied")

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_analysis_task",
        fake_get_workspace_analysis_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_analysis_result_for_task",
        fake_get_analysis_result_for_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "create_review_decision_for_result",
        fake_create_review_decision_for_result,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/analysis-tasks/{task_id}"
            f"/results/{result_id}/review-decisions",
            json={"decision": "approve"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found"


def test_create_review_decision_returns_400_for_invalid_action_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task = make_task(workspace.id, user.id)
    result = make_result(workspace.id, task.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == REVIEW_ROLES
        return workspace

    async def fake_get_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> AnalysisTask:
        return task

    async def fake_get_analysis_result_for_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
        analysis_result_id: uuid.UUID,
    ) -> AnalysisResult:
        return result

    async def fake_create_review_decision_for_result(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_result: AnalysisResult,
        reviewer_id: uuid.UUID,
        decision_create: object,
    ) -> ReviewDecision:
        raise ReviewDecisionValidationError("edited_result is required for edit decisions")

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_analysis_task",
        fake_get_workspace_analysis_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_analysis_result_for_task",
        fake_get_analysis_result_for_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "create_review_decision_for_result",
        fake_create_review_decision_for_result,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/analysis-tasks/{task.id}"
            f"/results/{result.id}/review-decisions",
            json={"decision": "edit"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert response.json()["message"] == "edited_result is required for edit decisions"


def test_list_review_decisions_returns_decisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    task = make_task(workspace.id, user.id)
    result = make_result(workspace.id, task.id)
    decision = make_review_decision(workspace.id, result.id, user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_workspace_analysis_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> AnalysisTask:
        return task

    async def fake_get_analysis_result_for_task(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
        analysis_result_id: uuid.UUID,
    ) -> AnalysisResult:
        return result

    async def fake_list_review_decisions_for_result(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        analysis_result_id: uuid.UUID,
    ) -> list[ReviewDecision]:
        return [decision]

    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_workspace_analysis_task",
        fake_get_workspace_analysis_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "get_analysis_result_for_task",
        fake_get_analysis_result_for_task,
    )
    monkeypatch.setattr(
        analysis_task_endpoints,
        "list_review_decisions_for_result",
        fake_list_review_decisions_for_result,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/workspaces/{workspace.id}/analysis-tasks/{task.id}"
            f"/results/{result.id}/review-decisions"
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["id"] == str(decision.id)
    assert body["data"][0]["decision"] == "approve"


def test_analysis_task_routes_are_registered_in_openapi() -> None:
    clear_overrides()
    client = TestClient(app)

    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/workspaces/{workspace_id}/analysis-tasks" in paths
    assert "/api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}" in paths
    assert "/api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/run" in paths
    assert "/api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/results" in paths
    assert (
        "/api/v1/workspaces/{workspace_id}/analysis-tasks/{analysis_task_id}/results/"
        "{analysis_result_id}/review-decisions"
    ) in paths
    assert "/api/v1/workspaces/{workspace_id}/analysis-tasks/review-queue" in paths
