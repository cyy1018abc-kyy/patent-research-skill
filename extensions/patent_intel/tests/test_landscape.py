"""WP-E landscape tests (E-01..E-04): family-aware aggregation, missing-field
visibility, deterministic offline reports, boundary statements."""

from __future__ import annotations

from pathlib import Path

from patent_intel.landscape.aggregation import aggregate_landscape
from patent_intel.landscape.report import build_landscape_report
from patent_intel.landscape.trends import extract_year, trend_by_axis, trend_by_year


def _records() -> list[dict]:
    return [
        {"publication_number": "EP1234567A1", "assignee": "Acme", "class_code": "H04W",
         "publication_date": "2020-03-01", "family_refs": [{"family_id": "FAM-1"}], "tags": ["N1@T"]},
        {"publication_number": "US9999999B2", "assignee": "Acme", "class_code": "H04W",
         "publication_date": "2021-06-01", "family_refs": [{"family_id": "FAM-1"}], "tags": ["N1@T"]},
        {"publication_number": "CN119000001A", "assignee": "球厂", "class_code": "G06F",
         "publication_date": "", "tags": []},  # no family metadata, no date, no axis
    ]


def test_family_and_document_counts_stay_separate() -> None:
    stats = aggregate_landscape(_records())
    # Acme: 2 docs in one reported family → families=1, documents=2
    acme = stats.by_applicant["Acme"]
    assert acme["families"] == 1
    assert acme["documents"] == 2
    # CN doc has no family metadata → counted, never merged
    assert stats.by_applicant["球厂"]["documents"] == 1
    assert stats.by_applicant["球厂"]["families"] == 0
    assert stats.totals["unknown_family_docs"] == 1
    assert stats.totals["family_group_docs"] == 2


def test_missing_fields_are_visible_buckets() -> None:
    stats = aggregate_landscape(_records())
    # the CN record HAS a class (G06F) so no missing bucket appears in by_class
    assert stats.by_class["G06F"]["documents"] == 1
    # a record with no class at all must show up as an explicit "(missing)" bucket
    stats2 = aggregate_landscape([{"publication_number": "EP1111111A1", "family_refs": [{"family_id": "F"}]}])
    assert stats2.by_class["(missing)"]["documents"] == 1
    year_report = trend_by_year(_records())
    assert year_report["by_year"].get("(missing)", 0) == 1
    assert year_report["missing_year_share"] > 0
    axis_report = trend_by_axis(_records())
    assert axis_report["documents_without_axis"] == 1


def test_extract_year_variants() -> None:
    assert extract_year({"publication_date": "1999-12-31"}) == "1999"
    assert extract_year({"year": 2026}) == "2026"
    assert extract_year({"publication_date": ""}) is None
    assert extract_year({"year": "bad"}) is None


def test_report_boundary_statement_present(tmp_path: Path) -> None:
    paths = build_landscape_report(_records(), tmp_path)
    md = Path(paths["markdown"]).read_text(encoding="utf-8")
    assert "技术空白" in md
    assert "分开计" in md
    assert "不能证明" in md
    csv_text = Path(paths["csv"]).read_text(encoding="utf-8")
    assert "applicant" in csv_text and "Acme" in csv_text


def test_report_deterministic(tmp_path: Path) -> None:
    a = build_landscape_report(_records(), tmp_path / "a")
    b = build_landscape_report(_records(), tmp_path / "b")
    import re

    def strip_stamp(text: str) -> str:
        text = re.sub(r"landscape_\d{8}_\d{6}", "landscape", text)
        return re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "<ts>", text)

    assert strip_stamp(Path(a["markdown"]).read_text(encoding="utf-8")) == strip_stamp(
        Path(b["markdown"]).read_text(encoding="utf-8")
    )


def test_landscape_cli_command(tmp_path: Path) -> None:
    import shutil
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "extensions" / "patent_intel" / "src"))
    from patent_intel.cli import main

    ws = tmp_path / "ws"
    shutil.copytree(Path(__file__).resolve().parents[3] / "benchmarks" / "cases" / "bm01-timesync" / "gold", ws)
    code = main(["landscape", "report", "--root", str(ws)])
    assert code == 0
    reports = ws / ".patent-intel" / "reports"
    assert list(reports.glob("landscape_*.csv"))
    assert list(reports.glob("landscape_*.md"))
