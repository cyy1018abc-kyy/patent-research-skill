#!/usr/bin/env python3
"""Phase V scoring pipeline (V3-3/V3-5): score both sides, group report, gate verdict.

Reads the preregistered gate (benchmarks/retrieval/gate.yaml), runs
tools/score_retrieval.py on each side's run file against the committed suite
manifest, computes the preregistered comparison (Family Recall@100 mean gain +
per-topic paired bootstrap), the group slices (domain / era), and the Audit
Integrity indicators. Emits ONE report JSON into benchmarks/retrieval/results/
(single source for README/CHANGELOG fragments — V3-4 wording machinery reads it).

The bootstrap here is the PAIRED per-topic difference (extension - baseline) with
the gate's fixed seed — score_retrieval's own CI is per-suite, not paired, so the
gate comparison lives in this pipeline and quotes the same seeds/preregistration.

Usage:
    python benchmarks/retrieval/score_phase_v.py --splits test --bootstrap-n 10000
    python benchmarks/retrieval/score_phase_v.py --limit-topics 3   # smoke against run smoke files
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))

MANIFEST = BASE / "topics" / "public" / "manifest.json"
GATE = BASE / "gate.yaml"
RUNS_DIR = BASE / "runs"
RESULTS_DIR = BASE / "results"
SCORER = REPO_ROOT / "tools" / "score_retrieval.py"


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def load_gate() -> dict:
    """Minimal flat-parse of gate.yaml (no pyyaml dependency here; the file is
    written by us and validated by tests)."""
    text = GATE.read_text(encoding="utf-8")
    gate: dict = {}
    for line in text.splitlines():
        line = line.split("  #", 1)[0].strip()
        for key in ("primary_metric:", "min_mean_gain_pp:", "paired_bootstrap_ci_lower_pp:",
                    "candidate_k_per_request:", "baseline_requests_per_topic:",
                    "extension_requests_per_topic_max:", "test_topics_min:"):
            if line.startswith(key):
                gate[key.rstrip(":")] = line.split(":", 1)[1].strip().strip('"')
    gate["protocol_sha256"] = ""
    match = __import__("re").search(r'protocol_sha256: "([0-9a-f]{64})"', text)
    if match:
        gate["protocol_sha256"] = match.group(1)
    return gate


def score_side(side: str) -> dict:
    import shutil
    import tempfile
    # score_retrieval expects one suite dir (manifest.json at root) and one runs dir
    # (it globs every *.jsonl) — isolate each side into its own temp pair.
    with tempfile.TemporaryDirectory(prefix="phase-v-suite-") as tmp:
        suite = Path(tmp) / "suite"
        suite.mkdir()
        (suite / "manifest.json").write_bytes(MANIFEST.read_bytes())
        runs = Path(tmp) / "runs"
        runs.mkdir()
        shutil.copy(RUNS_DIR / f"{side}.jsonl", runs / f"{side}.jsonl")
        proc = subprocess.run(
            [sys.executable, str(SCORER), "--suite", str(suite), "--runs", str(runs),
             "--split", "test", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SystemExit(f"[FATAL] score_retrieval {side} failed ({proc.returncode}):\n{proc.stderr[-2000:]}")
    return json.loads(proc.stdout)


def recall_at_100_per_topic(side_rows: dict[str, list[dict]], topics: dict[str, dict]) -> dict[str, float]:
    """Family Recall@100 per topic from the run file (family ids are already family-level)."""
    out: dict[str, float] = {}
    for tid, entries in side_rows.items():
        gold = set(topics[tid]["gold_families"])
        if not gold:
            continue  # gold-empty excluded from denominator (gate/protocol)
        seen = [e["family_id"] for e in entries if e["rank"] <= 100]
        out[tid] = len(set(seen) & gold) / len(gold)
    return out


def paired_bootstrap(per_topic_base: dict[str, float], per_topic_ext: dict[str, float],
                     *, n: int, seed: int) -> dict:
    topics = sorted(set(per_topic_base) & set(per_topic_ext))
    diffs = [per_topic_ext[t] - per_topic_base[t] for t in topics]
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        sample = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo = means[int(0.025 * n)]
    hi = means[min(n - 1, int(0.975 * n))]
    mean = sum(diffs) / len(diffs)
    return {"topics": len(topics), "mean_gain_pp": round(mean * 100, 4),
            "ci_lower_pp": round(lo * 100, 4), "ci_upper_pp": round(hi * 100, 4),
            "seed": seed, "n": n}


def load_run_rows(side: str, limit: int = 0) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {}
    with open(RUNS_DIR / f"{side}.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            rows.setdefault(row["topic_id"], []).append(row)
    if limit:
        rows = {tid: entries for i, (tid, entries) in enumerate(sorted(rows.items())) if i < limit}
    return rows


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bootstrap-n", type=int, default=10000)
    parser.add_argument("--limit-topics", type=int, default=0, help="冒烟：只对前 N 个主题评（不产出正式报告）")
    args = parser.parse_args()

    gate = load_gate()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    topics = {t["topic_id"]: t for t in manifest["topics"] if t["split"] == "test"}
    if args.limit_topics:
        keep = set(sorted(topics)[: args.limit_topics])
        topics = {tid: t for tid, t in topics.items() if tid in keep}

    print(f"[gate] primary={gate.get('primary_metric')} min_gain={gate.get('min_mean_gain_pp')}pp "
          f"ci_lower={gate.get('paired_bootstrap_ci_lower_pp')}pp protocol={gate.get('protocol_sha256')[:12]}…")
    print("[score] scoring baseline…")
    report_base = score_side("baseline")
    print("[score] scoring extension…")
    report_ext = score_side("extension")

    rows_base = load_run_rows("baseline", args.limit_topics)
    rows_ext = load_run_rows("extension", args.limit_topics)
    r100_base = recall_at_100_per_topic(rows_base, topics)
    r100_ext = recall_at_100_per_topic(rows_ext, topics)
    common = sorted(set(r100_base) & set(r100_ext))
    if len(common) != len(r100_base) or len(common) != len(r100_ext):
        raise SystemExit("[FATAL] 两侧主题集合不一致——运行产物损坏")

    paired = paired_bootstrap({t: r100_base[t] for t in common}, {t: r100_ext[t] for t in common},
                              n=args.bootstrap_n, seed=20261030)

    # group slices (preregistered: domain / era); bucket n published alongside the
    # mean — a 0.0 mean over a small bucket (e.g. 6 pure-OUT topics) must be
    # readable as such, never as a large-sample finding
    def slice_mean(per_topic: dict[str, float], key) -> dict[str, dict]:
        buckets: dict[str, list[float]] = {}
        for tid, val in per_topic.items():
            buckets.setdefault(key(topics[tid]), []).append(val)
        return {k: {"mean_pp": round(sum(v) / len(v) * 100, 2), "n": len(v)}
                for k, v in sorted(buckets.items())}

    def era(topic: dict) -> str:
        boundary = manifest["time_split"].get("test_first_date", "")[:10]
        return "era1_early" if (topic.get("time_split_key") or "")[:10] < "2012-01-01" else "era2_late"

    groups = {
        "domain": {
            "baseline": slice_mean(r100_base, lambda t: t.get("domain", "UNKNOWN")),
            "extension": slice_mean(r100_ext, lambda t: t.get("domain", "UNKNOWN")),
        },
        "era": {
            "baseline": slice_mean(r100_base, era),
            "extension": slice_mean(r100_ext, era),
        },
    }

    meta_base = json.loads((RUNS_DIR / "meta-baseline.json").read_text(encoding="utf-8"))
    meta_ext = json.loads((RUNS_DIR / "meta-extension.json").read_text(encoding="utf-8"))
    mean_gain = paired["mean_gain_pp"]
    ci_ok = paired["ci_lower_pp"] > float(gate["paired_bootstrap_ci_lower_pp"])
    gain_ok = mean_gain >= float(gate["min_mean_gain_pp"])
    verdict = "PASS" if (gain_ok and ci_ok) else "FAIL"
    claim = ("provisional-public-only" if verdict == "PASS" else "experimental")
    # gate claim_rule: private topics (20-40, EX-01) are a prerequisite for the final
    # "improvement" claim — a public-only pass is provisional by definition.

    report = {
        "tool": "score_phase_v",
        "suite": manifest["suite"],
        "qrels_version": manifest["qrels_version"],
        "protocol_sha256": gate["protocol_sha256"],
        "gate_yaml_sha256": sha256_file(GATE),
        "manifest_sha256": sha256_file(MANIFEST),
        "snapshot_sha256": manifest["source_snapshot"],
        "topics_evaluated": len(common),
        "primary_metric": "family_recall_at_100",
        "baseline_recall100_pp": round(sum(r100_base.values()) / len(r100_base) * 100, 2),
        "extension_recall100_pp": round(sum(r100_ext.values()) / len(r100_ext) * 100, 2),
        "paired_bootstrap": paired,
        "groups": groups,
        "budget": {
            "baseline_requests_total": meta_base["requests_total"],
            "extension_requests_total": meta_ext["requests_total"],
            "k_per_request": 200,
            "network_requests": meta_base.get("network_requests", 0) + meta_ext.get("network_requests", 0),
        },
        "audit_integrity": {
            "unauthorized_network_requests": meta_base.get("network_requests", 0) + meta_ext.get("network_requests", 0),
            "artifact_hashes_recorded": bool(meta_base.get("snapshot_sha256") and meta_ext.get("snapshot_sha256")),
        },
        "gate_verdict": verdict,
        "gate_detail": {"gain_ok": gain_ok, "ci_ok": ci_ok,
                        "min_mean_gain_pp": float(gate["min_mean_gain_pp"])},
        "claim": claim,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }
    if args.limit_topics:
        print(f"[SMOKE] paired={paired} verdict={verdict}")
        return 0
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{time.strftime('%Y-%m-%d')}-phase-v.json"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"[report] {out}")
    print(f"[verdict] {verdict} — gain={mean_gain}pp ci=[{paired['ci_lower_pp']}, {paired['ci_upper_pp']}]pp "
          f"baseline={report['baseline_recall100_pp']}pp extension={report['extension_recall100_pp']}pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
