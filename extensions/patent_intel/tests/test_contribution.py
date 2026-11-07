"""P1-A2 tests (roadmap 41A-2): per-query contribution ledger over ControllerReport.

Fixtures are synthetic ``ControllerReport`` objects. Two construction styles, both
matching real controller output:

* ``_synthetic_report`` — outcomes replayed through ``QueryYieldLedger`` with the
  controller's recording semantics (families then documents, in execution order),
  so recorded ``new_families``/``new_documents`` fields and the attached ledger are
  consistent, exactly as ``AdaptiveController.run_plan`` leaves them;
* raw ``ControllerReport(outcomes=[...])`` — hand-built fields for the
  inconsistent-input (problems list) cases.

Outcomes carry family ids and document ids only — no publication numbers are
involved, so identifier normalization never comes into play here.
"""

from __future__ import annotations

import json

from patent_intel.retrieval.controller import ControllerReport, FamilyBasis, RunOutcome
from patent_intel.retrieval.contribution import ContributionReport
from patent_intel.retrieval.coverage import QueryYieldLedger


def _synthetic_report(outcomes: list[RunOutcome]) -> ControllerReport:
    """Replay outcomes through the yield ledger the way the controller does."""
    report = ControllerReport()
    ledger = QueryYieldLedger()
    for outcome in outcomes:
        report.queries_run.append(outcome.query_id)
        report.outcomes.append(outcome)
        report.budget_spent += outcome.cost
        outcome.new_families = ledger.record(outcome.query_id, outcome.families)
        outcome.new_documents = ledger.record_documents(outcome.query_id, outcome.hits)
    report.total_new_families = ledger.total_new_families
    report.total_new_documents = ledger.total_new_documents
    report.ledger = ledger
    return report


def _main_outcomes() -> list[RunOutcome]:
    """Q1 discovers F1/F2; Q2 adds F3; Q3 re-hits everything and adds nothing."""
    return [
        RunOutcome(query_id="Q1", hits=["D1", "D2"], families=["F1", "F2"], cost=2.0),
        RunOutcome(query_id="Q2", hits=["D1", "D3"], families=["F1", "F3"], cost=1.0),
        RunOutcome(query_id="Q3", hits=["D1"], families=["F1", "F2", "F3"], cost=0.5),
    ]


# ── per-query rows: contribution, repetition, ranking ────────────────


def test_per_query_rows_ranking_and_fields() -> None:
    report = ContributionReport.from_report(_synthetic_report(_main_outcomes()))

    assert [row.query_id for row in report.rows] == ["Q1", "Q2", "Q3"]  # new families desc
    assert report.rows_in_execution_order[0].query_id == "Q1"

    q1, q2, q3 = report.rows
    assert q1.new_families == ["F1", "F2"]
    assert q1.new_documents == ["D1", "D2"]
    assert q1.family_hits == 2
    assert q1.total_hits == 2
    assert q1.marginal_benefit == 4
    assert q1.yield_per_cost == 2.0
    assert q1.repeated_families == []
    assert q1.duplicate is False

    assert q2.new_families == ["F3"]
    assert q2.new_documents == ["D3"]
    assert q2.repeated_families == ["F1"]
    assert q2.repeated_documents == ["D1"]
    assert q2.marginal_benefit == 2
    assert q2.duplicate is False

    # Q3: same-family repeated hits, zero additions → duplicate labor
    assert q3.duplicate is True
    assert q3.repeated_families == ["F1", "F2", "F3"]
    assert q3.repeated_documents == ["D1"]
    assert q3.new_families == [] and q3.new_documents == []
    assert q3.marginal_benefit == 0
    assert q3.yield_per_cost == 0.0  # zero gain, not zero cost — a real 0.0

    assert report.problems == []  # replay-consistent fixture raises no problems
    assert report.first_finder_of("F1") == "Q1"
    assert report.first_finder_of("F3") == "Q2"
    assert report.first_finder_of("F-NONE") is None


def test_summary_totals() -> None:
    summary = ContributionReport.from_report(_synthetic_report(_main_outcomes())).summary
    assert summary["queries_total"] == 3
    assert summary["queries_contributing"] == 2
    assert summary["queries_duplicate"] == 1
    assert summary["queries_errored"] == 0
    assert summary["queries_empty_result"] == 0
    assert summary["queries_nonpositive_cost"] == 0
    assert summary["hits_total"] == 5
    assert summary["family_hits_total"] == 7
    assert summary["repeated_family_hits_total"] == 4
    assert summary["repeated_document_hits_total"] == 2
    assert summary["new_families_total"] == 3
    assert summary["new_documents_total"] == 3
    assert summary["unique_families_total"] == 3
    assert summary["marginal_benefit_total"] == 6
    assert summary["cost_total"] == 3.5
    assert summary["yield_per_cost_total"] == 1.7143  # round(6/3.5, 4)


