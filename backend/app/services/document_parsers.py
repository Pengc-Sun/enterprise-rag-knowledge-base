from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.app.models.document import Document


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    file_type: str
    pages: list[ParsedPage]

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)


class DocumentParsingError(Exception):
    message = "Document parsing failed"


class UnsupportedDocumentTypeError(DocumentParsingError):
    message = "Unsupported document type"


class DocumentFileNotFoundError(DocumentParsingError):
    message = "Document file not found"


class DocumentTextDecodeError(DocumentParsingError):
    message = "Document text could not be decoded"


def parse_document(document: Document) -> ParsedDocument:
    path = Path(document.storage_path)
    if not path.is_file():
        raise DocumentFileNotFoundError

    match document.file_type:
        case "pdf":
            pages = parse_pdf(path)
        case "txt":
            pages = parse_txt(path)
        case _:
            raise UnsupportedDocumentTypeError

    return ParsedDocument(
        document_id=str(document.id),
        file_type=document.file_type,
        pages=pages,
    )


def parse_txt(path: Path) -> list[ParsedPage]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentTextDecodeError from exc
    except OSError as exc:
        raise DocumentParsingError from exc

    return [ParsedPage(page_number=1, text=text)]


def parse_pdf(path: Path) -> list[ParsedPage]:
    try:
        reader = PdfReader(path)
        return [
            ParsedPage(page_number=page_number, text=page.extract_text() or "")
            for page_number, page in enumerate(reader.pages, start=1)
        ]
    except (PdfReadError, OSError, ValueError) as exc:
        raise DocumentParsingError from exc
