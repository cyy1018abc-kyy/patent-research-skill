"""Terminology helpers (blueprint A-02): relations, language detection, normalization.

The load-bearing distinction: **hypernym/hyponym/cross-domain terms broaden the
net but are not legal equivalents** of the source feature. Retrieval may use them;
anything downstream that maps evidence back to features must re-verify disclosure
against the *original* feature statement, never against the expanded term.
"""

from __future__ import annotations

import re

__all__ = [
    "TermRelation",
    "BROADENING_RELATIONS",
    "is_broadening",
    "detect_language",
    "normalize_term",
]


class TermRelation:
    BASE = "base"
    SYNONYM = "synonym"
    HYPERNYM = "hypernym"
    HYPONYM = "hyponym"
    TRANSLATION = "translation"
    ABBREVIATION = "abbreviation"
    CROSS_DOMAIN = "cross_domain"

    ALL = (BASE, SYNONYM, HYPERNYM, HYPONYM, TRANSLATION, ABBREVIATION, CROSS_DOMAIN)


#: Relations that widen meaning — usable for recall, never for equivalence claims.
BROADENING_RELATIONS = frozenset({TermRelation.HYPERNYM, TermRelation.HYPONYM, TermRelation.CROSS_DOMAIN})


def is_broadening(relation: str) -> bool:
    return relation in BROADENING_RELATIONS


_ZH = re.compile(r"[\u4e00-\u9fff]")
_EN = re.compile(r"[a-zA-Z]")


def detect_language(text: str) -> str:
    """'zh' | 'en' | 'zh+en' — composite tags are the norm in patent search."""
    has_zh = bool(_ZH.search(text))
    has_en = bool(_EN.search(text))
    if has_zh and has_en:
        return "zh+en"
    if has_zh:
        return "zh"
    if has_en:
        return "en"
    return "unknown"


def normalize_term(term: str) -> str:
    """Casefold + collapse whitespace for dedup comparisons (display keeps original)."""
    return re.sub(r"\s+", " ", term.strip()).casefold()
