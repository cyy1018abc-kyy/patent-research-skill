"""WP-A A-04..A-06 tests: BM25 determinism, RRF, family collapse, coverage, citation
tasks, adaptive controller stop conditions (UT-R01/UT-R02, UT-S03 discipline)."""

from __future__ import annotations

import pytest

from patent_intel.contracts import QuerySpec
from patent_intel.retrieval.citation_expand import CitationExpansionError, plan_citation_expansion
from patent_intel.retrieval.controller import AdaptiveController, Cancelled, RunOutcome, StopReason
from patent_intel.retrieval.coverage import CoverageTracker, QueryYieldLedger
from patent_intel.retrieval.hybrid import family_collapse, rrf_fuse
from patent_intel.retrieval.lexical import BM25Index, CorpusDoc, tokenize


def _corpus() -> list[CorpusDoc]:
    return [
        CorpusDoc("D1", "信标发送时刻估计 beacon timing estimation in wireless sensor networks", family_id="FAM-1"),
        CorpusDoc("D2", "漂移估计与补偿 drift compensation via least squares", family_id="FAM-1"),
        CorpusDoc("D3", "电池管理系统 battery management state of charge estimation", family_id="FAM-2"),
        CorpusDoc("D4", "信标周期动态调整 dynamic beacon period adaptation", family_id=None),
        CorpusDoc("D5", "agv 调度调度调度 unrelated scheduling", family_id="FAM-3"),
    ]


# ── lexical BM25 (UT-R01) ────────────────────────────────────────────


def test_bm25_deterministic() -> None:
    a = BM25Index(_corpus()).search("信标 发送时刻 beacon", k=5)
    b = BM25Index(_corpus()).search("信标 发送时刻 beacon", k=5)
    assert a == b
    assert [d for d, _ in a][:2] == ["D1", "D4"]  # beacon docs first


def test_bm25_irrelevant_query_scores_zero() -> None:
    hits = BM25Index(_corpus()).search("量子纠缠 entanglement", k=5)
    assert hits == []


def test_bm25_tokenizer_cjk_bigrams() -> None:
    tokens = tokenize("信标时间 beacon")
    assert "信标" in tokens and "标时" in tokens
    assert "beacon" in tokens


def test_bm25_explain_breaks_down_scores() -> None:
    index = BM25Index(_corpus())
    explain = index.explain("D1", "信标 beacon")
    assert explain and all(v > 0 for v in explain.values())


def test_bm25_duplicate_doc_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        BM25Index([CorpusDoc("X", "a"), CorpusDoc("X", "b")])


# ── hybrid (RRF + family collapse) ───────────────────────────────────


def test_rrf_fuse_deterministic_and_fair() -> None:
    rankings = {"bm25": ["D1", "D2", "D3"], "dense": ["D3", "D1"]}
    fused = rrf_fuse(rankings, k=60)
    scores = dict(fused)
    # D1 appears in both lists near top; D2 only in one
    assert scores["D1"] > scores["D2"]
    assert rrf_fuse(rankings, k=60) == fused  # deterministic


def test_family_collapse_keeps_best_per_family() -> None:
    ranked = [("D1", 10.0), ("D2", 8.0), ("D3", 6.0), ("D4", 4.0)]
    family_of = {"D1": "FAM-1", "D2": "FAM-1", "D3": "FAM-2"}
    out = family_collapse(ranked, family_of)
    assert [d for d, _ in out] == ["D1", "D3", "D4"]  # D2 collapses into FAM-1; D4 unknown stays


# ── coverage + yield ledger ──────────────────────────────────────────


def test_yield_ledger_counts_only_new_families() -> None:
    ledger = QueryYieldLedger()
    first = ledger.record("Q1", ["F1", "F2"])
    second = ledger.record("Q2", ["F2", "F3"])
    assert first == ["F1", "F2"]
    assert second == ["F3"]
    assert ledger.total_new_families == 3


def test_coverage_tracker_reports_uncovered() -> None:
    tracker = CoverageTracker()
    tracker.record_hit("N1@T", "信标", "F1")
    report = tracker.report(
        ["N1@T", "N2@T"],
        {"N1@T": ["信标", "漂移"], "N2@T": ["重同步"]},
    )
    assert report.per_axis["N1@T"]["concepts_covered"] == 1
    assert report.per_axis["N1@T"]["concepts_uncovered"] == ["漂移"]
    assert report.uncovered_axes == ["N2@T"]
    assert "≠" in report.describe()["note"]


# ── citation expansion ───────────────────────────────────────────────


def test_citation_tasks_from_reported_fields() -> None:
    records = [
        {
            "id": "P-001",
            "cited_by": ["EP0000002A1", "EP0000003A1"],
            "citations": ["US0000001A1"],
            "family_refs": [{"family_id": "FAM-9"}],
        }
    ]
    tasks = plan_citation_expansion(records)
    directions = {(t.direction, t.target_ref) for t in tasks}
    assert ("cited_by", "EP0000002A1") in directions
    assert ("cites", "US0000001A1") in directions
    assert ("family", "FAM-9") in directions
    assert all(t.provenance_field for t in tasks)


