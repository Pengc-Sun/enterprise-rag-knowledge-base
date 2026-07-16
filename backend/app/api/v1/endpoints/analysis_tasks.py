import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.db.session import get_db_session
from backend.app.models.analysis import AnalysisResult, AnalysisTask
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.analysis import (
    AnalysisResultCreate,
    AnalysisResultRead,
    AnalysisTaskCreate,
    AnalysisTaskRead,
)
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.analysis_tasks import (
    create_analysis_result_for_task,
    create_workspace_analysis_task,
    execute_analysis_task,
    get_analysis_result_for_task,
    get_workspace_analysis_task,
    list_analysis_results_for_task,
    list_workspace_analysis_tasks,
)
from backend.app.services.workspaces import READ_ROLES, WRITE_ROLES, get_workspace_for_user

router = APIRouter(
    prefix="/workspaces/{workspace_id}/analysis-tasks",
    tags=["analysis tasks"],
)


@router.get("", response_model=APIResponse[list[AnalysisTaskRead]])
async def list_workspace_analysis_tasks_endpoint(
    workspace_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[AnalysisTaskRead]]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    tasks = await list_workspace_analysis_tasks(session, workspace_id)
    return success_response([AnalysisTaskRead.model_validate(task) for task in tasks])


@router.post(
    "",
    response_model=APIResponse[AnalysisTaskRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_analysis_task_endpoint(
    workspace_id: uuid.UUID,
    task_create: AnalysisTaskCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[AnalysisTaskRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, WRITE_ROLES)
    task = await create_workspace_analysis_task(
        session,
        workspace_id,
        current_user.id,
        task_create,
    )
    return success_response(
        AnalysisTaskRead.model_validate(task),
        message="analysis task created",
    )


@router.get("/{analysis_task_id}", response_model=APIResponse[AnalysisTaskRead])
async def read_workspace_analysis_task_endpoint(
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[AnalysisTaskRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    task = await get_analysis_task_or_404(session, workspace_id, analysis_task_id)
    return success_response(AnalysisTaskRead.model_validate(task))


@router.post(
    "/{analysis_task_id}/run",
    response_model=APIResponse[AnalysisResultRead],
    status_code=status.HTTP_201_CREATED,
)
async def run_workspace_analysis_task_endpoint(
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[AnalysisResultRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, WRITE_ROLES)
    task = await get_analysis_task_or_404(session, workspace_id, analysis_task_id)
    analysis_result = await execute_analysis_task(session, task)
    return success_response(
        AnalysisResultRead.model_validate(analysis_result),
        message="analysis task executed",
    )


@router.get(
    "/{analysis_task_id}/results",
    response_model=APIResponse[list[AnalysisResultRead]],
)
async def list_analysis_results_endpoint(
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[AnalysisResultRead]]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    await get_analysis_task_or_404(session, workspace_id, analysis_task_id)
    results = await list_analysis_results_for_task(session, workspace_id, analysis_task_id)
    return success_response([AnalysisResultRead.model_validate(result) for result in results])


@router.post(
    "/{analysis_task_id}/results",
    response_model=APIResponse[AnalysisResultRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis_result_endpoint(
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    result_create: AnalysisResultCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[AnalysisResultRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, WRITE_ROLES)
    await get_analysis_task_or_404(session, workspace_id, analysis_task_id)
    analysis_result = await create_analysis_result_for_task(
        session,
        workspace_id,
        analysis_task_id,
        result_create,
    )
    return success_response(
        AnalysisResultRead.model_validate(analysis_result),
        message="analysis result created",
    )


@router.get(
    "/{analysis_task_id}/results/{analysis_result_id}",
    response_model=APIResponse[AnalysisResultRead],
)
async def read_analysis_result_endpoint(
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    analysis_result_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[AnalysisResultRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    await get_analysis_task_or_404(session, workspace_id, analysis_task_id)
    analysis_result = await get_analysis_result_or_404(
        session,
        workspace_id,
        analysis_task_id,
        analysis_result_id,
    )
    return success_response(AnalysisResultRead.model_validate(analysis_result))


async def get_workspace_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    allowed_roles: frozenset[str],
) -> Workspace:
    workspace = await get_workspace_for_user(session, workspace_id, user_id, allowed_roles)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return workspace


async def get_analysis_task_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
) -> AnalysisTask:
    task = await get_workspace_analysis_task(session, workspace_id, analysis_task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis task not found",
        )
    return task


async def get_analysis_result_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    analysis_result_id: uuid.UUID,
) -> AnalysisResult:
    analysis_result = await get_analysis_result_for_task(
        session,
        workspace_id,
        analysis_task_id,
        analysis_result_id,
    )
    if analysis_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis result not found",
        )
    return analysis_result
