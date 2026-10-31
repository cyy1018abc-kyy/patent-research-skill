"""Query plan builder (blueprint A-03, WP-A).

Produces the *query family* for one technical axis as ``QuerySpec`` proposals:

* ``single_feature`` — one query per required/optional feature;
* ``broad_recall``   — one wide OR-query per axis (recall safety net);
* ``feature_cross``  — AND across required feature term groups (max 3 ANDs — the
  CNIPA constraint is enforced here and **only for CNIPA rendering**, never
  generalized to other databases, UT-Q02);
* ``cross_domain``   — migration queries from cross-domain dictionary entries.

Hard rules:
* negation features never become positive terms (they annotate the plan as filters);
* every plan is a proposal (``approved=False``) living in the sidecar — the kernel's
  ``query_library.yml`` numbering (N1/N2/…) is never touched; plan ids use a
  ``Q-<axis>-<kind>-<n>`` scheme of their own;
* all term provenance flows through untouched (UT-Q03).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from patent_intel.contracts import FeatureSpec, QuerySpec, Requiredness
from patent_intel.retrieval.features import FeatureBundle
from patent_intel.retrieval.query_expand import (
    DictionaryExpander,
    Expander,
    TermCandidate,
    expand_features,
)
from patent_intel.retrieval.terminology import detect_language, is_broadening, normalize_term

__all__ = ["QueryPlan", "QueryPlanBuilder", "render_query", "CNIPA_MAX_AND"]

#: CNIPA epub 现行约束：主检索式最多 3 个 AND（SKILL 约束；按数据源渲染时才施加）。
CNIPA_MAX_AND = 3

_OWNER = "WP-A"


@dataclass
class QueryPlan:
    """One axis's query family — proposals only, human approval required."""

    axis_id: str
    queries: list[QuerySpec] = field(default_factory=list)
    #: negation/numeric features recorded as filters instead of positive queries
    annotations: list[dict[str, str]] = field(default_factory=list)

    def approved_queries(self) -> list[QuerySpec]:
        return [q for q in self.queries if q.approved]

    def describe(self) -> dict[str, object]:
        return {
            "axis_id": self.axis_id,
            "query_count": len(self.queries),
            "queries": [
                {
                    "query_id": q.query_id,
                    "query_type": q.query_type,
                    "terms": q.terms,
                    "language": q.language,
                    "approved": q.approved,
                    "provenance_count": len(q.provenance or []),
                }
                for q in self.queries
            ],
            "annotations": self.annotations,
        }


