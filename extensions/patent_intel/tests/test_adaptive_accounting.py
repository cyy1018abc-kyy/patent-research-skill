"""Adaptive retrieval Task 1 (Stage 0): identity & coverage accounting discipline.

Covers the roadmap §2.3 corrections:

* ``QuerySpec.feature_ids`` — explicit feature dimension, validated (UT: no axis/query-type
  substitution);
* ``RunOutcome.family_basis`` — a document id never masquerades as a family id (UT-S03);
* yield ledger — candidate vs suspected vs confirmed relevant are separate buckets;
* coverage — recorded per technical feature id (fixes the always-zero feature coverage
  the old controller produced by recording query types as "concepts");
* query planner — all four query kinds carry feature ids (or honestly none);
* OPS capability honesty — declared query fields are exactly what build_request consumes.
"""

from __future__ import annotations

import pytest

from patent_intel.contracts import RecordValidationError, QuerySpec
from patent_intel.retrieval.controller import AdaptiveController, FamilyBasis, RunOutcome
from patent_intel.retrieval.coverage import CoverageTracker, QueryYieldLedger
from patent_intel.retrieval.features import extract_features
from patent_intel.retrieval.query_plan import QueryPlanBuilder


AXIS = "N1@TGT-0001"


def _spec(qid: str, axis: str = AXIS, query_type: str = "single_feature",
          feature_ids: list[str] | None = None) -> QuerySpec:
    return QuerySpec(
        owner="WP-A", query_id=qid, axis_id=axis, terms=["信标"], language="zh",
        query_type=query_type, source="multi", feature_ids=feature_ids,
    )


# ── QuerySpec.feature_ids contract ───────────────────────────────────


def test_query_spec_feature_ids_round_trip() -> None:
    query = _spec("Q-001", feature_ids=["F-1", "F-2"])
    data = query.to_dict()
    assert data["feature_ids"] == ["F-1", "F-2"]
    restored = QuerySpec.from_dict(data)
    assert restored.feature_ids == ["F-1", "F-2"]


def test_query_spec_feature_ids_optional_and_default_none() -> None:
    query = _spec("Q-002")
    assert query.feature_ids is None
    assert "feature_ids" not in query.to_dict()  # None fields are not serialized


@pytest.mark.parametrize("bad", [["F-1", ""], ["F-1", 3], ["F-1", "F-1"]])
def test_query_spec_feature_ids_rejects_bad_values(bad: list) -> None:
    with pytest.raises(RecordValidationError):
        QuerySpec(
            owner="WP-A", query_id="Q-bad", axis_id=AXIS, terms=["t"], language="zh",
            query_type="single_feature", source="multi", feature_ids=bad,
        )


# ── RunOutcome family identity discipline ────────────────────────────


def test_runoutcome_unknown_basis_refuses_family_ids() -> None:
    with pytest.raises(ValueError, match="never|unknown|masquerade|families"):
        RunOutcome(query_id="Q-1", hits=["D1"], families=["D1"], family_basis=FamilyBasis.UNKNOWN)


def test_runoutcome_rejects_unknown_basis_value() -> None:
    with pytest.raises(ValueError, match="family_basis"):
        RunOutcome(query_id="Q-1", families=["F1"], family_basis="guessed")


def test_runoutcome_suspected_must_be_subset_of_families() -> None:
    with pytest.raises(ValueError, match="subset"):
        RunOutcome(query_id="Q-1", families=["F1"], suspected_relevant=["F9"])


def test_runoutcome_defaults_are_honest() -> None:
    outcome = RunOutcome(query_id="Q-1", hits=["D1"])
    assert outcome.families == []
    assert outcome.family_basis == FamilyBasis.REPORTED
    assert outcome.new_documents == []
    assert outcome.suspected_relevant == []


# ── yield ledger: dimensions + three buckets ─────────────────────────


def test_ledger_dedupes_documents_and_families_independently() -> None:
    ledger = QueryYieldLedger()
    assert ledger.record("Q1", ["F1", "F2"]) == ["F1", "F2"]
    assert ledger.record("Q2", ["F2"]) == []
    assert ledger.record_documents("Q1", ["D1", "D2"]) == ["D1", "D2"]
    assert ledger.record_documents("Q2", ["D2", "D3"]) == ["D3"]
    assert ledger.total_new_families == 2
    assert ledger.total_new_documents == 3


def test_ledger_relevance_buckets_stay_separate() -> None:
    ledger = QueryYieldLedger()
    ledger.record("Q1", ["F1", "F2", "F3"])
    with pytest.raises(ValueError, match="candidate"):
        ledger.mark_suspected(["F9"])  # never seen as a candidate
    assert ledger.mark_suspected(["F1", "F2"]) == ["F1", "F2"]
    assert ledger.mark_confirmed(["F1"]) == ["F1"]
    acct = ledger.accounting()
    assert acct["candidate_families"] == 3
    assert acct["suspected_relevant_families"] == 2
    assert acct["confirmed_relevant_families"] == 1


# ── coverage: feature dimension is authoritative ─────────────────────


def test_coverage_records_feature_hits_and_axis_presence() -> None:
    tracker = CoverageTracker()
    tracker.record_feature_hit("F-1", "FAM-1", query_id="Q1", axis_id=AXIS)
    tracker.record_feature_hit("F-1", "FAM-2", query_id="Q2", axis_id=AXIS)
    tracker.record_axis_family(AXIS, "FAM-3")  # axis saw a family; no feature attribution
    report = tracker.report([AXIS], {"nonexistent": []}).describe()
    assert report["per_feature"]["F-1"] == {
        "axis_id": AXIS, "covered": True, "families": 2, "queries": ["Q1", "Q2"],
    }
    assert report["per_axis"][AXIS]["families_found"] == 3
    assert report["uncovered_axes"] == []


