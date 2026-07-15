"""create default workspaces for v1 owners

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-15 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_WORKSPACE_NAME = "Default Workspace"
DEFAULT_WORKSPACE_DESCRIPTION = (
    "Auto-created during v2.0 migration for existing v1.0 knowledge bases."
)
DEFAULT_WORKSPACE_SLUG_PREFIX = "v1-default-"

CREATE_DEFAULT_WORKSPACES_SQL = sa.text(
    f"""
    with v1_owners as (
        select distinct owner_id
        from knowledge_bases
    ),
    default_workspaces as (
        select
            (
                substr(md5(owner_id::text || '|default-workspace'), 1, 8) || '-' ||
                substr(md5(owner_id::text || '|default-workspace'), 9, 4) || '-' ||
                substr(md5(owner_id::text || '|default-workspace'), 13, 4) || '-' ||
                substr(md5(owner_id::text || '|default-workspace'), 17, 4) || '-' ||
                substr(md5(owner_id::text || '|default-workspace'), 21, 12)
            )::uuid as workspace_id,
            owner_id,
            '{DEFAULT_WORKSPACE_SLUG_PREFIX}' || replace(owner_id::text, '-', '') as slug
        from v1_owners
    )
    insert into workspaces (
        id,
        name,
        slug,
        description,
        owner_id,
        template_id,
        status,
        created_at,
        updated_at
    )
    select
        workspace_id,
        '{DEFAULT_WORKSPACE_NAME}',
        slug,
        '{DEFAULT_WORKSPACE_DESCRIPTION}',
        owner_id,
        null,
        'active',
        now(),
        now()
    from default_workspaces
    on conflict do nothing
    """
)

CREATE_DEFAULT_WORKSPACE_MEMBERS_SQL = sa.text(
    """
    with v1_owners as (
        select distinct owner_id
        from knowledge_bases
    ),
    default_workspaces as (
        select
            (
                substr(md5(owner_id::text || '|default-workspace'), 1, 8) || '-' ||
                substr(md5(owner_id::text || '|default-workspace'), 9, 4) || '-' ||
                substr(md5(owner_id::text || '|default-workspace'), 13, 4) || '-' ||
                substr(md5(owner_id::text || '|default-workspace'), 17, 4) || '-' ||
                substr(md5(owner_id::text || '|default-workspace'), 21, 12)
            )::uuid as workspace_id,
            (
                substr(md5(owner_id::text || '|default-workspace-member'), 1, 8) || '-' ||
                substr(md5(owner_id::text || '|default-workspace-member'), 9, 4) || '-' ||
                substr(md5(owner_id::text || '|default-workspace-member'), 13, 4) || '-' ||
                substr(md5(owner_id::text || '|default-workspace-member'), 17, 4) || '-' ||
                substr(md5(owner_id::text || '|default-workspace-member'), 21, 12)
            )::uuid as member_id,
            owner_id
        from v1_owners
    )
    insert into workspace_members (
        id,
        workspace_id,
        user_id,
        role,
        created_at,
        updated_at
    )
    select
        member_id,
        workspaces.id,
        default_workspaces.owner_id,
        'owner',
        now(),
        now()
    from default_workspaces
    join workspaces on workspaces.id = default_workspaces.workspace_id
    on conflict (workspace_id, user_id) do nothing
    """
)

DELETE_DEFAULT_WORKSPACE_MEMBERS_SQL = sa.text(
    """
    delete from workspace_members
    where workspace_id in (
        select id
        from workspaces
        where description = :description
          and slug like :slug_pattern
    )
      and role = 'owner'
    """
).bindparams(
    sa.bindparam("description", DEFAULT_WORKSPACE_DESCRIPTION),
    sa.bindparam("slug_pattern", f"{DEFAULT_WORKSPACE_SLUG_PREFIX}%"),
)

DELETE_DEFAULT_WORKSPACES_SQL = sa.text(
    """
    delete from workspaces
    where description = :description
      and slug like :slug_pattern
    """
).bindparams(
    sa.bindparam("description", DEFAULT_WORKSPACE_DESCRIPTION),
    sa.bindparam("slug_pattern", f"{DEFAULT_WORKSPACE_SLUG_PREFIX}%"),
)


def upgrade() -> None:
    op.execute(CREATE_DEFAULT_WORKSPACES_SQL)
    op.execute(CREATE_DEFAULT_WORKSPACE_MEMBERS_SQL)


def downgrade() -> None:
    op.execute(DELETE_DEFAULT_WORKSPACE_MEMBERS_SQL)
    op.execute(DELETE_DEFAULT_WORKSPACES_SQL)
