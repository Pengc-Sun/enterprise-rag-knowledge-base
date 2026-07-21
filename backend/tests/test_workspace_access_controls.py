import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.api.v1.endpoints import workspaces as workspace_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.analysis import AnalysisTask
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.report import Report
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import (
    Workspace,
    WorkspaceDirectory,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspaceStatus,
    WorkspaceTemplate,
    WorkspaceTemplateCategory,
)
from backend.app.schemas.workspace import WorkspaceCreate
from backend.app.services.workspaces import (
    WRITE_ROLES,
    WorkspaceMemberRoleError,
    WorkspaceOwnerMemberError,
    WorkspaceTemplateNotFoundError,
    create_workspace,
    get_workspace_for_user,
    get_workspace_member,
    list_workspace_members,
    list_workspaces_for_user,
    remove_workspace_member,
)


def make_user(email: str = "user@example.com") -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=email,
        username=email.split("@")[0],
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
        description="Review policies",
        owner_id=owner_id,
        status=WorkspaceStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
    )


def make_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: WorkspaceMemberRole = WorkspaceMemberRole.VIEWER,
) -> WorkspaceMember:
    now = datetime.now(UTC)
    return WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role=role.value,
        created_at=now,
        updated_at=now,
    )


def make_directory(workspace_id: uuid.UUID) -> WorkspaceDirectory:
    now = datetime.now(UTC)
    return WorkspaceDirectory(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        name="Policies",
        path="policies",
        description="Policy documents",
        sort_order=10,
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
        directory_schema={
            "version": "1.0",
            "directories": [
                {
                    "key": "policies",
                    "name": "Policies",
                    "path": "policies",
                    "description": "Policy documents",
                    "parent_key": None,
                    "sort_order": 10,
                },
                {
                    "key": "evidence",
                    "name": "Evidence",
                    "path": "evidence",
                    "description": "Supporting evidence",
                    "parent_key": None,
                    "sort_order": 20,
                },
            ],
            "knowledge_bases": [
                {
                    "key": "policies",
                    "name": "Policies",
                    "description": "Policy documents under review.",
                    "directory_key": "policies",
                    "visibility": "private",
                    "sort_order": 10,
                },
                {
                    "key": "evidence",
                    "name": "Evidence",
                    "description": "Supporting evidence.",
                    "directory_key": "evidence",
                    "visibility": "private",
                    "sort_order": 20,
                },
            ],
        },
        analysis_task_schema={
            "version": "1.0",
            "tasks": [
                {
                    "key": "policy_requirements",
                    "name": "Policy Requirement Extraction",
                    "description": "Extract policy requirements.",
                    "task_type": "extraction",
                    "output_schema": {
                        "type": "object",
                        "required": ["requirements", "citations"],
                        "properties": {},
                    },
                },
                {
                    "key": "policy_risk_review",
                    "name": "Policy Risk Review",
                    "description": "Identify policy risks.",
                    "task_type": "risk_review",
                    "output_schema": {
                        "type": "object",
                        "required": ["risks", "citations"],
                        "properties": {},
                    },
                },
            ],
        },
        report_schema={
            "version": "1.0",
            "sections": [
                {
                    "key": "requirements",
                    "title": "Policy Requirements",
                    "source_task_keys": ["policy_requirements"],
                    "sort_order": 10,
                },
                {
                    "key": "risk_findings",
                    "title": "Risk Findings",
                    "source_task_keys": ["policy_risk_review"],
                    "sort_order": 20,
                },
            ],
        },
        created_at=now,
        updated_at=now,
    )


class FakeCreateWorkspaceSession:
    def __init__(self, result: object | None = None) -> None:
        self.added: list[object] = []
        self.flushed = False
        self.committed = False
        self.refreshed: object | None = None
        self.result = result
        self.statement: object | None = None

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def execute(self, statement: object) -> object:
        self.statement = statement
        assert self.result is not None
        return self.result

    async def flush(self) -> None:
        self.flushed = True
        for instance in self.added:
            if isinstance(instance, Workspace) and instance.id is None:
                instance.id = uuid.uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = instance


