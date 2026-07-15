"""backfill v1 data workspace ids

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-15 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_WORKSPACE_SLUG_PREFIX = "v1-default-"

BACKFILL_KNOWLEDGE_BASE_WORKSPACES_SQL = sa.text(
    f"""
    update knowledge_bases
    set workspace_id = workspaces.id
    from workspaces
    where knowledge_bases.workspace_id is null
      and workspaces.owner_id = knowledge_bases.owner_id
      and workspaces.slug = '{DEFAULT_WORKSPACE_SLUG_PREFIX}' ||
          replace(knowledge_bases.owner_id::text, '-', '')
    """
)

BACKFILL_DOCUMENT_WORKSPACES_SQL = sa.text(
    """
    update documents
    set workspace_id = knowledge_bases.workspace_id
    from knowledge_bases
    where documents.workspace_id is null
      and documents.knowledge_base_id = knowledge_bases.id
      and knowledge_bases.workspace_id is not null
    """
)

BACKFILL_CHUNK_WORKSPACES_SQL = sa.text(
    """
    update document_chunks
    set workspace_id = documents.workspace_id
    from documents
    where document_chunks.workspace_id is null
      and document_chunks.document_id = documents.id
      and documents.workspace_id is not null
    """
)

BACKFILL_CONVERSATION_WORKSPACES_SQL = sa.text(
    """
    update conversations
    set workspace_id = knowledge_bases.workspace_id
    from knowledge_bases
    where conversations.workspace_id is null
      and conversations.knowledge_base_id = knowledge_bases.id
      and knowledge_bases.workspace_id is not null
    """
)

CLEAR_CONVERSATION_WORKSPACES_SQL = sa.text(
    f"""
    update conversations
    set workspace_id = null
    from workspaces
    where conversations.workspace_id = workspaces.id
      and workspaces.slug like '{DEFAULT_WORKSPACE_SLUG_PREFIX}%'
    """
)

CLEAR_CHUNK_WORKSPACES_SQL = sa.text(
    f"""
    update document_chunks
    set workspace_id = null
    from workspaces
    where document_chunks.workspace_id = workspaces.id
      and workspaces.slug like '{DEFAULT_WORKSPACE_SLUG_PREFIX}%'
    """
)

CLEAR_DOCUMENT_WORKSPACES_SQL = sa.text(
    f"""
    update documents
    set workspace_id = null
    from workspaces
    where documents.workspace_id = workspaces.id
      and workspaces.slug like '{DEFAULT_WORKSPACE_SLUG_PREFIX}%'
    """
)

CLEAR_KNOWLEDGE_BASE_WORKSPACES_SQL = sa.text(
    f"""
    update knowledge_bases
    set workspace_id = null
    from workspaces
    where knowledge_bases.workspace_id = workspaces.id
      and workspaces.slug like '{DEFAULT_WORKSPACE_SLUG_PREFIX}%'
    """
)


def upgrade() -> None:
    op.execute(BACKFILL_KNOWLEDGE_BASE_WORKSPACES_SQL)
    op.execute(BACKFILL_DOCUMENT_WORKSPACES_SQL)
    op.execute(BACKFILL_CHUNK_WORKSPACES_SQL)
    op.execute(BACKFILL_CONVERSATION_WORKSPACES_SQL)


def downgrade() -> None:
    op.execute(CLEAR_CONVERSATION_WORKSPACES_SQL)
    op.execute(CLEAR_CHUNK_WORKSPACES_SQL)
    op.execute(CLEAR_DOCUMENT_WORKSPACES_SQL)
    op.execute(CLEAR_KNOWLEDGE_BASE_WORKSPACES_SQL)
