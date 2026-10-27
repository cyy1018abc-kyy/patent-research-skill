"""Document locators (blueprint C-04): hash-bound, verifiable citation anchors.

Contract (interface rule 6, UT-D02):

* an anchor binds ``raw_sha256`` (the raw artifact), ``paragraph`` id, ``text_hash``
  (SHA-256 of the quoted text), and ``parser_version``;
* :func:`make_anchor` refuses to emit a citable anchor from a low-quality parse —
  it returns one graded ``unverified`` instead;
* :func:`verify_anchor` re-checks the raw file hash AND the paragraph text: a changed
  file, a drifted paragraph id, or a changed text yields ``stale`` — old locators are
  never silently reused after the document changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patent_intel.contracts import AnchorVerification, DocumentAnchor
from patent_intel.documents.quality import QUALITY_THRESHOLD
from patent_intel.documents.schema import StructuredPatentDocument
from patent_intel.io.safe_io import sha256_file

__all__ = ["make_anchor", "verify_anchor", "LocatorError"]

_OWNER = "WP-C"


class LocatorError(ValueError):
    """Anchor creation/verification received an impossible request."""


def make_anchor(
    doc: StructuredPatentDocument,
    para_id: str,
    *,
    quote: str | None = None,
) -> DocumentAnchor:
    """Create an anchor for one paragraph. ``quote`` selects the cited span (default: whole paragraph)."""
    para = doc.paragraph_by_id(para_id)
    if para is None:
        raise LocatorError(f"paragraph {para_id!r} not in parsed document {doc.source_document}")
    text = (quote if quote is not None else para.text).strip()
    if not text:
        raise LocatorError("empty quote cannot anchor a citation")
    if quote is not None and quote.strip() not in para.text:
        raise LocatorError(
            f"quote not found verbatim inside paragraph {para_id}: anchor would be fabricated"
        )
    quality = doc.quality or {}
    citable = bool(quality.get("citable", False))
    return DocumentAnchor(
        owner=_OWNER,
        raw_sha256=doc.raw_sha256,
        source_document=doc.source_document,
        paragraph=para.para_id,
        page=para.page,
        text_hash=_hash_text(text),
        parser_version=doc.parser_version,
        verification_status=(
            AnchorVerification.MACHINE_PARSED
            if citable and para.origin == "native_xml"
            else AnchorVerification.UNVERIFIED
        ),
        extra={
            "quote": text[:200],
            "quote_full": text,
            "paragraph_origin": para.origin,
            "section": para.section,
            "quality_score": quality.get("score"),
        },
    )


def verify_anchor(anchor: DocumentAnchor, doc: StructuredPatentDocument, *, raw_path: Path | None = None) -> str:
    """Re-verify an anchor against the (possibly changed) document/raw file.

    Returns the effective status; the input anchor object is not mutated.
    """
    if anchor.parser_version != doc.parser_version:
        return AnchorVerification.STALE  # parser changed: coordinates may have drifted
    if anchor.raw_sha256 != doc.raw_sha256:
        return AnchorVerification.STALE
    if raw_path is not None:
        try:
            if sha256_file(raw_path) != anchor.raw_sha256:
                return AnchorVerification.STALE
        except OSError:
            return AnchorVerification.STALE
    para = doc.paragraph_by_id(anchor.paragraph)
    if para is None:
        return AnchorVerification.STALE  # paragraph id drifted away
    quote = str((anchor.extra or {}).get("quote_full") or (anchor.extra or {}).get("quote") or "")
    if quote and quote.strip() not in para.text:
        return AnchorVerification.STALE
    return anchor.verification_status


def _hash_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_ = Any  # type-checker touchpoint
