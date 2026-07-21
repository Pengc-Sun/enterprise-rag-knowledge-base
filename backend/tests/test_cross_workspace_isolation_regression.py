import uuid
from typing import Any

import pytest

from backend.app.services.analysis_tasks import list_review_queue_results
from backend.app.services.knowledge_bases import (
    get_knowledge_base_for_workspace,
    list_knowledge_bases_for_workspace,
)
from backend.app.services.reports import (
    ReportSectionSourceError,
    get_export_job_for_workspace,
    validate_report_section_source_results,
)
from backend.app.services.retrieval import (
    build_keyword_search_statement,
    build_vector_search_statement,
)


class FakeScalarResult:
    def __init__(self, items: list[object]) -> None:
        self.items = items

    def all(self) -> list[object]:
        return self.items


class FakeResult:
    def __init__(self, items: list[object] | None = None, scalar: object | None = None) -> None:
        self.items = items or []
        self.scalar = scalar

    def all(self) -> list[object]:
        return self.items

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.items)

    def scalar_one_or_none(self) -> object | None:
        return self.scalar


class FakeSession:
    def __init__(self, results: list[FakeResult] | None = None) -> None:
        self.results = results or []
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return self.results.pop(0) if self.results else FakeResult()


def statement_sql(statement: Any) -> str:
    return str(statement.compile())


def statement_params(statement: Any) -> dict[str, object]:
    return dict(statement.compile().params)


def assert_uuid_bound(statement: Any, value: uuid.UUID, *, minimum_count: int = 1) -> None:
    assert list(statement_params(statement).values()).count(value) >= minimum_count


@pytest.mark.asyncio
async def test_knowledge_base_queries_are_workspace_scoped() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    session: Any = FakeSession([FakeResult(), FakeResult()])

    await list_knowledge_bases_for_workspace(session, workspace_id)
    await get_knowledge_base_for_workspace(
        session,
        knowledge_base_id,
        workspace_id,
    )

    list_sql = statement_sql(session.statements[0])
    get_sql = statement_sql(session.statements[1])

    assert "knowledge_bases.workspace_id" in list_sql
    assert "knowledge_bases.workspace_id" in get_sql
    assert "knowledge_bases.id" in get_sql
    assert_uuid_bound(session.statements[0], workspace_id)
    assert_uuid_bound(session.statements[1], workspace_id)
    assert_uuid_bound(session.statements[1], knowledge_base_id)


def test_retrieval_queries_require_workspace_and_knowledge_base_boundaries() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()

    statements: list[Any] = [
        build_vector_search_statement(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            query_embedding=[1.0, 0.0, 0.0],
            limit=5,
        ),
        build_keyword_search_statement(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            query="policy",
            limit=5,
        ),
    ]

    for statement in statements:
        sql = statement_sql(statement)
        assert "document_chunks.workspace_id" in sql
        assert "document_chunks.knowledge_base_id" in sql
        assert_uuid_bound(statement, workspace_id)
        assert_uuid_bound(statement, knowledge_base_id)


@pytest.mark.asyncio
async def test_review_queue_requires_matching_result_and_task_workspace() -> None:
    workspace_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session: Any = FakeSession([FakeResult()])

    await list_review_queue_results(
        session,
        workspace_id,
        analysis_task_id=task_id,
        task_type="summary",
    )

    statement = session.statements[0]
    sql = statement_sql(statement)

    assert "analysis_results.workspace_id" in sql
    assert "analysis_tasks.workspace_id" in sql
    assert "analysis_results.analysis_task_id" in sql
    assert "analysis_tasks.task_type" in sql
    assert_uuid_bound(statement, workspace_id, minimum_count=2)
    assert_uuid_bound(statement, task_id)


@pytest.mark.asyncio
async def test_report_source_validation_requires_matching_result_and_task_workspace() -> None:
    workspace_id = uuid.uuid4()
    result_id = uuid.uuid4()
    session: Any = FakeSession([FakeResult(items=[])])

    with pytest.raises(ReportSectionSourceError):
        await validate_report_section_source_results(
            session,
            workspace_id,
            [str(result_id)],
        )

    statement = session.statements[0]
    sql = statement_sql(statement)

    assert "analysis_results.workspace_id" in sql
    assert "analysis_tasks.workspace_id" in sql
    assert "analysis_results.id" in sql
    assert_uuid_bound(statement, workspace_id, minimum_count=2)


@pytest.mark.asyncio
async def test_export_job_lookup_is_workspace_scoped() -> None:
    workspace_id = uuid.uuid4()
    export_id = uuid.uuid4()
    session: Any = FakeSession([FakeResult()])

    await get_export_job_for_workspace(
        session,
        workspace_id,
        export_id,
    )

    statement = session.statements[0]
    sql = statement_sql(statement)

    assert "export_jobs.workspace_id" in sql
    assert "export_jobs.id" in sql
    assert_uuid_bound(statement, workspace_id)
    assert_uuid_bound(statement, export_id)
