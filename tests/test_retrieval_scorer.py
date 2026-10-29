"""Score_retrieval end-to-end tests (T-02/T-03): hand-checked numbers + error injection (UT-M01).

Builds a tiny synthetic suite per test (no real patent text), runs the scorer as a
subprocess, and asserts exact metric values / audit failures.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORER = REPO_ROOT / "tools" / "score_retrieval.py"


def _write_suite(tmp_path: Path, topics: list[dict], families: dict[str, str] | None = None) -> Path:
    suite = tmp_path / "suite"
    suite.mkdir()
    manifest = {
        "suite": "test-suite",
        "version": "1.0.0",
        "qrels_version": "qrels-v1",
        "gold_completeness": "pool_biased",
        "license": "synthetic, no real patent text",
        "topics": topics,
    }
    if families is not None:
        manifest["families"] = families
    (suite / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return suite


def _write_runs(tmp_path: Path, name: str, entries: list[dict]) -> Path:
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    with open(runs / f"{name}.jsonl", "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return runs


def _score(tmp_path: Path, suite: Path, runs: Path, *extra: str) -> tuple[int, dict | None, str]:
    proc = subprocess.run(
        [sys.executable, str(SCORER), "--suite", str(suite), "--runs", str(runs), "--json", *extra],
        capture_output=True, text=True, encoding="utf-8", timeout=300, check=False,
    )
    report = json.loads(proc.stdout) if proc.returncode == 0 and proc.stdout.strip() else None
    return proc.returncode, report, proc.stderr


def _default_topics() -> list[dict]:
    return [
        {
            "topic_id": "TP-0001",
            "split": "test",
            "language": "zh",
            "domain": "timesync",
            "gold_families": ["F1", "F2", "F3"],
            "critical_families": ["F1"],
            "relevance_levels": {"F1": 3, "F2": 2, "F3": 1},
        },
        {
            "topic_id": "TP-0002",
            "split": "test",
            "language": "en",
            "domain": "bms",
            "gold_families": ["F4"],
        },
    ]


def test_hand_computed_small_sample(tmp_path: Path) -> None:
    """TP-0001: ranked [F2,F9,F1] -> recall(any K>=3)=2/3, MRR=1, nDCG graded, crit=1.0.
    TP-0002: ranked [F7] -> recall 0, MRR 0. Macro mean recall = 1/3."""
    suite = _write_suite(tmp_path, _default_topics())
    runs = _write_runs(tmp_path, "run-a", [
        {"topic_id": "TP-0001", "family_id": "F2", "rank": 1, "score": 9.0},
        {"topic_id": "TP-0001", "family_id": "F9", "rank": 2, "score": 5.0},
        {"topic_id": "TP-0001", "family_id": "F1", "rank": 3, "score": 4.0},
        {"topic_id": "TP-0002", "family_id": "F7", "rank": 1, "score": 1.0},
    ])
    code, report, err = _score(tmp_path, suite, runs)
    assert code == 0, err
    assert report["topics_evaluated"] == 2
    assert report["recall_at_k"]["50"] == pytest.approx(1 / 3)
    assert report["recall_at_k"]["100"] == pytest.approx(1 / 3)
    assert report["recall_at_k"]["200"] == pytest.approx(1 / 3)
    assert report["mrr"] == pytest.approx(0.5)  # (1 + 0) / 2
    assert report["critical_recall"]["value"] == pytest.approx(1.0)
    assert "pool_biased" in report["critical_recall"]["caveat"]
    assert report["ci"]["degenerate"] is False
    # per-topic slice checks
    per = {row["topic_id"]: row for row in report["per_topic"]}
    assert per["TP-0001"]["recall"]["50"] == pytest.approx(2 / 3)
    assert per["TP-0002"]["recall"]["50"] == 0.0
    assert report["ndcg_at_k"]["100"] > 0


def test_recall_k_cuts_differ(tmp_path: Path) -> None:
    """G1 at rank 60, G2 at rank 150 -> recall@50=0, @100=0.5, @200=1.0."""
    topics = [{
        "topic_id": "TP-0001", "split": "test",
        "gold_families": ["G1", "G2"],
    }]
    suite = _write_suite(tmp_path, topics)
    entries = [
        {"topic_id": "TP-0001", "family_id": f"F{i}", "rank": i, "score": 100.0 - i}
        for i in range(1, 201)
        if i not in (60, 150)
    ]
    entries += [
        {"topic_id": "TP-0001", "family_id": "G1", "rank": 60, "score": 50.0},
        {"topic_id": "TP-0001", "family_id": "G2", "rank": 150, "score": 20.0},
    ]
    runs = _write_runs(tmp_path, "r", entries)
    code, report, err = _score(tmp_path, suite, runs)
    assert code == 0, err
    assert report["recall_at_k"]["50"] == pytest.approx(0.0)
    assert report["recall_at_k"]["100"] == pytest.approx(0.5)
    assert report["recall_at_k"]["200"] == pytest.approx(1.0)


def test_publication_level_runs_collapse_to_family(tmp_path: Path) -> None:
    """Two members of F1 ranked 1 and 2 -> family counted once, best rank kept."""
    topics = [{"topic_id": "TP-0001", "split": "test", "gold_families": ["F1"]}]
    suite = _write_suite(tmp_path, topics, families={
        "EP0001A1": "F1", "EP0002A1": "F1", "EP0003A1": "F2",
    })
    runs = _write_runs(tmp_path, "pub-runs", [
        {"topic_id": "TP-0001", "publication_number": "EP0001A1", "rank": 1},
        {"topic_id": "TP-0001", "publication_number": "EP0002A1", "rank": 2},
        {"topic_id": "TP-0001", "publication_number": "EP0003A1", "rank": 3},
    ])
    code, report, err = _score(tmp_path, suite, runs)
    assert code == 0, err
    per = report["per_topic"][0]
    assert per["ranked_size"] == 2  # F1 collapsed, F2 separate
    assert per["mrr"] == 1.0
    assert per["recall"]["50"] == 1.0


def test_gold_zero_topic_excluded_and_reported(tmp_path: Path) -> None:
    topics = [
        {"topic_id": "TP-0001", "split": "test", "gold_families": ["F1"]},
        {"topic_id": "TP-0002", "split": "test", "gold_families": [], "gold_known_incomplete": True},
    ]
    suite = _write_suite(tmp_path, topics)
    runs = _write_runs(tmp_path, "r", [{"topic_id": "TP-0001", "family_id": "F1", "rank": 1}])
    code, report, err = _score(tmp_path, suite, runs)
    assert code == 0, err
    assert report["topics_gold_zero"] == ["TP-0002"]
    assert report["topics_evaluated"] == 1
    assert report["recall_at_k"]["50"] == pytest.approx(1.0)  # denominator excludes gold-zero topic


def test_empty_qrels_everywhere_is_audit_failure(tmp_path: Path) -> None:
    """空 qrels 不默认为满分: every topic gold-empty -> exit 1, no report."""
    topics = [{"topic_id": "TP-0001", "split": "test", "gold_families": [], "gold_known_incomplete": True}]
    suite = _write_suite(tmp_path, topics)
    runs = _write_runs(tmp_path, "r", [{"topic_id": "TP-0001", "family_id": "F1", "rank": 1}])
    code, report, err = _score(tmp_path, suite, runs)
    assert code == 1
    assert report is None
    assert "empty gold" in err or "nothing to evaluate" in err


def test_manifest_rejects_empty_gold_without_flag(tmp_path: Path) -> None:
    topics = [{"topic_id": "TP-0001", "split": "test", "gold_families": []}]
    suite = _write_suite(tmp_path, topics)
    runs = _write_runs(tmp_path, "r", [])
    code, _, err = _score(tmp_path, suite, runs)
    assert code == 1
    assert "gold_known_incomplete" in err


# ── error injection (UT-M01): sabotaged inputs must move the numbers ──


def _baseline_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    suite = _write_suite(tmp_path, _default_topics())
    runs = _write_runs(tmp_path, "r", [
        {"topic_id": "TP-0001", "family_id": "F2", "rank": 1, "score": 9.0},
        {"topic_id": "TP-0001", "family_id": "F1", "rank": 2, "score": 5.0},
        {"topic_id": "TP-0002", "family_id": "F4", "rank": 1, "score": 3.0},
    ])
    return suite, runs, {"recall": 1.0, "mrr": 1.0}


def test_sabotage_removing_gold_hit_degrades_recall(tmp_path: Path) -> None:
    suite, runs, base = _baseline_fixture(tmp_path)
    (runs / "r.jsonl").write_text("\n".join([
        json.dumps({"topic_id": "TP-0001", "family_id": "F2", "rank": 1}),
        json.dumps({"topic_id": "TP-0002", "family_id": "F4", "rank": 1}),
    ]) + "\n", encoding="utf-8")
    code, report, err = _score(tmp_path, suite, runs)
    assert code == 0, err
    assert report["recall_at_k"]["50"] < base["recall"]  # 0.5 < 1.0


def test_sabotage_flipping_qrels_changes_scores(tmp_path: Path) -> None:
    suite, runs, base = _baseline_fixture(tmp_path)
    manifest_path = suite / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["topics"][0]["gold_families"] = ["F8", "F9"]  # unrelated families
    manifest["qrels_version"] = "qrels-v2-sabotaged"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    code, report, err = _score(tmp_path, suite, runs)
    assert code == 0, err
    # TP-0001 now scores 0; TP-0002 still 1.0 -> macro mean drops to 0.5 (was 1.0)
    assert report["recall_at_k"]["50"] == pytest.approx(0.5)
    assert report["qrels_version"] == "qrels-v2-sabotaged"


def test_sabotage_reordering_runs_changes_mrr(tmp_path: Path) -> None:
    suite, runs, base = _baseline_fixture(tmp_path)
    (runs / "r.jsonl").write_text("\n".join([
        json.dumps({"topic_id": "TP-0001", "family_id": "F9", "rank": 1}),
        json.dumps({"topic_id": "TP-0001", "family_id": "F2", "rank": 2}),
        json.dumps({"topic_id": "TP-0002", "family_id": "F4", "rank": 1}),
    ]) + "\n", encoding="utf-8")
    code, report, err = _score(tmp_path, suite, runs)
    assert code == 0, err
    assert report["mrr"] < base["mrr"]


def test_unknown_topic_id_is_audit_failure(tmp_path: Path) -> None:
    suite = _write_suite(tmp_path, _default_topics())
    runs = _write_runs(tmp_path, "r", [{"topic_id": "TP-9999", "family_id": "F1", "rank": 1}])
    code, _, err = _score(tmp_path, suite, runs)
    assert code == 1
    assert "unknown topic_id" in err


def test_duplicate_rank_conflict_is_audit_failure(tmp_path: Path) -> None:
    suite = _write_suite(tmp_path, _default_topics())
    runs = _write_runs(tmp_path, "r", [
        {"topic_id": "TP-0001", "family_id": "F1", "rank": 1},
        {"topic_id": "TP-0001", "family_id": "F2", "rank": 1},
    ])
    code, _, err = _score(tmp_path, suite, runs)
    assert code == 1
    assert "duplicate rank" in err


def test_unknown_publication_is_audit_failure(tmp_path: Path) -> None:
    suite = _write_suite(
        tmp_path,
        [{"topic_id": "TP-0001", "split": "test", "gold_families": ["F1"]}],
        families={"EP0001A1": "F1"},
    )
    runs = _write_runs(tmp_path, "r", [{"topic_id": "TP-0001", "publication_number": "EPXXXXX", "rank": 1}])
    code, _, err = _score(tmp_path, suite, runs)
    assert code == 1
    assert "not in manifest families" in err


def test_split_filter_selects_topics(tmp_path: Path) -> None:
    topics = [
        {"topic_id": "TP-0001", "split": "train", "gold_families": ["F1"]},
        {"topic_id": "TP-0002", "split": "test", "gold_families": ["F1"]},
    ]
    suite = _write_suite(tmp_path, topics)
    runs = _write_runs(tmp_path, "r", [
        {"topic_id": "TP-0001", "family_id": "F1", "rank": 1},
        {"topic_id": "TP-0002", "family_id": "F1", "rank": 1},
    ])
    code, report, err = _score(tmp_path, suite, runs, "--split", "test")
    assert code == 0, err
    assert report["topics_evaluated"] == 1
    assert report["split"] == "test"


def test_empty_runs_dir_is_audit_failure(tmp_path: Path) -> None:
    suite = _write_suite(tmp_path, _default_topics())
    runs = tmp_path / "runs"
    runs.mkdir()
    code, _, err = _score(tmp_path, suite, runs)
    assert code == 1
    assert "no *.jsonl" in err
