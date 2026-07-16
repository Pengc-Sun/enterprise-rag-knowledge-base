import uuid

import pytest

from backend.app.models.audit import AuditAction, AuditLog, AuditResourceType
from backend.app.services.audit_logs import create_audit_log, list_audit_logs_for_workspace


class FakeScalars:
    def __init__(self, logs: list[AuditLog]) -> None:
        self.logs = logs

    def all(self) -> list[AuditLog]:
        return self.logs


class FakeListResult:
    def __init__(self, logs: list[AuditLog]) -> None:
        self.logs = logs

    def scalars(self) -> FakeScalars:
        return FakeScalars(self.logs)


class FakeAuditSession:
    def __init__(self, logs: list[AuditLog] | None = None) -> None:
        self.added: AuditLog | None = None
        self.logs = logs or []
        self.statement: object | None = None
        self.committed = False
        self.refreshed: object | None = None

    def add(self, instance: object) -> None:
        self.added = instance  # type: ignore[assignment]

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = instance

    async def execute(self, statement: object) -> FakeListResult:
        self.statement = statement
        return FakeListResult(self.logs)


@pytest.mark.asyncio
async def test_create_audit_log_persists_structured_event() -> None:
    session = FakeAuditSession()
    workspace_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    document_id = uuid.uuid4()

    audit_log = await create_audit_log(
        session,  # type: ignore[arg-type]
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=AuditAction.DOCUMENT_REPROCESSED,
        resource_type=AuditResourceType.DOCUMENT,
        resource_id=document_id,
        metadata={"chunk_count": 4},
    )

    assert session.added is audit_log
    assert session.committed is True
    assert session.refreshed is audit_log
    assert audit_log.workspace_id == workspace_id
    assert audit_log.actor_user_id == actor_user_id
    assert audit_log.action == "document.reprocessed"
    assert audit_log.resource_type == "document"
    assert audit_log.resource_id == document_id
    assert audit_log.audit_metadata == {"chunk_count": 4}


@pytest.mark.asyncio
async def test_list_audit_logs_for_workspace_filters_and_orders() -> None:
    workspace_id = uuid.uuid4()
    log = AuditLog(
        workspace_id=workspace_id,
        actor_user_id=uuid.uuid4(),
        action=AuditAction.WORKSPACE_CREATED.value,
        resource_type=AuditResourceType.WORKSPACE.value,
        resource_id=workspace_id,
        audit_metadata={},
    )
    session = FakeAuditSession([log])

    logs = await list_audit_logs_for_workspace(
        session,  # type: ignore[arg-type]
        workspace_id,
        limit=25,
    )

    assert logs == [log]
    assert session.statement is not None
    compiled = str(session.statement.compile(compile_kwargs={"literal_binds": False}))  # type: ignore[attr-defined]
    params = session.statement.compile(compile_kwargs={"literal_binds": False}).params  # type: ignore[attr-defined]
    assert "audit_logs.workspace_id" in compiled
    assert "ORDER BY audit_logs.created_at DESC" in compiled
    assert params["workspace_id_1"] == workspace_id
    assert params["param_1"] == 25


@pytest.mark.asyncio
async def test_list_audit_logs_for_workspace_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        await list_audit_logs_for_workspace(
            FakeAuditSession(),  # type: ignore[arg-type]
            uuid.uuid4(),
            limit=0,
        )
