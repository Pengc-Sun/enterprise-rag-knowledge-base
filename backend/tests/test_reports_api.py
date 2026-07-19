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
from backend.app.models.report import (
    ExportFormat,
    ExportJob,
    ExportJobStatus,
    Report,
    ReportSection,
    ReportSectionStatus,
    ReportStatus,
)
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import Workspace
from backend.app.schemas.report import (
    ReportExportCreate,
    ReportPreviewRead,
    ReportSectionGenerateRequest,
    ReportSectionReorderRequest,
    ReportSectionUpdate,
    ReportUpdate,
)
from backend.app.services.reports import (
    ReportSectionGenerationError,
    ReportSectionOrderingError,
    ReportSectionSourceError,
)
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


def make_export_job(
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    created_by: uuid.UUID,
    export_format: ExportFormat = ExportFormat.MARKDOWN,
) -> ExportJob:
    now = datetime.now(UTC)
    return ExportJob(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        report_id=report_id,
        format=export_format.value,
        status=ExportJobStatus.COMPLETED.value,
        file_path=None,
        error_message=None,
        created_by=created_by,
        export_metadata={"markdown": "# Policy Review Report\n", "section_count": 1},
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


def test_update_report_requires_workspace_write_role(monkeypatch: pytest.MonkeyPatch) -> None:
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

    async def fake_get_report_for_workspace(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> Report:
        return report

    async def fake_update_report(
        session: AsyncSession,
        report: Report,
        report_update: ReportUpdate,
    ) -> Report:
        assert report_update.title == "Updated Report"
        report.title = "Updated Report"
        return report

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(report_endpoints, "update_report", fake_update_report)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}",
            json={"title": "Updated Report"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "report updated"
    assert body["data"]["title"] == "Updated Report"


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


def test_preview_report_returns_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
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

    async def fake_get_report_for_workspace(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> Report:
        assert workspace_id == workspace.id
        assert report_id == report.id
        return report

    async def fake_build_report_preview(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report: Report,
    ) -> ReportPreviewRead:
        return ReportPreviewRead(
            report_id=report.id,
            workspace_id=workspace_id,
            title=report.title,
            status=ReportStatus.DRAFT,
            section_count=1,
            markdown="# Policy Review Report\n\n## Executive Summary\n\nDraft summary.\n",
        )

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(report_endpoints, "build_report_preview", fake_build_report_preview)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/preview"
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["report_id"] == str(report.id)
    assert body["data"]["section_count"] == 1
    assert body["data"]["markdown"].startswith("# Policy Review Report")


def test_create_report_export_returns_completed_markdown_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)
    export_job = make_export_job(workspace.id, report.id, user.id)

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

    async def fake_create_report_export(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report: Report,
        created_by: uuid.UUID,
        export_create: ReportExportCreate,
    ) -> ExportJob:
        assert workspace_id == workspace.id
        assert report.id == report.id
        assert created_by == user.id
        assert export_create.format == ExportFormat.MARKDOWN
        return export_job

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(report_endpoints, "create_report_export", fake_create_report_export)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/exports",
            json={"format": "markdown"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "report export created"
    assert body["data"]["id"] == str(export_job.id)
    assert body["data"]["format"] == "markdown"
    assert body["data"]["status"] == "completed"
    assert body["data"]["export_metadata"]["markdown"] == "# Policy Review Report\n"


def test_create_report_export_returns_completed_docx_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)
    export_job = make_export_job(workspace.id, report.id, user.id, ExportFormat.DOCX)
    export_job.export_metadata = {
        "docx_base64": "UEsDBAo=",
        "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "filename": "policy-review-report.docx",
        "section_count": 1,
    }

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

    async def fake_create_report_export(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report: Report,
        created_by: uuid.UUID,
        export_create: ReportExportCreate,
    ) -> ExportJob:
        assert export_create.format == ExportFormat.DOCX
        return export_job

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(report_endpoints, "create_report_export", fake_create_report_export)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/exports",
            json={"format": "docx"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["format"] == "docx"
    assert body["data"]["status"] == "completed"
    assert body["data"]["export_metadata"]["filename"] == "policy-review-report.docx"


def test_create_report_export_returns_completed_pdf_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)
    export_job = make_export_job(workspace.id, report.id, user.id, ExportFormat.PDF)
    export_job.export_metadata = {
        "pdf_base64": "JVBERi0=",
        "content_type": "application/pdf",
        "filename": "policy-review-report.pdf",
        "section_count": 1,
    }

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

    async def fake_create_report_export(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report: Report,
        created_by: uuid.UUID,
        export_create: ReportExportCreate,
    ) -> ExportJob:
        assert export_create.format == ExportFormat.PDF
        return export_job

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(report_endpoints, "create_report_export", fake_create_report_export)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/exports",
            json={"format": "pdf"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["format"] == "pdf"
    assert body["data"]["status"] == "completed"
    assert body["data"]["export_metadata"]["filename"] == "policy-review-report.pdf"


def test_read_export_job_returns_workspace_export_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)
    export_job = make_export_job(workspace.id, report.id, user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == READ_ROLES
        return workspace

    async def fake_get_export_job_for_workspace(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        export_id: uuid.UUID,
    ) -> ExportJob:
        assert workspace_id == workspace.id
        assert export_id == export_job.id
        return export_job

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(
        report_endpoints,
        "get_export_job_for_workspace",
        fake_get_export_job_for_workspace,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace.id}/exports/{export_job.id}")
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["id"] == str(export_job.id)
    assert body["data"]["status"] == "completed"


def test_create_report_section_returns_400_for_unreportable_sources(
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

    async def fake_create_report_section(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
        section_create: object,
    ) -> ReportSection:
        raise ReportSectionSourceError("Report section source results must be approved or edited")

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
                "source_result_ids": [str(uuid.uuid4())],
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert response.json()["message"] == (
        "Report section source results must be approved or edited"
    )


def test_update_report_section_returns_updated_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    async def fake_get_report_section_for_report(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
        section_id: uuid.UUID,
    ) -> ReportSection:
        return section

    async def fake_update_report_section(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        section: ReportSection,
        section_update: ReportSectionUpdate,
    ) -> ReportSection:
        assert section_update.body_markdown == "Updated summary"
        section.body_markdown = "Updated summary"
        return section

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(
        report_endpoints,
        "get_report_section_for_report",
        fake_get_report_section_for_report,
    )
    monkeypatch.setattr(report_endpoints, "update_report_section", fake_update_report_section)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/sections/{section.id}",
            json={"body_markdown": "Updated summary"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "report section updated"
    assert body["data"]["body_markdown"] == "Updated summary"


def test_reorder_report_sections_returns_ordered_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    report = make_report(workspace.id, user.id)
    first_section = make_section(workspace.id, report.id)
    second_section = make_section(workspace.id, report.id)

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

    async def fake_reorder_report_sections(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
        reorder_request: ReportSectionReorderRequest,
    ) -> list[ReportSection]:
        assert reorder_request.sections[0].section_id == second_section.id
        second_section.sort_order = 10
        first_section.sort_order = 20
        return [second_section, first_section]

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(report_endpoints, "reorder_report_sections", fake_reorder_report_sections)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/sections/reorder",
            json={
                "sections": [
                    {"section_id": str(second_section.id), "sort_order": 10},
                    {"section_id": str(first_section.id), "sort_order": 20},
                ]
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "report sections reordered"
    assert [section["id"] for section in body["data"]] == [
        str(second_section.id),
        str(first_section.id),
    ]


def test_reorder_report_sections_returns_400_for_invalid_ordering(
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

    async def fake_reorder_report_sections(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        report_id: uuid.UUID,
        reorder_request: ReportSectionReorderRequest,
    ) -> list[ReportSection]:
        raise ReportSectionOrderingError("Report section ordering cannot contain duplicates")

    monkeypatch.setattr(report_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(report_endpoints, "get_report_for_workspace", fake_get_report_for_workspace)
    monkeypatch.setattr(report_endpoints, "reorder_report_sections", fake_reorder_report_sections)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/workspaces/{workspace.id}/reports/{report.id}/sections/reorder",
            json={
                "sections": [
                    {"section_id": str(uuid.uuid4()), "sort_order": 10},
                ]
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert response.json()["message"] == "Report section ordering cannot contain duplicates"


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
    assert "/api/v1/workspaces/{workspace_id}/reports/{report_id}/preview" in paths
    assert "/api/v1/workspaces/{workspace_id}/reports/{report_id}/exports" in paths
    assert "/api/v1/workspaces/{workspace_id}/exports/{export_id}" in paths
    assert "/api/v1/workspaces/{workspace_id}/reports/{report_id}/sections" in paths
    assert (
        "/api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/reorder"
    ) in paths
    assert (
        "/api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/generate"
    ) in paths
    assert (
        "/api/v1/workspaces/{workspace_id}/reports/{report_id}/sections/{section_id}"
    ) in paths
