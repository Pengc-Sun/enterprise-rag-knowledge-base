import uuid
from collections.abc import Iterable
from json import dumps

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.analysis import AnalysisResult, AnalysisResultStatus, AnalysisTask
from backend.app.models.report import Report, ReportSection, ReportSectionStatus, ReportStatus
from backend.app.schemas.report import (
    ReportCreate,
    ReportPreviewRead,
    ReportSectionCreate,
    ReportSectionGenerateRequest,
    ReportSectionReorderRequest,
    ReportSectionUpdate,
    ReportUpdate,
)

REPORTABLE_ANALYSIS_RESULT_STATUSES = frozenset(
    {
        AnalysisResultStatus.APPROVED.value,
        AnalysisResultStatus.EDITED.value,
    }
)


class ReportSectionSourceError(ValueError):
    pass


class ReportSectionGenerationError(ReportSectionSourceError):
    pass


class ReportSectionOrderingError(ValueError):
    pass


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


async def update_report(
    session: AsyncSession,
    report: Report,
    report_update: ReportUpdate,
) -> Report:
    update_data = report_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(report, field, value)

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


async def build_report_preview(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report: Report,
) -> ReportPreviewRead:
    sections = await list_report_sections_for_report(session, workspace_id, report.id)
    return ReportPreviewRead(
        report_id=report.id,
        workspace_id=workspace_id,
        title=report.title,
        status=ReportStatus(report.status),
        section_count=len(sections),
        markdown=render_report_preview_markdown(report, sections),
    )


async def create_report_section(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    section_create: ReportSectionCreate,
) -> ReportSection:
    source_result_ids = await validate_report_section_source_results(
        session,
        workspace_id,
        section_create.source_result_ids,
    )
    section = ReportSection(
        workspace_id=workspace_id,
        report_id=report_id,
        template_section_key=section_create.template_section_key,
        title=section_create.title,
        body_markdown=section_create.body_markdown,
        source_task_keys=section_create.source_task_keys,
        source_result_ids=source_result_ids,
        sort_order=section_create.sort_order,
        status=ReportSectionStatus.DRAFT.value,
    )
    session.add(section)
    await session.commit()
    await session.refresh(section)
    return section


async def update_report_section(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    section: ReportSection,
    section_update: ReportSectionUpdate,
) -> ReportSection:
    update_data = section_update.model_dump(exclude_unset=True)
    if "source_result_ids" in update_data:
        source_result_ids = update_data["source_result_ids"] or []
        update_data["source_result_ids"] = await validate_report_section_source_results(
            session,
            workspace_id,
            source_result_ids,
        )

    for field, value in update_data.items():
        setattr(section, field, value)

    await session.commit()
    await session.refresh(section)
    return section


async def reorder_report_sections(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    reorder_request: ReportSectionReorderRequest,
) -> list[ReportSection]:
    section_ids = [item.section_id for item in reorder_request.sections]
    if len(section_ids) != len(set(section_ids)):
        raise ReportSectionOrderingError("Report section ordering cannot contain duplicates")

    result = await session.execute(
        select(ReportSection).where(
            ReportSection.workspace_id == workspace_id,
            ReportSection.report_id == report_id,
            ReportSection.id.in_(section_ids),
        )
    )
    sections = list(result.scalars().all())
    sections_by_id = {section.id: section for section in sections}
    missing_section_ids = [
        section_id for section_id in section_ids if section_id not in sections_by_id
    ]
    if missing_section_ids:
        raise ReportSectionOrderingError(
            "Report section ordering contains sections outside this report"
        )

    for item in reorder_request.sections:
        sections_by_id[item.section_id].sort_order = item.sort_order

    await session.commit()
    for section in sections:
        await session.refresh(section)

    return sorted(
        sections,
        key=lambda section: (section.sort_order, section.created_at, str(section.id)),
    )


def render_report_preview_markdown(
    report: Report,
    sections: Iterable[ReportSection],
) -> str:
    lines = [f"# {_markdown_heading_text(report.title)}", ""]
    section_list = list(sections)
    if not section_list:
        lines.append("_No report sections yet._")
        return "\n".join(lines).strip() + "\n"

    for section in section_list:
        lines.extend([f"## {_markdown_heading_text(section.title)}", ""])
        body_markdown = section.body_markdown.strip()
        lines.append(body_markdown or "_No content yet._")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


