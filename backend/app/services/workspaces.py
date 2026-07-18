import uuid
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.analysis import AnalysisTask, AnalysisTaskStatus
from backend.app.models.knowledge_base import (
    KnowledgeBase,
    KnowledgeBaseMember,
    KnowledgeBasePermission,
    KnowledgeBaseVisibility,
)
from backend.app.models.report import Report, ReportSection, ReportSectionStatus, ReportStatus
from backend.app.models.workspace import (
    Workspace,
    WorkspaceDirectory,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspaceTemplate,
)
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from backend.app.services.workspace_templates import get_active_workspace_template

READ_ROLES = frozenset(
    {
        WorkspaceMemberRole.OWNER.value,
        WorkspaceMemberRole.ADMIN.value,
        WorkspaceMemberRole.EDITOR.value,
        WorkspaceMemberRole.REVIEWER.value,
        WorkspaceMemberRole.VIEWER.value,
    }
)
WRITE_ROLES = frozenset(
    {
        WorkspaceMemberRole.OWNER.value,
        WorkspaceMemberRole.ADMIN.value,
    }
)
REVIEW_ROLES = frozenset(
    {
        WorkspaceMemberRole.OWNER.value,
        WorkspaceMemberRole.ADMIN.value,
        WorkspaceMemberRole.REVIEWER.value,
    }
)
OWNER_ROLES = frozenset({WorkspaceMemberRole.OWNER.value})
MEMBER_MANAGEMENT_ROLES = WRITE_ROLES
DEFAULT_WORKSPACE_NAME = "Default Workspace"
DEFAULT_WORKSPACE_DESCRIPTION = (
    "Auto-created for v1-compatible knowledge-base flows."
)
DEFAULT_WORKSPACE_SLUG_PREFIX = "v1-default-"

ASSIGNABLE_MEMBER_ROLES = frozenset(
    {
        WorkspaceMemberRole.ADMIN.value,
        WorkspaceMemberRole.EDITOR.value,
        WorkspaceMemberRole.REVIEWER.value,
        WorkspaceMemberRole.VIEWER.value,
    }
)


class WorkspaceMemberRoleError(ValueError):
    message = "Workspace owner role cannot be managed through member endpoints"


class WorkspaceOwnerMemberError(ValueError):
    message = "Workspace owner membership cannot be modified through member endpoints"


class WorkspaceTemplateNotFoundError(ValueError):
    message = "Workspace template not found"


def default_workspace_slug_for_user(user_id: uuid.UUID) -> str:
    return f"{DEFAULT_WORKSPACE_SLUG_PREFIX}{str(user_id).replace('-', '')}"


async def get_default_workspace_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Workspace | None:
    result = await session.execute(
        select(Workspace).where(
            Workspace.owner_id == user_id,
            Workspace.slug == default_workspace_slug_for_user(user_id),
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_default_workspace_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Workspace:
    existing_workspace = await get_default_workspace_for_user(session, user_id)
    if existing_workspace is not None:
        return existing_workspace

    workspace = Workspace(
        name=DEFAULT_WORKSPACE_NAME,
        slug=default_workspace_slug_for_user(user_id),
        description=DEFAULT_WORKSPACE_DESCRIPTION,
        owner_id=user_id,
    )
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user_id,
            role=WorkspaceMemberRole.OWNER.value,
        )
    )
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def create_workspace(
    session: AsyncSession,
    owner_id: uuid.UUID,
    workspace_create: WorkspaceCreate,
) -> Workspace:
    template: WorkspaceTemplate | None = None
    if workspace_create.template_id is not None:
        template = await get_active_workspace_template(session, workspace_create.template_id)
        if template is None:
            raise WorkspaceTemplateNotFoundError

    workspace = Workspace(
        name=workspace_create.name,
        slug=workspace_create.slug,
        description=workspace_create.description,
        owner_id=owner_id,
        template_id=workspace_create.template_id,
    )
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceMemberRole.OWNER.value,
        )
    )
    if template is not None:
        instantiate_workspace_directories_from_template(workspace, template)
        for knowledge_base in instantiate_workspace_knowledge_bases_from_template(
            workspace,
            owner_id,
            template,
        ):
            session.add(knowledge_base)
        for analysis_task in instantiate_workspace_analysis_tasks_from_template(
            workspace,
            owner_id,
            template,
        ):
            session.add(analysis_task)
        session.add(instantiate_workspace_report_from_template(workspace, owner_id, template))

    await session.commit()
    await session.refresh(workspace)
    return workspace


