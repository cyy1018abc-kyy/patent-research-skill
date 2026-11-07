"""Tests for advisory.confidence — hard-negative & overconfidence diagnostics (41A-4).

Contract under test: deterministic byte-stable ``describe()``, fail-closed
validation (duplicates / non-finite scores / term-coverage gaps), injected
synthetic hard negatives must surface in the grades, and empty / single-
candidate boundaries never crash.
"""

from __future__ import annotations

import json

import pytest

from patent_intel.advisory.confidence import (
    CandidateSignal,
    ConfidenceDiagnosis,
    ConfidenceError,
    diagnose_candidates,
)


def _dump(diagnosis: ConfidenceDiagnosis) -> str:
    return json.dumps(diagnosis.describe(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class TestSyntheticHardNegative:
    def test_non_gold_above_gold_is_flagged(self):
        diagnosis = diagnose_candidates(
            [("FAM-90001", 12.0), ("FAM-90002", 9.0)],
            query_terms=["frame", "sync"],
            candidate_terms={"FAM-90001": ["frame"], "FAM-90002": ["frame", "sync"]},
            gold=["FAM-90002"],
        )
        assert diagnosis.signals[0].grades == ("above_gold",)
        assert diagnosis.signals[0].margin_to_gold == pytest.approx(3.0)
        assert diagnosis.grades["above_gold"] == ["FAM-90001"]
        assert [s.family_id for s in diagnosis.subjects] == ["FAM-90001", "FAM-90002"] or [
            s.family_id for s in diagnosis.subjects
        ] == ["FAM-90001"]

    def test_hard_negative_gets_margin_and_subject_listing(self):
        # A strong non-gold candidate directly above a gold one: the classic
        # hard-negative shape — tight margin AND above-gold at once.
        diagnosis = diagnose_candidates(
            [("FAM-90001", 10.0), ("FAM-90002", 9.97), ("FAM-90003", 1.0)],
            query_terms=["timing"],
            candidate_terms={
                "FAM-90001": ["timing"],
                "FAM-90002": ["timing"],
                "FAM-90003": ["timing"],
            },
            gold=["FAM-90002"],
        )
        top = diagnosis.signals[0]
        assert top.margin_below == pytest.approx(0.03)
        assert "near_tie" in top.grades and "above_gold" in top.grades
        assert diagnosis.margins == [pytest.approx(0.03), pytest.approx(8.97)]
        assert diagnosis.grades["near_tie"] == ["FAM-90001"]
        # The gold one itself carries no grades — diagnostics target hard negatives.
        assert diagnosis.signals[1].grades == ()

    def test_dominant_top_score_flagged(self):
        diagnosis = diagnose_candidates(
            [("FAM-90001", 100.0), ("FAM-90002", 10.0)],
            query_terms=["t"],
            candidate_terms={"FAM-90001": ["t"], "FAM-90002": ["t"]},
        )
        assert diagnosis.grades["dominant"] == ["FAM-90001"]
        assert diagnosis.describe()["dominance"]["ratio"] == pytest.approx(0.9)

    def test_gold_top_is_never_dominant_flagged(self):
        diagnosis = diagnose_candidates(
            [("FAM-90001", 100.0), ("FAM-90002", 10.0)],
            query_terms=["t"],
            candidate_terms={"FAM-90001": ["t"], "FAM-90002": ["t"]},
            gold=["FAM-90001"],
        )
        assert diagnosis.grades["dominant"] == []

    def test_zero_overlap_flagged(self):
        diagnosis = diagnose_candidates(
            [("FAM-90001", 5.0)],
            query_terms=["frame"],
            candidate_terms={"FAM-90001": []},
        )
        assert diagnosis.grades["zero_overlap"] == ["FAM-90001"]
        assert diagnosis.signals[0].overlap == 0
        assert diagnosis.signals[0].overlap_ratio == 0.0


class TestContract:
    def test_duplicate_candidates_rejected(self):
        with pytest.raises(ConfidenceError, match="duplicate"):
            diagnose_candidates(
                [("FAM-90001", 1.0), ("FAM-90001", 2.0)],
                query_terms=["t"],
                candidate_terms={"FAM-90001": ["t"]},
            )

    def test_non_finite_score_rejected(self):
        with pytest.raises(ConfidenceError, match="finite"):
            diagnose_candidates(
                [("FAM-90001", float("nan"))],
                query_terms=["t"],
                candidate_terms={"FAM-90001": ["t"]},
            )

    def test_missing_term_coverage_rejected_fail_closed(self):
        with pytest.raises(ConfidenceError, match="missing ranked candidates"):
            diagnose_candidates(
                [("FAM-90001", 1.0), ("FAM-90002", 0.5)],
                query_terms=["t"],
                candidate_terms={"FAM-90001": ["t"]},
            )

    @pytest.mark.parametrize("kwargs", [{"n": 0}, {"margin_threshold": -0.1}, {"dominance_ratio": 0.0}, {"dominance_ratio": 1.5}])
    def test_bad_params_rejected(self, kwargs):
        with pytest.raises(ConfidenceError):
            diagnose_candidates(
                [("FAM-90001", 1.0)],
                query_terms=["t"],
                candidate_terms={"FAM-90001": ["t"]},
                **kwargs,
            )

    def test_subject_n_cap(self):
        diagnosis = diagnose_candidates(
            [(f"FAM-{90000 + i}", float(10 - i)) for i in range(5)],
            query_terms=["t"],
            candidate_terms={f"FAM-{90000 + i}": ["t"] for i in range(5)},
            n=2,
        )
        assert len(diagnosis.subjects) == 2
        assert [s.rank for s in diagnosis.subjects] == [1, 2]


class TestBoundaries:
    def test_empty_ranked_list(self):
        diagnosis = diagnose_candidates([], query_terms=["t"], candidate_terms={}, gold=["FAM-90001"])
        assert diagnosis.signals == []
        assert diagnosis.subjects == []
        assert diagnosis.margins == []
        described = diagnosis.describe()
        assert described["margins"]["summary"]["count"] == 0
        assert described["margins"]["summary"]["median"] is None
        assert described["gold"]["best_gold_rank"] is None

    def test_single_candidate_has_no_margins(self):
        diagnosis = diagnose_candidates(
            [("FAM-90001", 3.0)],
            query_terms=["t"],
            candidate_terms={"FAM-90001": ["t"]},
        )
        only = diagnosis.signals[0]
        assert only.rank == 1
        assert only.margin_above is None and only.margin_below is None
        assert only.margin_to_gold is None
        assert diagnosis.margins == []

    def test_gold_absent_from_list_is_reported_not_error(self):
        diagnosis = diagnose_candidates(
            [("FAM-90001", 3.0)],
            query_terms=["t"],
            candidate_terms={"FAM-90001": ["t"]},
            gold=["FAM-99999"],
        )
        assert diagnosis.describe()["gold"]["gold_count_ranked"] == 0
        assert diagnosis.signals[0].margin_to_gold is None
        assert diagnosis.grades["above_gold"] == []

    def test_empty_query_terms_give_zero_ratio_without_crash(self):
        diagnosis = diagnose_candidates(
            [("FAM-90001", 3.0)],
            query_terms=[],
            candidate_terms={"FAM-90001": ["t"]},
        )
        assert diagnosis.signals[0].overlap == 0
        assert diagnosis.signals[0].overlap_ratio == 0.0


class TestDeterminism:
    def test_describe_is_byte_stable_across_runs(self):
        ranked = [("FAM-90001", 12.0), ("FAM-90002", 9.97), ("FAM-90003", 1.0)]
        terms = {fid: ["frame", "sync"][: (i % 2) + 1] for i, (fid, _) in enumerate(ranked)}
        kwargs = dict(query_terms=["frame", "sync"], candidate_terms=terms, gold=["FAM-90003"])
        first = _dump(diagnose_candidates(ranked, **kwargs))
        second = _dump(diagnose_candidates(ranked, **kwargs))
        assert first == second

    def test_describe_is_json_safe(self):
        diagnosis = diagnose_candidates(
            [("FAM-90001", 12.0)],
            query_terms=["frame"],
            candidate_terms={"FAM-90001": ["frame"]},
            gold=["FAM-90002"],
        )
        payload = diagnosis.describe()
        assert isinstance(json.dumps(payload), str)
        assert payload["caveat"].startswith("diagnostic signals")

    def test_signal_dataclass_is_frozen(self):
        diagnosis = diagnose_candidates(
            [("FAM-90001", 1.0)],
            query_terms=["t"],
            candidate_terms={"FAM-90001": ["t"]},
        )
        signal = diagnosis.signals[0]
        assert isinstance(signal, CandidateSignal)
        with pytest.raises(Exception):
            signal.score = 2.0  # type: ignore[misc]