def test_feature_coverage_via_controller_no_longer_records_query_types() -> None:
    """The §2.3-3 live symptom: the old controller recorded query_type strings as
    'concepts', so feature coverage from recall reports was always zero."""
    queries = [_spec("Q1", feature_ids=["F-1", "F-2"]), _spec("Q2", query_type="broad_recall",
                                                             feature_ids=["F-1"])]
    outcomes = {"Q1": ["FAM-1"], "Q2": []}

    def runner(q: QuerySpec) -> RunOutcome:
        return RunOutcome(query_id=q.query_id, hits=["D1"], families=outcomes[q.query_id])

    controller = AdaptiveController(runner, concepts_by_axis={AXIS: ["F-1", "F-2"]})
    report = controller.run_plan(queries).describe()

    per_feature = report["coverage"]["per_feature"]
    assert per_feature["F-1"]["covered"] is True
    assert per_feature["F-2"]["covered"] is True  # FAM-1 hit covered both query features
    per_axis = report["coverage"]["per_axis"][AXIS]
    assert per_axis["features_total"] == 2
    assert per_axis["features_covered"] == 2
    # query types were never ingested as concepts
    assert "single_feature" not in report["coverage"]["per_axis"][AXIS]["concepts_uncovered"]
    assert per_axis["concepts_covered"] == 2


def test_controller_counts_document_yield_for_unknown_basis() -> None:
    """Unknown family relations: docs count document-level, families stay empty,
    and document discovery resets the zero-gain streak."""
    queries = [_spec(f"Q{i}") for i in range(1, 5)]

    def runner(q: QuerySpec) -> RunOutcome:
        return RunOutcome(
            query_id=q.query_id,
            hits=[f"D{q.query_id[1]}"],  # one new doc per query
            families=[],
            family_basis=FamilyBasis.UNKNOWN,
        )

    report = AdaptiveController(runner, zero_gain_rounds=2).run_plan(queries)
    assert report.stop_reason == "plan_exhausted"  # doc-level gain kept it running
    assert report.total_new_documents == 4
    assert report.total_new_families == 0
    assert report.family_accounting["candidate_documents"] == 4
    assert all(o.family_basis == FamilyBasis.UNKNOWN for o in report.outcomes)


def test_controller_accounting_buckets_and_mark_relevant() -> None:
    def runner(q: QuerySpec) -> RunOutcome:
        return RunOutcome(
            query_id=q.query_id,
            hits=["D1"],
            families=["F1", "F2"],
            suspected_relevant=["F1"],  # runner/evaluator judgement, travels with outcome
        )

    controller = AdaptiveController(runner)
    report = controller.run_plan([_spec("Q1")])
    marked = controller.mark_relevant(["F2"])  # human confirms F2
    assert marked == ["F2"]
    acct = report.family_accounting
    assert acct["candidate_families"] == 2
    assert acct["suspected_relevant_families"] == 1
    assert acct["confirmed_relevant_families"] == 1
    assert report.relevant_families == ["F2"]
    assert report.describe()["family_accounting"]["candidate_families"] == 2


# ── query planner fills feature_ids ──────────────────────────────────


def test_planner_single_feature_carries_its_feature_id() -> None:
    bundle = extract_features(["信标发送时刻估计"], axis_id=AXIS)
    plan = QueryPlanBuilder().build(bundle)
    sf = [q for q in plan.queries if q.query_type == "single_feature"]
    assert len(sf) == 1
    assert sf[0].feature_ids == [bundle.features[0].feature_id]


def test_planner_broad_and_cross_carry_participating_features() -> None:
    bundle = extract_features(["信标发送时刻估计；漂移估计与补偿"], axis_id=AXIS)
    plan = QueryPlanBuilder().build(bundle)
    by_type = {}
    for q in plan.queries:
        by_type.setdefault(q.query_type, []).append(q)
    ids = {f.feature_id for f in bundle.features}
    for q in by_type.get("broad_recall", []):
        assert set(q.feature_ids or []) == ids
    for q in by_type.get("feature_cross", []):
        assert set(q.feature_ids or []) == ids


def test_planner_cross_domain_without_origin_feature_stays_none() -> None:
    from patent_intel.retrieval.query_expand import DictionaryExpander, TermCandidate

    class OriginlessExpander:
        def expand(self, feature) -> list[TermCandidate]:  # type: ignore[no-untyped-def]
            return [TermCandidate(term="quantum sensing", relation="cross_domain",
                                  feature_id=None, source="test-dict")]

    bundle = extract_features(["信标发送时刻估计"], axis_id=AXIS)
    plan = QueryPlanBuilder(expanders=[OriginlessExpander()]).build(bundle)
    xd = [q for q in plan.queries if q.query_type == "cross_domain"]
    assert xd and all(q.feature_ids is None for q in xd)  # unknown, not fabricated


# ── runner honesty in reporting.recall ───────────────────────────────


def test_recall_runner_keeps_familyless_docs_document_level() -> None:
    from patent_intel.retrieval.lexical import BM25Index, CorpusDoc
    from patent_intel.retrieval import reporting

    docs = [
        CorpusDoc("D1", "信标发送时刻估计 beacon timing", family_id="FAM-1"),
        CorpusDoc("D2", "信标周期调整 beacon period", family_id=None),
    ]
    index = BM25Index(docs)
    runner = reporting._runner_for(index, docs, k=5)
    outcome = runner(_spec("Q1"))
    assert "D1" in outcome.hits and "D2" in outcome.hits
    assert "D2" not in outcome.families  # never promoted
    assert "FAM-1" in outcome.families
