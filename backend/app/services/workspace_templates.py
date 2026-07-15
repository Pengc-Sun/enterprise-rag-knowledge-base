import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.workspace import WorkspaceTemplate


async def list_active_workspace_templates(session: AsyncSession) -> list[WorkspaceTemplate]:
    result = await session.execute(
        select(WorkspaceTemplate)
        .where(WorkspaceTemplate.is_active.is_(True))
        .order_by(WorkspaceTemplate.category.asc(), WorkspaceTemplate.name.asc())
    )
    return list(result.scalars().all())


async def get_active_workspace_template(
    session: AsyncSession,
    template_id: uuid.UUID,
) -> WorkspaceTemplate | None:
    result = await session.execute(
        select(WorkspaceTemplate).where(
            WorkspaceTemplate.id == template_id,
            WorkspaceTemplate.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