class FakeScalarResult:
    def __init__(self, items: list[object]) -> None:
        self.items = items

    def all(self) -> list[object]:
        return self.items


class FakeResult:
    def __init__(
        self,
        items: list[object] | None = None,
        row: tuple[Workspace, str | None] | None = None,
        scalar: object | None = None,
    ) -> None:
        self.items = items or []
        self.row = row
        self.scalar = scalar

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.items)

    def first(self) -> tuple[Workspace, str | None] | None:
        return self.row

    def scalar_one_or_none(self) -> object | None:
        return self.scalar


class FakeExecuteSession:
    def __init__(self, result: FakeResult) -> None:
        self.result = result
        self.statement: object | None = None

    async def execute(self, statement: object) -> FakeResult:
        self.statement = statement
        return self.result


class FakeDeleteSession:
    def __init__(self) -> None:
        self.deleted: object | None = None
        self.committed = False

    async def delete(self, instance: object) -> None:
        self.deleted = instance

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_create_workspace_creates_owner_membership() -> None:
    owner = make_user()
    session = FakeCreateWorkspaceSession()

    workspace = await create_workspace(
        session,  # type: ignore[arg-type]
        owner.id,
        WorkspaceCreate(
            name="Policy Review",
            slug="policy-review",
            description="Review policies",
        ),
    )

    owner_member = next(item for item in session.added if isinstance(item, WorkspaceMember))
    assert workspace.owner_id == owner.id
    assert workspace.template_id is None
    assert owner_member.workspace_id == workspace.id
    assert owner_member.user_id == owner.id
    assert owner_member.role == WorkspaceMemberRole.OWNER.value
    assert session.flushed is True
    assert session.committed is True
    assert session.refreshed is workspace


@pytest.mark.asyncio
async def test_create_workspace_instantiates_directories_from_template() -> None:
    owner = make_user()
    template = make_template()
    session = FakeCreateWorkspaceSession(FakeResult(scalar=template))

    workspace = await create_workspace(
        session,  # type: ignore[arg-type]
        owner.id,
        WorkspaceCreate(
            name="Policy Review",
            slug="policy-review",
            description="Review policies",
            template_id=template.id,
        ),
    )

    directory_paths = {directory.path for directory in workspace.directories}
    persisted_directories = [
        item for item in session.added if isinstance(item, WorkspaceDirectory)
    ]
    knowledge_bases = [item for item in session.added if isinstance(item, KnowledgeBase)]
    analysis_tasks = [item for item in session.added if isinstance(item, AnalysisTask)]
    reports = [item for item in session.added if isinstance(item, Report)]
    knowledge_base_members = [
        member
        for knowledge_base in knowledge_bases
        for member in knowledge_base.members
        if isinstance(member, KnowledgeBaseMember)
    ]

    assert workspace.template_id == template.id
    assert directory_paths == {"policies", "evidence"}
    assert {directory.path for directory in persisted_directories} == {"policies", "evidence"}
    assert {directory.workspace for directory in persisted_directories} == {workspace}
    assert {knowledge_base.name for knowledge_base in knowledge_bases} == {"Policies", "Evidence"}
    assert {knowledge_base.workspace_id for knowledge_base in knowledge_bases} == {workspace.id}
    assert {knowledge_base.owner_id for knowledge_base in knowledge_bases} == {owner.id}
    assert {member.user_id for member in knowledge_base_members} == {owner.id}
    assert {member.permission for member in knowledge_base_members} == {"owner"}
    assert {task.template_task_key for task in analysis_tasks} == {
        "policy_requirements",
        "policy_risk_review",
    }
    assert {task.status for task in analysis_tasks} == {"pending"}
    assert {task.created_by for task in analysis_tasks} == {owner.id}
    assert len(reports) == 1
    assert reports[0].title == "Policy Review Report"
    assert [section.title for section in reports[0].sections] == [
        "Policy Requirements",
        "Risk Findings",
    ]
    assert reports[0].sections[0].source_task_keys == ["policy_requirements"]
    assert {directory.workspace for directory in workspace.directories} == {workspace}
    assert session.statement is not None
    assert session.committed is True


