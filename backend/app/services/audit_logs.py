import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.audit import AuditAction, AuditLog, AuditResourceType


async def create_audit_log(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    action: AuditAction,
    resource_type: AuditResourceType,
    resource_id: uuid.UUID | None = None,
    metadata: dict[str, object] | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action.value,
        resource_type=resource_type.value,
        resource_id=resource_id,
        audit_metadata=metadata or {},
    )
    session.add(audit_log)
    await session.commit()
    await session.refresh(audit_log)
    return audit_log


async def list_audit_logs_for_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    limit: int = 100,
) -> list[AuditLog]:
    if limit <= 0:
        raise ValueError("limit must be positive")

    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.workspace_id == workspace_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
