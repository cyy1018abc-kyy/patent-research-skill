"""Document locators (blueprint C-04): hash-bound, verifiable citation anchors.

Contract (interface rule 6, UT-D02):

* an anchor binds ``raw_sha256`` (the raw artifact), ``paragraph`` id, ``text_hash``
  (SHA-256 of the quoted text), and ``parser_version``;
* :func:`make_anchor` refuses to emit a citable anchor from a low-quality parse —
  it returns one graded ``unverified`` instead;
* :func:`verify_anchor` re-checks the raw file hash AND the paragraph text: a changed
  file, a drifted paragraph id, or a changed text yields ``stale`` — old locators are
  never silently reused after the document changes;
* 41C-2 extension: an anchor may additionally bind the corpus record's content hash
  (``extra.record_content_sha256``). :func:`anchor_staleness` checks that binding —
  a drifted or vanished record makes the anchor stale, and **every citation bound
  to a stale anchor is invalid until re-anchored** (锚点失效即引用失效).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patent_intel.contracts import AnchorVerification, DocumentAnchor
from patent_intel.documents.quality import QUALITY_THRESHOLD
from patent_intel.documents.schema import StructuredPatentDocument
from patent_intel.io.safe_io import sha256_file

__all__ = ["make_anchor", "verify_anchor", "anchor_staleness", "LocatorError"]

_OWNER = "WP-C"


class LocatorError(ValueError):
    """Anchor creation/verification received an impossible request."""


def make_anchor(
    doc: StructuredPatentDocument,
    para_id: str,
    *,
    quote: str | None = None,
    record_content_sha256: str | None = None,
) -> DocumentAnchor:
    """Create an anchor for one paragraph. ``quote`` selects the cited span (default: whole paragraph).

    ``record_content_sha256`` (41C-2) optionally binds the corpus record the
    anchored document came from — the binding ``anchor_staleness`` later checks.
    It is stored verbatim in ``extra``; anchors created without it simply carry
    no corpus binding (staleness verdicts then honestly stay ``unknown``).
    """
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
            "record_content_sha256": record_content_sha256,
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


def anchor_staleness(
    anchor: DocumentAnchor,
    records: Any,
    *,
    key: str | None = None,
    content_sha_field: str = "_content_sha256",
) -> dict[str, Any]:
    """41C-2: is the anchor's corpus binding still current? (read-only; C-04 extension)

    Checks the ``record_content_sha256`` binding carried in ``extra`` against the
    corpus ``records`` mapping (record key → record dict, e.g. the production
    store keyed by normalized publication number — pass ``key`` when the anchor's
    ``source_document`` is not the record key). Verdicts:

    * ``current``  — record exists and its content hash equals the binding;
    * ``drifted``  — record exists with different content → **stale**;
    * ``missing``  — record key vanished → **stale**;
    * ``unknown``  — the anchor carries no binding (or the record none) →
      currency cannot be confirmed; never reported as current.

    A ``stale`` verdict invalidates every citation bound to this anchor until it
    is re-anchored (锚点失效即引用失效). The anchor object is not mutated.
    """
    record_key = str(key) if key is not None else str(anchor.source_document)
    binding = (anchor.extra or {}).get("record_content_sha256")
    if not binding:
        return {
            "record_key": record_key,
            "verdict": "unknown",
            "stale": None,
            "reason": "anchor carries no corpus content binding",
        }
    get = records.get if hasattr(records, "get") else (lambda k, default=None: default)  # type: ignore[union-attr]
    record = get(record_key)
    if record is None:
        return {
            "record_key": record_key,
            "verdict": "missing",
            "stale": True,
            "reason": "bound record is no longer in the corpus",
        }
    current_sha = record.get(content_sha_field) if isinstance(record, dict) else None
    if not current_sha:
        return {
            "record_key": record_key,
            "verdict": "unknown",
            "stale": None,
            "reason": f"record carries no {content_sha_field!r} to compare against",
        }
    if str(current_sha) != str(binding):
        return {
            "record_key": record_key,
            "verdict": "drifted",
            "stale": True,
            "reason": "record content changed since the anchor was created",
        }
    return {
        "record_key": record_key,
        "verdict": "current",
        "stale": False,
        "reason": None,
    }


def _hash_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_ = Any  # type-checker touchpoint