@pytest.mark.asyncio
async def test_create_workspace_rejects_missing_template() -> None:
    owner = make_user()
    session = FakeCreateWorkspaceSession(FakeResult(scalar=None))

    with pytest.raises(WorkspaceTemplateNotFoundError):
        await create_workspace(
            session,  # type: ignore[arg-type]
            owner.id,
            WorkspaceCreate(
                name="Policy Review",
                slug="policy-review",
                description="Review policies",
                template_id=uuid.uuid4(),
            ),
        )

    assert session.committed is False


@pytest.mark.asyncio
async def test_list_workspaces_for_user_returns_owned_or_member_workspaces() -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    session = FakeExecuteSession(FakeResult(items=[workspace]))

    workspaces = await list_workspaces_for_user(session, user.id)  # type: ignore[arg-type]

    assert workspaces == [workspace]
    assert session.statement is not None


@pytest.mark.asyncio
async def test_get_workspace_for_user_allows_admin_for_write_roles() -> None:
    owner = make_user("owner@example.com")
    admin = make_user("admin@example.com")
    workspace = make_workspace(owner.id)
    session = FakeExecuteSession(FakeResult(row=(workspace, WorkspaceMemberRole.ADMIN.value)))

    result = await get_workspace_for_user(
        session,  # type: ignore[arg-type]
        workspace.id,
        admin.id,
        WRITE_ROLES,
    )

    assert result is workspace


@pytest.mark.asyncio
async def test_list_workspace_members_returns_workspace_members() -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    owner_member = make_member(workspace.id, user.id, WorkspaceMemberRole.OWNER)
    viewer_member = make_member(workspace.id, uuid.uuid4(), WorkspaceMemberRole.VIEWER)
    session = FakeExecuteSession(FakeResult(items=[owner_member, viewer_member]))

    members = await list_workspace_members(session, workspace.id)  # type: ignore[arg-type]

    assert members == [owner_member, viewer_member]
    assert session.statement is not None


@pytest.mark.asyncio
async def test_get_workspace_member_returns_none_when_member_is_missing() -> None:
    session = FakeExecuteSession(FakeResult(scalar=None))

    member = await get_workspace_member(
        session,  # type: ignore[arg-type]
        uuid.uuid4(),
        uuid.uuid4(),
    )

    assert member is None
    assert session.statement is not None


@pytest.mark.asyncio
async def test_remove_workspace_member_deletes_non_owner_member() -> None:
    owner = make_user("owner@example.com")
    workspace = make_workspace(owner.id)
    member = make_member(workspace.id, uuid.uuid4(), WorkspaceMemberRole.REVIEWER)
    session = FakeDeleteSession()

    await remove_workspace_member(session, workspace, member)  # type: ignore[arg-type]

    assert session.deleted is member
    assert session.committed is True


def override_db_session() -> AsyncSession:
    return cast(AsyncSession, object())


def set_overrides(user: User) -> None:
    def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_active_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_db_session


def clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_list_workspace_members_returns_404_for_non_member(
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

    async def fake_list_workspace_members(
        session: AsyncSession,
        workspace_id: uuid.UUID,
    ) -> list[WorkspaceMember]:
        pytest.fail("members must not be listed when workspace access is denied")

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "list_workspace_members", fake_list_workspace_members)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace_id}/members")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found"


