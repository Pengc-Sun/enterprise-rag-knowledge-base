import pytest

from backend.app.services.document_chunkers import (
    ChunkingConfig,
    chunk_document,
    count_tokens,
    split_text_recursively,
)
from backend.app.services.document_parsers import ParsedDocument, ParsedHeading, ParsedPage


def test_chunk_document_returns_single_chunk_for_short_document() -> None:
    parsed_document = ParsedDocument(
        document_id="doc-1",
        file_type="txt",
        pages=[ParsedPage(page_number=3, text="short document text")],
        headings=[],
    )

    chunks = chunk_document(
        parsed_document, ChunkingConfig(chunk_size_tokens=20, chunk_overlap_tokens=3)
    )

    assert len(chunks) == 1
    assert chunks[0].document_id == "doc-1"
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 3
    assert chunks[0].section_title is None
    assert chunks[0].content == "short document text"
    assert chunks[0].token_count == count_tokens("short document text")


def test_split_text_recursively_respects_chunk_size_and_overlap() -> None:
    text = "\n\n".join(
        [
            "alpha beta gamma delta",
            "epsilon zeta eta theta",
            "iota kappa lambda mu",
        ]
    )

    chunks = split_text_recursively(
        text, ChunkingConfig(chunk_size_tokens=8, chunk_overlap_tokens=2)
    )

    assert len(chunks) == 2
    assert all(count_tokens(chunk) <= 8 for chunk in chunks)
    assert chunks[0].endswith("eta theta")
    assert chunks[1].startswith("eta theta")


def test_chunk_document_splits_oversized_sentence_by_tokens() -> None:
    parsed_document = ParsedDocument(
        document_id="doc-1",
        file_type="txt",
        pages=[ParsedPage(page_number=1, text=" ".join(f"token{i}" for i in range(25)))],
        headings=[],
    )

    chunks = chunk_document(
        parsed_document, ChunkingConfig(chunk_size_tokens=10, chunk_overlap_tokens=2)
    )

    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert all(chunk.token_count <= 10 for chunk in chunks)
    assert chunks[1].content.startswith("token8 token9")
    assert chunks[2].content.startswith("token16 token17")


def test_chunk_document_uses_headings_as_section_titles() -> None:
    parsed_document = ParsedDocument(
        document_id="doc-1",
        file_type="md",
        pages=[
            ParsedPage(
                page_number=1,
                text="Intro\nalpha beta\nDetails\ngamma delta",
            )
        ],
        headings=[
            ParsedHeading(level=1, text="Intro"),
            ParsedHeading(level=2, text="Details"),
        ],
    )

    chunks = chunk_document(
        parsed_document, ChunkingConfig(chunk_size_tokens=20, chunk_overlap_tokens=2)
    )

    assert [chunk.section_title for chunk in chunks] == ["Intro", "Details"]
    assert chunks[0].content == "Intro\nalpha beta"
    assert chunks[1].content == "Details\ngamma delta"


def test_chunk_document_keeps_page_metadata_for_unheaded_pages() -> None:
    parsed_document = ParsedDocument(
        document_id="doc-1",
        file_type="pdf",
        pages=[
            ParsedPage(page_number=1, text="first page"),
            ParsedPage(page_number=2, text="second page"),
        ],
        headings=[],
    )

    chunks = chunk_document(
        parsed_document, ChunkingConfig(chunk_size_tokens=20, chunk_overlap_tokens=0)
    )

    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert [chunk.content for chunk in chunks] == ["first page", "second page"]


def test_chunking_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        ChunkingConfig(chunk_size_tokens=0)

    with pytest.raises(ValueError):
        ChunkingConfig(chunk_size_tokens=10, chunk_overlap_tokens=10)

    with pytest.raises(ValueError):
        ChunkingConfig(chunk_size_tokens=10, chunk_overlap_tokens=-1)


def test_chunk_document_ignores_empty_pages() -> None:
    parsed_document = ParsedDocument(
        document_id="doc-empty",
        file_type="txt",
        pages=[ParsedPage(page_number=1, text="   "), ParsedPage(page_number=2, text="\n")],
        headings=[],
    )

    assert chunk_document(parsed_document) == []
