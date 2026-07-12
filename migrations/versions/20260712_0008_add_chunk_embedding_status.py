"""add chunk embedding status

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-12 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding_status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column("document_chunks", sa.Column("embedding_error", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_document_chunks_embedding_status"),
        "document_chunks",
        ["embedding_status"],
        unique=False,
    )
    op.alter_column("document_chunks", "embedding_status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_chunks_embedding_status"), table_name="document_chunks")
    op.drop_column("document_chunks", "embedding_error")
    op.drop_column("document_chunks", "embedding_status")
