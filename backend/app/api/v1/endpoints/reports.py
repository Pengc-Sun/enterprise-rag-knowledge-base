import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.db.session import get_db_session
from backend.app.models.report import Report, ReportSection
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.report import (
    ReportCreate,
    ReportRead,
    ReportSectionCreate,
    ReportSectionRead,
)
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.reports import (
    create_report,
    create_report_section,
    get_report_for_workspace,
    get_report_section_for_report,
    list_report_sections_for_report,
    list_reports_for_workspace,
)
from backend.app.services.workspaces import READ_ROLES, WRITE_ROLES, get_workspace_for_user

router = APIRouter(prefix="/workspaces/{workspace_id}/reports", tags=["reports"])


@router.get("", response_model=APIResponse[list[ReportRead]])
async def list_reports_endpoint(
    workspace_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[ReportRead]]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    reports = await list_reports_for_workspace(session, workspace_id)
    return success_response([ReportRead.model_validate(report) for report in reports])


@router.post("", response_model=APIResponse[ReportRead], status_code=status.HTTP_201_CREATED)
async def create_report_endpoint(
    workspace_id: uuid.UUID,
    report_create: ReportCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[ReportRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, WRITE_ROLES)
    report = await create_report(session, workspace_id, current_user.id, report_create)
    return success_response(ReportRead.model_validate(report), message="report created")


@router.get("/{report_id}", response_model=APIResponse[ReportRead])
async def read_report_endpoint(
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[ReportRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    report = await get_report_or_404(session, workspace_id, report_id)
    return success_response(ReportRead.model_validate(report))


@router.get("/{report_id}/sections", response_model=APIResponse[list[ReportSectionRead]])
async def list_report_sections_endpoint(
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[ReportSectionRead]]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    await get_report_or_404(session, workspace_id, report_id)
    sections = await list_report_sections_for_report(session, workspace_id, report_id)
    return success_response(
        [ReportSectionRead.model_validate(section) for section in sections]
    )


@router.post(
    "/{report_id}/sections",
    response_model=APIResponse[ReportSectionRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_report_section_endpoint(
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    section_create: ReportSectionCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[ReportSectionRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, WRITE_ROLES)
    await get_report_or_404(session, workspace_id, report_id)
    section = await create_report_section(session, workspace_id, report_id, section_create)
    return success_response(
        ReportSectionRead.model_validate(section),
        message="report section created",
    )


@router.get("/{report_id}/sections/{section_id}", response_model=APIResponse[ReportSectionRead])
async def read_report_section_endpoint(
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[ReportSectionRead]:
    await get_workspace_or_404(session, workspace_id, current_user.id, READ_ROLES)
    await get_report_or_404(session, workspace_id, report_id)
    section = await get_report_section_or_404(session, workspace_id, report_id, section_id)
    return success_response(ReportSectionRead.model_validate(section))


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


async def get_report_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
) -> Report:
    report = await get_report_for_workspace(session, workspace_id, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return report


async def get_report_section_or_404(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    section_id: uuid.UUID,
) -> ReportSection:
    section = await get_report_section_for_report(
        session,
        workspace_id,
        report_id,
        section_id,
    )
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report section not found",
        )
    return section
