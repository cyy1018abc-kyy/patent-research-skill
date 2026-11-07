"""INT (W3) wiring tests: contribution report / bench run / doctor sources / recall time flags.

Contract under test: the 4.2 library entry points are reachable as CLI commands
with honest failure modes (exit 2 usage / exit 3 missing dependency), `doctor`
keeps working standalone (backward compat), and the EXIT_USAGE constant the
validate command always meant to use actually exists.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from patent_intel import cli
from patent_intel.retrieval.controller import ControllerReport, RunOutcome

_HAS_PYARROW = importlib.util.find_spec("pyarrow") is not None


def _dump_report(path: Path, *, summarized: bool = False) -> None:
    report = ControllerReport(
        queries_run=["q1", "q2"],
        outcomes=[
            RunOutcome(query_id="q1", hits=["D1", "D2"], families=["FAM-90001"], cost=1.0),
            RunOutcome(query_id="q2", hits=["D1"], families=["FAM-90001"], cost=1.0),
        ],
    )
    if summarized:
        payload = {
            "queries_run": report.queries_run,
            "outcomes": [
                {"query_id": o.query_id, "hits": len(o.hits), "families": len(o.families), "cost": o.cost}
                for o in report.outcomes
            ],
        }
    else:
        payload = {
            "queries_run": report.queries_run,
            "outcomes": [
                {
                    "query_id": o.query_id,
                    "hits": o.hits,
                    "families": o.families,
                    "cost": o.cost,
                    "family_basis": o.family_basis,
                }
                for o in report.outcomes
            ],
        }
    path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")


class TestContributionReportCommand:
    def test_end_to_end_from_dumped_report(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        report_path = tmp_path / "report.json"
        _dump_report(report_path)
        code = cli.main(["contribution", "report", "--report", str(report_path), "--json"])
        assert code == cli.EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        contribution = payload["contribution"]
        assert len(contribution["queries"]) == 2
        assert len(contribution["duplicates"]) == 1  # q2 repeated FAM-90001 with zero new
        assert contribution["problems"] == []

    def test_summarized_report_is_rejected_honestly(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        report_path = tmp_path / "summarized.json"
        _dump_report(report_path, summarized=True)
        code = cli.main(["contribution", "report", "--report", str(report_path), "--json"])
        assert code == cli.EXIT_USAGE
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert "counts" in payload["error"]

    def test_missing_file_and_bad_json_exit_usage(self, tmp_path: Path):
        assert cli.main(["contribution", "report", "--report", str(tmp_path / "nope.json"), "--json"]) == cli.EXIT_USAGE
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert cli.main(["contribution", "report", "--report", str(bad), "--json"]) == cli.EXIT_USAGE

    def test_run_key_wrapper_accepted(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        report_path = tmp_path / "wrapped.json"
        _dump_report(report_path)
        raw = json.loads(report_path.read_text(encoding="utf-8"))
        report_path.write_text(json.dumps({"run": raw}), encoding="utf-8", newline="\n")
        code = cli.main(["contribution", "report", "--report", str(report_path), "--json"])
        assert code == cli.EXIT_OK
        assert len(json.loads(capsys.readouterr().out)["contribution"]["queries"]) == 2


class TestDoctorSourcesCommand:
    def test_skip_only_run_is_ok(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        code = cli.main(
            ["doctor", "sources", "--state-dir", str(tmp_path / "state"), "--only", "ops", "--json"]
        )
        assert code == cli.EXIT_OK  # no credentials → ops is a skip, not a blocking
        payload = json.loads(capsys.readouterr().out)
        entry = payload["diagnostics"]["sources"][0]
        assert entry["source"] == "ops"
        assert entry["status"] == "skip"

    def test_consent_closed_is_blocking(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        code = cli.main(
            ["doctor", "sources", "--state-dir", str(tmp_path / "state"), "--only", "cnipa", "--json"]
        )
        assert code == cli.EXIT_FAIL  # consent gate closed → blocked is actionable
        payload = json.loads(capsys.readouterr().out)
        assert payload["diagnostics"]["status_counts"]["blocked"] == 1
        assert payload["ok"] is False

    def test_doctor_standalone_still_works(self, capsys: pytest.CaptureFixture[str]):
        code = cli.main(["doctor", "--json"])
        assert code in (cli.EXIT_OK, cli.EXIT_FAIL)
        payload = json.loads(capsys.readouterr().out)
        assert payload["tool"] == "patent_intel"
        assert "kernel" in payload["checks"]  # no subcommand → the classic doctor ran


class TestBenchRunCommand:
    def test_missing_corpus_dir_is_usage_error(self, tmp_path: Path):
        code = cli.main(
            [
                "bench", "run",
                "--corpus-dir", str(tmp_path / "nope"),
                "--topics", str(tmp_path / "topics.json"),
                "--side", "baseline",
                "--out-dir", str(tmp_path / "out"),
                "--json",
            ]
        )
        assert code == cli.EXIT_USAGE

    @pytest.mark.skipif(_HAS_PYARROW, reason="pyarrow present: the dependency refusal path cannot trigger")
    def test_pyarrow_missing_is_dependency_error(self, tmp_path: Path):
        (tmp_path / "corpus").mkdir()
        (tmp_path / "topics.json").write_text('{"topics": []}', encoding="utf-8")
        code = cli.main(
            [
                "bench", "run",
                "--corpus-dir", str(tmp_path / "corpus"),
                "--topics", str(tmp_path / "topics.json"),
                "--side", "baseline",
                "--out-dir", str(tmp_path / "out"),
                "--json",
            ]
        )
        assert code == cli.EXIT_DEPENDENCY

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow required to synthesize the parquet corpus")
    def test_end_to_end_baseline_rows_and_meta(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        import pyarrow as pa
        import pyarrow.parquet as pq

        corpus_dir = tmp_path / "corpus"
        corpus_dir.mkdir()
        docs = pa.table(
            {
                "relevant_id": ["FAM-90001", "FAM-90002", "FAM-90003"],
                "title_en": ["frame sync timing", "water pump valve", "chemical catalyst"],
                "abstract_en": ["frame sync marker", "pressure", "composition"],
                "claims_text": ["timing frame", "pump", "catalyst"],
            }
        )
        pq.write_table(docs, corpus_dir / "corpus.parquet")
        queries = pa.table(
            {
                "query_id": ["q1"],
                "title_en": ["frame sync timing"],
                "abstract_en": [""],
                "claims_text": [""],
            }
        )
        pq.write_table(queries, corpus_dir / "queries.parquet")
        topics = tmp_path / "topics.json"
        topics.write_text(
            json.dumps({"topics": [{"topic_id": "TP-9001", "source_id": "q1", "split": "test"}]}),
            encoding="utf-8",
            newline="\n",
        )
        code = cli.main(
            [
                "bench", "run",
                "--corpus-dir", str(corpus_dir),
                "--topics", str(topics),
                "--side", "baseline",
                "--k", "5",
                "--out-dir", str(tmp_path / "out"),
                "--json",
            ]
        )
        assert code == cli.EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True and payload["topics_run"] == 1
        assert payload["batch_mode"] == "cli:bench-run:baseline"

        rows_bytes = Path(payload["rows_file"]).read_bytes()
        expected = "".join(
            json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n"
            for r in [
                {"topic_id": "TP-9001", "family_id": "FAM-90001", "rank": 1},
                {"topic_id": "TP-9001", "family_id": "FAM-90003", "rank": 2},
                {"topic_id": "TP-9001", "family_id": "FAM-90002", "rank": 3},
            ]
        ).encode("utf-8")
        assert rows_bytes == expected  # same byte format as the preregistered runner
        meta = json.loads(Path(payload["meta_file"]).read_text(encoding="utf-8"))
        assert meta["batch_mode"] == "cli:bench-run:baseline"
        assert meta["network_requests"] == 0

    def test_limit_on_non_test_split_refused(self, tmp_path: Path):
        (tmp_path / "corpus").mkdir()
        topics = tmp_path / "topics.json"
        topics.write_text('{"topics": []}', encoding="utf-8")
        code = cli.main(
            [
                "bench", "run",
                "--corpus-dir", str(tmp_path / "corpus"),
                "--topics", str(topics),
                "--split", "val",
                "--limit", "2",
                "--side", "baseline",
                "--out-dir", str(tmp_path / "out"),
                "--json",
            ]
        )
        assert code == cli.EXIT_USAGE


class TestRecallTimeFlags:
    def test_dates_file_attaches_time_view(self, gold_workspace: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        dates = tmp_path / "dates.json"
        dates.write_text(
            json.dumps({"FAM-90001": {"publication_date": "2018-01-01"}}), encoding="utf-8", newline="\n"
        )
        code = cli.main(
            [
                "recall", "report",
                "--root", str(gold_workspace),
                "--state-dir", str(tmp_path / "sidecar"),
                "--dates-file", str(dates),
                "--target-filing-date", "2015-06-01",
                "--json",
            ]
        )
        assert code == cli.EXIT_OK
        report = json.loads(capsys.readouterr().out)["report"]
        assert "time_view" in report
        assert report["time_view"]["summary"]["suggestions"]["filter_publication_after_target"] >= 0

    def test_non_object_dates_file_refused(self, gold_workspace: Path, tmp_path: Path):
        dates = tmp_path / "dates.json"
        dates.write_text("[1, 2, 3]", encoding="utf-8")
        code = cli.main(
            [
                "recall", "report",
                "--root", str(gold_workspace),
                "--state-dir", str(tmp_path / "sidecar"),
                "--dates-file", str(dates),
                "--json",
            ]
        )
        assert code == cli.EXIT_USAGE


class TestExitUsageConstant:
    def test_query_validate_missing_plan_is_usage_error_not_nameerror(self, tmp_path: Path):
        # Regression: EXIT_USAGE was referenced before it was ever defined.
        code = cli.main(["query", "validate", "--plan", str(tmp_path / "missing.json"), "--json"])
        assert code == cli.EXIT_USAGE
