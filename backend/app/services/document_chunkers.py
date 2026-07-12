import re
from dataclasses import dataclass

from backend.app.services.document_parsers import ParsedDocument, ParsedHeading, ParsedPage

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?。！？])\s+")
DEFAULT_CHUNK_SIZE_TOKENS = 700
DEFAULT_CHUNK_OVERLAP_TOKENS = 100


@dataclass(frozen=True)
class ChunkingConfig:
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS

    def __post_init__(self) -> None:
        if self.chunk_size_tokens <= 0:
            raise ValueError("chunk_size_tokens must be positive")
        if self.chunk_overlap_tokens < 0:
            raise ValueError("chunk_overlap_tokens cannot be negative")
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError("chunk_overlap_tokens must be smaller than chunk_size_tokens")


@dataclass(frozen=True)
class TextChunk:
    document_id: str
    content: str
    chunk_index: int
    page_number: int
    section_title: str | None
    token_count: int


@dataclass(frozen=True)
class SectionBlock:
    text: str
    page_number: int
    section_title: str | None


def chunk_document(
    parsed_document: ParsedDocument,
    config: ChunkingConfig | None = None,
) -> list[TextChunk]:
    effective_config = config or ChunkingConfig()
    chunks: list[TextChunk] = []

    for block in build_section_blocks(parsed_document):
        for content in split_text_recursively(block.text, effective_config):
            chunks.append(
                TextChunk(
                    document_id=parsed_document.document_id,
                    content=content,
                    chunk_index=len(chunks),
                    page_number=block.page_number,
                    section_title=block.section_title,
                    token_count=count_tokens(content),
                )
            )

    return chunks


def build_section_blocks(parsed_document: ParsedDocument) -> list[SectionBlock]:
    headings = sorted(parsed_document.headings, key=lambda heading: heading.page_number)
    if not headings:
        return [
            SectionBlock(text=page.text, page_number=page.page_number, section_title=None)
            for page in parsed_document.pages
            if page.text.strip()
        ]

    blocks: list[SectionBlock] = []
    heading_index = 0
    current_title: str | None = None
    current_page_number = parsed_document.pages[0].page_number if parsed_document.pages else 1
    current_lines: list[str] = []

    for page in parsed_document.pages:
        for line in page.text.splitlines():
            normalized_line = line.strip()
            next_heading = get_matching_heading(headings, heading_index, normalized_line, page)
            if next_heading is not None:
                append_section_block(blocks, current_lines, current_page_number, current_title)
                current_lines = []
                current_title = next_heading.text
                current_page_number = page.page_number
                heading_index += 1

            if normalized_line:
                current_lines.append(normalized_line)

    append_section_block(blocks, current_lines, current_page_number, current_title)
    return blocks


def get_matching_heading(
    headings: list[ParsedHeading],
    heading_index: int,
    normalized_line: str,
    page: ParsedPage,
) -> ParsedHeading | None:
    if heading_index >= len(headings):
        return None

    heading = headings[heading_index]
    if heading.page_number > page.page_number:
        return None
    if normalize_heading_text(normalized_line) != normalize_heading_text(heading.text):
        return None
    return heading


def append_section_block(
    blocks: list[SectionBlock],
    lines: list[str],
    page_number: int,
    section_title: str | None,
) -> None:
    text = "\n".join(lines).strip()
    if text:
        blocks.append(
            SectionBlock(
                text=text,
                page_number=page_number,
                section_title=section_title,
            )
        )


def split_text_recursively(text: str, config: ChunkingConfig) -> list[str]:
    normalized_text = text.strip()
    if not normalized_text:
        return []
    if count_tokens(normalized_text) <= config.chunk_size_tokens:
        return [normalized_text]

    parts = recursive_split(normalized_text, config)
    return merge_parts_with_overlap(parts, config)


def recursive_split(text: str, config: ChunkingConfig) -> list[str]:
    if count_tokens(text) <= config.chunk_size_tokens:
        return [text.strip()]

    for separator in ("\n\n", "\n"):
        pieces = [piece.strip() for piece in text.split(separator) if piece.strip()]
        if len(pieces) > 1:
            return split_oversized_parts(pieces, config)

    sentence_pieces = [
        piece.strip() for piece in SENTENCE_BOUNDARY_PATTERN.split(text) if piece.strip()
    ]
    if len(sentence_pieces) > 1:
        return split_oversized_parts(sentence_pieces, config)

    return split_tokens_with_overlap(text, config)


def split_oversized_parts(parts: list[str], config: ChunkingConfig) -> list[str]:
    split_parts: list[str] = []
    for part in parts:
        split_parts.extend(recursive_split(part, config))
    return split_parts


def split_tokens_with_overlap(text: str, config: ChunkingConfig) -> list[str]:
    tokens = tokenize(text)
    step = config.chunk_size_tokens - config.chunk_overlap_tokens
    chunks: list[str] = []
    index = 0
    while index < len(tokens):
        chunks.append(detokenize(tokens[index : index + config.chunk_size_tokens]))
        if index + config.chunk_size_tokens >= len(tokens):
            break
        index += step
    return chunks


def merge_parts_with_overlap(parts: list[str], config: ChunkingConfig) -> list[str]:
    chunks: list[str] = []
    current_parts: list[str] = []

    for part in parts:
        if count_tokens(part) >= config.chunk_size_tokens:
            if current_parts:
                chunks.append("\n\n".join(current_parts).strip())
                current_parts = []
            chunks.append(part)
            continue

        candidate_parts = [*current_parts, part]
        candidate = "\n\n".join(candidate_parts).strip()
        if current_parts and count_tokens(candidate) > config.chunk_size_tokens:
            current_chunk = "\n\n".join(current_parts).strip()
            chunks.append(current_chunk)
            current_parts = build_overlap_parts(current_chunk, config.chunk_overlap_tokens)

        current_parts.append(part)

    if current_parts:
        chunks.append("\n\n".join(current_parts).strip())

    return [chunk for chunk in chunks if chunk]


def build_overlap_parts(text: str, overlap_tokens: int) -> list[str]:
    if overlap_tokens == 0:
        return []

    tokens = tokenize(text)
    if not tokens:
        return []
    return [detokenize(tokens[-overlap_tokens:])]


def count_tokens(text: str) -> int:
    return len(tokenize(text))


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text)


def detokenize(tokens: list[str]) -> str:
    text = " ".join(tokens)
    text = re.sub(r"\s+([,.!?;:%。！？；：、）】}])", r"\1", text)
    text = re.sub(r"([（【{])\s+", r"\1", text)
    return text.strip()


def normalize_heading_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()
