import uuid

from backend.app.models.knowledge_base import (
    KnowledgeBase,
    KnowledgeBaseMember,
    KnowledgeBasePermission,
    KnowledgeBaseVisibility,
)
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


def test_knowledge_base_member_relationship() -> None:
    user = User(
        id=uuid.uuid4(),
        email="viewer@example.com",
        username="viewer",
        hashed_password="hashed",
    )
    knowledge_base = KnowledgeBase(
        id=uuid.uuid4(),
        name="Engineering Handbook",
        owner_id=uuid.uuid4(),
    )
    member = KnowledgeBaseMember(
        knowledge_base=knowledge_base,
        user=user,
        permission=KnowledgeBasePermission.VIEWER.value,
    )

    assert member.knowledge_base is knowledge_base
    assert member.user is user
    assert member in knowledge_base.members
    assert member in user.knowledge_base_memberships
    assert member.permission == "viewer"