def test_citation_tasks_none_without_metadata() -> None:
    """缺家族元数据不静默合并：no citation fields → no tasks, no invention."""
    records = [{"id": "P-002", "title": "no links here"}]
    assert plan_citation_expansion(records) == []


def test_citation_tasks_budget_and_dedupe() -> None:
    records = [{"id": "P-1", "cited_by": [f"EP{i:07d}A1" for i in range(10)]}]
    tasks = plan_citation_expansion(records, max_tasks=3)
    assert len(tasks) == 3
    again = plan_citation_expansion(records, max_tasks=10, seen_refs={t.target_ref for t in tasks})
    assert not ({t.target_ref for t in again} & {t.target_ref for t in tasks})


def test_citation_tasks_bad_args() -> None:
    with pytest.raises(CitationExpansionError):
        plan_citation_expansion([], max_depth=0)


# ── adaptive controller (UT-R02) ─────────────────────────────────────


def _spec(qid: str, axis: str = "N1@T", query_type: str = "single_feature") -> QuerySpec:
    return QuerySpec(
        owner="WP-A", query_id=qid, axis_id=axis, terms=["t"], language="zh",
        query_type=query_type, source="multi",
    )


def test_controller_runs_whole_plan() -> None:
    def runner(q: QuerySpec) -> RunOutcome:
        return RunOutcome(query_id=q.query_id, hits=["D1"], families=["F1"], new_families=[])

    report = AdaptiveController(runner).run_plan([_spec("Q1"), _spec("Q2")])
    assert report.stop_reason == StopReason.PLAN_EXHAUSTED
    assert report.queries_run == ["Q1", "Q2"]
    assert "停止不等同已查全" in report.describe()["caveat"]


def test_controller_stops_on_budget() -> None:
    counter = {"n": 0}

    def runner(q: QuerySpec) -> RunOutcome:
        counter["n"] += 1
        return RunOutcome(query_id=q.query_id, hits=["D1"], families=["F1"], new_families=["F1"], cost=10.0)

    # 4 queries × 10 = 40 > 25: the 4th is refused, stop_reason=budget_exhausted
    report = AdaptiveController(runner, max_cost=25.0).run_plan(
        [_spec("Q1"), _spec("Q2"), _spec("Q3"), _spec("Q4")]
    )
    assert report.stop_reason == StopReason.BUDGET_EXHAUSTED
    assert counter["n"] == 3
    assert report.budget_spent == 30.0


def test_controller_budget_never_exceeded_by_partial_run() -> None:
    def runner(q: QuerySpec) -> RunOutcome:
        return RunOutcome(query_id=q.query_id, hits=[], families=[], new_families=[], cost=6.0)

    report = AdaptiveController(runner, max_cost=10.0).run_plan([_spec("Q1")])
    assert report.stop_reason == StopReason.PLAN_EXHAUSTED  # 6 < 10, single query completes


def test_controller_stops_on_zero_gain() -> None:
    def runner(q: QuerySpec) -> RunOutcome:
        return RunOutcome(query_id=q.query_id, hits=["D9"], families=["F9"], new_families=[])

    # Q1 discovers F9 (genuine novelty); Q2/Q3 re-find it -> 2 zero-gain rounds -> stop
    report = AdaptiveController(runner, zero_gain_rounds=2).run_plan(
        [_spec("Q1"), _spec("Q2"), _spec("Q3"), _spec("Q4")]
    )
    assert report.stop_reason == StopReason.ZERO_GAIN
    assert len(report.queries_run) == 3
    assert report.outcomes[0].new_families == ["F9"]
    assert report.outcomes[1].new_families == []
    assert report.total_new_families == 1


def test_controller_records_runner_failure_as_zero_gain() -> None:
    def runner(q: QuerySpec) -> RunOutcome:
        raise RuntimeError("source down")

    report = AdaptiveController(runner, zero_gain_rounds=1).run_plan([_spec("Q1")])
    assert report.stop_reason == StopReason.ZERO_GAIN
    assert report.outcomes[0].error and "source down" in report.outcomes[0].error


def test_controller_manual_cancel() -> None:
    def runner(q: QuerySpec) -> RunOutcome:
        raise Cancelled()

    report = AdaptiveController(runner).run_plan([_spec("Q1"), _spec("Q2")])
    assert report.stop_reason == StopReason.MANUAL
    assert report.queries_run == []


def test_controller_selection_is_coverage_gap_first() -> None:
    ran: list[str] = []

    def runner(q: QuerySpec) -> RunOutcome:
        ran.append(q.query_id)
        return RunOutcome(query_id=q.query_id, hits=[], families=[], new_families=[])

    queries = [
        _spec("Q-BROAD", query_type="broad_recall"),
        _spec("Q-SF1", axis="N1@T"),
        _spec("Q-SF2", axis="N2@T"),
    ]
    AdaptiveController(runner, zero_gain_rounds=99).run_plan(queries)
    assert ran[0].endswith("SF1") or ran[0].endswith("SF2")  # single_feature first
    assert ran[-1].endswith("BROAD")


def test_controller_rejects_negative_budget() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        AdaptiveController(lambda q: None, max_requests=-1)  # type: ignore[arg-type,return-value]
