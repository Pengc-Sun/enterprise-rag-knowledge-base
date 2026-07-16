"""update workspace template schemas

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-16 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.app.services.workspace_template_definitions import BUILT_IN_WORKSPACE_TEMPLATES

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPDATE_TEMPLATE_SQL = sa.text(
    """
    update workspace_templates
    set
        name = :name,
        description = :description,
        category = :category,
        version = :version,
        directory_schema = :directory_schema,
        analysis_task_schema = :analysis_task_schema,
        report_schema = :report_schema,
        updated_at = now()
    where id = :id
    """
).bindparams(
    sa.bindparam("directory_schema", type_=postgresql.JSONB),
    sa.bindparam("analysis_task_schema", type_=postgresql.JSONB),
    sa.bindparam("report_schema", type_=postgresql.JSONB),
)

LEGACY_TEMPLATE_SCHEMAS: tuple[dict[str, object], ...] = (
    {
        "id": "10000000-0000-4000-8000-000000000001",
        "directory_schema": {
            "directories": [
                {"name": "Documents", "path": "documents"},
                {"name": "Reports", "path": "reports"},
            ]
        },
        "analysis_task_schema": {
            "tasks": [
                {
                    "key": "document_summary",
                    "name": "Document Summary",
                    "task_type": "summary",
                }
            ]
        },
        "report_schema": {
            "sections": [
                {"title": "Overview", "source": "approved_findings"},
                {"title": "References", "source": "citations"},
            ]
        },
    },
    {
        "id": "10000000-0000-4000-8000-000000000002",
        "directory_schema": {
            "directories": [
                {"name": "Policies", "path": "policies"},
                {"name": "Evidence", "path": "evidence"},
                {"name": "Reports", "path": "reports"},
            ]
        },
        "analysis_task_schema": {
            "tasks": [
                {
                    "key": "policy_requirements",
                    "name": "Policy Requirement Extraction",
                    "task_type": "extraction",
                },
                {
                    "key": "policy_risk_review",
                    "name": "Policy Risk Review",
                    "task_type": "risk_review",
                },
            ]
        },
        "report_schema": {
            "sections": [
                {"title": "Executive Summary", "source": "approved_findings"},
                {"title": "Policy Requirements", "source": "approved_findings"},
                {"title": "Risk Findings", "source": "approved_findings"},
                {"title": "Citations", "source": "citations"},
            ]
        },
    },
    {
        "id": "10000000-0000-4000-8000-000000000003",
        "directory_schema": {
            "directories": [
                {"name": "Runbooks", "path": "runbooks"},
                {"name": "Incident Procedures", "path": "incidents"},
                {"name": "SLA", "path": "sla"},
            ]
        },
        "analysis_task_schema": {
            "tasks": [
                {
                    "key": "support_steps",
                    "name": "Support Step Extraction",
                    "task_type": "extraction",
                },
                {
                    "key": "incident_priority_summary",
                    "name": "Incident Priority Summary",
                    "task_type": "classification",
                },
            ]
        },
        "report_schema": {
            "sections": [
                {"title": "Support Scope", "source": "approved_findings"},
                {"title": "Priority Matrix", "source": "approved_findings"},
                {"title": "Runbook References", "source": "citations"},
            ]
        },
    },
    {
        "id": "10000000-0000-4000-8000-000000000004",
        "directory_schema": {
            "directories": [
                {"name": "Papers", "path": "papers"},
                {"name": "Notes", "path": "notes"},
                {"name": "Evidence Tables", "path": "evidence-tables"},
            ]
        },
        "analysis_task_schema": {
            "tasks": [
                {
                    "key": "evidence_table",
                    "name": "Evidence Table Extraction",
                    "task_type": "extraction",
                },
                {
                    "key": "paper_comparison",
                    "name": "Paper Comparison",
                    "task_type": "comparison",
                },
            ]
        },
        "report_schema": {
            "sections": [
                {"title": "Research Question", "source": "approved_findings"},
                {"title": "Evidence Table", "source": "approved_findings"},
                {"title": "Synthesis", "source": "approved_findings"},
                {"title": "References", "source": "citations"},
            ]
        },
    },
)

DOWNGRADE_TEMPLATE_SQL = sa.text(
    """
    update workspace_templates
    set
        directory_schema = :directory_schema,
        analysis_task_schema = :analysis_task_schema,
        report_schema = :report_schema,
        updated_at = now()
    where id = :id
    """
).bindparams(
    sa.bindparam("directory_schema", type_=postgresql.JSONB),
    sa.bindparam("analysis_task_schema", type_=postgresql.JSONB),
    sa.bindparam("report_schema", type_=postgresql.JSONB),
)


def upgrade() -> None:
    connection = op.get_bind()
    for template in BUILT_IN_WORKSPACE_TEMPLATES:
        connection.execute(
            UPDATE_TEMPLATE_SQL,
            {
                "id": template["id"],
                "name": template["name"],
                "description": template["description"],
                "category": template["category"].value,
                "version": template["version"],
                "directory_schema": template["directory_schema"],
                "analysis_task_schema": template["analysis_task_schema"],
                "report_schema": template["report_schema"],
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    for template in LEGACY_TEMPLATE_SCHEMAS:
        connection.execute(
            DOWNGRADE_TEMPLATE_SQL,
            {
                "id": template["id"],
                "directory_schema": template["directory_schema"],
                "analysis_task_schema": template["analysis_task_schema"],
                "report_schema": template["report_schema"],
            },
        )

