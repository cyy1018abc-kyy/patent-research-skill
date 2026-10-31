"""Retrieval evaluator (adaptive roadmap Task 2 / Phase 2): coverage states, honest
metrics, gap report.

Boundary discipline:

* coverage states are **retrieval-level** judgements over candidates — a hit is not
  a disclosure; evidence levels stay with the kernel;
* ``unknown`` is a first-class state and is never auto-downgraded to ``not_found``
  (a feature no query ever targeted cannot be claimed absent);
* without a gold set the evaluator reports **proxy indicators only** and stamps
  ``metrics.gold_available=false`` — presenting them as true recall is forbidden
  (roadmap §4.1: 真实 Recall 必须依赖标注相关文献集合);
* relevance buckets come from the ledger: confirmed > suspected > candidates — the
  evaluator never upgrades a candidate on its own.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from typing import Any

from patent_intel.contracts import (
    CoverageState,
    FeatureSpec,
    QuerySpec,
    RetrievalGapReport,
)
from patent_intel.retrieval import metrics
from patent_intel.retrieval.controller import ControllerReport
from patent_intel.retrieval.coverage import QueryYieldLedger

__all__ = ["RetrievalConstraints", "RetrievalEvaluator", "EVALUATOR_PARTIAL_LABEL"]

_OWNER = "WP-A"

#: roadmap Phase 5 wording — required on the report while important gaps remain
EVALUATOR_PARTIAL_LABEL = "Partial Retrieval — Important Coverage Gaps Remain"

_RECALL_KS = (20, 50, 100)


@dataclass
class RetrievalConstraints:
    """What the retrieval task promised to cover (user-facing scope)."""

    jurisdictions: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    #: technical domains the plan should have addressed via cross-domain queries
    domains: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)


def _feature_universe(
    features: Iterable[FeatureSpec], coverage: Any, queries: Iterable[QuerySpec]
) -> list[str]:
    """Declared features first (stable order), then any feature seen in queries/coverage."""
    out: list[str] = []
    for feature in features:
        if feature.feature_id not in out:
            out.append(feature.feature_id)
    for query in queries:
        for feature_id in query.feature_ids or ():
            if feature_id not in out:
                out.append(feature_id)
    for feature_id in sorted(coverage.feature_axis):
        if feature_id not in out:
            out.append(feature_id)
    return out


class RetrievalEvaluator:
    """Turns a controller run into a feature-state map, honest metrics and gap lists."""

    OWNER = _OWNER

    def evaluate(
        self,
        *,
        report: ControllerReport,
        queries: list[QuerySpec],
        features: list[FeatureSpec] | None = None,
        coverage: Any | None = None,
        ledger: QueryYieldLedger | None = None,
        constraints: RetrievalConstraints | None = None,
        gold_families: Collection[str] | None = None,
        feature_graph: dict[str, set[str]] | dict[str, list[str]] | None = None,
        observed_jurisdictions: Collection[str] | None = None,
        run_label: str | None = None,
    ) -> RetrievalGapReport:
        constraints = constraints or RetrievalConstraints()
        coverage = coverage if coverage is not None else report.coverage_tracker
        ledger = ledger if ledger is not None else report.ledger
        if coverage is None or ledger is None:
            raise ValueError(
                "evaluate needs the run's coverage tracker and yield ledger "
                "(pass them or run the evaluator on a ControllerReport that carries them)"
            )
        errored_queries = {o.query_id for o in report.outcomes if o.error}

        feature_states, uncovered, partially, unknown = self._feature_states(
            _feature_universe(features or (), coverage, queries), coverage, ledger, errored_queries
        )

        metrics_block = self._metrics(coverage, ledger, feature_states, gold_families)

        executed_sources = sorted(
            {q.source for q in queries if q.query_id in set(report.queries_run)}
        )
        missing_sources = [s for s in constraints.data_sources if s not in executed_sources]
        observed = set(observed_jurisdictions or ())
        missing_jurisdictions = [j for j in constraints.jurisdictions if j not in observed]
        missing_domains = self._missing_domains(constraints.domains, queries)
        missing_relations = self._missing_relations(feature_graph or {}, coverage)

        actions = self._recommended_actions(
            uncovered=uncovered,
            partially=partially,
            unknown=unknown,
            missing_relations=missing_relations,
            missing_jurisdictions=missing_jurisdictions,
            missing_sources=missing_sources,
            missing_domains=missing_domains,
            ledger=ledger,
            executed_sources=executed_sources,
        )

        stop_context = {
            "stop_reason": report.stop_reason,
            "budget_spent": report.budget_spent,
            "queries_run": len(report.queries_run),
            "partial_retrieval": bool(uncovered),
            "partial_retrieval_label": EVALUATOR_PARTIAL_LABEL if uncovered else None,
            "caveat": (
                "stopping/未覆盖 ≠ 证明不存在 — not_found only means the executed scope "
                "found nothing; unknown means the feature was never properly targeted"
            ),
        }

        return RetrievalGapReport(
            owner=_OWNER,
            run_label=run_label,
            feature_states=feature_states,
            uncovered_features=uncovered,
            partially_covered_features=partially,
            unknown_features=unknown,
            missing_technical_relations=missing_relations,
            missing_technical_domains=missing_domains,
            missing_jurisdictions=missing_jurisdictions,
            missing_data_sources=missing_sources,
            recommended_actions=actions,
            metrics=metrics_block,
            stop_context=stop_context,
        )

    # -- states ----------------------------------------------------------

    def _feature_states(
        self,
        feature_ids: list[str],
        coverage: Any,
        ledger: QueryYieldLedger,
        errored_queries: set[str],
    ) -> tuple[dict[str, str], list[str], list[str], list[str]]:
        states: dict[str, str] = {}
        uncovered: list[str] = []
        partially: list[str] = []
        unknown: list[str] = []
        confirmed = ledger.confirmed_relevant
        suspected = ledger.suspected_relevant
        for feature_id in feature_ids:
            families = coverage.feature_families.get(feature_id, set())
            attempts = coverage.feature_queries.get(feature_id, set())
            if families & confirmed:
                state = CoverageState.DISCLOSED
            elif families & suspected:
                state = CoverageState.PARTIALLY_DISCLOSED
            elif attempts and not attempts <= errored_queries:
                # cleanly executed against the feature, nothing covered it
                state = CoverageState.NOT_FOUND
                uncovered.append(feature_id)
            else:
                # never targeted, or every targeting query failed — absence unproven
                state = CoverageState.UNKNOWN
                unknown.append(feature_id)
            states[feature_id] = state
            if state == CoverageState.PARTIALLY_DISCLOSED:
                partially.append(feature_id)
        return states, uncovered, partially, unknown

    # -- metrics ---------------------------------------------------------

    def _metrics(
        self,
        coverage: Any,
        ledger: QueryYieldLedger,
        feature_states: dict[str, str],
        gold_families: Collection[str] | None,
    ) -> dict[str, Any]:
        total_features = len(feature_states)
        covered_features = sum(
            1 for s in feature_states.values() if s != CoverageState.UNKNOWN
        )
        proxy = {
            "candidate_families": ledger.total_new_families,
            "candidate_documents": ledger.total_new_documents,
            "suspected_relevant_families": len(ledger.suspected_relevant),
            "confirmed_relevant_families": len(ledger.confirmed_relevant),
            "feature_coverage_ratio": round(covered_features / total_features, 4)
            if total_features
            else None,
            "note": (
                "proxy indicators over the executed scope only — 命中数≠相关数，"
                "覆盖率≠查全率 (candidate ≠ relevant; coverage ≠ recall)"
            ),
        }
        if gold_families is None:
            return {
                "gold_available": False,
                "proxy": proxy,
                "note": "no gold/annotation set: only proxy indicators are reported; "
                "真实查全率无法计算 (true recall is undefined without a gold set)",
            }
        if not gold_families:
            raise ValueError(
                "gold_families is empty: an empty gold set is a data error, not a "
                "zero-score run (metrics contract) — pass None for proxy-only mode"
            )
        ranked = ledger.discovery_order_families
        gold = list(dict.fromkeys(gold_families))
        gains = {fid: 1.0 for fid in gold}
        return {
            "gold_available": True,
            "gold_size": len(gold),
            "recall_at_k": {
                str(k): round(metrics.family_recall_at_k(ranked, gold, k), 4) for k in _RECALL_KS
            },
            "known_item_recall": round(
                metrics.family_recall_at_k(ranked, gold, max(len(ranked), 1)), 4
            ),
            "precision_at_10": round(metrics.precision_at_k(ranked, gold, 10), 4),
            "ndcg_at_10": round(metrics.ndcg_at_k(ranked, gains, 10), 4),
            "proxy": proxy,
        }

    # -- gap dimensions ----------------------------------------------------

    def _missing_domains(self, domains: list[str], queries: list[QuerySpec]) -> list[str]:
        """Requested domains addressed by no executed cross_domain query.

        Deliberately conservative: a domain without linkage evidence is reported as
        missing, never as covered.
        """
        if not domains:
            return []
        executed_xd = {
            q
            for q in queries
            if q.query_type == "cross_domain"
        }
        addressed: set[str] = set()
        for query in executed_xd:
            addressed.update(str(d) for d in (query.filters or {}).get("domains", ()) if d)
        return [d for d in domains if d not in addressed]

    def _missing_relations(
        self, feature_graph: dict[str, Collection[str]], coverage: Any
    ) -> list[str]:
        out: list[str] = []
        for left, rights in feature_graph.items():
            for right in rights:
                if left == right:
                    continue
                pair = "~".join(sorted((left, right)))
                if pair in out:
                    continue
                left_cov = coverage.feature_families.get(left)
                right_cov = coverage.feature_families.get(right)
                if not left_cov and not right_cov:
                    out.append(pair)
        return out

    # -- recommended actions (roadmap §4.1 Phase 3 mapping, deterministic) ---

    def _recommended_actions(
        self,
        *,
        uncovered: list[str],
        partially: list[str],
        unknown: list[str],
        missing_relations: list[str],
        missing_jurisdictions: list[str],
        missing_sources: list[str],
        missing_domains: list[str],
        ledger: QueryYieldLedger,
        executed_sources: list[str],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for feature_id in unknown:
            actions.append({
                "action": "plan_feature_query",
                "targets": [feature_id],
                "reason": "feature never targeted by an executed query — coverage unknown",
            })
        for feature_id in uncovered:
            actions.append({
                "action": "term_expansion_and_dense",
                "targets": [feature_id],
                "reason": "cleanly executed queries found no candidate families for this feature",
            })
        if len(partially) + len(uncovered) >= 2:
            actions.append({
                "action": "feature_cross",
                "targets": partially[:3] + uncovered[:3],
                "reason": "multiple features lack independent coverage — combination queries may surface designs covering them together",
            })
        for pair in missing_relations[:10]:
            actions.append({
                "action": "cross_domain",
                "targets": pair.split("~"),
                "reason": "neither endpoint of this technical relation saw any candidate family",
            })
        for domain in missing_domains:
            actions.append({
                "action": "cross_domain",
                "targets": [domain],
                "reason": "requested technical domain addressed by no executed cross-domain query",
            })
        for jurisdiction in missing_jurisdictions:
            actions.append({
                "action": "online_source",
                "targets": [jurisdiction],
                "reason": "requested jurisdiction with no observed coverage (subject to source support_level)",
            })
        for source in missing_sources:
            actions.append({
                "action": "enable_source",
                "targets": [source],
                "reason": f"requested data source not executed (executed: {executed_sources or ['none']})",
            })
        if ledger.total_new_families and not ledger.suspected_relevant and not ledger.confirmed_relevant:
            actions.append({
                "action": "relevance_review",
                "targets": [],
                "reason": "candidates were found but none marked suspected/confirmed relevant — relevance dimension is unjudged",
            })
        return actions
