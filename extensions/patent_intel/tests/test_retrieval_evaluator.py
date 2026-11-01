"""Adaptive retrieval Stage 1 tests (roadmap Tasks 2+3): RetrievalEvaluator /
RetrievalGapReport and the policy layer.

Honesty invariants under test:

* unknown never degrades to not_found (never-targeted features stay unknown);
* no gold set → proxy metrics only, gold_available=false, no recall claim;
* relevance buckets only move by explicit marking — the evaluator never upgrades;
* MarginalUtilityPolicy decisions are deterministic, explainable, and soft-stop
  with an explicit reason instead of claiming the space is exhausted.
"""

from __future__ import annotations

import pytest

from patent_intel.contracts import CoverageState, RecordValidationError, QuerySpec, RetrievalGapReport
from patent_intel.retrieval.controller import AdaptiveController, RunOutcome, StopReason
from patent_intel.retrieval.evaluator import (
    EVALUATOR_PARTIAL_LABEL,
    RetrievalConstraints,
    RetrievalEvaluator,
)
from patent_intel.retrieval.policy import (
    GapFirstPolicy,
    MarginalUtilityPolicy,
    PolicyState,
    TypeStats,
)
from patent_intel.retrieval.coverage import CoverageTracker, QueryYieldLedger

AXIS = "N1@TGT-0001"


def _spec(qid: str, axis: str = AXIS, query_type: str = "single_feature",
          feature_ids: list[str] | None = None, source: str = "multi") -> QuerySpec:
    return QuerySpec(
        owner="WP-A", query_id=qid, axis_id=axis, terms=["信标"], language="zh",
        query_type=query_type, source=source, feature_ids=feature_ids,
    )


def _run(queries: list[QuerySpec], families_by_query: dict[str, list[str]],
         hits_by_query: dict[str, list[str]] | None = None,
         suspected_by_query: dict[str, list[str]] | None = None,
         **controller_kwargs) -> tuple[AdaptiveController, object]:
    hits_by_query = hits_by_query or {}
    suspected_by_query = suspected_by_query or {}

    def runner(q: QuerySpec) -> RunOutcome:
        return RunOutcome(
            query_id=q.query_id,
            hits=hits_by_query.get(q.query_id, []),
            families=families_by_query.get(q.query_id, []),
            suspected_relevant=suspected_by_query.get(q.query_id, []),
        )

    controller = AdaptiveController(runner, **controller_kwargs)
    report = controller.run_plan(queries)
    return controller, report


# ── RetrievalGapReport contract ──────────────────────────────────────


def test_gap_report_round_trip_and_state_validation() -> None:
    report = RetrievalGapReport(
        owner="WP-A",
        feature_states={"F-1": CoverageState.DISCLOSED, "F-2": CoverageState.UNKNOWN},
        metrics={"gold_available": False, "proxy": {}},
        uncovered_features=[],
        unknown_features=["F-2"],
    )
    data = report.to_dict()
    restored = RetrievalGapReport.from_dict(data)
    assert restored.feature_states["F-1"] == CoverageState.DISCLOSED

    with pytest.raises(RecordValidationError, match="not in"):
        RetrievalGapReport(
            owner="WP-A", feature_states={"F-1": "found_pretty_sure"},
            metrics={"gold_available": False},
        )


def test_gap_report_rejects_unknown_downgraded_to_not_found() -> None:
    with pytest.raises(RecordValidationError, match="unknown"):
        RetrievalGapReport(
            owner="WP-A",
            feature_states={"F-1": CoverageState.UNKNOWN, "F-2": CoverageState.NOT_FOUND},
            unknown_features=["F-1"],
            uncovered_features=["F-1"],  # same feature in both buckets is a contract violation
            metrics={"gold_available": False},
        )


def test_gap_report_requires_explicit_gold_flag() -> None:
    with pytest.raises(RecordValidationError, match="gold_available"):
        RetrievalGapReport(owner="WP-A", feature_states={}, metrics={"recall": 0.9})


