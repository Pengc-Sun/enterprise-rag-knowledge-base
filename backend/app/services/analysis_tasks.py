import json
import uuid
from copy import deepcopy
from typing import cast

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
from backend.app.services.llms import (
    DeterministicLLMProvider,
    LLMMessage,
    LLMProvider,
    LLMProviderName,
    LLMProviderResponseError,
    LLMResponse,
)

DEFAULT_ANALYSIS_CONTEXT_LIMIT = 8
LOCAL_ANALYSIS_PROVIDER = "local"
LOCAL_ANALYSIS_MODEL = "workspace-scoped-retrieval"
JSON_SCHEMA_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
}
STRUCTURED_ANALYSIS_SYSTEM_PROMPT = """\
You are an enterprise document analysis engine.
Return only valid JSON. Do not include Markdown fences, prose, or comments.
The response must conform to the expected output schema supplied by the user.
The JSON object must include:
- summary: string
- findings: array of structured finding objects
- citations: array of citation objects referencing provided chunk_id values
- confidence: number between 0 and 1, or null
"""


class AnalysisOutputValidationError(LLMProviderResponseError):
    message = "AI analysis output did not match the task schema"


class AnalysisCitationValidationError(AnalysisOutputValidationError):
    message = "AI analysis output citations were missing or invalid"


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
    *,
    llm_provider: LLMProvider | None = None,
    temperature: float | None = 0.0,
    max_tokens: int | None = 1024,
) -> AnalysisResult:
    task.status = AnalysisTaskStatus.RUNNING.value
    chunks = await retrieve_analysis_context_chunks(session, task)
    if llm_provider is None:
        return await create_local_analysis_result(session, task, chunks)
    if isinstance(llm_provider, DeterministicLLMProvider):
        structured_result = build_deterministic_structured_analysis_result(task, chunks)
        validate_structured_analysis_result(structured_result, task.output_schema)
        normalized_result, normalized_citations = normalize_structured_analysis_output(
            structured_result,
            chunks,
        )
        return await create_structured_analysis_result(
            session,
            task,
            normalized_result=normalized_result,
            normalized_citations=normalized_citations,
            confidence=extract_structured_analysis_confidence(structured_result),
            model=llm_provider.model,
            provider=LLMProviderName.DETERMINISTIC.value,
            token_usage={},
        )

    try:
        response = await llm_provider.generate(
            build_structured_analysis_messages(task, chunks),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        structured_result = parse_structured_analysis_response(response.content)
        validate_structured_analysis_result(structured_result, task.output_schema)
        normalized_result, normalized_citations = normalize_structured_analysis_output(
            structured_result,
            chunks,
        )
    except LLMProviderResponseError:
        task.status = AnalysisTaskStatus.FAILED.value
        await session.commit()
        raise
    return await create_structured_analysis_result(
        session,
        task,
        normalized_result=normalized_result,
        normalized_citations=normalized_citations,
        confidence=extract_structured_analysis_confidence(structured_result),
        model=response.model,
        provider=response.provider.value,
        token_usage=llm_usage_to_dict(response),
    )


async def create_structured_analysis_result(
    session: AsyncSession,
    task: AnalysisTask,
    *,
    normalized_result: dict[str, object],
    normalized_citations: list[dict[str, object]],
    confidence: float | None,
    model: str,
    provider: str,
    token_usage: dict[str, object],
) -> AnalysisResult:
    analysis_result = AnalysisResult(
        workspace_id=task.workspace_id,
        analysis_task_id=task.id,
        status=AnalysisResultStatus.NEEDS_REVIEW.value,
        result=normalized_result,
        citations=normalized_citations,
        confidence=confidence,
        model=model,
        provider=provider,
        token_usage=token_usage,
    )
    task.status = AnalysisTaskStatus.COMPLETED.value
    session.add(analysis_result)
    await session.commit()
    await session.refresh(task)
    await session.refresh(analysis_result)
    return analysis_result


async def create_local_analysis_result(
    session: AsyncSession,
    task: AnalysisTask,
    chunks: list[DocumentChunk],
) -> AnalysisResult:
    analysis_result = AnalysisResult(
        workspace_id=task.workspace_id,
        analysis_task_id=task.id,
        status=AnalysisResultStatus.NEEDS_REVIEW.value,
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


def build_structured_analysis_messages(
    task: AnalysisTask,
    chunks: list[DocumentChunk],
) -> list[LLMMessage]:
    return [
        LLMMessage(role="system", content=STRUCTURED_ANALYSIS_SYSTEM_PROMPT),
        LLMMessage(role="user", content=build_structured_analysis_user_prompt(task, chunks)),
    ]


def build_structured_analysis_user_prompt(
    task: AnalysisTask,
    chunks: list[DocumentChunk],
) -> str:
    context_blocks = [build_analysis_context_block(chunk) for chunk in chunks]
    context = (
        "\n\n".join(context_blocks)
        if context_blocks
        else "No workspace context chunks found."
    )
    output_schema = json.dumps(task.output_schema, ensure_ascii=False, sort_keys=True)
    return "\n".join(
        [
            f"Task ID: {task.id}",
            f"Task name: {task.name}",
            f"Task type: {task.task_type}",
            f"Template task key: {task.template_task_key or ''}",
            f"Task description: {task.description or ''}",
            f"Expected output schema: {output_schema}",
            "",
            "Use only the workspace context below.",
            "Every finding, requirement, risk, row, procedure, or priority item must include a "
            "non-empty citations array.",
            "Every citation must reference one of the provided chunk_id values.",
            "",
            "Workspace context:",
            context,
        ]
    )


def build_analysis_context_block(chunk: DocumentChunk) -> str:
    document = getattr(chunk, "document", None)
    return "\n".join(
        [
            f"chunk_id: {chunk.id}",
            f"document_id: {chunk.document_id}",
            f"document_name: {getattr(document, 'filename', None) or ''}",
            f"page_number: {chunk.page_number}",
            f"section_title: {chunk.section_title or ''}",
            "content:",
            chunk.content,
        ]
    )


def parse_structured_analysis_response(content: str) -> dict[str, object]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMProviderResponseError from exc

    if not isinstance(parsed, dict):
        raise LLMProviderResponseError
    return parsed


def validate_structured_analysis_result(
    structured_result: dict[str, object],
    output_schema: dict[str, object],
) -> None:
    if not output_schema:
        return
    validate_json_schema_value(structured_result, output_schema, "$")


def build_deterministic_structured_analysis_result(
    task: AnalysisTask,
    chunks: list[DocumentChunk],
) -> dict[str, object]:
    if not task.output_schema:
        return build_deterministic_analysis_result(task, chunks)

    structured_result = build_deterministic_json_schema_value(
        task.output_schema,
        chunks,
        key=task.template_task_key or task.task_type,
    )
    if not isinstance(structured_result, dict):
        raise AnalysisOutputValidationError
    return structured_result


def build_deterministic_json_schema_value(
    schema: dict[str, object],
    chunks: list[DocumentChunk],
    *,
    key: str,
    in_result_array: bool = False,
) -> object:
    schema_type = schema.get("type")
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        return enum_values[0]

    if schema_type == "object":
        return build_deterministic_json_object(
            schema,
            chunks,
            key=key,
            in_result_array=in_result_array,
        )
    if schema_type == "array":
        return build_deterministic_json_array(schema, chunks, key=key)
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 0.8
    if schema_type == "boolean":
        return True
    if isinstance(schema_type, list):
        for candidate_type in schema_type:
            if candidate_type != "null":
                candidate_schema = dict(schema)
                candidate_schema["type"] = candidate_type
                return build_deterministic_json_schema_value(candidate_schema, chunks, key=key)
        return None
    return build_deterministic_string(key, chunks)


def build_deterministic_json_object(
    schema: dict[str, object],
    chunks: list[DocumentChunk],
    *,
    key: str,
    in_result_array: bool,
) -> dict[str, object]:
    properties = schema.get("properties")
    required = schema.get("required")
    required_keys = (
        {item for item in required if isinstance(item, str)}
        if isinstance(required, list)
        else set()
    )
    result: dict[str, object] = {}

    if isinstance(properties, dict):
        for property_key, property_schema in properties.items():
            if not isinstance(property_key, str) or not isinstance(property_schema, dict):
                continue
            if property_key in required_keys or property_key in {
                "summary",
                "citations",
                "confidence",
            }:
                result[property_key] = build_deterministic_json_schema_value(
                    property_schema,
                    chunks,
                    key=property_key,
                )

    if in_result_array and "citations" not in result:
        result["citations"] = build_deterministic_chunk_id_citations(chunks)
    return result


def build_deterministic_json_array(
    schema: dict[str, object],
    chunks: list[DocumentChunk],
    *,
    key: str,
) -> list[object]:
    if key == "citations":
        return build_deterministic_chunk_id_citations(chunks)

    items_schema = schema.get("items")
    if not isinstance(items_schema, dict):
        return []

    if not chunks:
        return []

    return [
        build_deterministic_json_schema_value(
            items_schema,
            chunks,
            key=key,
            in_result_array=True,
        )
    ]


def build_deterministic_chunk_id_citations(chunks: list[DocumentChunk]) -> list[object]:
    if not chunks:
        return []
    return [str(chunks[0].id)]


def build_deterministic_string(key: str, chunks: list[DocumentChunk]) -> str:
    if chunks:
        return f"Deterministic {key}: {chunks[0].content}"
    return f"Deterministic {key}: no workspace context found"


def normalize_structured_analysis_output(
    structured_result: dict[str, object],
    chunks: list[DocumentChunk],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    normalized_result = deepcopy(structured_result)
    chunk_map = build_chunk_citation_context(chunks)
    citation_store: dict[tuple[str, str | None], dict[str, object]] = {}

    top_level_citation_count = normalize_top_level_citations(
        normalized_result,
        chunk_map,
        citation_store,
    )
    finding_count = normalize_finding_citations(
        normalized_result,
        chunk_map,
        citation_store,
        "$",
    )
    string_conclusion_count = count_string_conclusion_arrays(normalized_result)

    if string_conclusion_count > 0 and top_level_citation_count == 0:
        raise AnalysisCitationValidationError
    if finding_count == 0 and string_conclusion_count == 0 and top_level_citation_count == 0:
        raise AnalysisCitationValidationError

    normalized_citations = list(citation_store.values())
    normalized_result["citations"] = normalized_citations
    return normalized_result, normalized_citations


def build_chunk_citation_context(chunks: list[DocumentChunk]) -> dict[str, DocumentChunk]:
    return {str(chunk.id): chunk for chunk in chunks}


def normalize_top_level_citations(
    structured_result: dict[str, object],
    chunk_map: dict[str, DocumentChunk],
    citation_store: dict[tuple[str, str | None], dict[str, object]],
) -> int:
    citations = structured_result.get("citations")
    if citations is None:
        return 0
    if not isinstance(citations, list):
        raise AnalysisCitationValidationError
    normalized_citations = normalize_citation_list(
        citations,
        chunk_map,
        citation_store,
        "$.citations",
    )
    structured_result["citations"] = normalized_citations
    return len(normalized_citations)


def normalize_finding_citations(
    value: object,
    chunk_map: dict[str, DocumentChunk],
    citation_store: dict[tuple[str, str | None], dict[str, object]],
    path: str,
    *,
    list_key: str | None = None,
) -> int:
    if isinstance(value, dict):
        finding_count = 0
        for key, item in value.items():
            if key == "citations":
                continue
            item_path = f"{path}.{key}"
            finding_count += normalize_finding_citations(
                item,
                chunk_map,
                citation_store,
                item_path,
                list_key=key,
            )
        return finding_count

    if isinstance(value, list):
        finding_count = 0
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            if isinstance(item, dict):
                if list_key != "citations":
                    item["citations"] = normalize_required_finding_citations(
                        item,
                        chunk_map,
                        citation_store,
                        item_path,
                    )
                    finding_count += 1
                finding_count += normalize_finding_citations(
                    item,
                    chunk_map,
                    citation_store,
                    item_path,
                )
            elif isinstance(item, list):
                finding_count += normalize_finding_citations(
                    item,
                    chunk_map,
                    citation_store,
                    item_path,
                    list_key=list_key,
                )
        return finding_count

    return 0


def normalize_required_finding_citations(
    finding: dict[object, object],
    chunk_map: dict[str, DocumentChunk],
    citation_store: dict[tuple[str, str | None], dict[str, object]],
    path: str,
) -> list[dict[str, object]]:
    citations = finding.get("citations")
    if not isinstance(citations, list) or not citations:
        raise AnalysisCitationValidationError(f"{path}.citations is required")
    return normalize_citation_list(citations, chunk_map, citation_store, f"{path}.citations")


def normalize_citation_list(
    citations: list[object],
    chunk_map: dict[str, DocumentChunk],
    citation_store: dict[tuple[str, str | None], dict[str, object]],
    path: str,
) -> list[dict[str, object]]:
    normalized_citations: list[dict[str, object]] = []
    for index, citation in enumerate(citations):
        normalized_citation = normalize_citation(
            citation,
            chunk_map,
            f"{path}[{index}]",
        )
        citation_key = (
            cast(str, normalized_citation["chunk_id"]),
            cast(str | None, normalized_citation.get("quote")),
        )
        citation_store.setdefault(citation_key, normalized_citation)
        normalized_citations.append(normalized_citation)
    return normalized_citations


def normalize_citation(
    citation: object,
    chunk_map: dict[str, DocumentChunk],
    path: str,
) -> dict[str, object]:
    if isinstance(citation, str):
        chunk_id = citation
        quote = None
    elif isinstance(citation, dict):
        raw_chunk_id = citation.get("chunk_id")
        if not isinstance(raw_chunk_id, str):
            raise AnalysisCitationValidationError(f"{path}.chunk_id is required")
        chunk_id = raw_chunk_id
        raw_quote = citation.get("quote")
        quote = raw_quote if isinstance(raw_quote, str) and raw_quote else None
    else:
        raise AnalysisCitationValidationError(f"{path} must be a citation object or chunk id")

    chunk = chunk_map.get(chunk_id)
    if chunk is None:
        raise AnalysisCitationValidationError(f"{path}.chunk_id must reference retrieved context")
    normalized = build_analysis_citation(chunk)
    if quote is not None:
        normalized["quote"] = quote
    return normalized


def count_string_conclusion_arrays(value: object, *, key: str | None = None) -> int:
    if isinstance(value, dict):
        count = 0
        for item_key, item in value.items():
            if item_key == "citations":
                continue
            count += count_string_conclusion_arrays(item, key=item_key)
        return count

    if isinstance(value, list):
        if key != "citations" and all(isinstance(item, str) for item in value):
            return len(value)
        return sum(count_string_conclusion_arrays(item, key=key) for item in value)

    return 0


def validate_json_schema_value(value: object, schema: dict[str, object], path: str) -> None:
    schema_type = schema.get("type")
    if schema_type is not None:
        validate_json_schema_type(value, schema_type, path)

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        raise AnalysisOutputValidationError(f"{path} must be one of the allowed enum values")

    const_value = schema.get("const")
    if "const" in schema and value != const_value:
        raise AnalysisOutputValidationError(f"{path} must equal the schema const value")

    if isinstance(value, dict):
        validate_json_object_schema(value, schema, path)
    elif isinstance(value, list):
        validate_json_array_schema(value, schema, path)
    elif isinstance(value, str):
        validate_json_string_schema(value, schema, path)
    elif is_json_number(value):
        validate_json_number_schema(value, schema, path)


def validate_json_schema_type(value: object, schema_type: object, path: str) -> None:
    if isinstance(schema_type, list):
        if any(is_json_schema_type(value, item) for item in schema_type):
            return
        allowed_types = ", ".join(str(item) for item in schema_type)
        raise AnalysisOutputValidationError(f"{path} must match one of: {allowed_types}")

    if isinstance(schema_type, str) and not is_json_schema_type(value, schema_type):
        raise AnalysisOutputValidationError(f"{path} must be {schema_type}")


def is_json_schema_type(value: object, schema_type: object) -> bool:
    if not isinstance(schema_type, str):
        return True
    if schema_type == "null":
        return value is None
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return is_json_number(value)

    expected_type = JSON_SCHEMA_TYPE_MAP.get(schema_type)
    if expected_type is None:
        return True
    return isinstance(value, expected_type)


def validate_json_object_schema(
    value: dict[object, object],
    schema: dict[str, object],
    path: str,
) -> None:
    required = schema.get("required")
    if isinstance(required, list):
        for key in required:
            if isinstance(key, str) and key not in value:
                raise AnalysisOutputValidationError(f"{path}.{key} is required")

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for key, property_schema in properties.items():
            if not isinstance(key, str) or key not in value:
                continue
            if isinstance(property_schema, dict):
                validate_json_schema_value(value[key], property_schema, f"{path}.{key}")


def validate_json_array_schema(
    value: list[object],
    schema: dict[str, object],
    path: str,
) -> None:
    min_items = schema.get("minItems")
    if isinstance(min_items, int) and len(value) < min_items:
        raise AnalysisOutputValidationError(f"{path} must contain at least {min_items} item(s)")

    max_items = schema.get("maxItems")
    if isinstance(max_items, int) and len(value) > max_items:
        raise AnalysisOutputValidationError(f"{path} must contain at most {max_items} item(s)")

    items_schema = schema.get("items")
    if isinstance(items_schema, dict):
        for index, item in enumerate(value):
            validate_json_schema_value(item, items_schema, f"{path}[{index}]")


def validate_json_string_schema(
    value: str,
    schema: dict[str, object],
    path: str,
) -> None:
    min_length = schema.get("minLength")
    if isinstance(min_length, int) and len(value) < min_length:
        raise AnalysisOutputValidationError(
            f"{path} must contain at least {min_length} character(s)"
        )

    max_length = schema.get("maxLength")
    if isinstance(max_length, int) and len(value) > max_length:
        raise AnalysisOutputValidationError(
            f"{path} must contain at most {max_length} character(s)"
        )


def validate_json_number_schema(
    value: object,
    schema: dict[str, object],
    path: str,
) -> None:
    if not is_json_number(value):
        return

    number_value = cast(int | float, value)
    minimum = schema.get("minimum")
    if isinstance(minimum, int | float) and number_value < minimum:
        raise AnalysisOutputValidationError(f"{path} must be greater than or equal to {minimum}")

    maximum = schema.get("maximum")
    if isinstance(maximum, int | float) and number_value > maximum:
        raise AnalysisOutputValidationError(f"{path} must be less than or equal to {maximum}")


def is_json_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def extract_structured_analysis_confidence(structured_result: dict[str, object]) -> float | None:
    confidence = structured_result.get("confidence")
    if isinstance(confidence, int | float):
        return max(0.0, min(float(confidence), 1.0))
    return None


def llm_usage_to_dict(response: LLMResponse) -> dict[str, object]:
    if response.usage is None:
        return {}
    return {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }


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
            "citations": [build_analysis_citation(chunk)],
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
    return [build_analysis_citation(chunk) for chunk in chunks]


def build_analysis_citation(chunk: DocumentChunk) -> dict[str, object]:
    document = getattr(chunk, "document", None)
    return {
        "chunk_id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "document_name": getattr(document, "filename", None),
        "knowledge_base_id": str(chunk.knowledge_base_id),
        "page_number": chunk.page_number,
        "section_title": chunk.section_title,
        "quote": chunk.content,
    }
