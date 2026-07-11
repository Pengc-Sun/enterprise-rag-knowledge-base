import uuid

from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User


def test_knowledge_base_owner_relationship() -> None:
    user = User(
        id=uuid.uuid4(),
        email="owner@example.com",
        username="owner",
        hashed_password="hashed",
    )
    knowledge_base = KnowledgeBase(
        name="Engineering Handbook",
        description="Internal engineering documents",
        visibility=KnowledgeBaseVisibility.PRIVATE.value,
        owner=user,
    )

    assert knowledge_base.owner is user
    assert knowledge_base in user.knowledge_bases
    assert knowledge_base.visibility == "private"
