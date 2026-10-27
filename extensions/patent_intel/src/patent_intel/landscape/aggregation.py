"""Landscape aggregation (blueprint E-01): applicant / classification / region stats
after family deduplication.

Honesty rules:
* **family counts and document counts are reported separately** — never conflated;
* records with unknown family status are **never merged** into families; they are
  counted as single-document entries and their share is disclosed;
* missing fields (no applicant, no class, no region) are counted and shown, never
  silently dropped from the denominators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from patent_intel.sources.family import FamilyView

__all__ = ["aggregate_landscape", "LandscapeStats"]

_OWNER = "WP-E"


def _norm(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "(missing)"


@dataclass
class LandscapeStats:
    #: dimension -> value -> {"families": n, "documents": n, "unknown_family_docs": n}
    by_applicant: dict[str, dict[str, int]] = field(default_factory=dict)
    by_class: dict[str, dict[str, int]] = field(default_factory=dict)
    by_region: dict[str, dict[str, int]] = field(default_factory=dict)
    totals: dict[str, int] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "by_applicant": self.by_applicant,
            "by_class": self.by_class,
            "by_region": self.by_region,
            "totals": self.totals,
            "caveat": "descriptive statistics over the searched sample only; "
            "sparse clusters do NOT prove a technology blank (E-04)",
        }


def aggregate_landscape(records: list[dict[str, Any]]) -> LandscapeStats:
    """Aggregate records into family-aware counts per dimension.

    ``records``: dicts with optional ``publication_number``, ``assignee`` /
    ``applicants`` (list or str), ``class_code``/``ipc``/``cpc``, ``region``
    (from country code) and ``family_refs``. Family grouping uses the same
    conservative rules as WP-B (reported family ids only).

    Counting model: a **family group contributes 1 family** per dimension value
    it touches (once, not per member) and 1 document per member; unknown-family
    documents contribute documents only, tracked separately.
    """
    from collections import Counter

    view = FamilyView()
    for record in records:
        view.add(record)

    tables: dict[str, dict[str, dict[str, int]]] = {
        "applicant": {},
        "class": {},
        "region": {},
    }
    doc_total = 0
    unknown_family_docs = 0
    family_docs = 0

    for group in view.groups:
        is_family = group.family_status == "reported"
        per_dim: dict[str, Counter[str]] = {"applicant": Counter(), "class": Counter(), "region": Counter()}
        for member in group.members:
            doc_total += 1
            if is_family:
                family_docs += 1
            else:
                unknown_family_docs += 1
            applicants = member.get("assignee") or member.get("applicants") or []
            if isinstance(applicants, str):
                applicants = [applicants]
            for applicant in applicants or ["(missing)"]:
                per_dim["applicant"][str(applicant)] += 1
            cls = member.get("class_code") or member.get("ipc") or member.get("cpc")
            cls_items = list(cls) if isinstance(cls, (list, tuple)) else [cls or "(missing)"]
            for item in cls_items:
                per_dim["class"][str(item)] += 1
            pub = str(member.get("publication_number") or "")
            region = pub[:2] if len(pub) >= 2 and pub[:2].isalpha() else "(missing)"
            per_dim["region"][region] += 1

        for dim, counter in per_dim.items():
            for value, member_count in counter.items():
                table = tables[dim]
                cell = table.setdefault(
                    value, {"families": 0, "documents": 0, "unknown_family_docs": 0}
                )
                cell["documents"] += member_count
                if is_family:
                    cell["families"] += 1  # once per group, not per member
                else:
                    cell["unknown_family_docs"] += member_count

    stats = LandscapeStats(
        by_applicant=tables["applicant"],
        by_class=tables["class"],
        by_region=tables["region"],
        totals={
            "documents": doc_total,
            "family_group_docs": family_docs,
            "unknown_family_docs": unknown_family_docs,
            "family_groups": sum(1 for g in view.groups if g.family_status == "reported"),
        },
    )
    return stats