def instantiate_workspace_directories_from_template(
    workspace: Workspace,
    template: WorkspaceTemplate,
) -> list[WorkspaceDirectory]:
    directories = get_template_directory_entries(template.directory_schema)
    directory_by_key: dict[str, WorkspaceDirectory] = {}
    created_directories: list[WorkspaceDirectory] = []

    for entry in directories:
        key = cast(str, entry.get("key") or entry["path"])
        parent_key = cast(str | None, entry.get("parent_key"))
        directory = WorkspaceDirectory(
            workspace=workspace,
            parent=directory_by_key.get(parent_key) if parent_key is not None else None,
            name=cast(str, entry["name"]),
            path=cast(str, entry["path"]),
            description=cast(str | None, entry.get("description")),
            sort_order=cast(int, entry.get("sort_order", 0)),
        )
        directory_by_key[key] = directory
        created_directories.append(directory)

    return created_directories


def get_template_directory_entries(
    directory_schema: dict[str, object],
) -> list[dict[str, object]]:
    directories = directory_schema.get("directories", [])
    if not isinstance(directories, list):
        return []

    normalized_directories: list[dict[str, object]] = []
    for directory in directories:
        if not isinstance(directory, dict):
            continue
        if not isinstance(directory.get("name"), str):
            continue
        if not isinstance(directory.get("path"), str):
            continue
        normalized_directories.append(cast(dict[str, object], directory))
    return normalized_directories


def instantiate_workspace_knowledge_bases_from_template(
    workspace: Workspace,
    owner_id: uuid.UUID,
    template: WorkspaceTemplate,
) -> list[KnowledgeBase]:
    knowledge_base_entries = get_template_knowledge_base_entries(template.directory_schema)
    created_knowledge_bases: list[KnowledgeBase] = []

    for entry in knowledge_base_entries:
        knowledge_base_id = uuid.uuid4()
        knowledge_base = KnowledgeBase(
            id=knowledge_base_id,
            name=cast(str, entry["name"]),
            description=cast(str | None, entry.get("description")),
            visibility=get_template_knowledge_base_visibility(entry),
            owner_id=owner_id,
            workspace_id=workspace.id,
        )
        workspace_knowledge_base_member = KnowledgeBaseMember(
            knowledge_base_id=knowledge_base_id,
            user_id=owner_id,
            permission=KnowledgeBasePermission.OWNER.value,
        )
        created_knowledge_bases.append(knowledge_base)
        workspace_knowledge_base_member.knowledge_base = knowledge_base

    return created_knowledge_bases


def get_template_knowledge_base_entries(
    directory_schema: dict[str, object],
) -> list[dict[str, object]]:
    knowledge_bases = directory_schema.get("knowledge_bases", [])
    if not isinstance(knowledge_bases, list):
        return []

    normalized_knowledge_bases: list[dict[str, object]] = []
    for knowledge_base in knowledge_bases:
        if not isinstance(knowledge_base, dict):
            continue
        if not isinstance(knowledge_base.get("name"), str):
            continue
        normalized_knowledge_bases.append(cast(dict[str, object], knowledge_base))
    return normalized_knowledge_bases


def get_template_knowledge_base_visibility(entry: dict[str, object]) -> str:
    visibility = entry.get("visibility", KnowledgeBaseVisibility.PRIVATE.value)
    if visibility == KnowledgeBaseVisibility.PUBLIC.value:
        return KnowledgeBaseVisibility.PUBLIC.value
    return KnowledgeBaseVisibility.PRIVATE.value


def instantiate_workspace_analysis_tasks_from_template(
    workspace: Workspace,
    owner_id: uuid.UUID,
    template: WorkspaceTemplate,
) -> list[AnalysisTask]:
    task_entries = get_template_analysis_task_entries(template.analysis_task_schema)
    analysis_tasks: list[AnalysisTask] = []

    for entry in task_entries:
        template_task_key = cast(str, entry["key"])
        analysis_tasks.append(
            AnalysisTask(
                workspace_id=workspace.id,
                template_task_key=template_task_key,
                name=cast(str, entry["name"]),
                description=cast(str | None, entry.get("description")),
                task_type=cast(str, entry["task_type"]),
                status=AnalysisTaskStatus.PENDING.value,
                input_scope=get_template_task_input_scope(template, entry),
                output_schema=get_template_task_output_schema(entry),
                created_by=owner_id,
            )
        )

    return analysis_tasks


