#!/usr/bin/env python3
"""Ablation scoring (Phase L3 / ABL-1) — preregistered in gate-ablation.yaml.

Scores each config's run file with the SAME scorer (tools/score_retrieval.py) and
the committed suite manifest, then computes the preregistered paired per-topic
step deltas (A1−A0, A2−A1, A3−A2) with the gate's fixed seed, the domain/era
group slices, and the A0 byte-reproduction verdict against the archived Phase V
baseline. Emits ONE report JSON into results/ (ablation-<date>.json).

Discipline (protocol §4/§5): every step delta is published as-is (negative
included); a step claim requires mean ≥ 2.0pp AND bootstrap CI lower > 0; the
Phase V overall gate stays FAILED — nothing here reopens it. Smoke reports carry
"claims": false.

Usage:
    python benchmarks/retrieval/score_ablation.py --mode smoke
    python benchmarks/retrieval/score_ablation.py --mode full --bootstrap-n 10000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))
import run_benchmark as rb  # noqa: E402  (RUNS_DIR, TOPICS_MANIFEST, sha256_file)

GATE = BASE / "gate-ablation.yaml"
PROTOCOL = BASE / "protocol-prereg-ablation.md"
MANIFEST = rb.TOPICS_MANIFEST
SCORER = REPO_ROOT / "tools" / "score_retrieval.py"
CONFIGS = ("A0", "A1", "A2", "A3")
STEPS = (("A1", "A0"), ("A2", "A1"), ("A3", "A2"))
ARCHIVED_BASELINE = Path("E:/Users/amdir/Desktop/专利调研与润色/patent-research-skill/benchmarks/retrieval/runs/baseline.jsonl")


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def load_ablation_gate() -> dict:
    text = GATE.read_text(encoding="utf-8")
    gate: dict = {}
    match = re.search(r"protocol_sha256: \"([0-9a-f]{64})\"", text)
    gate["protocol_sha256"] = match.group(1) if match else ""
    match = re.search(r"min_mean_gain_pp: ([0-9.]+)", text)
    gate["min_mean_gain_pp"] = float(match.group(1)) if match else None
    match = re.search(r"paired_bootstrap_ci_lower_pp: ([0-9.]+)", text)
    gate["ci_lower_pp"] = float(match.group(1)) if match else None
    match = re.search(r"seed (\d+)", text)
    gate["bootstrap_seed"] = int(match.group(1)) if match else 20261101
    match = re.search(r"subset: first (\d+) test topics", text)
    gate["smoke_topics"] = int(match.group(1)) if match else 24
    return gate


def score_side(config: str) -> dict:
    """tools/score_retrieval.py over one isolated suite+runs pair (glob discipline)."""
    with tempfile.TemporaryDirectory(prefix="ablation-suite-") as tmp:
        suite = Path(tmp) / "suite"
        suite.mkdir()
        (suite / "manifest.json").write_bytes(MANIFEST.read_bytes())
        runs = Path(tmp) / "runs"
        runs.mkdir()
        shutil.copy(rb.RUNS_DIR / f"ablation-{config}.jsonl", runs / f"ablation-{config}.jsonl")
        proc = subprocess.run(
            [sys.executable, str(SCORER), "--suite", str(suite), "--runs", str(runs),
             "--split", "test", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SystemExit(f"[FATAL] score_retrieval {config} failed ({proc.returncode}):\n{proc.stderr[-2000:]}")
    return json.loads(proc.stdout)


def load_run_rows(config: str) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {}
    with open(rb.RUNS_DIR / f"ablation-{config}.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            rows.setdefault(row["topic_id"], []).append(row)
    return rows


def recall_at_k_per_topic(rows_by_topic: dict[str, list[dict]], topics: dict[str, dict], k: int = 100) -> dict[str, float]:
    out: dict[str, float] = {}
    for tid, entries in rows_by_topic.items():
        gold = set(topics[tid]["gold_families"])
        if not gold:
            continue  # gold-empty excluded from the denominator (protocol/prereg)
        seen = [e["family_id"] for e in entries if e["rank"] <= k]
        out[tid] = len(set(seen) & gold) / len(gold)
    return out


def paired_bootstrap(per_topic_a: dict[str, float], per_topic_b: dict[str, float],
                     *, n: int, seed: int) -> dict:
    topics = sorted(set(per_topic_a) & set(per_topic_b))
    diffs = [per_topic_a[t] - per_topic_b[t] for t in topics]
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        sample = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        means.append(sum(sample) / len(sample))
    means.sort()
    mean = sum(diffs) / len(diffs)
    return {"topics": len(topics), "mean_gain_pp": round(mean * 100, 4),
            "ci_lower_pp": round(means[int(0.025 * n)] * 100, 4),
            "ci_upper_pp": round(means[min(n - 1, int(0.975 * n))] * 100, 4),
            "seed": seed, "n": n}


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument("--bootstrap-n", type=int, default=10000)
    args = parser.parse_args()

    gate = load_ablation_gate()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    topics = {t["topic_id"]: t for t in manifest["topics"] if t.get("split") == "test"}

    for config in CONFIGS:
        if not (rb.RUNS_DIR / f"ablation-{config}.jsonl").is_file():
            raise SystemExit(f"[FATAL] missing run file: runs/ablation-{config}.jsonl")

    per_topic: dict[str, dict[str, float]] = {}
    suite_metrics: dict[str, dict] = {}
    for config in CONFIGS:
        suite_metrics[config] = score_side(config)
        rows = load_run_rows(config)
        per_topic[config] = recall_at_k_per_topic(rows, topics, k=100)
        print(f"[score] {config}: recall@100 over {len(per_topic[config])} gold topics")

    a0_mean = sum(per_topic["A0"].values()) / len(per_topic["A0"])
    report: dict = {
        "tool": "patent_intel ablation scoring (ABL-1)",
        "mode": args.mode,
        "claims": args.mode == "full",
        "protocol_sha256": rb.sha256_file(PROTOCOL),
        "gate_sha256": rb.sha256_file(GATE),
        "gate": {"min_mean_gain_pp": gate["min_mean_gain_pp"], "ci_lower_pp": gate["ci_lower_pp"],
                 "bootstrap_seed": gate["bootstrap_seed"]},
        "suite_metrics": suite_metrics,
        "a0_mean_recall100": round(a0_mean, 4),
        "steps": {},
        "smoke_pass_condition": None,
        "elapsed_seconds": None,
    }

    if args.mode == "smoke":
        budgets_ok = all(
            json.loads((rb.RUNS_DIR / f"meta-ablation-{c}.json").read_text(encoding="utf-8"))["requests_total"]
            <= 3 * json.loads((rb.RUNS_DIR / f"meta-ablation-{c}.json").read_text(encoding="utf-8"))["topics_run"]
            for c in CONFIGS
        )
        report["smoke_pass_condition"] = {
            "all_configs_scored": True,
            "a0_recall100_positive": a0_mean > 0,
            "budgets_respected": budgets_ok,
            "pass": a0_mean > 0 and budgets_ok,
            "note": "smoke 结果不进任何宣称 (smoke results never enter claims)",
        }
    else:
        reproduction = {"archived_baseline": str(ARCHIVED_BASELINE)}
        if ARCHIVED_BASELINE.is_file():
            reproduction["a0_sha256"] = rb.sha256_file(rb.RUNS_DIR / "ablation-A0.jsonl")
            reproduction["archived_sha256"] = rb.sha256_file(ARCHIVED_BASELINE)
            reproduction["byte_identical"] = reproduction["a0_sha256"] == reproduction["archived_sha256"]
        else:
            reproduction["byte_identical"] = None
            reproduction["note"] = "archived baseline not found on this machine — reproduction check UNRESOLVED"
        report["reproduction"] = reproduction

        for step_new, step_base in STEPS:
            boot = paired_bootstrap(per_topic[step_new], per_topic[step_base],
                                    n=args.bootstrap_n, seed=gate["bootstrap_seed"])
            verdict_gate = (
                boot["mean_gain_pp"] >= (gate["min_mean_gain_pp"] or 0.0)
                and boot["ci_lower_pp"] > (gate["ci_lower_pp"] or 0.0)
            )
            # group slices: mean per-topic delta within each preregistered group
            groups: dict[str, dict[str, float]] = {"domain": {}, "era": {}}
            common = sorted(set(per_topic[step_new]) & set(per_topic[step_base]))
            for tid in common:
                topic = topics.get(tid, {})
                groups["domain"].setdefault(str(topic.get("domain", "UNKNOWN")), []).append(
                    per_topic[step_new][tid] - per_topic[step_base][tid])
                first_half = topic.get("earliest_claim_date", "") <= (manifest.get("time_split", {}).get("val_last_date") or "")
                groups["era"].setdefault("first" if first_half else "second", []).append(
                    per_topic[step_new][tid] - per_topic[step_base][tid])
            group_means = {
                name: {key: round(sum(v) / len(v) * 100, 4) for key, v in slices.items()}
                for name, slices in groups.items()
            }
            report["steps"][f"{step_new}-{step_base}"] = {
                "bootstrap": boot,
                "gate_min_mean_gain_pp": gate["min_mean_gain_pp"],
                "gate_ci_lower_pp": gate["ci_lower_pp"],
                "claim": verdict_gate,
                "groups_mean_gain_pp": group_means,
            }

    out = BASE / "results" / f"ablation-{time.strftime('%Y-%m-%d')}-{args.mode}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"[report] {out}")

    if args.mode == "smoke":
        print(f"[smoke] A0 mean recall@100 = {report['a0_mean_recall100']}, "
              f"pass = {report['smoke_pass_condition']['pass']}")
    else:
        for step, data in report["steps"].items():
            b = data["bootstrap"]
            print(f"[step] {step}: Δ={b['mean_gain_pp']:+.2f}pp CI=[{b['ci_lower_pp']:+.2f}, "
                  f"{b['ci_upper_pp']:+.2f}] claim={'YES' if data['claim'] else 'no'}")
        if report.get("reproduction"):
            print(f"[repro] A0 byte-identical to archived baseline: "
                  f"{report['reproduction'].get('byte_identical')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
