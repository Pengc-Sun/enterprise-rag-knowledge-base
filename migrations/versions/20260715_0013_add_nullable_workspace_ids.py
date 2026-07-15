"""add nullable workspace ids

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-15 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKSPACE_SCOPED_TABLES = (
    "knowledge_bases",
    "documents",
    "document_chunks",
    "conversations",
)


def upgrade() -> None:
    for table_name in WORKSPACE_SCOPED_TABLES:
        op.add_column(
            table_name,
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        )


def downgrade() -> None:
    for table_name in reversed(WORKSPACE_SCOPED_TABLES):
        op.drop_column(table_name, "workspace_id")
