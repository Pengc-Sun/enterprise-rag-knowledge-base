"""create analysis tasks and reports

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-16 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_task_key", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("input_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["created_by"],
            ["users.id"],
            name=op.f("fk_analysis_tasks_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_analysis_tasks_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_tasks")),
    )
    op.create_index(
        op.f("ix_analysis_tasks_created_by"),
        "analysis_tasks",
        ["created_by"],
        unique=False,
    )
    op.create_index(op.f("ix_analysis_tasks_status"), "analysis_tasks", ["status"], unique=False)
    op.create_index(
        op.f("ix_analysis_tasks_task_type"),
        "analysis_tasks",
        ["task_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_tasks_template_task_key"),
        "analysis_tasks",
        ["template_task_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_tasks_workspace_id"),
        "analysis_tasks",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["created_by"],
            ["users.id"],
            name=op.f("fk_reports_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_reports_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(op.f("ix_reports_created_by"), "reports", ["created_by"], unique=False)
    op.create_index(op.f("ix_reports_status"), "reports", ["status"], unique=False)
    op.create_index(op.f("ix_reports_workspace_id"), "reports", ["workspace_id"], unique=False)

    op.create_table(
        "report_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_section_key", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("source_task_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_result_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
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
            ["report_id"],
            ["reports.id"],
            name=op.f("fk_report_sections_report_id_reports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_report_sections_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_sections")),
    )
    op.create_index(
        op.f("ix_report_sections_report_id"),
        "report_sections",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_sections_status"),
        "report_sections",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_sections_template_section_key"),
        "report_sections",
        ["template_section_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_sections_workspace_id"),
        "report_sections",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_report_sections_workspace_id"), table_name="report_sections")
    op.drop_index(op.f("ix_report_sections_template_section_key"), table_name="report_sections")
    op.drop_index(op.f("ix_report_sections_status"), table_name="report_sections")
    op.drop_index(op.f("ix_report_sections_report_id"), table_name="report_sections")
    op.drop_table("report_sections")
    op.drop_index(op.f("ix_reports_workspace_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_status"), table_name="reports")
    op.drop_index(op.f("ix_reports_created_by"), table_name="reports")
    op.drop_table("reports")
    op.drop_index(op.f("ix_analysis_tasks_workspace_id"), table_name="analysis_tasks")
    op.drop_index(op.f("ix_analysis_tasks_template_task_key"), table_name="analysis_tasks")
    op.drop_index(op.f("ix_analysis_tasks_task_type"), table_name="analysis_tasks")
    op.drop_index(op.f("ix_analysis_tasks_status"), table_name="analysis_tasks")
    op.drop_index(op.f("ix_analysis_tasks_created_by"), table_name="analysis_tasks")
    op.drop_table("analysis_tasks")

