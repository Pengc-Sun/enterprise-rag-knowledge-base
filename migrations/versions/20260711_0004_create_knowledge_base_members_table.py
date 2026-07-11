"""create knowledge base members table

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-11 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            name=op.f("fk_knowledge_base_members_knowledge_base_id_knowledge_bases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_knowledge_base_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_base_members")),
        sa.UniqueConstraint(
            "knowledge_base_id",
            "user_id",
            name="uq_knowledge_base_members_knowledge_base_id_user_id",
        ),
    )
    op.create_index(
        op.f("ix_knowledge_base_members_knowledge_base_id"),
        "knowledge_base_members",
        ["knowledge_base_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_base_members_user_id"),
        "knowledge_base_members",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_base_members_user_id"), table_name="knowledge_base_members")
    op.drop_index(
        op.f("ix_knowledge_base_members_knowledge_base_id"),
        table_name="knowledge_base_members",
    )
    op.drop_table("knowledge_base_members")
