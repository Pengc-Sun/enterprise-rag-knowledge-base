import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.analysis import AnalysisResult, AnalysisTask, AnalysisTaskStatus
from backend.app.schemas.analysis import AnalysisResultCreate, AnalysisTaskCreate


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

