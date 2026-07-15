import uuid
from datetime import UTC, datetime

import pytest

from backend.app.models.workspace import WorkspaceTemplate, WorkspaceTemplateCategory
from backend.app.services.workspace_templates import (
    get_active_workspace_template,
    list_active_workspace_templates,
)


class FakeScalarResult:
    def __init__(self, templates: list[WorkspaceTemplate]) -> None:
        self.templates = templates

    def all(self) -> list[WorkspaceTemplate]:
        return self.templates


class FakeResult:
    def __init__(self, templates: list[WorkspaceTemplate]) -> None:
        self.templates = templates

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.templates)

    def scalar_one_or_none(self) -> WorkspaceTemplate | None:
        return self.templates[0] if self.templates else None


class FakeSession:
    def __init__(self, templates: list[WorkspaceTemplate]) -> None:
        self.templates = templates
        self.statement: object | None = None

    async def execute(self, statement: object) -> FakeResult:
        self.statement = statement
        return FakeResult(self.templates)


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


@pytest.mark.asyncio
async def test_list_active_workspace_templates_returns_templates() -> None:
    template = make_template()
    session = FakeSession([template])

    templates = await list_active_workspace_templates(session)  # type: ignore[arg-type]

    assert templates == [template]
    assert session.statement is not None


@pytest.mark.asyncio
async def test_get_active_workspace_template_returns_template() -> None:
    template = make_template()
    session = FakeSession([template])

    result = await get_active_workspace_template(
        session,  # type: ignore[arg-type]
        template.id,
    )

    assert result is template


@pytest.mark.asyncio
async def test_get_active_workspace_template_returns_none_when_missing() -> None:
    session = FakeSession([])

    result = await get_active_workspace_template(
        session,  # type: ignore[arg-type]
        uuid.uuid4(),
    )

    assert result is None