def get_template_analysis_task_entries(
    analysis_task_schema: dict[str, object],
) -> list[dict[str, object]]:
    tasks = analysis_task_schema.get("tasks", [])
    if not isinstance(tasks, list):
        return []

    normalized_tasks: list[dict[str, object]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if not isinstance(task.get("key"), str):
            continue
        if not isinstance(task.get("name"), str):
            continue
        if not isinstance(task.get("task_type"), str):
            continue
        normalized_tasks.append(cast(dict[str, object], task))
    return normalized_tasks


def get_template_task_input_scope(
    template: WorkspaceTemplate,
    entry: dict[str, object],
) -> dict[str, object]:
    input_scope = entry.get("input_scope")
    if isinstance(input_scope, dict):
        return cast(dict[str, object], input_scope)
    return {
        "template_id": str(template.id),
        "template_version": template.version,
        "template_task_key": cast(str, entry["key"]),
    }


def get_template_task_output_schema(entry: dict[str, object]) -> dict[str, object]:
    output_schema = entry.get("output_schema")
    if isinstance(output_schema, dict):
        return cast(dict[str, object], output_schema)
    return {}


def instantiate_workspace_report_from_template(
    workspace: Workspace,
    owner_id: uuid.UUID,
    template: WorkspaceTemplate,
) -> Report:
    report = Report(
        workspace_id=workspace.id,
        title=f"{workspace.name} Report",
        status=ReportStatus.DRAFT.value,
        created_by=owner_id,
    )
    for entry in get_template_report_section_entries(template.report_schema):
        report.sections.append(
            ReportSection(
                workspace_id=workspace.id,
                template_section_key=cast(str, entry.get("key")),
                title=cast(str, entry["title"]),
                body_markdown="",
                source_task_keys=get_template_report_source_task_keys(entry),
                source_result_ids=[],
                sort_order=cast(int, entry.get("sort_order", 0)),
                status=ReportSectionStatus.DRAFT.value,
            )
        )
    return report


def get_template_report_section_entries(
    report_schema: dict[str, object],
) -> list[dict[str, object]]:
    sections = report_schema.get("sections", [])
    if not isinstance(sections, list):
        return []

    normalized_sections: list[dict[str, object]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        if not isinstance(section.get("title"), str):
            continue
        normalized_sections.append(cast(dict[str, object], section))
    return normalized_sections


def get_template_report_source_task_keys(entry: dict[str, object]) -> list[str]:
    source_task_keys = entry.get("source_task_keys", [])
    if not isinstance(source_task_keys, list):
        return []
    return [item for item in source_task_keys if isinstance(item, str)]


async def list_workspaces_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[Workspace]:
    membership_subquery = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == user_id
    )
    result = await session.execute(
        select(Workspace)
        .where(
            or_(
                Workspace.owner_id == user_id,
                Workspace.id.in_(membership_subquery),
            )
        )
        .order_by(Workspace.created_at.desc())
    )
    return list(result.scalars().all())


async def get_workspace_for_user(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    allowed_roles: frozenset[str] = READ_ROLES,
) -> Workspace | None:
    result = await session.execute(
        select(Workspace, WorkspaceMember.role)
        .outerjoin(
            WorkspaceMember,
            (WorkspaceMember.workspace_id == Workspace.id) & (WorkspaceMember.user_id == user_id),
        )
        .where(Workspace.id == workspace_id)
    )
    row = result.first()
    if row is None:
        return None

    workspace = cast(Workspace, row[0])
    role = cast(str | None, row[1])
    if workspace.owner_id == user_id:
        return workspace
    if role in allowed_roles:
        return workspace
    return None


async def update_workspace(
    session: AsyncSession,
    workspace: Workspace,
    workspace_update: WorkspaceUpdate,
) -> Workspace:
    update_data = workspace_update.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value

    for field, value in update_data.items():
        setattr(workspace, field, value)

    await session.commit()
    await session.refresh(workspace)
    return workspace


async def delete_workspace(session: AsyncSession, workspace: Workspace) -> None:
    await session.delete(workspace)
    await session.commit()


async def list_workspace_members(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[WorkspaceMember]:
    result = await session.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    return list(result.scalars().all())


async def get_workspace_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember | None:
    result = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def add_workspace_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: WorkspaceMemberRole,
) -> WorkspaceMember:
    role_value = validate_assignable_member_role(role)
    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role_value,
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def update_workspace_member_role(
    session: AsyncSession,
    workspace: Workspace,
    member: WorkspaceMember,
    role: WorkspaceMemberRole,
) -> WorkspaceMember:
    ensure_not_workspace_owner(workspace, member)
    member.role = validate_assignable_member_role(role)
    await session.commit()
    await session.refresh(member)
    return member


async def remove_workspace_member(
    session: AsyncSession,
    workspace: Workspace,
    member: WorkspaceMember,
) -> None:
    ensure_not_workspace_owner(workspace, member)
    await session.delete(member)
    await session.commit()


def validate_assignable_member_role(role: WorkspaceMemberRole) -> str:
    role_value = role.value
    if role_value not in ASSIGNABLE_MEMBER_ROLES:
        raise WorkspaceMemberRoleError
    return role_value


def ensure_not_workspace_owner(workspace: Workspace, member: WorkspaceMember) -> None:
    if member.user_id == workspace.owner_id or member.role == WorkspaceMemberRole.OWNER.value:
        raise WorkspaceOwnerMemberError
