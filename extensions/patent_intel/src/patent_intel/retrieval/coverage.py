"""Coverage diagnostics and incremental-yield accounting (blueprint A-05).

Answers: "哪些技术特征已覆盖、哪些子领域还没有任何命中、下一条查询带来了多少
独立新增候选"。All state is derived from query results and rebuildable —
never treated as kernel truth.

Accounting discipline (adaptive roadmap Task 1):

* **feature dimension is authoritative.** Hits are recorded per ``feature_id``
  (via :meth:`CoverageTracker.record_feature_hit`); the axis dimension only tracks
  which sub-areas saw any family at all. Query-type strings are never treated as
  technical concepts.
* **three separate yield buckets.** Every first-seen family is a *candidate*;
  *suspected relevant* and *confirmed relevant* are separate sets that can only be
  filled by explicit marking (an evaluator or a human) — they are never inferred
  from hit counts. Candidate ≠ relevant.
* **document-level and family-level yield are recorded side by side.** When family
  relations are unreported, documents stay document-level evidence; nothing
  promotes a document id into the family dimension (UT-S03).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

__all__ = ["CoverageTracker", "CoverageReport", "QueryYieldLedger"]

_OWNER = "WP-A"


class QueryYieldLedger:
    """Per-query yield of *independent new* candidates, deduped per dimension.

    ``record()`` dedupes family ids; ``record_documents()`` dedupes document ids.
    Relevance lives in separate ``suspected`` / ``confirmed`` sets filled only via
    explicit :meth:`mark_suspected` / :meth:`mark_confirmed` calls.
    """

    def __init__(self) -> None:
        self._seen_families: set[str] = set()
        self._seen_docs: set[str] = set()
        self._discovery_order: list[str] = []
        self._by_query: dict[str, list[str]] = {}
        self._docs_by_query: dict[str, list[str]] = {}
        self._order: list[str] = []
        self._suspected: set[str] = set()
        self._confirmed: set[str] = set()

    def record(self, query_id: str, family_hits: list[str]) -> list[str]:
        """Register family-level hits; returns the subset that is genuinely new."""
        new: list[str] = []
        for fam in family_hits:
            if fam not in self._seen_families:
                self._seen_families.add(fam)
                self._discovery_order.append(fam)
                new.append(fam)
        self._by_query[query_id] = new
        if query_id not in self._order:
            self._order.append(query_id)
        return new

    def record_documents(self, query_id: str, doc_hits: list[str]) -> list[str]:
        """Register document-level hits; returns the subset that is genuinely new."""
        new: list[str] = []
        for doc in doc_hits:
            if doc not in self._seen_docs:
                self._seen_docs.add(doc)
                new.append(doc)
        merged = self._docs_by_query.get(query_id, [])
        merged = merged + [doc for doc in new if doc not in merged]
        self._docs_by_query[query_id] = merged
        if query_id not in self._order:
            self._order.append(query_id)
        return new

    def _mark(self, target: set[str], family_ids: Iterable[str]) -> list[str]:
        marked: list[str] = []
        for fam in family_ids:
            if fam not in self._seen_families:
                raise ValueError(
                    f"cannot mark relevance for unknown family {fam!r}: only families the "
                    "ledger actually saw as candidates can be marked (candidate ≠ relevant)"
                )
            if fam not in target:
                target.add(fam)
                marked.append(fam)
        return marked

    def mark_suspected(self, family_ids: Iterable[str]) -> list[str]:
        """Explicitly mark first-seen families as *suspected relevant* (evaluator judgement)."""
        return self._mark(self._suspected, family_ids)

    def mark_confirmed(self, family_ids: Iterable[str]) -> list[str]:
        """Explicitly mark first-seen families as *confirmed relevant* (human/annotation)."""
        return self._mark(self._confirmed, family_ids)

    def yield_of(self, query_id: str) -> list[str]:
        return list(self._by_query.get(query_id, []))

    @property
    def total_new_families(self) -> int:
        """Candidate new families — first-seen, NOT relevance-filtered."""
        return len(self._seen_families)

    @property
    def discovery_order_families(self) -> list[str]:
        """Candidate families in first-seen order (deduped) — the fusion/ranking input."""
        return list(self._discovery_order)

    @property
    def total_new_documents(self) -> int:
        return len(self._seen_docs)

    @property
    def suspected_relevant(self) -> set[str]:
        return set(self._suspected)

    @property
    def confirmed_relevant(self) -> set[str]:
        return set(self._confirmed)

    def accounting(self) -> dict[str, Any]:
        """The three-bucket accounting report (candidates vs suspected vs confirmed)."""
        return {
            "candidate_families": self.total_new_families,
            "candidate_documents": self.total_new_documents,
            "suspected_relevant_families": len(self._suspected),
            "confirmed_relevant_families": len(self._confirmed),
            "note": (
                "候选新增 ≠ 相关新增：suspected/confirmed 只能显式标注，"
                "命中数不自动升级为相关 (candidate ≠ relevant)"
            ),
        }

    def describe(self) -> dict[str, Any]:
        return {
            "queries_in_order": list(self._order),
            "new_families_by_query": dict(self._by_query),
            "total_new_families": self.total_new_families,
            "new_documents_by_query": dict(self._docs_by_query),
            "total_new_documents": self.total_new_documents,
            "accounting": self.accounting(),
        }


@dataclass
class CoverageTracker:
    """Technical-feature coverage per feature id, plus per-axis family presence."""

    #: feature_id -> family ids whose retrieval covered the feature
    feature_families: dict[str, set[str]] = field(default_factory=dict)
    #: feature_id -> query ids that contributed coverage
    feature_queries: dict[str, set[str]] = field(default_factory=dict)
    #: feature_id -> axis it was first recorded under
    feature_axis: dict[str, str] = field(default_factory=dict)
    #: axis_id -> set of concept labels with at least one hit (legacy concept view)
    covered_concepts: dict[str, set[str]] = field(default_factory=dict)
    #: axis_id -> sub-area -> hit count (concept from terminology expansions)
    concept_hits: dict[str, dict[str, int]] = field(default_factory=dict)
    #: axis_id -> discovered family ids
    families: dict[str, set[str]] = field(default_factory=dict)

    def record_feature_attempt(self, feature_id: str, *, query_id: str, axis_id: str = "") -> None:
        """Record that a query targeting ``feature_id`` executed (independent of hits).

        Attempts distinguish ``not_found`` (cleanly executed, nothing covered the
        feature) from ``unknown`` (never targeted, or the queries failed) — the
        evaluator's state machine needs both signals.
        """
        if query_id:
            self.feature_queries.setdefault(feature_id, set()).add(query_id)
        if axis_id:
            self.feature_axis.setdefault(feature_id, axis_id)

    def record_feature_hit(
        self, feature_id: str, family_id: str, *, query_id: str = "", axis_id: str = ""
    ) -> None:
        """Record that ``family_id`` was retrieved for technical feature ``feature_id``."""
        self.feature_families.setdefault(feature_id, set()).add(family_id)
        if query_id:
            self.feature_queries.setdefault(feature_id, set()).add(query_id)
        if axis_id:
            self.feature_axis.setdefault(feature_id, axis_id)
            self.families.setdefault(axis_id, set()).add(family_id)

    def record_axis_family(self, axis_id: str, family_id: str) -> None:
        """Axis-level family presence only (no concept attribution)."""
        self.families.setdefault(axis_id, set()).add(family_id)

    def record_hit(self, axis_id: str, concept: str, family_id: str) -> None:
        """Legacy concept-keyed hit recording (kept for direct callers; the adaptive
        controller uses :meth:`record_feature_hit` — query types are not concepts)."""
        self.covered_concepts.setdefault(axis_id, set()).add(concept)
        hits = self.concept_hits.setdefault(axis_id, {})
        hits[concept] = hits.get(concept, 0) + 1
        self.families.setdefault(axis_id, set()).add(family_id)

    def uncovered_concepts(self, axis_id: str, all_concepts: list[str]) -> list[str]:
        covered = self.covered_concepts.get(axis_id, set())
        return [c for c in all_concepts if c not in covered]

    def uncovered_axes(self, axes: list[str]) -> list[str]:
        return [axis for axis in axes if not self.families.get(axis)]

    def covered_feature_ids(self, candidate_features: Iterable[str]) -> list[str]:
        """Features from ``candidate_features`` with at least one covering family."""
        return [f for f in candidate_features if self.feature_families.get(f)]

    def report(
        self,
        axes: list[str],
        concepts_by_axis: dict[str, list[str]],
        *,
        feature_ids_by_axis: dict[str, list[str]] | None = None,
    ) -> "CoverageReport":
        """Build the coverage report.

        ``concepts_by_axis`` may carry legacy concept labels or feature ids; a concept
        counts as covered when it was recorded either via the legacy concept view or
        (for feature ids) via the feature dimension.
        """
        per_axis: dict[str, dict[str, Any]] = {}
        per_feature: dict[str, dict[str, Any]] = {}
        for axis in axes:
            all_concepts = concepts_by_axis.get(axis, [])
            feature_ids = (feature_ids_by_axis or {}).get(axis) or [
                c for c in all_concepts if c in self.feature_families
            ]
            # features actually recorded under this axis always surface — the report
            # describes what was recorded, not only what the caller remembered
            for feature_id in sorted(
                f for f, ax in self.feature_axis.items() if ax == axis
            ):
                if feature_id not in feature_ids:
                    feature_ids.append(feature_id)
            for feature_id in feature_ids:
                fams = self.feature_families.get(feature_id, set())
                per_feature[feature_id] = {
                    "axis_id": self.feature_axis.get(feature_id, axis),
                    "covered": bool(fams),
                    "families": len(fams),
                    "queries": sorted(self.feature_queries.get(feature_id, set())),
                }
            uncovered = self.uncovered_concepts(axis, all_concepts)
            # a concept is covered when legacy-recorded OR feature-recorded
            uncovered = [
                c for c in uncovered if not self.feature_families.get(c)
            ]
            per_axis[axis] = {
                "concepts_total": len(all_concepts),
                "concepts_covered": len(all_concepts) - len(uncovered),
                "concepts_uncovered": uncovered,
                "features_total": len(feature_ids),
                "features_covered": len(self.covered_feature_ids(feature_ids)),
                "families_found": len(self.families.get(axis, set())),
                "has_hits": bool(self.families.get(axis)),
            }
        return CoverageReport(
            per_axis=per_axis,
            uncovered_axes=self.uncovered_axes(axes),
            per_feature=per_feature,
        )


@dataclass
class CoverageReport:
    per_axis: dict[str, dict[str, Any]]
    #: axes with zero hits anywhere — the "未覆盖子领域" list
    uncovered_axes: list[str]
    #: feature_id -> {axis_id, covered, families, queries} (feature-authoritative view)
    per_feature: dict[str, dict[str, Any]] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "per_axis": self.per_axis,
            "uncovered_axes": self.uncovered_axes,
            "per_feature": self.per_feature,
            "note": "coverage describes the searched sample only; 停止/未覆盖≠证明不存在",
        }
