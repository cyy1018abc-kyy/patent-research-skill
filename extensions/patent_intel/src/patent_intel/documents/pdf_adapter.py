"""Optional PDF parsing adapter (blueprint C-03).

The base wheel contains **no PDF code**: PDF parsing needs the ``pdf`` extra
(Docling). This module degrades honestly:

* missing dependency → :class:`PdfDependencyError` with the exact install command;
* oversize / encrypted PDFs → :class:`DocumentParseError` (controlled failure, never
  a half-parsed hallucination);
* on success, pages are parsed into Paragraphs with ``page`` set and
  ``origin=parser_assigned`` — OCR output never claims official paragraph numbers.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from patent_intel.documents.quality import assess_quality
from patent_intel.documents.schema import (
    DocumentParseError,
    PARSER_VERSION,
    Paragraph,
    StructuredPatentDocument,
)

__all__ = ["PdfDependencyError", "parse_pdf", "MAX_PDF_BYTES"]

MAX_PDF_BYTES = 200 * 1024 * 1024

_OWNER = "WP-C"


class PdfDependencyError(ImportError):
    """The `pdf` extra is not installed."""


def _require_docling() -> Any:
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401
    except ImportError as exc:
        raise PdfDependencyError(
            "PDF parsing requires the optional 'pdf' extra: "
            "pip install 'patent_intel[pdf]' (installs docling)"
        ) from exc
    from docling.document_converter import DocumentConverter

    return DocumentConverter


def parse_pdf(path: Path, *, source_document: str | None = None) -> StructuredPatentDocument:
    """Parse a PDF via Docling (optional extra). Controlled failures only."""
    path = Path(path)
    size = path.stat().st_size
    if size > MAX_PDF_BYTES:
        raise DocumentParseError(f"PDF larger than {MAX_PDF_BYTES} bytes: {path}")
    raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()

    Converter = _require_docling()
    converter = Converter()
    try:
        result = converter.convert(str(path))
    except Exception as exc:  # noqa: BLE001 - docling raises many shapes; all are parse failures
        raise DocumentParseError(f"PDF parsing failed for {path}: {type(exc).__name__}: {exc}") from None

    doc = StructuredPatentDocument(
        source_document=source_document or str(path),
        raw_sha256=raw_sha,
        parser_version=PARSER_VERSION,
    )
    exported = result.document.export_to_markdown()
    counter = 0
    page = 1
    for block in exported.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("<!---page"):  # docling page markers, if any
            digits = "".join(ch for ch in block if ch.isdigit())
            page = int(digits) if digits else page + 1
            continue
        counter += 1
        doc.paragraphs.append(
            Paragraph(para_id=f"pdf{counter:04d}", text=block, origin="parser_assigned", section="description", page=page)
        )
    doc.quality = assess_quality(doc)
    # OCR-derived text is never machine-citable without human confirmation: quality
    # cannot exceed "unverified" at parse time (locators.py enforces downstream).
    doc.quality["ocr_source"] = True
    return doc