async def generate_report_section_from_results(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    generation: ReportSectionGenerateRequest,
) -> ReportSection:
    result_ids = _dedupe_uuids(generation.analysis_result_ids)
    rows = await _get_reportable_analysis_result_rows(session, workspace_id, result_ids)
    rows_by_id = {analysis_result.id: (analysis_result, task) for analysis_result, task in rows}

    missing_result_ids = [result_id for result_id in result_ids if result_id not in rows_by_id]
    if missing_result_ids:
        raise ReportSectionGenerationError(
            "Analysis results must exist in this workspace and be approved or edited"
        )

    ordered_rows = [rows_by_id[result_id] for result_id in result_ids]
    section = ReportSection(
        workspace_id=workspace_id,
        report_id=report_id,
        template_section_key=generation.template_section_key,
        title=generation.title or _build_generated_section_title(ordered_rows),
        body_markdown=_build_generated_section_markdown(ordered_rows),
        source_task_keys=_collect_source_task_keys(task for _, task in ordered_rows),
        source_result_ids=[str(analysis_result.id) for analysis_result, _ in ordered_rows],
        sort_order=generation.sort_order,
        status=ReportSectionStatus.DRAFT.value,
    )
    session.add(section)
    await session.commit()
    await session.refresh(section)
    return section


async def validate_report_section_source_results(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    source_result_ids: Iterable[str],
) -> list[str]:
    result_ids = _parse_source_result_ids(source_result_ids)
    if not result_ids:
        return []

    rows = await _get_reportable_analysis_result_rows(session, workspace_id, result_ids)
    reportable_result_ids = {analysis_result.id for analysis_result, _ in rows}
    missing_result_ids = [
        result_id for result_id in result_ids if result_id not in reportable_result_ids
    ]
    if missing_result_ids:
        raise ReportSectionSourceError(
            "Report section source results must exist in this workspace and be approved or edited"
        )
    return [str(result_id) for result_id in result_ids]


async def _get_reportable_analysis_result_rows(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    result_ids: list[uuid.UUID],
) -> list[tuple[AnalysisResult, AnalysisTask]]:
    if not result_ids:
        return []

    result = await session.execute(
        select(AnalysisResult, AnalysisTask)
        .join(AnalysisTask, AnalysisResult.analysis_task_id == AnalysisTask.id)
        .where(
            AnalysisResult.workspace_id == workspace_id,
            AnalysisResult.id.in_(result_ids),
            AnalysisResult.status.in_(REPORTABLE_ANALYSIS_RESULT_STATUSES),
        )
    )
    return [(analysis_result, task) for analysis_result, task in result.all()]


def _parse_source_result_ids(source_result_ids: Iterable[str]) -> list[uuid.UUID]:
    parsed_ids: list[uuid.UUID] = []
    for source_result_id in source_result_ids:
        try:
            parsed_ids.append(uuid.UUID(source_result_id))
        except ValueError as exc:
            raise ReportSectionSourceError(
                "Report section source results must be valid UUIDs"
            ) from exc
    return _dedupe_uuids(parsed_ids)


def _dedupe_uuids(values: Iterable[uuid.UUID]) -> list[uuid.UUID]:
    seen: set[uuid.UUID] = set()
    deduped: list[uuid.UUID] = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def _build_generated_section_title(
    rows: list[tuple[AnalysisResult, AnalysisTask]],
) -> str:
    if len(rows) == 1:
        return rows[0][1].name
    return "Draft Report Section"


def _build_generated_section_markdown(
    rows: list[tuple[AnalysisResult, AnalysisTask]],
) -> str:
    blocks: list[str] = []
    for index, (analysis_result, task) in enumerate(rows, start=1):
        heading = task.name if len(rows) == 1 else f"{index}. {task.name}"
        blocks.append(f"### {heading}")
        blocks.append("")
        blocks.append(_json_block(analysis_result.result))

        if analysis_result.citations:
            blocks.append("")
            blocks.append("#### Citations")
            blocks.extend(
                f"- {_format_citation(citation)}" for citation in analysis_result.citations
            )

        blocks.append("")

    return "\n".join(blocks).strip()


def _json_block(value: object) -> str:
    return f"```json\n{dumps(value, ensure_ascii=False, indent=2, sort_keys=True)}\n```"


def _format_citation(citation: dict[str, object]) -> str:
    title = str(
        citation.get("document_title")
        or citation.get("document_name")
        or citation.get("file_name")
        or citation.get("source")
        or "Source"
    )
    page = citation.get("page")
    chunk_id = citation.get("chunk_id")
    suffix_parts = []
    if page is not None:
        suffix_parts.append(f"page {page}")
    if chunk_id is not None:
        suffix_parts.append(f"chunk {chunk_id}")
    if not suffix_parts:
        return title
    return f"{title} ({', '.join(suffix_parts)})"


def _collect_source_task_keys(tasks: Iterable[AnalysisTask]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        if task.template_task_key and task.template_task_key not in seen:
            keys.append(task.template_task_key)
            seen.add(task.template_task_key)
    return keys


def _markdown_heading_text(value: str) -> str:
    return " ".join(value.split()).strip() or "Untitled"
