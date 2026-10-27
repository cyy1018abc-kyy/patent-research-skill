"""WP-C document understanding tests (UT-D01/UT-D02, blueprint C-01..C-05 acceptance)."""

from __future__ import annotations

from pathlib import Path

import pytest

from patent_intel.contracts import AnchorVerification
from patent_intel.documents.claims import parse_claim_dependencies
from patent_intel.documents.locators import LocatorError, make_anchor, verify_anchor
from patent_intel.documents.patent_xml import parse_patent_xml, parse_text_document
from patent_intel.documents.pdf_adapter import PdfDependencyError, parse_pdf
from patent_intel.documents.schema import DocumentParseError, PARSER_VERSION

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "documents"
XML_PATH = FIXTURES / "sample_exchange.xml"
TEXT_PATH = FIXTURES / "sample_text.md"


@pytest.fixture()
def xml_doc() -> object:
    return parse_patent_xml(XML_PATH)


# ── C-01: XML parsing (UT-D01) ───────────────────────────────────────


def test_parse_xml_multi_namespace_and_native_ids(xml_doc: object) -> None:
    doc = xml_doc  # type: ignore[union-attr]
    assert doc.publication_number == "CN119000001A"  # from exchange-document attributes (OPS form)
    assert doc.title and "时间同步" in doc.title
    assert doc.language == "zh"
    sections = {p.section for p in doc.paragraphs}
    assert {"abstract", "claims", "description"}.issubset(sections)
    # native numbering preserved with origin=native_xml
    p0012 = doc.paragraph_by_id("0012")
    assert p0012 is not None
    assert p0012.origin == "native_xml"
    assert "MAC层打戳" in p0012.text


def test_parse_xml_quality_is_assessed(xml_doc: object) -> None:
    doc = xml_doc  # type: ignore[union-attr]
    assert doc.quality["score"] > 0.7
    assert doc.quality["citable"] is True


def test_xxe_entity_document_refused(tmp_path: Path) -> None:
    """UT-D01: entity declarations are refused outright — no external resolution."""
    evil = tmp_path / "evil.xml"
    evil.write_text(
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]>'
        "<root><p>&a;</p></root>",
        encoding="utf-8",
    )
    with pytest.raises(DocumentParseError, match="DOCTYPE"):
        parse_patent_xml(evil)


def test_billion_laughs_declared_entity_refused(tmp_path: Path) -> None:
    evil = tmp_path / "laugh.xml"
    evil.write_text(
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]><lolz>&lol;</lolz>',
        encoding="utf-8",
    )
    with pytest.raises(DocumentParseError, match="DOCTYPE"):
        parse_patent_xml(evil)


def test_malformed_xml_controlled_failure(tmp_path: Path) -> None:
    bad = tmp_path / "bad.xml"
    bad.write_text("<root><p>unclosed", encoding="utf-8")
    with pytest.raises(DocumentParseError, match="malformed"):
        parse_patent_xml(bad)


def test_missing_paragraph_numbers_get_parser_ids(tmp_path: Path) -> None:
    plain = tmp_path / "plain.xml"
    plain.write_text(
        '<doc><abstract><p>摘要内容</p></abstract><description><p>说明内容</p></description></doc>',
        encoding="utf-8",
    )
    doc = parse_patent_xml(plain)
    assert all(p.origin == "parser_assigned" for p in doc.paragraphs)
    assert len(doc.paragraphs) == 2


# ── text documents ───────────────────────────────────────────────────


def test_parse_text_document_sections() -> None:
    doc = parse_text_document(TEXT_PATH)
    assert doc.publication_number == "ZZ900011A1"
    sections = {p.section for p in doc.paragraphs}
    assert "claims" in sections and "abstract" in sections and "description" in sections


# ── C-02: claims (dependency tree) ───────────────────────────────────


def test_claim_dependency_tree(xml_doc: object) -> None:
    doc = xml_doc  # type: ignore[union-attr]
    claims = parse_claim_dependencies(doc)  # type: ignore[arg-type]
    numbers = [c.number for c in claims]
    assert numbers == [1, 2, 3, 4]
    assert claims[0].is_independent
    assert claims[1].depends_on == [1]
    assert claims[2].depends_on == [1, 2]  # range 1-2 expanded
    # reference to nonexistent claim 9 → unresolved (never dropped, never guessed)
    assert claims[3].unresolved_refs == ["9"]
    assert claims[3].depends_on == []


def test_circular_dependency_detected() -> None:
    from patent_intel.documents.schema import Claim, StructuredPatentDocument

    doc = StructuredPatentDocument(source_document="x", raw_sha256="0" * 64)
    doc.claims = [
        Claim(number=1, text="a", depends_on=[2]),
        Claim(number=2, text="b", depends_on=[1]),
    ]
    issues = doc.claim_tree_issues()
    assert any("circular" in i for i in issues)