def test_duplicate_detail_names_the_first_finder() -> None:
    described = ContributionReport.from_report(_synthetic_report(_main_outcomes())).describe()
    duplicates = described["duplicates"]
    assert len(duplicates) == 1
    detail = duplicates[0]
    assert detail["query_id"] == "Q3"
    assert detail["family_first_found_by"] == {"F1": "Q1", "F2": "Q1", "F3": "Q2"}
    assert detail["document_first_found_by"] == {"D1": "Q1"}


def test_deterministic_sort_breaks_ties_by_query_id() -> None:
    outcomes = [
        RunOutcome(query_id="Q-B", hits=["D-B"], families=["F-B"], cost=1.0),
        RunOutcome(query_id="Q-A", hits=["D-A"], families=["F-A"], cost=1.0),
    ]
    report = ContributionReport.from_report(_synthetic_report(outcomes))
    assert [row.query_id for row in report.rows] == ["Q-A", "Q-B"]  # tie → query_id asc
    assert [row.execution_index for row in report.rows_in_execution_order] == [0, 1]


# ── acceptance gates: zero cost, empty report, determinism ───────────


def test_zero_cost_never_divides() -> None:
    outcomes = [RunOutcome(query_id="Q-FREE", hits=["D1"], families=["F1"], cost=0.0)]
    report = ContributionReport.from_report(_synthetic_report(outcomes))
    row = report.rows[0]
    assert row.yield_per_cost is None  # undefined, not 0.0/inf
    assert row.duplicate is False  # it did contribute a new family
    assert report.summary["yield_per_cost_total"] is None
    assert report.summary["queries_nonpositive_cost"] == 1
    assert report.problems == []  # zero cost is legitimate local-query pricing


def test_empty_report_boundary() -> None:
    report = ContributionReport.from_report(ControllerReport())
    assert report.rows == []
    assert report.problems == []
    assert report.duplicate_rows == []
    summary = report.summary
    assert summary["queries_total"] == 0
    assert summary["cost_total"] == 0.0
    assert summary["yield_per_cost_total"] is None
    assert summary["unique_families_total"] == 0
    assert json.loads(report.describe_json())["queries"] == []
    assert report.describe_json() == report.describe_json()
    assert (
        ContributionReport.from_report(ControllerReport()).describe_json()
        == report.describe_json()
    )


def test_deterministic_same_input_same_bytes() -> None:
    a = ContributionReport.from_report(_synthetic_report(_main_outcomes()))
    b = ContributionReport.from_report(_synthetic_report(_main_outcomes()))
    assert a.describe_json() == b.describe_json()  # canonical JSON: same bytes
    assert a.describe_json() == a.describe_json()
    # insertion-order determinism holds too (caller-side json.dumps without sort_keys)
    assert json.dumps(a.describe(), ensure_ascii=False) == json.dumps(
        b.describe(), ensure_ascii=False
    )
    assert json.loads(a.describe_json()) == a.describe()
    assert "候选" in json.loads(a.describe_json())["note"]


# ── duplicate semantics ───────────────────────────────────────────────


def test_empty_result_is_not_duplicate() -> None:
    """A clean query that found nothing at all is an empty result, not repeated labor."""
    outcomes = [RunOutcome(query_id="Q-NOTHING", hits=[], families=[], cost=0.0)]
    report = ContributionReport.from_report(_synthetic_report(outcomes))
    assert report.rows[0].duplicate is False
    assert report.rows[0].yield_per_cost is None
    assert report.summary["queries_empty_result"] == 1


