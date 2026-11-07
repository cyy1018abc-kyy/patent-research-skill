"""Tests for 41B-2 citation-chain budget allocation (unified controller budget).

Contract under test: directions admitted by marginal benefit; zero-yield
directions pruned without consuming budget; request/cost budget respected
(never a side budget); explicit per-direction provenance + stop reasons; no
unbounded citation walks; task→QuerySpec proposals stay approved=False with
honest empty feature coverage; controller regression stays zero.
"""

from __future__ import annotations

import json

import pytest

from patent_intel.contracts import QuerySpec
from patent_intel.retrieval.citation_expand import (
    MAX_DEPTH_CEILING,
    CitationExpansionError,
    allocate_citation_layers,
    citation_tasks_to_query_specs,
)
from patent_intel.retrieval.controller import AdaptiveController, RunOutcome

RECORDS = [
    {
        "id": "US0000001A1",
        "citations": ["US0000002A1", "US0000003A1"],
        "cited_by": ["US0000010A1", "US0000011A1", "US0000012A1"],
        "family_refs": [{"family_id": "FAM-90001"}],
    },
    {
        "id": "US0000004A1",
        "citations": ["US0000003A1"],
    },
]


class TestAllocation:
    def test_directions_admitted_by_marginal_benefit(self):
        plan = allocate_citation_layers(
            RECORDS, budget_requests=10, budget_cost=100.0, cost_per_task=2.0
        )
        # cited_by (3 new) > cites (2 new) > family (1 new)
        assert [a.direction for a in plan.accounts] == ["cited_by", "cites", "family"]
        assert len(plan.tasks) == 6
        assert plan.stop_reason == "all_directions_accounted"

    def test_seen_refs_reduce_benefit_and_prune_zero_yield(self):
        plan = allocate_citation_layers(
            RECORDS,
            seen_refs={"US0000010A1", "US0000011A1", "US0000012A1"},
            budget_requests=10,
            budget_cost=100.0,
        )
        by_dir = {a.direction: a for a in plan.accounts}
        assert by_dir["cited_by"].status == "zero_yield_pruned"
        assert by_dir["cited_by"].admitted == 0
        assert by_dir["cites"].admitted == 2  # budget NOT consumed by the pruned one
        assert len(plan.tasks) == 3

    def test_request_budget_exhaustion_stops_admission(self):
        plan = allocate_citation_layers(RECORDS, budget_requests=1, budget_cost=100.0)
        by_dir = {a.direction: a for a in plan.accounts}
        assert by_dir["cited_by"].admitted == 1
        assert by_dir["cites"].status == "budget_exhausted"
        assert by_dir["family"].status == "budget_exhausted"
        assert plan.stop_reason == "budget_exhausted"
        assert len(plan.tasks) == 1

    def test_cost_budget_gates_admission(self):
        plan = allocate_citation_layers(RECORDS, budget_requests=10, budget_cost=3.9, cost_per_task=2.0)
        assert len(plan.tasks) == 1  # 3.9 // 2.0 = 1 task

    def test_per_direction_task_cap(self):
        plan = allocate_citation_layers(
            RECORDS, budget_requests=10, budget_cost=100.0, max_tasks_per_direction=1
        )
        by_dir = {a.direction: a for a in plan.accounts}
        assert by_dir["cited_by"].status == "task_cap"
        assert by_dir["cited_by"].admitted == 1
        assert by_dir["cites"].admitted == 1  # other directions still served
        assert plan.stop_reason == "task_cap"

    def test_empty_records_account_everything(self):
        plan = allocate_citation_layers([], budget_requests=5, budget_cost=50.0)
        assert plan.tasks == []
        assert plan.stop_reason == "all_directions_accounted"
        assert all(a.status == "zero_yield_pruned" for a in plan.accounts)

    def test_zero_budget_admits_nothing(self):
        plan = allocate_citation_layers(RECORDS, budget_requests=0, budget_cost=0.0)
        assert plan.tasks == []
        assert all(a.status == "budget_exhausted" for a in plan.accounts)
        assert plan.stop_reason == "budget_exhausted"

    def test_describe_is_deterministic_bytes(self):
        kwargs = dict(budget_requests=4, budget_cost=9.0, cost_per_task=2.0)
        first = json.dumps(allocate_citation_layers(RECORDS, **kwargs).describe(), sort_keys=True)
        second = json.dumps(allocate_citation_layers(RECORDS, **kwargs).describe(), sort_keys=True)
        assert first == second


