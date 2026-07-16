import uuid

from backend.app.models.audit import AuditAction, AuditLog, AuditResourceType


def test_audit_action_values() -> None:
    assert AuditAction.WORKSPACE_CREATED.value == "workspace.created"
    assert AuditAction.WORKSPACE_UPDATED.value == "workspace.updated"
    assert AuditAction.WORKSPACE_DELETED.value == "workspace.deleted"
    assert AuditAction.WORKSPACE_MEMBER_ADDED.value == "workspace_member.added"
    assert AuditAction.WORKSPACE_MEMBER_UPDATED.value == "workspace_member.updated"
    assert AuditAction.WORKSPACE_MEMBER_REMOVED.value == "workspace_member.removed"
    assert AuditAction.DOCUMENT_UPLOADED.value == "document.uploaded"
    assert AuditAction.DOCUMENT_REPROCESSED.value == "document.reprocessed"
    assert AuditAction.DOCUMENT_DELETED.value == "document.deleted"


def test_audit_log_stores_actor_resource_and_metadata() -> None:
    workspace_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    document_id = uuid.uuid4()

    audit_log = AuditLog(
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=AuditAction.DOCUMENT_UPLOADED.value,
        resource_type=AuditResourceType.DOCUMENT.value,
        resource_id=document_id,
        audit_metadata={"filename": "policy.pdf", "chunk_count": 3},
    )

    assert audit_log.workspace_id == workspace_id
    assert audit_log.actor_user_id == actor_user_id
    assert audit_log.action == "document.uploaded"
    assert audit_log.resource_type == "document"
    assert audit_log.resource_id == document_id
    assert audit_log.audit_metadata == {"filename": "policy.pdf", "chunk_count": 3}
