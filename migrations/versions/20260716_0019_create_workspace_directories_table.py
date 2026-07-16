"""create workspace directories table

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-16 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_directories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
            ["parent_id"],
            ["workspace_directories.id"],
            name=op.f("fk_workspace_directories_parent_id_workspace_directories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_directories_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_directories")),
        sa.UniqueConstraint(
            "workspace_id",
            "path",
            name="uq_workspace_directories_workspace_path",
        ),
    )
    op.create_index(
        op.f("ix_workspace_directories_parent_id"),
        "workspace_directories",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workspace_directories_workspace_id"),
        "workspace_directories",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_workspace_directories_workspace_id"), table_name="workspace_directories")
    op.drop_index(op.f("ix_workspace_directories_parent_id"), table_name="workspace_directories")
    op.drop_table("workspace_directories")