class QueryPlanBuilder:
    """Build the query family for one axis from extracted features + expanders."""

    def __init__(self, expanders: list[Expander] | None = None) -> None:
        self._expanders = expanders or [DictionaryExpander()]

    def build(
        self,
        bundle: FeatureBundle,
        *,
        sources: list[str] | None = None,
        broad_recall_terms: int = 8,
        max_cross: int = CNIPA_MAX_AND,
    ) -> QueryPlan:
        plan = QueryPlan(axis_id=bundle.axis_id)
        axis = bundle.axis_id.split("@")[0]
        features = bundle.features
        expansions = expand_features(features, self._expanders)

        positive: list[FeatureSpec] = []
        for feature in features:
            if feature.requiredness == Requiredness.NEGATION:
                plan.annotations.append(
                    {"feature_id": feature.feature_id, "kind": "negation", "statement": feature.statement}
                )
                continue
            if feature.requiredness == Requiredness.NUMERIC_BOUND:
                plan.annotations.append(
                    {"feature_id": feature.feature_id, "kind": "numeric_bound", "statement": feature.statement}
                )
                continue
            positive.append(feature)
            plan.queries.append(
                self._single_feature_query(feature, expansions[feature.feature_id], axis, bundle.axis_id)
            )

        # broad recall: union of the most distinctive candidate terms
        terms: list[str] = []
        seen: set[str] = set()
        for feature in positive:
            for cand in expansions[feature.feature_id]:
                key = normalize_term(cand.term)
                if key and key not in seen and cand.relation != "base":
                    seen.add(key)
                    terms.append(cand.term)
        if terms:
            plan.queries.append(
                QuerySpec(
                    owner=_OWNER,
                    query_id=f"Q-{axis}-BR-001",
                    axis_id=bundle.axis_id,
                    terms=terms[:broad_recall_terms],
                    language=detect_language(" ".join(terms[:broad_recall_terms])),
                    query_type="broad_recall",
                    source="multi",
                    feature_ids=[f.feature_id for f in positive],
                    provenance=[c.to_provenance() for c in self._all_candidates(expansions)][:broad_recall_terms],
                    approved=False,
                )
            )

        # feature cross: AND across required feature groups (max_cross bounds groups)
        required = [f for f in positive if f.requiredness == Requiredness.REQUIRED]
        if len(required) >= 2:
            groups = [self._distinct_terms(expansions[f.feature_id])[:2] for f in required[:max_cross]]
            groups = [g for g in groups if g]
            if len(groups) >= 2:
                plan.queries.append(
                    QuerySpec(
                        owner=_OWNER,
                        query_id=f"Q-{axis}-FC-001",
                        axis_id=bundle.axis_id,
                        terms=[t for g in groups for t in g],
                        language=detect_language(" ".join(t for g in groups for t in g)),
                        query_type="feature_cross",
                        source="multi",
                        feature_ids=[f.feature_id for f in required[:max_cross]],
                        filters={"and_groups": groups, "max_and": max_cross},
                        provenance=[
                            c.to_provenance()
                            for f in required[:max_cross]
                            for c in expansions[f.feature_id]
                        ],
                        approved=False,
                    )
                )

        # cross-domain migration queries
        xd_terms = [
            cand
            for feature in positive
            for cand in expansions[feature.feature_id]
            if cand.relation == "cross_domain"
        ]
        for i, cand in enumerate(xd_terms, start=1):
            plan.queries.append(
                QuerySpec(
                    owner=_OWNER,
                    query_id=f"Q-{axis}-XD-{i:03d}",
                    axis_id=bundle.axis_id,
                    terms=[cand.term],
                    language=detect_language(cand.term),
                    query_type="cross_domain",
                    source="multi",
                    # an expansion term without a resolvable origin feature stays None —
                    # unknown coverage, never a fabricated feature attribution
                    feature_ids=[cand.feature_id] if cand.feature_id else None,
                    provenance=[cand.to_provenance()],
                    approved=False,
                )
            )

        # per-source rendered syntax attached lazily (render_query on demand)
        _ = sources  # rendering is per-source at execution time; kept on QuerySpec.rendered
        return plan

    # -- helpers -------------------------------------------------------

    def _single_feature_query(
        self,
        feature: FeatureSpec,
        candidates: list[TermCandidate],
        axis: str,
        axis_id: str,
    ) -> QuerySpec:
        terms = self._distinct_terms(candidates)
        return QuerySpec(
            owner=_OWNER,
            query_id=f"Q-{axis}-SF-{feature.feature_id.split('-')[-1]}",
            axis_id=axis_id,
            terms=terms,
            language=detect_language(" ".join(terms)),
            query_type="single_feature",
            source="multi",
            feature_ids=[feature.feature_id],
            filters={"requiredness": feature.requiredness},
            provenance=[c.to_provenance() for c in candidates],
            approved=False,
        )

    @staticmethod
    def _distinct_terms(candidates: list[TermCandidate]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for cand in candidates:
            key = normalize_term(cand.term)
            if key and key not in seen:
                seen.add(key)
                out.append(cand.term)
        return out

    @staticmethod
    def _all_candidates(expansions: dict[str, list[TermCandidate]]) -> list[TermCandidate]:
        return [cand for cands in expansions.values() for cand in cands if cand.relation != "base"]


# ── per-source rendering (UT-Q02) ────────────────────────────────────


def effective_feature_ids(query: QuerySpec) -> list[str]:
    """The query's authoritative feature dimension: ``feature_ids`` when present,
    else the provenance-declared feature ids (deduped, order-stable).

    Shared by the controller (coverage recording) and the policies (utility
    estimation). Empty = no feature attribution — unknown coverage, never a zero.
    """
    if query.feature_ids:
        return list(dict.fromkeys(query.feature_ids))
    out: list[str] = []
    for item in query.provenance or ():
        if isinstance(item, dict) and item.get("feature_id"):
            feature_id = str(item["feature_id"])
            if feature_id not in out:
                out.append(feature_id)
    return out


class RenderError(ValueError):
    """The query cannot be honestly rendered for the requested source."""


def render_query(query: QuerySpec, source_id: str) -> str:
    """Render a QuerySpec into source-specific syntax. CNIPA AND-limit enforced here only."""
    terms = list(query.terms)
    if source_id == "cnipa":
        filters = query.filters or {}
        if query.query_type == "feature_cross":
            groups = filters.get("and_groups") or []
            if len(groups) > CNIPA_MAX_AND:
                raise RenderError(
                    f"feature_cross has {len(groups)} AND groups; CNIPA allows at most {CNIPA_MAX_AND}"
                )
            parts = ["(" + " OR ".join(_quote_cnipa(t) for t in group) + ")" for group in groups]
            return " and ".join(parts)
        inner = " OR ".join(_quote_cnipa(t) for t in terms)
        return f"abstract=({inner})"
    if source_id == "crossref":
        # free-text: no boolean constraints claimed
        return " ".join(terms)
    if source_id == "ops":
        inner = " OR ".join(t.replace(" ", "%20") for t in terms)
        return f"ti or ab=({inner})"
    raise RenderError(f"no renderer for source {source_id!r}")


def _quote_cnipa(term: str) -> str:
    escaped = term.replace('"', "")
    return f'"{escaped}"'
