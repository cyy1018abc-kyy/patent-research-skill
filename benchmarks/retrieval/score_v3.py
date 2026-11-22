#!/usr/bin/env python3
"""V3 ladder scoring (4.3 / W3-EVAL) — preregistered in gate-v3.yaml.

Same discipline as score_v2.py: each config's run file is scored by the SAME
scorer (tools/score_retrieval.py) over an isolated suite+runs pair; step deltas
(V3-1−V3-0, V3-2−V3-1) come from the preregistered paired per-topic bootstrap
with the gate's fixed seed (20261121); domain (OUT first-class) and era slices
are always reported; V3-0 is byte-checked against the archived Phase V baseline.
Per-step gates (G4-ruled): V3-1 ≥ +5.0pp, V3-2 ≥ +2.0pp, CI lower > 0.
Negative deltas published as-is. The main Phase V gate stays FAILED — nothing
reopens it.

Usage:
    python benchmarks/retrieval/score_v3.py --mode smoke
    python benchmarks/retrieval/score_v3.py --mode full --bootstrap-n 10000
"""

from __future__ import annotations

import argparse
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

GATE = BASE / "gate-v3.yaml"
PROTOCOL = BASE / "protocol-prereg-v3.md"
MANIFEST = rb.TOPICS_MANIFEST
SCORER = REPO_ROOT / "tools" / "score_retrieval.py"
CONFIGS = ("V3-0", "V3-1", "V3-2")
STEPS = (("V3-1", "V3-0"), ("V3-2", "V3-1"))
BUDGET_PER_TOPIC = {"V3-0": 3, "V3-1": 3, "V3-2": 4}
SNAPSHOT_CORPUS_SHA256 = "469fe8e04d8bd8775a1116eccf0983e570a03444bef9c6e14c97aabafb7526d6"
ARCHIVED_BASELINE = Path("F:/GitHub项目合集/专利调研与润色/patent-research-skill/benchmarks/retrieval/runs/baseline.jsonl")
# OUT reference line (attribution only, not a gate): DAPFAM paper BM25 doc 0.1368 / passage 0.1521
OUT_REFERENCE = {"bm25_doc": 0.1368, "bm25_passage": 0.1521, "dense_passage": 0.1538,
                 "source": "Ayaou et al., 2025 (arXiv:2506.22141); attribution-only per gate"}


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def load_v3_gates() -> dict:
    """Per-step gates from gate-v3.yaml (V3-1: 5.0pp, V3-2: 2.0pp per G4)."""
    text = GATE.read_text(encoding="utf-8")
    gates: dict[str, dict] = {}
    for step in ("V3-1_field_coverage", "V3-2_dense_rrf"):
        block = text.split(step + ":", 1)[1].split("\n  V3-2_dense_rrf:" if step.startswith("V3-1") else "\nclaim_rule:", 1)[0]
        m = re.search(r"min_mean_gain_pp: ([0-9.]+)", block)
        gates[step] = {"min_mean_gain_pp": float(m.group(1)) if m else None}
    m = re.search(r"seed (\d+)", text)
    gates["bootstrap_seed"] = int(m.group(1)) if m else 20261121
    m = re.search(r"subset: first (\d+) test topics", text)
    gates["smoke_topics"] = int(m.group(1)) if m else 24
    return gates