def test_gap_report_actions_need_action_and_reason() -> None:
    with pytest.raises(RecordValidationError, match="recommended_action"):
        RetrievalGapReport(
            owner="WP-A", feature_states={}, metrics={"gold_available": False},
            recommended_actions=[{"targets": ["F-1"]}],
        )


# ── evaluator: feature states ────────────────────────────────────────


def test_evaluator_state_machine_end_to_end() -> None:
    queries = [
        _spec("Q1", feature_ids=["F-1"]),                     # suspected hit → partially
        _spec("Q2", axis="N2@TGT-0001", feature_ids=["F-2"]),  # clean execution, nothing → not_found
        _spec("Q3", feature_ids=["F-3"]),                      # runner error → unknown
    ]
    families = {"Q1": ["FAM-1"], "Q2": []}
    hits = {"Q1": ["D1"]}

    def runner(q: QuerySpec) -> RunOutcome:
        if q.query_id == "Q3":
            raise RuntimeError("source down")
        return RunOutcome(query_id=q.query_id, hits=hits.get(q.query_id, []),
                          families=families.get(q.query_id, []))

    controller = AdaptiveController(runner, zero_gain_rounds=99)
    report = controller.run_plan(queries)
    controller.mark_relevant(["FAM-1"], suspected=True)  # evaluator-suspected, not confirmed

    gap = RetrievalEvaluator().evaluate(
        report=report, queries=queries,
        run_label="stage1",
    )
    states = gap.feature_states
    assert states["F-1"] == CoverageState.PARTIALLY_DISCLOSED
    assert states["F-2"] == CoverageState.NOT_FOUND
    assert states["F-3"] == CoverageState.UNKNOWN
    assert gap.uncovered_features == ["F-2"]
    assert gap.partially_covered_features == ["F-1"]
    assert gap.unknown_features == ["F-3"]
    assert gap.stop_context["partial_retrieval"] is True
    assert gap.stop_context["partial_retrieval_label"] == EVALUATOR_PARTIAL_LABEL
    # any action in the report must be actionable (contract-validated shape)
    assert gap.recommended_actions and all("action" in a and "reason" in a for a in gap.recommended_actions)


def test_evaluator_confirmed_marking_upgrades_to_disclosed() -> None:
    queries = [_spec("Q1", feature_ids=["F-1"])]
    controller, report = _run(queries, {"Q1": ["FAM-1"]}, {"Q1": ["D1"]})
    controller.mark_relevant(["FAM-1"])  # human confirms
    gap = RetrievalEvaluator().evaluate(report=report, queries=queries)
    assert gap.feature_states["F-1"] == CoverageState.DISCLOSED
    assert gap.stop_context["partial_retrieval"] is False
    assert gap.stop_context["partial_retrieval_label"] is None


def test_evaluator_never_targeted_feature_stays_unknown() -> None:
    """The §4.1 rule: unknown 不得自动转为 not_found."""
    queries = [_spec("Q1", feature_ids=["F-1"])]
    _controller, report = _run(queries, {"Q1": ["FAM-1"]}, {"Q1": ["D1"]})
    gap = RetrievalEvaluator().evaluate(
        report=report, queries=queries,
        features=[],  # F-9 never declared, never targeted
    )
    gap.feature_states  # universe from coverage/queries — F-9 absent entirely
    assert "F-9" not in gap.feature_states
    # an explicitly declared-but-untargeted feature shows up as unknown
    from patent_intel.contracts import FeatureSpec
    phantom = FeatureSpec(
        owner="WP-A", feature_id="F-9", statement="phantom feature",
        source_refs=[{"ref": "spec"}], requiredness="required",
    )
    gap2 = RetrievalEvaluator().evaluate(report=report, queries=queries, features=[phantom])
    assert gap2.feature_states["F-9"] == CoverageState.UNKNOWN
    assert gap2.unknown_features == ["F-9"]
    assert any(a["action"] == "plan_feature_query" and a["targets"] == ["F-9"]
               for a in gap2.recommended_actions)


# ── evaluator: metrics honesty ───────────────────────────────────────