class TestNoUnboundedWalks:
    def test_depth_beyond_ceiling_refused(self):
        with pytest.raises(CitationExpansionError, match="ceiling"):
            allocate_citation_layers(RECORDS, max_depth=MAX_DEPTH_CEILING + 1)

    def test_depth_within_ceiling_accepted(self):
        plan = allocate_citation_layers(RECORDS, budget_requests=5, budget_cost=50.0, max_depth=3)
        assert all(t.depth == 1 for t in plan.tasks)

    def test_negative_budgets_refused(self):
        with pytest.raises(CitationExpansionError):
            allocate_citation_layers(RECORDS, budget_requests=-1)
        with pytest.raises(CitationExpansionError):
            allocate_citation_layers(RECORDS, budget_cost=-0.1)


class TestQuerySpecConversion:
    def test_tasks_become_unapproved_proposals(self):
        plan = allocate_citation_layers(RECORDS, budget_requests=10, budget_cost=100.0)
        specs = citation_tasks_to_query_specs(plan.tasks)
        assert len(specs) == len(plan.tasks)
        for spec in specs:
            assert isinstance(spec, QuerySpec)
            assert spec.query_type == "citation_expand"
            assert spec.approved is False
            assert spec.feature_ids == []  # citation hop has no feature → unknown coverage
            assert spec.terms and all(t.strip() for t in spec.terms)
            spec.validate()  # UT-Q03: provenance items must carry a feature_id key

    def test_conversion_is_deterministic_and_unique(self):
        plan = allocate_citation_layers(RECORDS, budget_requests=10, budget_cost=100.0)
        specs = citation_tasks_to_query_specs(plan.tasks)
        ids = [s.query_id for s in specs]
        assert len(ids) == len(set(ids))
        again = [s.query_id for s in citation_tasks_to_query_specs(plan.tasks)]
        assert ids == again


class TestControllerUnifiedBudget:
    @staticmethod
    def _runner(query: QuerySpec) -> RunOutcome:
        return RunOutcome(query_id=query.query_id, hits=["D1"], families=["FAM-1"], cost=0.5)

    def test_plan_uses_only_remaining_budget(self):
        controller = AdaptiveController(self._runner, max_requests=3, max_cost=100.0)
        plan_queries = [
            QuerySpec(
                owner="test",
                query_id="q1",
                axis_id="axis",
                terms=["t"],
                language="en",
                query_type="single_feature",
                source="bm25",
            ),
            QuerySpec(
                owner="test",
                query_id="q2",
                axis_id="axis",
                terms=["t"],
                language="en",
                query_type="single_feature",
                source="bm25",
            ),
        ]
        report = controller.run_plan(plan_queries)
        assert len(report.queries_run) == 2
        citation_plan = controller.plan_citation_layers(report, RECORDS)
        # only 1 request remains of max_requests=3
        assert citation_plan.budget_requests_before == 1
        assert len(citation_plan.tasks) == 1

    def test_fresh_controller_sees_full_budget(self):
        controller = AdaptiveController(self._runner, max_requests=6, max_cost=100.0)
        empty_report = controller.run_plan([])
        citation_plan = controller.plan_citation_layers(empty_report, RECORDS)
        assert citation_plan.budget_requests_before == 6
        assert len(citation_plan.tasks) == 6

    def test_cost_budget_shared_with_run(self):
        controller = AdaptiveController(self._runner, max_requests=50, max_cost=1.0)
        plan_queries = [
            QuerySpec(
                owner="test",
                query_id="q1",
                axis_id="axis",
                terms=["t"],
                language="en",
                query_type="single_feature",
                source="bm25",
            )
        ]
        report = controller.run_plan(plan_queries)  # spends 0.5
        citation_plan = controller.plan_citation_layers(report, RECORDS)
        assert citation_plan.budget_cost_before == pytest.approx(0.5)
        assert len(citation_plan.tasks) == 0  # 0.5 < 2.0 per citation task
        assert all(a.status == "budget_exhausted" for a in citation_plan.accounts)
