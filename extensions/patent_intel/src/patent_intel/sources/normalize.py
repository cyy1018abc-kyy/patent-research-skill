"""Identifier normalization (blueprint B-03).

Rule: **the original string is preserved verbatim** — normalization produces a
parallel view, never a rewrite. Confidence grades:
* ``exact``       — already canonical;
* ``normalized``  — cleaned into canonical form (spaces/case/prefixes);
* ``uncertain``   — cannot be parsed confidently; the caller must treat the record
  as unresolved (never guess a family or merge).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["NormalizedID", "normalize_publication_number", "normalize_doi"]

_TWO_LETTER = re.compile(r"^[A-Z]{2}$")
_KIND_CODE = re.compile(r"^[A-Z][0-9]?$")  # A, A1, B, B1, U, S, T9 …
_SPACES = re.compile(r"[\s\-–—]")


@dataclass(frozen=True)
class NormalizedID:
    original: str
    normalized: str
    kind: str  # "publication" | "application" | "doi" | "unknown"
    country_code: str | None
    kind_code: str | None
    confidence: str  # exact | normalized | uncertain


def _split_kind(serial: str) -> tuple[str, str | None]:
    """Split trailing kind code (letters[+digit]) from the numeric part."""
    match = re.fullmatch(r"([0-9]+)([A-Z][0-9]?)", serial)
    if match:
        return match.group(1), match.group(2)
    if serial.isdigit():
        return serial, None
    return serial, None


def normalize_publication_number(raw: str) -> NormalizedID:
    """Normalize a patent publication/application number.

    Accepted shapes (non-exhaustive, confidence degrades honestly):
    * ``CN119000001A`` / ``CN 119 000 001 A`` → publication, cc=CN, kind=A
    * ``EP1234567A1`` / ``US 2026/0100000 A1`` → publication
    * ``ZZ900011A1`` (synthetic test numbers) → publication, cc=ZZ
    * ``202610000000.1`` / ``CN202610000000.1`` → application
    """
    original = raw
    cleaned = _SPACES.sub("", raw.strip()).upper().replace("/", "")
    if not cleaned:
        return NormalizedID(original, "", "unknown", None, None, "uncertain")

    # application numbers like 202610000000.1
    if re.fullmatch(r"[0-9]{6,15}\.[0-9Xx]", cleaned) or re.fullmatch(
        r"(CN|US|EP|JP|KR|DE|WO)?[0-9]{6,15}\.[0-9Xx]", cleaned
    ):
        cc = cleaned[:2] if cleaned[:2].isalpha() else None
        return NormalizedID(original, cleaned, "application", cc, None, "normalized")

    # country prefix + serial (+ kind code)
    match = re.fullmatch(r"([A-Z]{2})([0-9]{5,12})([A-Z][0-9]?)?", cleaned)
    if match and _TWO_LETTER.match(match.group(1)):
        cc, serial, kind = match.group(1), match.group(2), match.group(3)
        numeric, kind_tail = _split_kind(serial)
        kind_code = kind or kind_tail
        canonical = f"{cc}{numeric}{kind_code or ''}"
        exact = original == canonical
        return NormalizedID(
            original=original,
            normalized=canonical,
            kind="publication",
            country_code=cc,
            kind_code=kind_code,
            confidence="exact" if exact else "normalized",
        )

    # bare numeric serial — not enough information to canonicalize
    if cleaned.isdigit():
        return NormalizedID(original, cleaned, "unknown", None, None, "uncertain")

    return NormalizedID(original, cleaned, "unknown", None, None, "uncertain")


_DOI_PREFIX = re.compile(r"^https?://(dx\.)?doi\.org/", re.IGNORECASE)
_DOI_BODY = re.compile(r"^10\.[0-9]{4,9}/\S+$", re.IGNORECASE)


def normalize_doi(raw: str) -> NormalizedID:
    """Normalize a DOI: strip resolver prefixes; the body keeps its original case
    (DOIs are case-insensitive, but the registrant's form is preserved for citations)."""
    original = raw.strip()
    body = _DOI_PREFIX.sub("", original)
    body = body.replace("doi:", "").replace("DOI:", "").strip()
    if not body:
        return NormalizedID(original, "", "doi", None, None, "uncertain")
    if _DOI_BODY.match(body):
        exact = body == original
        return NormalizedID(original, body, "doi", None, None, "exact" if exact else "normalized")
    return NormalizedID(original, body, "doi", None, None, "uncertain")
