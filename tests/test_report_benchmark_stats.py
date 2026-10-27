"""T-06: benchmark stats single-source generator — determinism + staleness check."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "report_benchmark_stats.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True, text=True, encoding="utf-8", timeout=120, check=False,
    )


def _write_report(results: Path, name: str, suite: str, r100: float) -> None:
    results.mkdir(parents=True, exist_ok=True)
    (results / name).write_text(
        json.dumps(
            {
                "tool": "score_retrieval",
                "suite": suite,
                "version": "1.0.0",
                "qrels_version": "qrels-v1",
                "topics_evaluated": 2,
                "recall_at_k": {"50": r100 - 0.1, "100": r100, "200": r100 + 0.02},
                "mrr": 0.75,
                "critical_recall": {"value": 0.9, "n_topics": 1},
            }
        ),
        encoding="utf-8",
    )


def test_generates_deterministic_table(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_report(results, "2026-10-28-smoke.json", "synthetic-smoke", 1.0)
    a = _run("--results", str(results))
    b = _run("--results", str(results))
    assert a.returncode == 0 and b.returncode == 0
    assert a.stdout == b.stdout
    assert "synthetic-smoke" in a.stdout
    assert "1.0000" in a.stdout
    assert "AUTO-GENERATED" in a.stdout


def test_non_score_reports_ignored_and_bad_json_fatal(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    (results / "manifest-backup.json").write_text(json.dumps({"suite": "x"}), encoding="utf-8")
    code = _run("--results", str(results))
    assert code.returncode == 0
    assert "(no archived reports)" in code.stdout

    (results / "broken.json").write_text("{bad", encoding="utf-8")
    assert _run("--results", str(results)).returncode == 1


def test_check_mode_detects_stale_doc(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_report(results, "r1.json", "suite-a", 1.0)
    out = tmp_path / "stats.md"
    assert _run("--results", str(results), "--out", str(out)).returncode == 0

    # doc in sync → check passes
    doc = tmp_path / "README-stat.md"
    doc.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
    assert _run("--results", str(results), "--check", str(doc)).returncode == 0

    # numbers drift (a new evaluation) → check fails
    _write_report(results, "r2.json", "suite-b", 0.42)
    assert _run("--results", str(results), "--check", str(doc)).returncode == 1
