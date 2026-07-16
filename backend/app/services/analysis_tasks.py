import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.analysis import (
    AnalysisResult,
    AnalysisResultStatus,
    AnalysisTask,
    AnalysisTaskStatus,
)
from backend.app.models.document import DocumentChunk
from backend.app.schemas.analysis import AnalysisResultCreate, AnalysisTaskCreate

DEFAULT_ANALYSIS_CONTEXT_LIMIT = 8
LOCAL_ANALYSIS_PROVIDER = "local"
LOCAL_ANALYSIS_MODEL = "workspace-scoped-retrieval"


async def list_workspace_analysis_tasks(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[AnalysisTask]:
    result = await session.execute(
        select(AnalysisTask)
        .where(AnalysisTask.workspace_id == workspace_id)
        .order_by(AnalysisTask.created_at.asc(), AnalysisTask.name.asc())
    )
    return list(result.scalars().all())


async def get_workspace_analysis_task(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
) -> AnalysisTask | None:
    result = await session.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == analysis_task_id,
            AnalysisTask.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def create_workspace_analysis_task(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    created_by: uuid.UUID,
    task_create: AnalysisTaskCreate,
) -> AnalysisTask:
    task = AnalysisTask(
        workspace_id=workspace_id,
        template_task_key=task_create.template_task_key,
        name=task_create.name,
        description=task_create.description,
        task_type=task_create.task_type,
        status=AnalysisTaskStatus.PENDING.value,
        input_scope=task_create.input_scope,
        output_schema=task_create.output_schema,
        created_by=created_by,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def list_analysis_results_for_task(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
) -> list[AnalysisResult]:
    result = await session.execute(
        select(AnalysisResult)
        .where(
            AnalysisResult.workspace_id == workspace_id,
            AnalysisResult.analysis_task_id == analysis_task_id,
        )
        .order_by(AnalysisResult.created_at.desc())
    )
    return list(result.scalars().all())


async def get_analysis_result_for_task(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    analysis_result_id: uuid.UUID,
) -> AnalysisResult | None:
    result = await session.execute(
        select(AnalysisResult).where(
            AnalysisResult.id == analysis_result_id,
            AnalysisResult.workspace_id == workspace_id,
            AnalysisResult.analysis_task_id == analysis_task_id,
        )
    )
    return result.scalar_one_or_none()


async def create_analysis_result_for_task(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    result_create: AnalysisResultCreate,
) -> AnalysisResult:
    analysis_result = AnalysisResult(
        workspace_id=workspace_id,
        analysis_task_id=analysis_task_id,
        status=result_create.status.value,
        result=result_create.result,
        citations=result_create.citations,
        confidence=result_create.confidence,
        model=result_create.model,
        provider=result_create.provider,
        token_usage=result_create.token_usage,
    )
    session.add(analysis_result)
    await session.commit()
    await session.refresh(analysis_result)
    return analysis_result


async def execute_analysis_task(
    session: AsyncSession,
    task: AnalysisTask,
) -> AnalysisResult:
    task.status = AnalysisTaskStatus.RUNNING.value
    chunks = await retrieve_analysis_context_chunks(session, task)
    analysis_result = AnalysisResult(
        workspace_id=task.workspace_id,
        analysis_task_id=task.id,
        status=AnalysisResultStatus.AI_GENERATED.value,
        result=build_deterministic_analysis_result(task, chunks),
        citations=build_analysis_citations(chunks),
        confidence=None,
        model=LOCAL_ANALYSIS_MODEL,
        provider=LOCAL_ANALYSIS_PROVIDER,
        token_usage={},
    )
    task.status = AnalysisTaskStatus.COMPLETED.value
    session.add(analysis_result)
    await session.commit()
    await session.refresh(task)
    await session.refresh(analysis_result)
    return analysis_result


async def retrieve_analysis_context_chunks(
    session: AsyncSession,
    task: AnalysisTask,
) -> list[DocumentChunk]:
    statement = build_analysis_context_statement(task)
    result = await session.execute(statement)
    return list(result.scalars().all())


def build_analysis_context_statement(task: AnalysisTask) -> Select[tuple[DocumentChunk]]:
    statement = (
        select(DocumentChunk)
        .options(selectinload(DocumentChunk.document))
        .where(DocumentChunk.workspace_id == task.workspace_id)
        .order_by(DocumentChunk.created_at.asc(), DocumentChunk.chunk_index.asc())
        .limit(get_analysis_context_limit(task.input_scope))
    )

    knowledge_base_ids = get_scope_uuid_values(
        task.input_scope,
        singular_key="knowledge_base_id",
        plural_key="knowledge_base_ids",
    )
    if knowledge_base_ids:
        statement = statement.where(DocumentChunk.knowledge_base_id.in_(knowledge_base_ids))

    document_ids = get_scope_uuid_values(
        task.input_scope,
        singular_key="document_id",
        plural_key="document_ids",
    )
    if document_ids:
        statement = statement.where(DocumentChunk.document_id.in_(document_ids))

    return statement


def get_analysis_context_limit(input_scope: dict[str, object]) -> int:
    limit = input_scope.get("limit", DEFAULT_ANALYSIS_CONTEXT_LIMIT)
    if isinstance(limit, int) and limit > 0:
        return limit
    return DEFAULT_ANALYSIS_CONTEXT_LIMIT


def get_scope_uuid_values(
    input_scope: dict[str, object],
    *,
    singular_key: str,
    plural_key: str,
) -> tuple[uuid.UUID, ...]:
    values: list[uuid.UUID] = []
    singular_value = input_scope.get(singular_key)
    if singular_value is not None:
        parsed_value = parse_scope_uuid(singular_value)
        if parsed_value is not None:
            values.append(parsed_value)

    plural_values = input_scope.get(plural_key)
    if isinstance(plural_values, list):
        for item in plural_values:
            parsed_value = parse_scope_uuid(item)
            if parsed_value is not None:
                values.append(parsed_value)

    return tuple(dict.fromkeys(values))


def parse_scope_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def build_deterministic_analysis_result(
    task: AnalysisTask,
    chunks: list[DocumentChunk],
) -> dict[str, object]:
    findings = [
        {
            "chunk_id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "page_number": chunk.page_number,
            "text": chunk.content,
        }
        for chunk in chunks
    ]
    return {
        "task_id": str(task.id),
        "template_task_key": task.template_task_key,
        "task_type": task.task_type,
        "summary": build_analysis_summary(task, chunks),
        "findings": findings,
        "chunk_count": len(chunks),
    }


def build_analysis_summary(task: AnalysisTask, chunks: list[DocumentChunk]) -> str:
    if not chunks:
        return f"No workspace context was found for analysis task '{task.name}'."
    return f"Retrieved {len(chunks)} workspace chunk(s) for analysis task '{task.name}'."


def build_analysis_citations(chunks: list[DocumentChunk]) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    for chunk in chunks:
        document = getattr(chunk, "document", None)
        citations.append(
            {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "document_name": getattr(document, "filename", None),
                "knowledge_base_id": str(chunk.knowledge_base_id),
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
            }
        )
    return citations
