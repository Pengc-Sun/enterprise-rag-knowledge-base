"""seed workspace templates

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-15 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

workspace_templates_table = sa.table(
    "workspace_templates",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.String(length=255)),
    sa.column("description", sa.Text()),
    sa.column("category", sa.String(length=50)),
    sa.column("version", sa.String(length=50)),
    sa.column("is_active", sa.Boolean()),
    sa.column("directory_schema", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("analysis_task_schema", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("report_schema", postgresql.JSONB(astext_type=sa.Text())),
)

SEEDED_TEMPLATE_IDS = (
    "10000000-0000-4000-8000-000000000001",
    "10000000-0000-4000-8000-000000000002",
    "10000000-0000-4000-8000-000000000003",
    "10000000-0000-4000-8000-000000000004",
)


def upgrade() -> None:
    op.bulk_insert(
        workspace_templates_table,
        [
            {
                "id": "10000000-0000-4000-8000-000000000001",
                "name": "General Knowledge Workspace",
                "description": "A general-purpose workspace for private document Q&A.",
                "category": "general",
                "version": "1.0",
                "is_active": True,
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
                "name": "Policy Review Workspace",
                "description": (
                    "A workspace for reviewing company policies and compliance evidence."
                ),
                "category": "policy_review",
                "version": "1.0",
                "is_active": True,
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
                "name": "IT Support Workspace",
                "description": (
                    "A workspace for IT runbooks, incident procedures, and support answers."
                ),
                "category": "it_support",
                "version": "1.0",
                "is_active": True,
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
                "name": "Research Review Workspace",
                "description": (
                    "A workspace for literature review, evidence tables, and cited reports."
                ),
                "category": "research_review",
                "version": "1.0",
                "is_active": True,
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
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text("delete from workspace_templates where id = any(:template_ids)").bindparams(
            sa.bindparam(
                "template_ids",
                list(SEEDED_TEMPLATE_IDS),
                type_=postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            )
        )
    )
