#!/usr/bin/env python3
"""V2 ladder scoring (4.2 / W4-EVAL) — preregistered in gate-v2.yaml.

Same discipline as score_ablation.py (ABL-1): each config's run file is scored
by the SAME scorer (tools/score_retrieval.py) over an isolated suite+runs pair;
step deltas (V2-1−V2-0, V2-2−V2-1, V2-3−V2-2) come from the preregistered
paired per-topic bootstrap with the gate's fixed seed; domain (OUT first-class)
and era group slices are always reported; V2-0 is byte-checked against the
archived Phase V baseline. Negative deltas published as-is; a step claim
requires mean ≥ 2.0pp AND bootstrap CI lower > 0. Smoke reports carry
"claims": false. The main Phase V gate stays FAILED — nothing reopens it.

Usage:
    python benchmarks/retrieval/score_v2.py --mode smoke
    python benchmarks/retrieval/score_v2.py --mode full --bootstrap-n 10000
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

GATE = BASE / "gate-v2.yaml"
PROTOCOL = BASE / "protocol-prereg-v2.md"
MINING_ARTIFACT = BASE / "topics" / "public" / "cooccurrence.json"
MANIFEST = rb.TOPICS_MANIFEST
SCORER = REPO_ROOT / "tools" / "score_retrieval.py"
CONFIGS = ("V2-0", "V2-1", "V2-2", "V2-3")
STEPS = (("V2-1", "V2-0"), ("V2-2", "V2-1"), ("V2-3", "V2-2"))
BUDGET_PER_TOPIC = {"V2-0": 3, "V2-1": 3, "V2-2": 3, "V2-3": 4}
ARCHIVED_BASELINE = Path("E:/Users/amdir/Desktop/专利调研与润色/patent-research-skill/benchmarks/retrieval/runs/baseline.jsonl")


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def load_v2_gate() -> dict:
    text = GATE.read_text(encoding="utf-8")
    gate: dict = {}
    match = re.search(r"protocol_sha256: \"([0-9a-f]{64})\"", text)
    gate["protocol_sha256"] = match.group(1) if match else ""
    match = re.search(r"min_mean_gain_pp: ([0-9.]+)", text)
    gate["min_mean_gain_pp"] = float(match.group(1)) if match else None
    match = re.search(r"paired_bootstrap_ci_lower_pp: ([0-9.]+)", text)
    gate["ci_lower_pp"] = float(match.group(1)) if match else None
    match = re.search(r"seed (\d+)", text)
    gate["bootstrap_seed"] = int(match.group(1)) if match else 20261107
    match = re.search(r"subset: first (\d+) test topics", text)
    gate["smoke_topics"] = int(match.group(1)) if match else 24
    return gate


def score_side(config: str) -> dict:
    """tools/score_retrieval.py over one isolated suite+runs pair (glob discipline)."""
    with tempfile.TemporaryDirectory(prefix="v2-suite-") as tmp:
        suite = Path(tmp) / "suite"
        suite.mkdir()
        (suite / "manifest.json").write_bytes(MANIFEST.read_bytes())
        runs = Path(tmp) / "runs"
        runs.mkdir()
        shutil.copy(rb.RUNS_DIR / f"v2-{config}.jsonl", runs / f"v2-{config}.jsonl")
        proc = subprocess.run(
            [sys.executable, str(SCORER), "--suite", str(suite), "--runs", str(runs),
             "--split", "test", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SystemExit(f"[FATAL] score_retrieval {config} failed ({proc.returncode}):\n{proc.stderr[-2000:]}")
    return json.loads(proc.stdout)


def load_run_rows(config: str) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {}
    with open(rb.RUNS_DIR / f"v2-{config}.jsonl", encoding="utf-8") as fh:
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


def audit_meta(config: str, *, mode: str) -> dict:
    """Run-metadata audit (budgets, hashes, mining artifact digest for V2-3)."""
    meta = json.loads((rb.RUNS_DIR / f"meta-v2-{config}.json").read_text(encoding="utf-8"))
    audit: dict = {
        "requests_total": meta["requests_total"],
        "topics_run": meta["topics_run"],
        "budget_respected": meta["requests_total"] <= BUDGET_PER_TOPIC[config] * meta["topics_run"],
        "network_requests": meta.get("network_requests"),
        "smoke": meta.get("smoke"),
    }
    audit["gate_yaml_sha256_matches"] = (
        meta.get("gate_v2_yaml_sha256") == rb.sha256_file(GATE)
    )
    audit["protocol_sha256_matches"] = (
        meta.get("protocol_v2_sha256") == rb.sha256_file(PROTOCOL)
    )
    if config == "V2-3":
        if MINING_ARTIFACT.is_file() and meta.get("mining_artifact_sha256"):
            actual = hashlib.sha256(MINING_ARTIFACT.read_bytes()).hexdigest()
            audit["mining_artifact_sha256_matches"] = meta["mining_artifact_sha256"] == actual
        else:
            audit["mining_artifact_sha256_matches"] = False
    return audit


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument("--bootstrap-n", type=int, default=10000)
    args = parser.parse_args()

    gate = load_v2_gate()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    topics = {t["topic_id"]: t for t in manifest["topics"] if t.get("split") == "test"}

    for config in CONFIGS:
        if not (rb.RUNS_DIR / f"v2-{config}.jsonl").is_file():
            raise SystemExit(f"[FATAL] missing run file: runs/v2-{config}.jsonl")

    audits = {config: audit_meta(config, mode=args.mode) for config in CONFIGS}
    network_violations = sum(1 for a in audits.values() if a["network_requests"])
    budget_violations = sum(1 for a in audits.values() if not a["budget_respected"])
    hash_violations = sum(
        1 for a in audits.values()
        if not a["gate_yaml_sha256_matches"] or not a["protocol_sha256_matches"]
    ) + sum(1 for a in audits.values() if "mining_artifact_sha256_matches" in a and not a["mining_artifact_sha256_matches"])
    if network_violations or budget_violations or hash_violations:
        raise SystemExit(
            f"[FATAL] audit gate failed: network={network_violations}, "
            f"budget={budget_violations}, hash={hash_violations} — 本轮评测不通过"
        )
    print(f"[audit] budgets/network/hash all consistent across {len(CONFIGS)} configs")

    per_topic: dict[str, dict[str, float]] = {}
    suite_metrics: dict[str, dict] = {}
    for config in CONFIGS:
        suite_metrics[config] = score_side(config)
        rows = load_run_rows(config)
        per_topic[config] = recall_at_k_per_topic(rows, topics, k=100)
        print(f"[score] {config}: recall@100 over {len(per_topic[config])} gold topics")

    v20_mean = sum(per_topic["V2-0"].values()) / len(per_topic["V2-0"])
    report: dict = {
        "tool": "patent_intel v2 ladder scoring (4.2 / W4-EVAL, 41A-3)",
        "mode": args.mode,
        "claims": args.mode == "full",
        "protocol_sha256": rb.sha256_file(PROTOCOL),
        "gate_sha256": rb.sha256_file(GATE),
        "gate": {"min_mean_gain_pp": gate["min_mean_gain_pp"], "ci_lower_pp": gate["ci_lower_pp"],
                 "bootstrap_seed": gate["bootstrap_seed"]},
        "audits": audits,
        "suite_metrics": suite_metrics,
        "v20_mean_recall100": round(v20_mean, 4),
        "steps": {},
        "smoke_pass_condition": None,
        "elapsed_seconds": None,
    }

    if args.mode == "smoke":
        report["smoke_pass_condition"] = {
            "all_configs_scored": True,
            "v20_recall100_positive": v20_mean > 0,
            "budgets_respected": budget_violations == 0,
            "audit_clean": network_violations == 0 and hash_violations == 0,
            "pass": v20_mean > 0 and budget_violations == 0 and network_violations == 0 and hash_violations == 0,
            "note": "smoke 结果不进任何宣称 (smoke results never enter claims)",
        }
    else:
        reproduction = {"archived_baseline": str(ARCHIVED_BASELINE)}
        if ARCHIVED_BASELINE.is_file():
            reproduction["v20_sha256"] = rb.sha256_file(rb.RUNS_DIR / "v2-V2-0.jsonl")
            reproduction["archived_sha256"] = rb.sha256_file(ARCHIVED_BASELINE)
            reproduction["byte_identical"] = reproduction["v20_sha256"] == reproduction["archived_sha256"]
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
            groups: dict[str, dict[str, list[float]]] = {"domain": {}, "era": {}}
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

    out = BASE / "results" / f"v2-ladder-{time.strftime('%Y-%m-%d')}-{args.mode}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"[report] {out}")

    if args.mode == "smoke":
        print(f"[smoke] V2-0 mean recall@100 = {report['v20_mean_recall100']}, "
              f"pass = {report['smoke_pass_condition']['pass']}")
    else:
        for step, data in report["steps"].items():
            b = data["bootstrap"]
            print(f"[step] {step}: Δ={b['mean_gain_pp']:+.2f}pp CI=[{b['ci_lower_pp']:+.2f}, "
                  f"{b['ci_upper_pp']:+.2f}] claim={'YES' if data['claim'] else 'no'}")
        if report.get("reproduction"):
            print(f"[repro] V2-0 byte-identical to archived baseline: "
                  f"{report['reproduction'].get('byte_identical')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