def test_unknown_family_basis_duplicates_are_document_level() -> None:
    """family_basis=unknown: families stay empty; doc-level repeats still flag duplicates."""
    outcomes = [
        RunOutcome(
            query_id="Q1", hits=["D1", "D2"], families=[],
            family_basis=FamilyBasis.UNKNOWN, cost=1.0,
        ),
        RunOutcome(
            query_id="Q2", hits=["D2", "D3"], families=[],
            family_basis=FamilyBasis.UNKNOWN, cost=1.0,
        ),
        RunOutcome(
            query_id="Q3", hits=["D1", "D3"], families=[],
            family_basis=FamilyBasis.UNKNOWN, cost=1.0,
        ),
    ]
    report = ContributionReport.from_report(_synthetic_report(outcomes))
    assert all(row.family_hits == 0 for row in report.rows)
    assert report.summary["new_families_total"] == 0
    assert report.summary["new_documents_total"] == 3
    q3 = report.rows_in_execution_order[2]
    assert q3.duplicate is True
    assert q3.repeated_documents == ["D1", "D3"]
    q2 = report.rows_in_execution_order[1]
    assert q2.duplicate is False  # D3 was genuinely new
    detail = report.describe()["duplicates"][0]
    assert detail["document_first_found_by"] == {"D1": "Q1", "D3": "Q2"}


# ── inconsistent input → problems list, never silent trust ───────────


def test_errored_outcomes_contribute_nothing_and_are_flagged() -> None:
    report = ContributionReport.from_report(
        ControllerReport(
            outcomes=[
                RunOutcome(query_id="Q1", hits=["D1"], families=["F1"], cost=1.0),
                RunOutcome(
                    query_id="Q-ERR", hits=["D2"], families=["F2"], cost=1.0,
                    error="RuntimeError: source down",
                ),
            ]
        )
    )
    q1, q_err = report.rows_in_execution_order
    assert q1.new_families == ["F1"]
    assert q_err.errored is True
    assert q_err.new_families == [] and q_err.new_documents == []
    assert q_err.duplicate is False  # errored is never classified as duplicate
    assert report.summary["queries_errored"] == 1
    assert report.summary["unique_families_total"] == 1  # F2 never entered the ledger
    assert any("errored" in problem and "Q-ERR" in problem for problem in report.problems)


def test_negative_cost_flagged_and_yield_undefined() -> None:
    outcomes = [RunOutcome(query_id="Q-NEG", hits=["D1"], families=["F1"], cost=-2.0)]
    report = ContributionReport.from_report(_synthetic_report(outcomes))
    assert any("negative cost" in problem for problem in report.problems)
    assert report.rows[0].yield_per_cost is None
    assert report.summary["queries_nonpositive_cost"] == 1


def test_duplicate_query_id_flagged() -> None:
    report = ContributionReport.from_report(
        ControllerReport(
            outcomes=[
                RunOutcome(query_id="Q-DUP", hits=["D1"], families=["F1"], cost=1.0),
                RunOutcome(query_id="Q-DUP", hits=["D2"], families=["F2"], cost=1.0),
            ]
        )
    )
    assert any("already executed earlier" in problem for problem in report.problems)
    assert [row.execution_index for row in report.rows] == [0, 1]  # stable tiebreak
    assert report.summary["new_families_total"] == 2
    assert report.summary["unique_families_total"] == 2


def test_stale_recorded_new_families_flagged() -> None:
    report = ContributionReport.from_report(
        ControllerReport(
            outcomes=[
                RunOutcome(query_id="Q1", hits=[], families=["F1"], new_families=["F9"]),
                RunOutcome(query_id="Q2", hits=[], families=["F2"], new_families=["F2"]),
            ]
        )
    )
    assert any(
        "recorded new_families disagrees" in problem and "Q1" in problem
        for problem in report.problems
    )
    assert not any("Q2" in problem for problem in report.problems)  # consistent → silent


def test_ledger_out_of_sync_flagged() -> None:
    ledger = QueryYieldLedger()
    ledger.record("Q-OTHER", ["F-EXTRA", "F-EXTRA2"])
    report = ContributionReport.from_report(
        ControllerReport(
            outcomes=[RunOutcome(query_id="Q1", hits=["D1"], families=["F1"])],
            ledger=ledger,
        )
    )
    assert any("ledger.total_new_families(2)" in problem for problem in report.problems)
    assert any("ledger.yield_of('Q1')" in problem for problem in report.problems)


def test_queries_run_length_mismatch_flagged() -> None:
    report = ContributionReport.from_report(
        ControllerReport(
            queries_run=["Q1"],
            outcomes=[
                RunOutcome(query_id="Q1", hits=[], families=[]),
                RunOutcome(query_id="Q2", hits=[], families=[]),
            ],
        )
    )
    assert any("queries_run(1) and outcomes(2) disagree" in problem for problem in report.problems)
