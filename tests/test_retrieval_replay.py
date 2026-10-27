"""T-04: retrieval replay — the fixture suite scores deterministically and the
offline recall pipeline replays identically (no network, fixed seeds)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORER = REPO_ROOT / "tools" / "score_retrieval.py"
SMOKE_SUITE = REPO_ROOT / "benchmarks" / "retrieval" / "fixtures" / "smoke"
GOLD = REPO_ROOT / "benchmarks" / "cases" / "bm01-timesync" / "gold"


def _score(tmp: Path, *extra: str) -> tuple[int, str]:
    runs = tmp / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    shutil.copy(SMOKE_SUITE / "runs" / "baseline.jsonl", runs / "baseline.jsonl")
    proc = subprocess.run(
        [sys.executable, str(SCORER), "--suite", str(SMOKE_SUITE), "--runs", str(runs), "--json", *extra],
        capture_output=True, text=True, encoding="utf-8", timeout=300, check=False,
    )
    return proc.returncode, proc.stdout


def test_smoke_suite_scores_expected_values(tmp_path: Path) -> None:
    """TP-0001: F1 (via 2 pub members, best rank 1) + F2 (rank 4) → recall 1.0;
    TP-0002: F3 rank 1 → 1.0. Critical (F1) = 1.0. MRR = (1 + 1)/2 = 1.0."""
    code, out = _score(tmp_path)
    assert code == 0, out
    import json

    report = json.loads(out)
    assert report["recall_at_k"]["50"] == 1.0
    assert report["mrr"] == 1.0
    assert report["critical_recall"]["value"] == 1.0
    # same-family collapse: TP-0001 ranked_size == 3 (F1 collapsed from 2 pubs)
    per = {row["topic_id"]: row for row in report["per_topic"]}
    assert per["TP-0001"]["ranked_size"] == 3


def test_smoke_replay_is_byte_stable_across_seeds(tmp_path: Path) -> None:
    """同套件+同 run+同种子 → 同一报告（回放稳定性）。"""
    _, out_a = _score(tmp_path / "a", "--seed", "42")
    _, out_b = _score(tmp_path / "b", "--seed", "42")
    assert out_a == out_b
    _, out_c = _score(tmp_path / "c", "--seed", "7")
    assert out_c == out_a  # recall deterministic; CI is degenerate-proof here (2 topics, stable)


def test_offline_recall_replay_over_gold_workspace(tmp_path: Path) -> None:
    """A-06 replay: the offline recall pipeline over the gold workspace is
    deterministic and touches no network."""
    import socket

    ws = tmp_path / "ws"
    shutil.copytree(GOLD, ws)

    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during offline replay")

    orig_connect = socket.socket.connect
    orig_create = socket.create_connection
    socket.socket.connect = blocked  # type: ignore[method-assign]
    socket.create_connection = blocked  # type: ignore[assignment]
    try:
        from patent_intel.cli import main

        code_a = main(["recall", "report", "--root", str(ws), "--json", "--state-dir", str(tmp_path / "sd-a")])
        report_a = (tmp_path / "sd-a" / "reports").glob("recall_*.json")
        first = sorted(report_a)[0].read_text(encoding="utf-8")
        code_b = main(["recall", "report", "--root", str(ws), "--json", "--state-dir", str(tmp_path / "sd-b")])
        second = sorted((tmp_path / "sd-b" / "reports").glob("recall_*.json"))[0].read_text(encoding="utf-8")
    finally:
        socket.socket.connect = orig_connect  # type: ignore[method-assign]
        socket.create_connection = orig_create  # type: ignore[assignment]
    assert code_a == 0 and code_b == 0
    # reports differ only in their timestamped filename/elapsed fields; normalize
    import json
    import re

    def norm(text: str) -> str:
        text = re.sub(r"recall_\d{8}_\d{6}", "recall", text)
        text = re.sub(r'"elapsed_sec": [0-9.]+', '"elapsed_sec": <e>', text)
        return text

    assert norm(first) == norm(second)
    payload = json.loads(first)
    assert payload["corpus_size"] == 4
