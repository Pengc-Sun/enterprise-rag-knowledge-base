"""create review decisions table

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-17 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("original_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("edited_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analysis_result_id"],
            ["analysis_results.id"],
            name=op.f("fk_review_decisions_analysis_result_id_analysis_results"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.id"],
            name=op.f("fk_review_decisions_reviewer_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_review_decisions_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_decisions")),
    )
    op.create_index(
        op.f("ix_review_decisions_analysis_result_id"),
        "review_decisions",
        ["analysis_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_decisions_decision"),
        "review_decisions",
        ["decision"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_decisions_reviewer_id"),
        "review_decisions",
        ["reviewer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_decisions_workspace_id"),
        "review_decisions",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_review_decisions_workspace_id"), table_name="review_decisions")
    op.drop_index(op.f("ix_review_decisions_reviewer_id"), table_name="review_decisions")
    op.drop_index(op.f("ix_review_decisions_decision"), table_name="review_decisions")
    op.drop_index(
        op.f("ix_review_decisions_analysis_result_id"),
        table_name="review_decisions",
    )
    op.drop_table("review_decisions")
