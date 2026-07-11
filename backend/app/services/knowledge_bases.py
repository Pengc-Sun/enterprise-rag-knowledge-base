import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate


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
    await session.commit()
    await session.refresh(knowledge_base)
    return knowledge_base


async def list_knowledge_bases_for_owner(
    session: AsyncSession,
    owner_id: uuid.UUID,
) -> list[KnowledgeBase]:
    result = await session.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.owner_id == owner_id)
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

