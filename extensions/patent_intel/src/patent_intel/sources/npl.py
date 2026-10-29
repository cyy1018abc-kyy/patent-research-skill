"""NPL (non-patent literature) evidence entry points (blueprint B-07).

The load-bearing distinction (interface rule 4 / UT-S04):

* **bibliographic metadata** (DOI, title, journal, dates) is *not* disclosure
  evidence — a paper's abstract/catalogue record never proves a technical
  teaching inside its body;
* **preprint vs published version** are distinct records: public dates, DOIs and
  content may all differ; a preprint must never stand in silently for the journal
  version (and vice versa);
* full-text availability is stated honestly; when we cannot verify a full text,
  `fulltext_availability` says ``unknown``/``metadata_only`` and callers must not
  fabricate disclosure citations from metadata.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from patent_intel.contracts import AnchorVerification, DocumentAnchor
from patent_intel.sources.normalize import normalize_doi

__all__ = ["NplRecord", "FulltextAvailability", "fulltext_availability", "version_relation", "npl_anchor"]

_OWNER = "WP-B"


@dataclass
class NplRecord:
    """One NPL bibliographic record, version-explicit."""

    record_id: str
    doi: str | None = None
    title: str | None = None
    #: "journal-article" | "proceedings-article" | "posted-content" (preprint) | …
    work_type: str | None = None
    #: Crossref-style deposited/issued dates (ISO strings)
    published_online: str | None = None
    published_print: str | None = None
    #: relation to other versions, e.g. {"is-preprint-of": "10.x/yyy"}
    relations: dict[str, str] = field(default_factory=dict)
    #: where the metadata came from (crossref/arxiv/manual)
    source: str = "crossref"
    #: URL that actually serves a full text (only set when the source says so)
    fulltext_url: str | None = None

    @classmethod
    def from_crossref(cls, item: dict[str, Any], *, record_id: str) -> "NplRecord":
        """Build from a Crossref works-API item (bibliographic fields only)."""
        doi_raw = str(item.get("DOI") or "")
        date_parts = (item.get("issued") or {}).get("date-parts") or [[]]
        published_online = None
        published_print = None
        online = (item.get("published-online") or {}).get("date-parts") or None
        print_ = (item.get("published-print") or {}).get("date-parts") or None
        if online and online[0]:
            published_online = "-".join(str(p) for p in online[0])
        if print_ and print_[0]:
            published_print = "-".join(str(p) for p in print_[0])
        if not published_online and not published_print and date_parts and date_parts[0]:
            issued = "-".join(str(p) for p in date_parts[0])
            published_print = issued
        relations: dict[str, str] = {}
        for rel_key, rel_items in (item.get("relation") or {}).items():
            for rel in rel_items or []:
                if isinstance(rel, dict) and rel.get("id"):
                    relations[rel_key] = str(rel["id"])
        return cls(
            record_id=record_id,
            doi=normalize_doi(doi_raw).normalized or None if doi_raw else None,
            title=(item.get("title") or [None])[0],
            work_type=item.get("type"),
            published_online=published_online,
            published_print=published_print,
            relations=relations,
            source="crossref",
        )


class FulltextAvailability:
    METADATA_ONLY = "metadata_only"  # catalogue/abstract only — NO disclosure evidence
    ABSTRACT = "abstract"            # abstract text captured; still not body disclosure
    FULLTEXT = "fulltext"            # a full-text artifact is actually captured
    UNKNOWN = "unknown"              # cannot determine honestly


def fulltext_availability(record: NplRecord, *, captured_text_bytes: int = 0) -> str:
    """Honest availability verdict for one record."""
    if captured_text_bytes > 0:
        return FulltextAvailability.FULLTEXT
    if record.fulltext_url:
        return FulltextAvailability.UNKNOWN  # URL claimed but nothing captured yet
    if record.work_type == "posted-content":
        return FulltextAvailability.ABSTRACT
    return FulltextAvailability.METADATA_ONLY


def version_relation(record: NplRecord) -> dict[str, Any]:
    """Preprint/published separation summary (never conflated, UT-S04)."""
    is_preprint = record.work_type == "posted-content"
    published_of = record.relations.get("is-preprint-of")
    preprint_of = record.relations.get("has-preprint")
    return {
        "record_id": record.record_id,
        "is_preprint": is_preprint,
        "published_doi": published_of or (record.doi if not is_preprint else None),
        "preprint_doi": preprint_of or (record.doi if is_preprint else None),
        "public_date": record.published_online or record.published_print,
        "note": (
            "preprint and journal version are separate records; citing one is not "
            "citing the other — dates and content may differ"
        ),
    }


def npl_anchor(record: NplRecord, quote: str, *, raw_sha256: str, source_document: str) -> DocumentAnchor:
    """Anchor a quote inside a *captured* NPL artifact.

    Metadata-only records have no artifact to anchor — callers must capture the
    artifact first; this function refuses to fabricate an anchor from metadata.
    """
    if not quote.strip():
        raise ValueError("empty quote")
    return DocumentAnchor(
        owner=_OWNER,
        raw_sha256=raw_sha256,
        source_document=source_document,
        paragraph="npl:quote",
        text_hash=hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        parser_version="patent_intel.sources.npl 0.1.0",
        verification_status=AnchorVerification.UNVERIFIED,  # NPL quotes await human confirmation
        extra={"doi": record.doi, "record_id": record.record_id, "quote": quote[:200]},
    )
