import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.api.v1.endpoints import workspace_templates as workspace_template_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import WorkspaceTemplate, WorkspaceTemplateCategory


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        username="enterprise_user",
        hashed_password="hashed",
        role=UserRole.USER.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_template() -> WorkspaceTemplate:
    now = datetime.now(UTC)
    return WorkspaceTemplate(
        id=uuid.uuid4(),
        name="Policy Review Workspace",
        description="Policy review",
        category=WorkspaceTemplateCategory.POLICY_REVIEW.value,
        version="1.0",
        is_active=True,
        directory_schema={"directories": [{"name": "Policies"}]},
        analysis_task_schema={"tasks": [{"key": "policy_review"}]},
        report_schema={"sections": [{"title": "Findings"}]},
        created_at=now,
        updated_at=now,
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


def test_list_workspace_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    template = make_template()

    async def fake_list_active_workspace_templates(
        session: AsyncSession,
    ) -> list[WorkspaceTemplate]:
        return [template]

    monkeypatch.setattr(
        workspace_template_endpoints,
        "list_active_workspace_templates",
        fake_list_active_workspace_templates,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get("/api/v1/workspace-templates")
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"][0]["name"] == "Policy Review Workspace"
    assert body["data"][0]["category"] == "policy_review"
    assert body["data"][0]["directory_schema"] == {"directories": [{"name": "Policies"}]}


def test_read_workspace_template(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    template = make_template()

    async def fake_get_active_workspace_template(
        session: AsyncSession,
        template_id: uuid.UUID,
    ) -> WorkspaceTemplate:
        assert template_id == template.id
        return template

    monkeypatch.setattr(
        workspace_template_endpoints,
        "get_active_workspace_template",
        fake_get_active_workspace_template,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspace-templates/{template.id}")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(template.id)


def test_read_workspace_template_returns_404_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    template_id = uuid.uuid4()

    async def fake_get_active_workspace_template(
        session: AsyncSession,
        template_id: uuid.UUID,
    ) -> None:
        return None

    monkeypatch.setattr(
        workspace_template_endpoints,
        "get_active_workspace_template",
        fake_get_active_workspace_template,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspace-templates/{template_id}")
    finally:
        clear_overrides()

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Workspace template not found"