def test_evaluator_without_gold_reports_proxy_only() -> None:
    queries = [_spec("Q1", feature_ids=["F-1"])]
    _controller, report = _run(queries, {"Q1": ["FAM-1", "FAM-2"]}, {"Q1": ["D1", "D2"]})
    gap = RetrievalEvaluator().evaluate(report=report, queries=queries)
    assert gap.metrics["gold_available"] is False
    assert "recall" not in str(gap.metrics).lower() or "recall is undefined" in gap.metrics["note"]
    assert gap.metrics["proxy"]["candidate_families"] == 2


def test_evaluator_with_gold_computes_real_metrics() -> None:
    queries = [_spec("Q1", feature_ids=["F-1"]), _spec("Q2", feature_ids=["F-1"])]
    _controller, report = _run(
        queries, {"Q1": ["FAM-1", "FAM-2"], "Q2": ["FAM-3"]},
        {"Q1": ["D1", "D2"], "Q2": ["D3"]},
    )
    gap = RetrievalEvaluator().evaluate(
        report=report, queries=queries, gold_families=["FAM-1", "FAM-3"],
    )
    assert gap.metrics["gold_available"] is True
    assert gap.metrics["gold_size"] == 2
    assert gap.metrics["known_item_recall"] == 1.0  # both gold families discovered
    assert gap.metrics["recall_at_k"]["20"] == 1.0
    assert gap.metrics["precision_at_10"] == pytest.approx(2 / 3, abs=1e-4)  # rounded to 4dp


def test_evaluator_rejects_empty_gold_set() -> None:
    queries = [_spec("Q1", feature_ids=["F-1"])]
    _controller, report = _run(queries, {"Q1": ["FAM-1"]}, {"Q1": ["D1"]})
    with pytest.raises(ValueError, match="empty gold"):
        RetrievalEvaluator().evaluate(report=report, queries=queries, gold_families=[])


# ── evaluator: gap dimensions ────────────────────────────────────────


def test_evaluator_jurisdiction_and_source_gaps() -> None:
    queries = [_spec("Q1", feature_ids=["F-1"], source="multi")]
    _controller, report = _run(queries, {"Q1": ["FAM-1"]}, {"Q1": ["D1"]})
    gap = RetrievalEvaluator().evaluate(
        report=report, queries=queries,
        constraints=RetrievalConstraints(
            jurisdictions=["CN", "EP"], data_sources=["multi", "ops"], domains=["quantum"],
        ),
        observed_jurisdictions=["CN"],
    )
    assert gap.missing_jurisdictions == ["EP"]
    assert gap.missing_data_sources == ["ops"]
    assert gap.missing_technical_domains == ["quantum"]
    actions = {a["action"]: a for a in gap.recommended_actions}
    assert "online_source" in actions and "enable_source" in actions


def test_evaluator_missing_relations_from_feature_graph() -> None:
    queries = [_spec("Q1", feature_ids=["F-1"])]
    _controller, report = _run(queries, {"Q1": ["FAM-1"]}, {"Q1": ["D1"]})
    gap = RetrievalEvaluator().evaluate(
        report=report, queries=queries,
        feature_graph={"F-1": ["F-2"], "F-3": ["F-4"]},  # F-1 covered; F-3/F-4 dark
    )
    assert gap.missing_technical_relations == ["F-3~F-4"]
    assert any(a["action"] == "cross_domain" for a in gap.recommended_actions)


def test_evaluator_flags_unjudged_relevance() -> None:
    queries = [_spec("Q1", feature_ids=["F-1"])]
    _controller, report = _run(queries, {"Q1": ["FAM-1"]}, {"Q1": ["D1"]})
    gap = RetrievalEvaluator().evaluate(report=report, queries=queries)
    assert any(a["action"] == "relevance_review" for a in gap.recommended_actions)


# ── policies ─────────────────────────────────────────────────────────


def test_gap_first_policy_matches_legacy_order() -> None:
    state = PolicyState(coverage=CoverageTracker(), ledger=QueryYieldLedger(),
                        budget_spent=0.0, max_cost=10.0)
    pending = [_spec("Q-B", query_type="broad_recall", feature_ids=["F-1", "F-2"]),
               _spec("Q-S1", feature_ids=["F-1"]),
               _spec("Q-S2", axis="N2@TGT-0001", feature_ids=["F-2"])]
    decision = GapFirstPolicy().select_next(pending, state)
    assert decision.query is not None and decision.query.query_id == "Q-S1"
    assert decision.reason  # every decision carries a reason


