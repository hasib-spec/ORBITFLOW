"""
OrbitFlow Document Parsers
==========================

Multi-format file readers supporting:
- PDF (via pypdf / native stream parser)
- Text / Markdown (.txt, .md)
- CSV / TSV (via pandas or standard csv)
- Raw text strings
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Optional

from backend.app.core.config import get_logger
from backend.app.engines.doc_intel.schemas import DocumentType

log = get_logger(__name__)


class ParsedDocument:
    """Standardized multi-page text and table container."""
    def __init__(self, document_name: str, document_type: DocumentType):
        self.document_name = document_name
        self.document_type = document_type
        self.pages: list[str] = []
        self.tables: list[list[list[str]]] = []  # list of tables, each table is rows x cols
        self.metadata: dict[str, str] = {}

    @property
    def full_text(self) -> str:
        return "\n\n--- PAGE BREAK ---\n\n".join(self.pages)

    @property
    def page_count(self) -> int:
        return max(1, len(self.pages))


class DocumentParser:
    """Universal parser for satellite specifications and regulatory documents."""

    @staticmethod
    def parse_file(file_path: str | Path) -> ParsedDocument:
        """Parse a local file into a ParsedDocument."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found at: {path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return DocumentParser.parse_pdf_bytes(path.read_bytes(), path.name)
        elif suffix in [".txt", ".md", ".log", ".json", ".yaml", ".yml"]:
            text = path.read_text(encoding="utf-8", errors="replace")
            return DocumentParser.parse_text(text, path.name)
        elif suffix in [".csv", ".tsv"]:
            text = path.read_text(encoding="utf-8", errors="replace")
            return DocumentParser.parse_csv_text(text, path.name, delimiter="," if suffix == ".csv" else "\t")
        else:
            # Fallback treat as text
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                return DocumentParser.parse_text(text, path.name)
            except Exception as err:
                log.error("Unable to parse file %s: %s", path.name, err)
                raise ValueError(f"Unsupported file format for: {path.name}") from err

    @staticmethod
    def parse_text(text: str, document_name: str = "raw_input.txt") -> ParsedDocument:
        """Parse raw text string."""
        doc = ParsedDocument(document_name=document_name, document_type=DocumentType.TXT)
        # Split on standard page break markers if present
        if "--- PAGE BREAK ---" in text:
            doc.pages = text.split("--- PAGE BREAK ---")
        elif "\x0c" in text:  # Form feed
            doc.pages = text.split("\x0c")
        else:
            doc.pages = [text]
        return doc

    @staticmethod
    def parse_pdf_bytes(pdf_bytes: bytes, document_name: str = "uploaded_spec.pdf") -> ParsedDocument:
        """Parse PDF content from bytes using pypdf."""
        doc = ParsedDocument(document_name=document_name, document_type=DocumentType.PDF)
        
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for page_idx, page in enumerate(reader.pages, start=1):
                extracted = page.extract_text() or ""
                doc.pages.append(extracted)
            if reader.metadata:
                doc.metadata = {str(k): str(v) for k, v in reader.metadata.items()}
            log.info("Parsed %d pages from PDF '%s' with pypdf", len(doc.pages), document_name)
        except Exception as err:
            log.warning("pypdf parsing failed (%s), attempting text stream extraction fallback", err)
            # Fallback naive text extraction from binary stream
            text = pdf_bytes.decode("latin1", errors="replace")
            # Extract ascii text segments
            import re
            readable = " ".join(re.findall(r'[A-Za-z0-9\s.,;:\-_/\\#%()+=<>]{4,}', text))
            doc.pages = [readable]

        if not doc.pages or all(not p.strip() for p in doc.pages):
            doc.pages = ["(No extractable text found in document)"]

        return doc

    @staticmethod
    def parse_csv_text(csv_text: str, document_name: str = "spec.csv", delimiter: str = ",") -> ParsedDocument:
        """Parse CSV/TSV table."""
        doc = ParsedDocument(document_name=document_name, document_type=DocumentType.CSV)
        doc.pages = [csv_text]
        
        table: list[list[str]] = []
        try:
            reader = csv.reader(io.StringIO(csv_text), delimiter=delimiter)
            for row in reader:
                if any(c.strip() for c in row):
                    table.append(row)
            if table:
                doc.tables.append(table)
        except Exception as err:
            log.warning("CSV parsing warning for %s: %s", document_name, err)

        return doc