def score_side(config: str) -> dict:
    """tools/score_retrieval.py over one isolated suite+runs pair (glob discipline)."""
    with tempfile.TemporaryDirectory(prefix="v3-suite-") as tmp:
        suite = Path(tmp) / "suite"
        suite.mkdir()
        (suite / "manifest.json").write_bytes(MANIFEST.read_bytes())
        runs = Path(tmp) / "runs"
        runs.mkdir()
        shutil.copy(rb.RUNS_DIR / f"v3-{config}.jsonl", runs / f"v3-{config}.jsonl")
        proc = subprocess.run(
            [sys.executable, str(SCORER), "--suite", str(suite), "--runs", str(runs),
             "--split", "test", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SystemExit(f"[FATAL] score_retrieval {config} failed ({proc.returncode}):\n{proc.stderr[-2000:]}")
    return json.loads(proc.stdout)


def load_run_rows(config: str) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {}
    with open(rb.RUNS_DIR / f"v3-{config}.jsonl", encoding="utf-8") as fh:
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
    """Run-metadata audit (budgets, hashes, dense index provenance for V3-2)."""
    meta = json.loads((rb.RUNS_DIR / f"meta-v3-{config}.json").read_text(encoding="utf-8"))
    audit: dict = {
        "requests_total": meta["requests_total"],
        "topics_run": meta["topics_run"],
        "budget_respected": meta["requests_total"] <= BUDGET_PER_TOPIC[config] * meta["topics_run"],
        "network_requests": meta.get("network_requests"),
        "smoke": meta.get("smoke"),
    }
    audit["gate_yaml_sha256_matches"] = (
        meta.get("gate_v3_yaml_sha256") == rb.sha256_file(GATE)
    )
    audit["protocol_sha256_matches"] = (
        meta.get("protocol_v3_sha256") == rb.sha256_file(PROTOCOL)
    )
    if config == "V3-2":
        channel = meta.get("dense_channel") or {}
        audit["dense_corpus_sha256_matches"] = channel.get("corpus_sha256") == SNAPSHOT_CORPUS_SHA256
        manifest_path = Path(channel.get("index_dir", "")) / f"{channel.get('index_name', '')}.manifest.json"
        audit["dense_manifest_sha256_matches"] = (
            bool(channel.get("index_manifest_sha256"))
            and manifest_path.is_file()
            and rb.sha256_file(manifest_path) == channel["index_manifest_sha256"]
        )
    return audit


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument("--bootstrap-n", type=int, default=10000)
    args = parser.parse_args()

    gates = load_v3_gates()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    topics = {t["topic_id"]: t for t in manifest["topics"] if t.get("split") == "test"}

    for config in CONFIGS:
        if not (rb.RUNS_DIR / f"v3-{config}.jsonl").is_file():
            raise SystemExit(f"[FATAL] missing run file: runs/v3-{config}.jsonl")

    audits = {config: audit_meta(config, mode=args.mode) for config in CONFIGS}
    network_violations = sum(1 for a in audits.values() if a["network_requests"])
    budget_violations = sum(1 for a in audits.values() if not a["budget_respected"])
    hash_violations = sum(
        1 for a in audits.values()
        if not a["gate_yaml_sha256_matches"] or not a["protocol_sha256_matches"]
    ) + sum(1 for a in audits.values()
            if "dense_corpus_sha256_matches" in a and not a["dense_corpus_sha256_matches"]) \
        + sum(1 for a in audits.values()
              if "dense_manifest_sha256_matches" in a and not a["dense_manifest_sha256_matches"])
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

    v30_mean = sum(per_topic["V3-0"].values()) / len(per_topic["V3-0"])
    report: dict = {
        "tool": "patent_intel v3 ladder scoring (4.3 / W3-EVAL, P0-GAP field coverage + dense channel)",
        "mode": args.mode,
        "claims": args.mode == "full",
        "protocol_sha256": rb.sha256_file(PROTOCOL),
        "gate_sha256": rb.sha256_file(GATE),
        "gates": {k: v for k, v in gates.items() if k.startswith("V3-")},
        "bootstrap_seed": gates["bootstrap_seed"],
        "audits": audits,
        "suite_metrics": suite_metrics,
        "v30_mean_recall100": round(v30_mean, 4),
        "out_reference_attribution_only": OUT_REFERENCE,
        "steps": {},
        "smoke_pass_condition": None,
        "elapsed_seconds": None,
    }

    if args.mode == "smoke":
        report["smoke_pass_condition"] = {
            "all_configs_scored": True,
            "v30_recall100_positive": v30_mean > 0,
            "budgets_respected": budget_violations == 0,
            "audit_clean": network_violations == 0 and hash_violations == 0,
            "pass": v30_mean > 0 and budget_violations == 0 and network_violations == 0 and hash_violations == 0,
            "note": "smoke 结果不进任何宣称 (smoke results never enter claims)",
        }
    else:
        reproduction = {"archived_baseline": str(ARCHIVED_BASELINE)}
        if ARCHIVED_BASELINE.is_file():
            reproduction["v30_sha256"] = rb.sha256_file(rb.RUNS_DIR / "v3-V3-0.jsonl")
            reproduction["archived_sha256"] = rb.sha256_file(ARCHIVED_BASELINE)
            reproduction["byte_identical"] = reproduction["v30_sha256"] == reproduction["archived_sha256"]
        else:
            reproduction["byte_identical"] = None
            reproduction["note"] = "archived baseline not found on this machine — reproduction check UNRESOLVED"
        report["reproduction"] = reproduction

        for step_new, step_base in STEPS:
            step_key = f"{step_new}_field_coverage" if step_new == "V3-1" else f"{step_new}_dense_rrf"
            gate_min = gates[step_key]["min_mean_gain_pp"]
            boot = paired_bootstrap(per_topic[step_new], per_topic[step_base],
                                    n=args.bootstrap_n, seed=gates["bootstrap_seed"])
            verdict_gate = (
                boot["mean_gain_pp"] >= (gate_min or 0.0)
                and boot["ci_lower_pp"] > 0.0
            )
            common = sorted(set(per_topic[step_new]) & set(per_topic[step_base]))
            group_vals: dict[str, list[float]] = {}
            era_vals: dict[str, list[float]] = {}
            for tid in common:
                topic = topics.get(tid, {})
                group_vals.setdefault(str(topic.get("domain", "UNKNOWN")), []).append(
                    per_topic[step_new][tid] - per_topic[step_base][tid])
                first_half = topic.get("earliest_claim_date", "") <= (manifest.get("time_split", {}).get("val_last_date") or "")
                era_vals.setdefault("first" if first_half else "second", []).append(
                    per_topic[step_new][tid] - per_topic[step_base][tid])
            group_means = {
                "domain": {k: round(sum(v) / len(v) * 100, 4) for k, v in group_vals.items()},
                "era": {k: round(sum(v) / len(v) * 100, 4) for k, v in era_vals.items()},
            }
            # per-group OUT mean levels (attribution context vs the paper line)
            out_levels = {}
            for cfg in CONFIGS:
                out_scores = [per_topic[cfg][t] for t in per_topic[cfg] if topics.get(t, {}).get("domain") == "OUT"]
                out_levels[cfg] = round(sum(out_scores) / len(out_scores) * 100, 4) if out_scores else None
            report["steps"][f"{step_new}-{step_base}"] = {
                "bootstrap": boot,
                "gate_min_mean_gain_pp": gate_min,
                "claim": verdict_gate,
                "groups_mean_gain_pp": group_means,
                "out_recall100_levels_pp": out_levels,
            }

    out = BASE / "results" / f"v3-ladder-{time.strftime('%Y-%m-%d')}-{args.mode}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"[report] {out}")

    if args.mode == "smoke":
        print(f"[smoke] V3-0 mean recall@100 = {report['v30_mean_recall100']}, "
              f"pass = {report['smoke_pass_condition']['pass']}")
    else:
        for step, data in report["steps"].items():
            b = data["bootstrap"]
            print(f"[step] {step}: mean {b['mean_gain_pp']:+.2f}pp "
                  f"CI [{b['ci_lower_pp']:+.2f}, {b['ci_upper_pp']:+.2f}] "
                  f"gate({data['gate_min_mean_gain_pp']}) claim={data['claim']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