def test_utility_policy_prefers_cheap_uncovered_features_first() -> None:
    state = PolicyState(coverage=CoverageTracker(), ledger=QueryYieldLedger(),
                        budget_spent=0.0, max_cost=10.0)
    pending = [_spec("Q-B", query_type="broad_recall", feature_ids=["F-1", "F-2"]),
               _spec("Q-S1", feature_ids=["F-1"]),
               _spec("Q-XD", query_type="cross_domain", feature_ids=["F-2"])]
    policy = MarginalUtilityPolicy()
    first = policy.select_next(pending, state)
    assert first.query is not None
    assert first.query.query_id == "Q-S1"  # highest utility-per-cost
    assert first.utility is not None and first.utility > 0
    assert "ΔC" in first.reason  # explainable


def test_utility_policy_soft_stops_when_no_expected_gain() -> None:
    tracker = CoverageTracker()
    tracker.record_feature_hit("F-1", "FAM-1", axis_id=AXIS)
    tracker.record_feature_hit("F-2", "FAM-1", axis_id=AXIS)
    state = PolicyState(coverage=tracker, ledger=QueryYieldLedger(),
                        budget_spent=0.0, max_cost=10.0)
    pending = [_spec("Q-S1", feature_ids=["F-1"]), _spec("Q-S2", feature_ids=["F-2"])]
    decision = MarginalUtilityPolicy().select_next(pending, state)
    assert decision.query is None  # soft stop, not a fabricated selection
    assert "min_utility" in decision.reason and "soft stop" in decision.reason


def test_utility_policy_respects_relevance_history() -> None:
    tracker = CoverageTracker()
    ledger = QueryYieldLedger()
    ledger.record("Q1", ["FAM-1"])
    ledger.mark_confirmed(["FAM-1"])
    state = PolicyState(
        coverage=tracker, ledger=ledger, budget_spent=0.0, max_cost=100.0,
        type_history={"citation_expand": TypeStats(runs=2, new_families=2, cost=4.0,
                                                   suspected=1, confirmed=1)},
    )
    pending = [_spec("Q-C", query_type="citation_expand", feature_ids=["F-9"])]
    decision = MarginalUtilityPolicy(w_relevance=4.0).select_next(pending, state)
    assert decision.query is not None  # observed relevance keeps the type running
    assert decision.utility is not None


def test_controller_with_utility_policy_records_decisions_and_soft_stop() -> None:
    queries = [_spec("Q1", feature_ids=["F-1"]), _spec("Q2", feature_ids=["F-1"])]
    controller = AdaptiveController(
        lambda q: RunOutcome(query_id=q.query_id, hits=["D1"], families=["FAM-1"]),
        policy=MarginalUtilityPolicy(),
    )
    report = controller.run_plan(queries)
    assert report.stop_reason == StopReason.SOFT_STOP
    assert "min_utility" in report.soft_stop_reason
    assert report.decisions and report.decisions[0]["policy"] == "MarginalUtilityPolicy"
    assert report.decisions[0]["utility"] is not None
    assert report.describe()["soft_stop_reason"] == report.soft_stop_reason


def test_controller_default_policy_keeps_legacy_behaviour() -> None:
    """No policy passed → GapFirstPolicy → plan-exhausted semantics unchanged."""
    queries = [_spec("Q1"), _spec("Q2")]
    controller = AdaptiveController(
        lambda q: RunOutcome(query_id=q.query_id, hits=["D1"], families=["FAM-1"]),
    )
    report = controller.run_plan(queries)
    assert report.stop_reason == StopReason.PLAN_EXHAUSTED
    assert all(d["policy"] == "GapFirstPolicy" for d in report.decisions)


def test_policy_rejects_negative_min_utility() -> None:
    with pytest.raises(ValueError, match="min_utility"):
        MarginalUtilityPolicy(min_utility=-0.1)
