import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.api.v1.endpoints import reports as report_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.report import Report, ReportSection, ReportSectionStatus, ReportStatus
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import Workspace
from backend.app.schemas.report import ReportSectionGenerateRequest
from backend.app.services.reports import ReportSectionGenerationError
from backend.app.services.workspaces import READ_ROLES, WRITE_ROLES


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="reporter@example.com",
        username="reporter",
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


def make_report(workspace_id: uuid.UUID, created_by: uuid.UUID) -> Report:
    now = datetime.now(UTC)
    return Report(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        title="Policy Review Report",
        status=ReportStatus.DRAFT.value,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def make_section(workspace_id: uuid.UUID, report_id: uuid.UUID) -> ReportSection:
    now = datetime.now(UTC)
    return ReportSection(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        report_id=report_id,
        template_section_key="summary",
        title="Executive Summary",
        body_markdown="Draft summary",
        source_task_keys=["policy_requirements"],
        source_result_ids=[],
        sort_order=10,
        status=ReportSectionStatus.DRAFT.value,
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


def test_list_reports_returns_workspace_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == READ_ROLES
        return workspace

    async def fake_list_reports_for_workspace(
        session: AsyncSession,
        workspace_id: uuid.UUID,
    ) -> list[Report]:
        assert workspace_id == workspace.id
        return [report]

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(
        report_endpoints,
        "list_reports_for_workspace",
        fake_list_reports_for_workspace,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace.id}/reports")
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["id"] == str(report.id)
    assert body["data"][0]["title"] == "Policy Review Report"


def test_create_report_requires_workspace_write_role(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == WRITE_ROLES
        return workspace

    async def fake_create_report(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        created_by: uuid.UUID,
        report_create: object,
    ) -> Report:
        assert workspace_id == workspace.id
        assert created_by == user.id
        return report

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "create_report", fake_create_report)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/reports",
            json={"title": "Policy Review Report"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "report created"
    assert body["data"]["id"] == str(report.id)


def test_read_report_returns_404_when_workspace_access_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> None:
        assert allowed_roles == READ_ROLES
        return None

    async def fake_get_report_for_workspace(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> Report:
        pytest.fail("report must not be loaded when workspace access is denied")

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace_id}/reports/{report_id}")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found"


def test_create_report_section_returns_created_section(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)
    section = make_section(workspace.id, report.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == WRITE_ROLES
        return workspace

    async def fake_get_report_for_workspace(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> Report:
        return report

    async def fake_create_report_section(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
        section_create: object,
    ) -> ReportSection:
        assert workspace_id == workspace.id
        assert report_id == report.id
        return section

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(report_endpoints, "create_report_section", fake_create_report_section)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/sections",
            json={
                "title": "Executive Summary",
                "body_markdown": "Draft summary",
                "source_task_keys": ["policy_requirements"],
                "sort_order": 10,
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "report section created"
    assert body["data"]["id"] == str(section.id)
    assert body["data"]["report_id"] == str(report.id)


def test_generate_report_section_returns_created_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)
    section = make_section(workspace.id, report.id)
    analysis_result_id = uuid.uuid4()

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == WRITE_ROLES
        return workspace

    async def fake_get_report_for_workspace(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> Report:
        return report

    async def fake_generate_report_section_from_results(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
        generation: ReportSectionGenerateRequest,
    ) -> ReportSection:
        assert workspace_id == workspace.id
        assert report_id == report.id
        assert generation.analysis_result_ids == [analysis_result_id]
        assert generation.template_section_key == "summary"
        return section

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(
        report_endpoints,
        "generate_report_section_from_results",
        fake_generate_report_section_from_results,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/sections/generate",
            json={
                "analysis_result_ids": [str(analysis_result_id)],
                "template_section_key": "summary",
                "title": "Executive Summary",
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "report section generated"
    assert body["data"]["id"] == str(section.id)


def test_generate_report_section_returns_400_for_unreportable_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_report_for_workspace(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> Report:
        return report

    async def fake_generate_report_section_from_results(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
        generation: ReportSectionGenerateRequest,
    ) -> ReportSection:
        raise ReportSectionGenerationError("Analysis results must be approved or edited")

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(
        report_endpoints,
        "generate_report_section_from_results",
        fake_generate_report_section_from_results,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/sections/generate",
            json={"analysis_result_ids": [str(uuid.uuid4())]},
        )
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert response.json()["message"] == "Analysis results must be approved or edited"


def test_report_routes_are_registered_in_openapi() -> None:
    clear_overrides()
    client = TestClient(app)

    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/workspaces/{workspace_id}/reports" in paths
    assert "/api/v1/workspaces/{workspace_id}/reports/{report_id}" in paths
    assert "/api/v1/workspaces/{workspace_id}/reports/{report_id}/sections" in paths
    assert (
        "/api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/generate"
    ) in paths
    assert (
        "/api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/{section_id}"
    ) in paths
