"""add document chunk full text search

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-12 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SEARCH_VECTOR_EXPRESSION = (
    "to_tsvector('simple'::regconfig, coalesce(section_title, '') || ' ' || content)"
)


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(SEARCH_VECTOR_EXPRESSION, persisted=True),
            nullable=True,
        ),
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_search_vector_gin "
        "ON document_chunks "
        "USING gin (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector_gin")
    op.drop_column("document_chunks", "search_vector")
