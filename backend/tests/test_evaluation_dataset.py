import json
import re
from pathlib import Path
from typing import Any

DATASET_PATH = Path(__file__).resolve().parents[2] / "evaluations" / "rag_qa_dataset.jsonl"
REQUIRED_FIELDS = {
    "id",
    "category",
    "difficulty",
    "question",
    "expected_answer",
    "expected_document",
    "expected_page",
    "answer_aliases",
    "required_terms",
    "metadata_filters",
}
SUPPORTED_DOCUMENT_SUFFIXES = {".pdf", ".txt", ".md", ".markdown", ".docx"}
SUPPORTED_FILE_TYPES = {"pdf", "txt", "md", "markdown", "docx"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


def load_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with DATASET_PATH.open() as dataset_file:
        for line_number, line in enumerate(dataset_file, start=1):
            stripped = line.strip()
            assert stripped, f"line {line_number} is empty"
            value = json.loads(stripped)
            assert isinstance(value, dict), f"line {line_number} must be a JSON object"
            records.append(value)
    return records


def test_rag_evaluation_dataset_has_expected_size_and_unique_ids() -> None:
    records = load_records()

    assert 30 <= len(records) <= 50
    ids = [record["id"] for record in records]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"rag_eval_\d{3}", record_id) for record_id in ids)


def test_rag_evaluation_dataset_schema_is_complete() -> None:
    records = load_records()

    for record in records:
        assert REQUIRED_FIELDS <= record.keys()
        assert record["difficulty"] in VALID_DIFFICULTIES
        assert isinstance(record["question"], str) and record["question"].strip()
        assert isinstance(record["expected_answer"], str) and record["expected_answer"].strip()
        assert isinstance(record["expected_page"], int) and record["expected_page"] > 0
        assert isinstance(record["answer_aliases"], list) and record["answer_aliases"]
        assert all(isinstance(alias, str) and alias.strip() for alias in record["answer_aliases"])
        assert isinstance(record["required_terms"], list) and record["required_terms"]
        assert all(isinstance(term, str) and term.strip() for term in record["required_terms"])
        assert isinstance(record["metadata_filters"], dict)


def test_rag_evaluation_dataset_matches_supported_ingestion_types() -> None:
    records = load_records()

    for record in records:
        expected_document = record["expected_document"]
        assert isinstance(expected_document, str) and expected_document.strip()
        assert Path(expected_document).suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES

        file_types = record["metadata_filters"].get("file_types", [])
        assert isinstance(file_types, list) and file_types
        assert set(file_types) <= SUPPORTED_FILE_TYPES


def test_rag_evaluation_dataset_covers_multiple_enterprise_domains() -> None:
    records = load_records()

    categories = {record["category"] for record in records}
    difficulties = {record["difficulty"] for record in records}

    assert len(categories) >= 10
    assert difficulties == VALID_DIFFICULTIES