def test_add_workspace_member_rejects_owner_role_at_api_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_user("owner@example.com")
    new_user = make_user("reviewer@example.com")
    workspace = make_workspace(owner.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User:
        return new_user

    async def fake_add_workspace_member(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: WorkspaceMemberRole,
    ) -> WorkspaceMember:
        raise WorkspaceMemberRoleError

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(workspace_endpoints, "add_workspace_member", fake_add_workspace_member)
    set_overrides(owner)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/members",
            json={"user_id": str(new_user.id), "role": "owner"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert "owner role" in response.json()["message"]


def test_remove_workspace_member_rejects_workspace_owner_at_api_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_user("owner@example.com")
    workspace = make_workspace(owner.id)
    owner_member = make_member(workspace.id, owner.id, WorkspaceMemberRole.OWNER)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_workspace_member(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceMember:
        return owner_member

    async def fake_remove_workspace_member(
        session: AsyncSession,
        workspace: Workspace,
        member: WorkspaceMember,
    ) -> None:
        raise WorkspaceOwnerMemberError

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(
        workspace_endpoints,
        "remove_workspace_member",
        fake_remove_workspace_member,
    )
    set_overrides(owner)

    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/workspaces/{workspace.id}/members/{owner.id}")
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert "owner membership" in response.json()["message"]


def test_create_workspace_returns_404_for_missing_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_user("owner@example.com")

    async def fake_create_workspace(
        session: AsyncSession,
        owner_id: uuid.UUID,
        workspace_create: WorkspaceCreate,
    ) -> Workspace:
        assert owner_id == owner.id
        raise WorkspaceTemplateNotFoundError

    async def fake_create_audit_log(*args: object, **kwargs: object) -> object:
        pytest.fail("audit log must not be written when workspace creation fails")

    monkeypatch.setattr(workspace_endpoints, "create_workspace", fake_create_workspace)
    monkeypatch.setattr(workspace_endpoints, "create_audit_log", fake_create_audit_log)
    set_overrides(owner)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/workspaces",
            json={
                "name": "Policy Review",
                "slug": "policy-review",
                "description": "Review policies",
                "template_id": str(uuid.uuid4()),
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace template not found"


def test_list_workspace_directories_returns_404_for_non_member(
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

    async def fake_list_workspace_directories(
        session: AsyncSession,
        workspace_id: uuid.UUID,
    ) -> list[WorkspaceDirectory]:
        pytest.fail("directories must not be listed when workspace access is denied")

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(
        workspace_endpoints,
        "list_workspace_directories",
        fake_list_workspace_directories,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace_id}/directories")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found"


def test_create_workspace_directory_uses_write_roles_and_returns_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_user("owner@example.com")
    workspace = make_workspace(owner.id)
    directory = make_directory(workspace.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert workspace_id == workspace.id
        assert user_id == owner.id
        assert allowed_roles == WRITE_ROLES
        return workspace

    async def fake_create_workspace_directory(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        directory_create: object,
    ) -> WorkspaceDirectory:
        assert workspace_id == workspace.id
        return directory

    async def fake_create_audit_log(*args: object, **kwargs: object) -> object:
        return object()

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(
        workspace_endpoints,
        "create_workspace_directory",
        fake_create_workspace_directory,
    )
    monkeypatch.setattr(workspace_endpoints, "create_audit_log", fake_create_audit_log)
    set_overrides(owner)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/directories",
            json={"name": "Policies", "path": "policies", "sort_order": 10},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["workspace_id"] == str(workspace.id)
    assert body["data"]["path"] == "policies"


def test_read_workspace_directory_returns_404_for_cross_workspace_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    directory_id = uuid.uuid4()

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_workspace_directory(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        directory_id: uuid.UUID,
    ) -> None:
        return None

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(
        workspace_endpoints,
        "get_workspace_directory",
        fake_get_workspace_directory,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace.id}/directories/{directory_id}")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace directory not found"


def test_workspace_template_routes_require_authentication() -> None:
    clear_overrides()
    client = TestClient(app)

    response = client.get("/api/v1/workspace-templates")

    assert response.status_code == 401
    assert response.json()["success"] is False


def test_workspace_routes_are_registered_in_openapi() -> None:
    clear_overrides()
    client = TestClient(app)

    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/workspaces" in paths
    assert "/api/v1/workspaces/{workspace_id}/dashboard" in paths
    assert "/api/v1/workspaces/{workspace_id}/directories" in paths
    assert "/api/v1/workspaces/{workspace_id}/members" in paths
    assert "/api/v1/workspace-templates" in paths
