from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class AuditAction(StrEnum):
    WORKSPACE_CREATED = "workspace.created"
    WORKSPACE_UPDATED = "workspace.updated"
    WORKSPACE_DELETED = "workspace.deleted"
    WORKSPACE_MEMBER_ADDED = "workspace_member.added"
    WORKSPACE_MEMBER_UPDATED = "workspace_member.updated"
    WORKSPACE_MEMBER_REMOVED = "workspace_member.removed"
    WORKSPACE_DIRECTORY_CREATED = "workspace_directory.created"
    WORKSPACE_DIRECTORY_UPDATED = "workspace_directory.updated"
    WORKSPACE_DIRECTORY_DELETED = "workspace_directory.deleted"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_REPROCESSED = "document.reprocessed"
    DOCUMENT_DELETED = "document.deleted"


class AuditResourceType(StrEnum):
    WORKSPACE = "workspace"
    WORKSPACE_MEMBER = "workspace_member"
    WORKSPACE_DIRECTORY = "workspace_directory"
    DOCUMENT = "document"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        index=True,
        nullable=True,
    )
    audit_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
