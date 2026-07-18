import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.report import Report, ReportSection, ReportSectionStatus, ReportStatus
from backend.app.schemas.report import ReportCreate, ReportSectionCreate


async def list_reports_for_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[Report]:
    result = await session.execute(
        select(Report)
        .where(Report.workspace_id == workspace_id)
        .order_by(Report.created_at.desc(), Report.id.desc())
    )
    return list(result.scalars().all())


async def get_report_for_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
) -> Report | None:
    result = await session.execute(
        select(Report).where(
            Report.id == report_id,
            Report.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def create_report(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    created_by: uuid.UUID,
    report_create: ReportCreate,
) -> Report:
    report = Report(
        workspace_id=workspace_id,
        title=report_create.title,
        status=ReportStatus.DRAFT.value,
        created_by=created_by,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def list_report_sections_for_report(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
) -> list[ReportSection]:
    result = await session.execute(
        select(ReportSection)
        .where(
            ReportSection.workspace_id == workspace_id,
            ReportSection.report_id == report_id,
        )
        .order_by(ReportSection.sort_order.asc(), ReportSection.created_at.asc())
    )
    return list(result.scalars().all())


async def get_report_section_for_report(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    section_id: uuid.UUID,
) -> ReportSection | None:
    result = await session.execute(
        select(ReportSection).where(
            ReportSection.id == section_id,
            ReportSection.workspace_id == workspace_id,
            ReportSection.report_id == report_id,
        )
    )
    return result.scalar_one_or_none()


async def create_report_section(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    section_create: ReportSectionCreate,
) -> ReportSection:
    section = ReportSection(
        workspace_id=workspace_id,
        report_id=report_id,
        template_section_key=section_create.template_section_key,
        title=section_create.title,
        body_markdown=section_create.body_markdown,
        source_task_keys=section_create.source_task_keys,
        source_result_ids=section_create.source_result_ids,
        sort_order=section_create.sort_order,
        status=ReportSectionStatus.DRAFT.value,
    )
    session.add(section)
    await session.commit()
    await session.refresh(section)
    return section
