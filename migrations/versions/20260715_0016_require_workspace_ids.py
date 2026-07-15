"""require workspace ids

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-15 00:00:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKSPACE_SCOPED_TABLES = (
    "knowledge_bases",
    "documents",
    "document_chunks",
    "conversations",
)

WORKSPACE_FOREIGN_KEYS = {
    "knowledge_bases": "fk_knowledge_bases_workspace_id_workspaces",
    "documents": "fk_documents_workspace_id_workspaces",
    "document_chunks": "fk_document_chunks_workspace_id_workspaces",
    "conversations": "fk_conversations_workspace_id_workspaces",
}

WORKSPACE_INDEXES = {
    "knowledge_bases": "ix_knowledge_bases_workspace_id",
    "documents": "ix_documents_workspace_id",
    "document_chunks": "ix_document_chunks_workspace_id",
    "conversations": "ix_conversations_workspace_id",
}


def upgrade() -> None:
    for table_name in WORKSPACE_SCOPED_TABLES:
        op.alter_column(
            table_name,
            "workspace_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
        )
        op.create_index(
            WORKSPACE_INDEXES[table_name],
            table_name,
            ["workspace_id"],
            unique=False,
        )
        op.create_foreign_key(
            WORKSPACE_FOREIGN_KEYS[table_name],
            table_name,
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    for table_name in reversed(WORKSPACE_SCOPED_TABLES):
        op.drop_constraint(
            WORKSPACE_FOREIGN_KEYS[table_name],
            table_name,
            type_="foreignkey",
        )
        op.drop_index(WORKSPACE_INDEXES[table_name], table_name=table_name)
        op.alter_column(
            table_name,
            "workspace_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=True,
        )
