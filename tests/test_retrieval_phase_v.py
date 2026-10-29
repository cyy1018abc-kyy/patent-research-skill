"""Phase V benchmark infrastructure tests (V1-5/V3-1): leakage checker integrity,
gate preregistration consistency, deterministic merge rule — all synthetic/offline."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "benchmarks" / "retrieval" / "check_leakage.py"
MANIFEST = REPO_ROOT / "benchmarks" / "retrieval" / "topics" / "public" / "manifest.json"
GATE = REPO_ROOT / "benchmarks" / "retrieval" / "gate.yaml"
PROTOCOL = REPO_ROOT / "docs" / "retrieval-evaluation.md"
RUNNER = REPO_ROOT / "benchmarks" / "retrieval" / "run_benchmark.py"

sys.path.insert(0, str(REPO_ROOT / "benchmarks" / "retrieval"))
from check_leakage import leakage_report, violations  # noqa: E402
from run_benchmark import BUDGET_REQUESTS, ENGINE_PARAMS, merge_rankings  # noqa: E402


def _run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CHECKER), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=120, check=False)


def test_committed_manifest_passes_leakage_check() -> None:
    assert MANIFEST.is_file(), "public topic manifest must be committed"
    proc = _run_checker("--manifest", str(MANIFEST))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0 命中" in proc.stdout


def test_injections_are_detected() -> None:
    for kind in ("family", "time", "empty_gold"):
        proc = _run_checker("--manifest", str(MANIFEST), "--inject", kind)
        assert proc.returncode == 0, f"{kind} 注入未被检出：{proc.stdout}{proc.stderr}"
        assert "检查器有效" in proc.stdout


def test_violations_function_catches_synthetic_cases() -> None:
    base_topic = {"topic_id": "TP-0001", "split": "train", "language": "en",
                  "source_id": "FAM-1", "gold_families": ["G-1"]}
    manifest = {"topics": [dict(base_topic)], "time_split": {"key": "time_split_key"}}
    assert violations(manifest) == []
    dup = dict(base_topic, topic_id="TP-0002", split="test")
    assert any("跨 split 重复" in p for p in violations({"topics": [base_topic, dup]}))
    empty = dict(base_topic, topic_id="TP-0003", split="val", gold_families=[])
    assert any("gold_known_incomplete" in p for p in violations({"topics": [empty]}))
    bad_id = dict(base_topic, topic_id="TP-99999")
    assert any("TP-####" in p for p in violations({"topics": [bad_id]}))


def test_leakage_report_counters() -> None:
    topics = [
        {"topic_id": "TP-0001", "split": "train", "source_id": "QF-1", "gold_families": ["G-1", "G-2"]},
        {"topic_id": "TP-0002", "split": "test", "source_id": "QF-2", "gold_families": ["G-1"]},
    ]
    report = leakage_report({"topics": topics})
    assert report["gold_families_total"] == 2
    assert report["gold_families_in_multiple_splits"] == 1  # G-1 shared (fixed-corpus, report-only)
    assert report["query_families_also_gold"] == 0


def test_gate_yaml_is_preregistered_and_consistent() -> None:
    text = GATE.read_text(encoding="utf-8")
    match = re.search(r'protocol_sha256: "([0-9a-f]{64})"', text)
    assert match, "gate.yaml must carry the protocol hash"
    actual = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    assert match.group(1) == actual, "protocol hash drifted — re-register before any new run"
    assert "PENDING" not in text
    assert 'test_topics_min: 100' in text
    assert 'network_requests: 0' in text or "unauthorized_network_requests: 0" in text


def test_committed_manifest_satisfies_gate_minimums() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    test_topics = [t for t in manifest["topics"] if t["split"] == "test"]
    assert len(test_topics) >= 100, "gate requires >=100 reproducible public test topics"
    assert manifest["gold_completeness"] == "pool_biased"
    assert manifest.get("source_snapshot"), "frozen snapshot hashes must be recorded"
    assert manifest["time_split"]["rule"]


def test_runner_budget_matches_gate() -> None:
    gate_text = GATE.read_text(encoding="utf-8")
    assert f"candidate_k_per_request: {ENGINE_PARAMS['k_per_request']}" in gate_text
    assert "extension_requests_per_topic_max: 3" in gate_text
    assert BUDGET_REQUESTS == 3
    assert ENGINE_PARAMS == {"k1": 1.5, "b": 0.75, "k_per_request": 200}


def test_merge_rankings_max_score_tie_by_family() -> None:
    a = {"F-2": 1.0, "F-1": 1.0}  # tie -> family_id ascending
    b = {"F-3": 2.0, "F-2": 0.5}  # per-doc max across requests
    ranked = merge_rankings([a, b], k=2)
    assert ranked == [("F-3", 2.0), ("F-1", 1.0)]
