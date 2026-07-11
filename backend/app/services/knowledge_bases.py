import uuid
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.knowledge_base import (
    KnowledgeBase,
    KnowledgeBaseMember,
    KnowledgeBasePermission,
)
from backend.app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate

READ_PERMISSIONS = frozenset(
    {
        KnowledgeBasePermission.OWNER.value,
        KnowledgeBasePermission.EDITOR.value,
        KnowledgeBasePermission.VIEWER.value,
    }
)
WRITE_PERMISSIONS = frozenset(
    {
        KnowledgeBasePermission.OWNER.value,
        KnowledgeBasePermission.EDITOR.value,
    }
)
OWNER_PERMISSIONS = frozenset({KnowledgeBasePermission.OWNER.value})


async def create_knowledge_base(
    session: AsyncSession,
    owner_id: uuid.UUID,
    knowledge_base_create: KnowledgeBaseCreate,
) -> KnowledgeBase:
    knowledge_base = KnowledgeBase(
        name=knowledge_base_create.name,
        description=knowledge_base_create.description,
        visibility=knowledge_base_create.visibility.value,
        owner_id=owner_id,
    )
    session.add(knowledge_base)
    await session.flush()
    session.add(
        KnowledgeBaseMember(
            knowledge_base_id=knowledge_base.id,
            user_id=owner_id,
            permission=KnowledgeBasePermission.OWNER.value,
        )
    )
    await session.commit()
    await session.refresh(knowledge_base)
    return knowledge_base


async def list_knowledge_bases_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[KnowledgeBase]:
    membership_subquery = select(KnowledgeBaseMember.knowledge_base_id).where(
        KnowledgeBaseMember.user_id == user_id
    )
    result = await session.execute(
        select(KnowledgeBase)
        .where(
            or_(
                KnowledgeBase.owner_id == user_id,
                KnowledgeBase.id.in_(membership_subquery),
            )
        )
        .order_by(KnowledgeBase.created_at.desc())
    )
    return list(result.scalars().all())


async def get_knowledge_base_for_owner(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> KnowledgeBase | None:
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.owner_id == owner_id,
        )
    )
    return result.scalar_one_or_none()


async def get_knowledge_base_for_user(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    user_id: uuid.UUID,
    allowed_permissions: frozenset[str] = READ_PERMISSIONS,
) -> KnowledgeBase | None:
    result = await session.execute(
        select(KnowledgeBase, KnowledgeBaseMember.permission)
        .outerjoin(
            KnowledgeBaseMember,
            (KnowledgeBaseMember.knowledge_base_id == KnowledgeBase.id)
            & (KnowledgeBaseMember.user_id == user_id),
        )
        .where(KnowledgeBase.id == knowledge_base_id)
    )
    row = result.first()
    if row is None:
        return None

    knowledge_base = cast(KnowledgeBase, row[0])
    permission = cast(str | None, row[1])
    if knowledge_base.owner_id == user_id:
        return knowledge_base
    if permission in allowed_permissions:
        return knowledge_base
    return None


async def update_knowledge_base(
    session: AsyncSession,
    knowledge_base: KnowledgeBase,
    knowledge_base_update: KnowledgeBaseUpdate,
) -> KnowledgeBase:
    update_data = knowledge_base_update.model_dump(exclude_unset=True)
    if "visibility" in update_data and update_data["visibility"] is not None:
        update_data["visibility"] = update_data["visibility"].value

    for field, value in update_data.items():
        setattr(knowledge_base, field, value)

    await session.commit()
    await session.refresh(knowledge_base)
    return knowledge_base


async def delete_knowledge_base(session: AsyncSession, knowledge_base: KnowledgeBase) -> None:
    await session.delete(knowledge_base)
    await session.commit()
