"""Landscape trends (blueprint E-02): counts by publication year / technology axis.

Missing dates and classes are first-class buckets — trends never silently drop
records they cannot date, and the report states the sample-bias caveat.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

__all__ = ["trend_by_year", "trend_by_axis", "extract_year"]

_YEAR = re.compile(r"(1[89]\d{2}|20\d{2})")


def extract_year(record: dict[str, Any]) -> str | None:
    """Publication year from ``publication_date``/``year``; None when absent/invalid
    (the record then lands in the explicit '(missing)' bucket at the caller)."""
    date = str(record.get("publication_date") or "")
    m = _YEAR.search(date)
    if m:
        return m.group(1)
    year = record.get("year")
    if isinstance(year, int) and 1800 <= year <= 2100:
        return str(year)
    return None


def trend_by_year(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for record in records:
        year = extract_year(record)
        counts[year if year else "(missing)"] += 1
    ordered = dict(sorted(counts.items(), key=lambda kv: (kv[0] == "(missing)", kv[0])))
    return {
        "by_year": ordered,
        "documents": len(records),
        "missing_year_share": round(counts.get("(missing)", 0) / len(records), 4) if records else 0.0,
        "caveat": "sample counts only; no interpolation, no field-completeness correction",
    }


def trend_by_axis(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    missing = 0
    for record in records:
        axes = record.get("tags") or []
        if not axes:
            missing += 1
            continue
        for axis in axes:
            counts[str(axis)] += 1
    return {
        "by_axis": dict(counts.most_common()),
        "documents_without_axis": missing,
        "caveat": "axis tags come from the workspace search logs; they reflect where we "
        "searched, not where the field is active",
    }
