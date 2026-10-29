"""Coverage diagnostics and incremental-yield accounting (blueprint A-05).

Answers: "哪些技术概念已覆盖、哪些子领域还没有任何命中、下一条查询带来了多少
独立新增有效专利族"。All state is derived from query results and rebuildable —
never treated as kernel truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["CoverageTracker", "CoverageReport", "QueryYieldLedger"]

_OWNER = "WP-A"


class QueryYieldLedger:
    """Per-query yield of *independent* new relevant families (dedup by family id)."""

    def __init__(self) -> None:
        self._seen_families: set[str] = set()
        self._by_query: dict[str, list[str]] = {}
        self._order: list[str] = []

    def record(self, query_id: str, family_hits: list[str]) -> list[str]:
        """Register hits for a query; returns the subset that is genuinely new."""
        new: list[str] = []
        for fam in family_hits:
            if fam not in self._seen_families:
                self._seen_families.add(fam)
                new.append(fam)
        self._by_query[query_id] = new
        if query_id not in self._order:
            self._order.append(query_id)
        return new

    def yield_of(self, query_id: str) -> list[str]:
        return list(self._by_query.get(query_id, []))

    @property
    def total_new_families(self) -> int:
        return len(self._seen_families)

    def describe(self) -> dict[str, Any]:
        return {
            "queries_in_order": list(self._order),
            "new_families_by_query": dict(self._by_query),
            "total_new_families": self.total_new_families,
        }


@dataclass
class CoverageTracker:
    """Technical-concept coverage per axis and sub-area."""

    #: axis_id -> set of concept labels with at least one hit
    covered_concepts: dict[str, set[str]] = field(default_factory=dict)
    #: axis_id -> sub-area -> hit count (concept from terminology expansions)
    concept_hits: dict[str, dict[str, int]] = field(default_factory=dict)
    #: axis_id -> discovered family ids
    families: dict[str, set[str]] = field(default_factory=dict)

    def record_hit(self, axis_id: str, concept: str, family_id: str) -> None:
        self.covered_concepts.setdefault(axis_id, set()).add(concept)
        hits = self.concept_hits.setdefault(axis_id, {})
        hits[concept] = hits.get(concept, 0) + 1
        self.families.setdefault(axis_id, set()).add(family_id)

    def uncovered_concepts(self, axis_id: str, all_concepts: list[str]) -> list[str]:
        covered = self.covered_concepts.get(axis_id, set())
        return [c for c in all_concepts if c not in covered]

    def uncovered_axes(self, axes: list[str]) -> list[str]:
        return [axis for axis in axes if not self.families.get(axis)]

    def report(self, axes: list[str], concepts_by_axis: dict[str, list[str]]) -> "CoverageReport":
        per_axis: dict[str, dict[str, Any]] = {}
        for axis in axes:
            all_concepts = concepts_by_axis.get(axis, [])
            uncovered = self.uncovered_concepts(axis, all_concepts)
            per_axis[axis] = {
                "concepts_total": len(all_concepts),
                "concepts_covered": len(all_concepts) - len(uncovered),
                "concepts_uncovered": uncovered,
                "families_found": len(self.families.get(axis, set())),
                "has_hits": bool(self.families.get(axis)),
            }
        return CoverageReport(per_axis=per_axis, uncovered_axes=self.uncovered_axes(axes))


@dataclass
class CoverageReport:
    per_axis: dict[str, dict[str, Any]]
    #: axes with zero hits anywhere — the "未覆盖子领域" list
    uncovered_axes: list[str]

    def describe(self) -> dict[str, Any]:
        return {
            "per_axis": self.per_axis,
            "uncovered_axes": self.uncovered_axes,
            "note": "coverage describes the searched sample only; 停止/未覆盖≠证明不存在",
        }
