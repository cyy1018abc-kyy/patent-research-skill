"""Tests for 41C-1: time-sensitive view with advisory-only semantics.

Contract under test: date conflicts/missing values are flagged honestly (never
fabricated, never silently resolved); suggestions come from a closed vocabulary
and are filter advice only; the ranked order passes through verbatim — the view
never re-sorts and never changes recall; reports without date data keep their
exact previous shape.
"""

from __future__ import annotations

import json

import pytest

from patent_intel.retrieval import reporting
from patent_intel.retrieval.time_view import TimeViewError, time_view


class TestDateStructuring:
    def test_known_dates_are_structured(self):
        report = time_view(
            ["FAM-90001", "FAM-90002"],
            {
                "FAM-90001": {"publication_date": "2015-03-01", "priority_date": "2013-01-01"},
                "FAM-90002": {"publication_date": "2016-06-10", "priority_date": "2014-02-02"},
            },
        )
        first, second = report.signals
        assert (first.publication_date, first.priority_date, first.date_status) == (
            "2015-03-01",
            "2013-01-01",
            "known",
        )
        assert first.suggestion is None

    def test_missing_entry_is_unknown_never_fabricated(self):
        report = time_view(["FAM-90001"], {})
        signal = report.signals[0]
        assert signal.date_status == "unknown"
        assert signal.publication_date is None and signal.priority_date is None
        assert signal.suggestion is None

    def test_partial_missing_priority_is_flagged(self):
        report = time_view(
            ["FAM-90001"],
            {"FAM-90001": {"publication_date": "2015-03-01"}},
        )
        signal = report.signals[0]
        assert signal.date_status == "partial"
        assert signal.suggestion == "priority_date_missing"

    def test_multi_source_conflict_is_flagged_values_preserved(self):
        report = time_view(
            ["FAM-90001"],
            {"FAM-90001": {"publication_dates": ["2015-03-02", "2015-03-01"]}},
        )
        signal = report.signals[0]
        assert signal.date_status == "conflicted"
        assert signal.publication_date is None  # no value asserted
        assert signal.conflicts == ("conflicting values: ['2015-03-01', '2015-03-02']",)
        assert signal.suggestion == "review_date_conflict"

    def test_unparseable_date_is_conflict_not_crash(self):
        report = time_view(["FAM-90001"], {"FAM-90001": {"publication_date": "March 2015"}})
        signal = report.signals[0]
        assert signal.date_status == "conflicted"
        assert "unparseable" in signal.conflicts[0]

    def test_unparseable_target_date_refused(self):
        with pytest.raises(TimeViewError, match="ISO date"):
            time_view(["FAM-90001"], {}, target_filing_date="March 2015")


class TestSuggestions:
    def test_published_after_target_gets_filter_suggestion(self):
        report = time_view(
            ["FAM-90001", "FAM-90002"],
            {
                "FAM-90001": {"publication_date": "2018-01-01"},
                "FAM-90002": {"publication_date": "2014-01-01"},
            },
            target_filing_date="2015-06-01",
        )
        assert report.signals[0].suggestion == "filter_publication_after_target"
        # FAM-90002: published before target but priority unknown → missing-priority advice
        assert report.signals[1].suggestion == "priority_date_missing"
        assert report.describe()["summary"]["suggestions"]["filter_publication_after_target"] == 1

    def test_unknown_dates_get_no_suggestion(self):
        report = time_view(["FAM-90001"], {}, target_filing_date="2015-06-01")
        assert report.signals[0].suggestion is None


class TestAdvisoryOnlyDiscipline:
    def test_ranked_order_passes_through_verbatim(self):
        ranked = ["FAM-90005", "FAM-90001", "FAM-90003"]
        dates = {
            "FAM-90001": {"publication_date": "2001-01-01"},  # oldest → would sort first
            "FAM-90003": {"publication_date": "2099-01-01"},
        }
        report = time_view(ranked, dates)
        assert report.ranked_order == ranked
        assert [s.family_id for s in report.signals] == ranked
        assert [s.rank for s in report.signals] == [1, 2, 3]

    def test_deterministic_describe_bytes(self):
        kwargs = dict(
            ranked=["FAM-90001", "FAM-90002"],
            dates_by_family={
                "FAM-90001": {"publication_dates": ["2015-03-02", "2015-03-01"]},
                "FAM-90002": {"publication_date": "2016-06-10"},
            },
            target_filing_date="2015-06-01",
        )
        first = json.dumps(time_view(**kwargs).describe(), sort_keys=True)
        second = json.dumps(time_view(**kwargs).describe(), sort_keys=True)
        assert first == second

    def test_empty_ranked_list(self):
        report = time_view([], {"FAM-90001": {"publication_date": "2015-03-01"}})
        assert report.signals == []
        assert report.describe()["summary"]["count"] == 0

    def test_describe_is_json_safe(self):
        payload = time_view(
            ["FAM-90001"], {"FAM-90001": {"publication_date": "2015-03-01"}}
        ).describe()
        assert isinstance(json.dumps(payload), str)
        assert "never changes recall or ranking" in payload["caveat"]


class TestReportingIntegration:
    def test_attach_time_view_is_additive(self):
        report: dict = {"existing": "shape"}
        out = reporting._attach_time_view(
            report,
            ["FAM-90001"],
            {"FAM-90001": {"publication_date": "2018-01-01"}},
            target_filing_date="2015-06-01",
        )
        assert out["existing"] == "shape"
        assert out["time_view"]["summary"]["suggestions"]["filter_publication_after_target"] == 1

    def test_no_dates_leaves_report_shape_untouched(self):
        report: dict = {"existing": "shape"}
        out = reporting._attach_time_view(report, ["FAM-90001"], None)
        assert out == {"existing": "shape"}
        assert "time_view" not in out

    def test_recall_report_smoke_with_dates(self, gold_workspace, tmp_path):
        report = reporting.recall_report(
            gold_workspace,
            tmp_path / "sidecar",
            dates_by_family={"FAM-90001": {"publication_date": "2018-01-01"}},
            target_filing_date="2015-06-01",
        )
        assert "time_view" in report
        assert report["time_view"]["summary"]["date_status"]["unknown"] >= 0

    def test_recall_report_without_dates_keeps_shape(self, gold_workspace, tmp_path):
        report = reporting.recall_report(gold_workspace, tmp_path / "sidecar")
        assert "time_view" not in report
