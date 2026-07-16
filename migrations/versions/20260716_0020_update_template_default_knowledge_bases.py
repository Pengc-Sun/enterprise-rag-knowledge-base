"""update template default knowledge bases

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-16 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.app.services.workspace_template_definitions import BUILT_IN_WORKSPACE_TEMPLATES

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPDATE_TEMPLATE_DIRECTORY_SCHEMA_SQL = sa.text(
    """
    update workspace_templates
    set
        directory_schema = :directory_schema,
        updated_at = now()
    where id = :id
    """
).bindparams(sa.bindparam("directory_schema", type_=postgresql.JSONB))

REMOVE_TEMPLATE_KNOWLEDGE_BASE_SCHEMA_SQL = sa.text(
    """
    update workspace_templates
    set
        directory_schema = directory_schema - 'knowledge_bases',
        updated_at = now()
    where id = any(:template_ids)
    """
).bindparams(
    sa.bindparam(
        "template_ids",
        [template["id"] for template in BUILT_IN_WORKSPACE_TEMPLATES],
        type_=postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
    )
)


def upgrade() -> None:
    connection = op.get_bind()
    for template in BUILT_IN_WORKSPACE_TEMPLATES:
        connection.execute(
            UPDATE_TEMPLATE_DIRECTORY_SCHEMA_SQL,
            {
                "id": template["id"],
                "directory_schema": template["directory_schema"],
            },
        )


def downgrade() -> None:
    op.execute(REMOVE_TEMPLATE_KNOWLEDGE_BASE_SCHEMA_SQL)