def test_duplicate_claim_numbers_flagged() -> None:
    from patent_intel.documents.schema import Claim, StructuredPatentDocument

    doc = StructuredPatentDocument(source_document="x", raw_sha256="0" * 64)
    doc.claims = [Claim(number=1, text="a", depends_on=[]), Claim(number=1, text="b", depends_on=[])]
    assert any("duplicate" in i for i in doc.claim_tree_issues())


# ── C-04: locators (UT-D02) ──────────────────────────────────────────


def test_make_anchor_binds_hashes(xml_doc: object) -> None:
    doc = xml_doc  # type: ignore[union-attr]
    anchor = make_anchor(doc, "0012")  # type: ignore[arg-type]
    assert anchor.raw_sha256 == doc.raw_sha256  # type: ignore[union-attr]
    assert anchor.verification_status == AnchorVerification.MACHINE_PARSED  # native numbering + clean parse
    assert len(anchor.text_hash) == 64


def test_make_anchor_with_subquote_must_match_verbatim(xml_doc: object) -> None:
    doc = xml_doc  # type: ignore[union-attr]
    anchor = make_anchor(doc, "0012", quote="MAC层打戳")  # type: ignore[arg-type]
    assert anchor.extra["quote_full"] == "MAC层打戳"
    with pytest.raises(LocatorError, match="verbatim"):
        make_anchor(doc, "0012", quote="这句话不存在")  # type: ignore[arg-type]


def test_anchor_from_low_quality_parse_is_unverified(tmp_path: Path) -> None:
    """OCR-damaged text: anchors may exist but only as unverified (no auto-citation)."""
    bad = tmp_path / "ocr.xml"
    bad.write_text(
        '<doc><description>'
        + "".join(f'<p num="00{i}">▓▒░ ;;:: 、、 ？？ </p>' for i in range(1, 20))
        + '</description></doc>',
        encoding="utf-8",
    )
    doc = parse_patent_xml(bad)
    assert doc.quality["citable"] is False
    anchor = make_anchor(doc, "001")
    assert anchor.verification_status == AnchorVerification.UNVERIFIED


def test_verify_anchor_detects_file_change(tmp_path: Path, xml_doc: object) -> None:
    doc = xml_doc  # type: ignore[union-attr]
    anchor = make_anchor(doc, "0012")  # type: ignore[arg-type]
    raw = tmp_path / "raw.xml"
    raw.write_bytes(XML_PATH.read_bytes())
    assert verify_anchor(anchor, doc, raw_path=raw) == AnchorVerification.MACHINE_PARSED
    raw.write_bytes(XML_PATH.read_bytes() + b"<!-- changed -->")
    assert verify_anchor(anchor, doc, raw_path=raw) == AnchorVerification.STALE


def test_verify_anchor_detects_paragraph_drift(xml_doc: object) -> None:
    """UT-D02: 段号漂移 → 失效，不静默复用。"""
    doc = xml_doc  # type: ignore[union-attr]
    anchor = make_anchor(doc, "0012")  # type: ignore[arg-type]
    drifted = parse_patent_xml(XML_PATH)
    object.__setattr__(drifted, "paragraphs", [p for p in drifted.paragraphs if p.para_id != "0012"])  # type: ignore[union-attr]
    assert verify_anchor(anchor, drifted) == AnchorVerification.STALE


def test_verify_anchor_detects_parser_version_change(xml_doc: object) -> None:
    doc = xml_doc  # type: ignore[union-attr]
    anchor = make_anchor(doc, "0012")  # type: ignore[arg-type]
    old_doc = parse_patent_xml(XML_PATH)
    old_doc.parser_version = "patent_intel.documents 0.0.9"  # type: ignore[union-attr]
    assert verify_anchor(anchor, old_doc) == AnchorVerification.STALE


def test_anchor_missing_paragraph_refused(xml_doc: object) -> None:
    with pytest.raises(LocatorError, match="not in parsed"):
        make_anchor(xml_doc, "9999")  # type: ignore[arg-type]


def test_parser_version_pin() -> None:
    """Anchors reference the parser version; changing it must be a deliberate bump."""
    assert PARSER_VERSION == "patent_intel.documents 0.1.0"


# ── C-03: PDF adapter (optional extra; guard + controlled failure) ───


def test_pdf_without_extra_degrades_with_install_hint(tmp_path: Path) -> None:
    fake = tmp_path / "doc.pdf"
    fake.write_bytes(b"%PDF-1.4 minimal")
    pytest.importorskip
    try:
        parse_pdf(fake)
    except PdfDependencyError as exc:
        assert "patent_intel[pdf]" in str(exc)
    except DocumentParseError:
        pass  # docling present but failed on the fake PDF: also a controlled failure
    else:
        pytest.fail("parse_pdf must not succeed on a non-PDF file")


def test_pdf_oversize_controlled_failure(tmp_path: Path) -> None:
    from patent_intel.documents import pdf_adapter

    big = tmp_path / "big.pdf"
    big.write_bytes(b"\0" * (pdf_adapter.MAX_PDF_BYTES + 1))
    with pytest.raises(DocumentParseError, match="larger than"):
        parse_pdf(big)
