"""Patent XML parsing (blueprint C-01) — OPS exchange-document style, namespace-agnostic.

Safety (UT-D01): the parser **refuses any document containing a DOCTYPE or entity
declaration** — external/internal entity expansion is a known XXE/ Billion-laughs
vector and patent XML never legitimately carries one. Parsing is size-capped.

Matching is by localname (namespace-prefix agnostic), mirroring the kernel's
``read_raw`` OPS convention. Paragraph ids come from the source's own ``num``
attributes when present (``origin=native_xml``), else parser-assigned sequential ids
(``origin=parser_assigned``) — the distinction is preserved so citations can say
whether a paragraph number is official.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from patent_intel.documents.quality import assess_quality
from patent_intel.documents.schema import (
    DocumentParseError,
    PARSER_VERSION,
    Paragraph,
    StructuredPatentDocument,
)
from patent_intel.io.safe_io import read_text_limited

__all__ = ["parse_patent_xml", "parse_text_document", "MAX_XML_BYTES"]

MAX_XML_BYTES = 32 * 1024 * 1024

_DOCTYPE = re.compile(r"<!DOCTYPE|<!ENTITY", re.IGNORECASE)


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iter_local(root: ET.Element, name: str):
    for el in root.iter():
        if _localname(el.tag) == name:
            yield el


def _first_local_text(root: ET.Element, name: str) -> str | None:
    for el in _iter_local(root, name):
        text = "".join(el.itertext()).strip()
        if text:
            return text
    return None


def parse_patent_xml(path: Path, *, source_document: str | None = None) -> StructuredPatentDocument:
    """Parse a patent XML export into a StructuredPatentDocument. XXE-safe, size-capped."""
    path = Path(path)
    raw = path.read_bytes()
    if len(raw) > MAX_XML_BYTES:
        raise DocumentParseError(f"XML larger than {MAX_XML_BYTES} bytes: {path}")
    sha = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if _DOCTYPE.search(text[:4096]):
        raise DocumentParseError(
            f"{path}: document declares DOCTYPE/ENTITY — refused (XXE-safe parser); "
            "patent exports never legitimately contain one"
        )
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise DocumentParseError(f"{path}: malformed XML: {exc}") from None

    doc = StructuredPatentDocument(
        source_document=source_document or str(path),
        raw_sha256=sha,
        parser_version=PARSER_VERSION,
    )

    # publication number: publication-reference / doc-number
    for el in _iter_local(root, "publication-reference"):
        num = _first_local_text(el, "doc-number")
        if num:
            doc.publication_number = num.strip()
            break
    if doc.publication_number is None:
        doc.publication_number = _first_local_text(root, "doc-number")

    doc.title = _first_local_text(root, "invention-title")
    xml_lang = "{http://www.w3.org/XML/1998/namespace}lang"
    doc.language = root.get("lang") or root.get(xml_lang)
    if doc.language is None:
        for el in _iter_local(root, "exchange-document"):
            doc.language = el.get("lang") or el.get(xml_lang)
            if doc.language:
                break

    counter = 0
    # abstract
    for el in _iter_local(root, "abstract"):
        for para_el in list(el):
            if _localname(para_el.tag) != "p":
                continue
            counter += 1
            doc.paragraphs.append(_make_paragraph(para_el, counter, "abstract"))
        if not list(el):  # abstract text directly under the element
            text_value = "".join(el.itertext()).strip()
            if text_value:
                counter += 1
                doc.paragraphs.append(Paragraph(f"p{counter:04d}", text_value, "parser_assigned", "abstract"))
        break

    # claims — paragraph id carries the native claim number so the claims parser
    # can read it without polluting the verbatim text
    for claims_el in _iter_local(root, "claims"):
        for claim_el in _iter_local(claims_el, "claim"):
            number_raw = claim_el.get("num") or ""
            claim_text = "".join(claim_el.itertext()).strip()
            if claim_text:
                counter += 1
                doc.paragraphs.append(
                    Paragraph(
                        para_id=f"claim-{number_raw}" if number_raw else f"p{counter:04d}",
                        text=claim_text,
                        origin="native_xml" if number_raw else "parser_assigned",
                        section="claims",
                    )
                )

    # description paragraphs
    for desc_el in _iter_local(root, "description"):
        for para_el in _iter_local(desc_el, "p"):
            counter += 1
            doc.paragraphs.append(_make_paragraph(para_el, counter, "description"))

    doc.quality = assess_quality(doc)
    return doc


def _make_paragraph(el: ET.Element, counter: int, section: str) -> Paragraph:
    num = el.get("num")
    text = "".join(el.itertext()).strip()
    return Paragraph(
        para_id=num if num else f"p{counter:04d}",
        text=text,
        origin="native_xml" if num else "parser_assigned",
        section=section,
    )


# ── plain text / markdown fallback ───────────────────────────────────


_HEADING = re.compile(r"^#{1,4}\s+", re.MULTILINE)
_PARA_SPLIT = re.compile(r"\n\s*\n")


def parse_text_document(path: Path, *, source_document: str | None = None) -> StructuredPatentDocument:
    """Parse a .md/.txt capture (e.g. CNIPA page export) into sections by headings."""
    path = Path(path)
    text = read_text_limited(path, max_bytes=MAX_XML_BYTES)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    doc = StructuredPatentDocument(
        source_document=source_document or str(path),
        raw_sha256=sha,
        parser_version=PARSER_VERSION,
    )
    m = re.search(r"^(?:#\s*)?((?:CN|EP|US|WO|ZZ)[0-9A-Z\s]+)$", text, re.MULTILINE)
    if m:
        doc.publication_number = m.group(1).strip().replace(" ", "")
    blocks = _PARA_SPLIT.split(text)
    section = "other"
    counter = 0
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        first_line = stripped.splitlines()[0]
        if _HEADING.match(first_line):
            heading = _HEADING.sub("", first_line).strip().lower()
            if "claim" in heading or "权利要求" in heading:
                section = "claims"
            elif "abstract" in heading or "摘要" in heading:
                section = "abstract"
            elif "description" in heading or "说明书" in heading:
                section = "description"
            continue
        counter += 1
        doc.paragraphs.append(
            Paragraph(para_id=f"t{counter:04d}", text=stripped, origin="parser_assigned", section=section)
        )
    doc.quality = assess_quality(doc)
    return doc


_ = Any  # type-checker touchpoint
