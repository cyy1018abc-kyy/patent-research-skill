#!/usr/bin/env python3
"""Retrieval benchmark scorer — family Recall@K, nDCG, MRR, critical recall, CI, audit.

Usage
-----
    python tools/score_retrieval.py --suite benchmarks/retrieval --runs <run-dir> --json
    python tools/score_retrieval.py --suite benchmarks/retrieval --runs <run-dir> --split test

Inputs
------
``--suite``   directory holding ``manifest.json`` (validated against
              ``benchmarks/retrieval/manifest.schema.json``).
``--runs``    directory of ``*.jsonl`` run files. One JSON object per line:
              ``{"topic_id": "TP-0001", "family_id": "FAM-1", "rank": 1,
                 "score": 12.5, "query_id": "Q-1", "source": "bm25"}``
              Publication-level runs use ``"publication_number"`` and are mapped
              through the manifest's ``families`` table (duplicate family members
              collapse to the best rank — a family is never double-counted).

Contract (blueprint T-02/T-03, §12)
-----------------------------------
* empty gold set on a topic → that topic is excluded from the recall denominator and
  reported under ``topics_gold_zero`` — never silently scored as perfect;
* an entirely empty qrels (no topic has gold) → exit 1, no report;
* unknown topic_id in a run file, duplicate (topic, rank), or non-positive ranks are
  audit-integrity failures → exit 1;
* metrics are computed once, in ``patent_intel.retrieval.metrics``; hand-written
  reports have no place in this pipeline;
* bootstrap CI is per-topic with a fixed seed; fewer than 2 topics ⇒ degenerate CI
  (point estimate echoed, flag set) so small suites cannot fake statistical claims.

Exit codes: 0 scored | 1 audit/contract failure | 2 usage/IO | 3 patent_intel missing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

EXIT_OK = 0
EXIT_AUDIT = 1
EXIT_USAGE = 2
EXIT_DEPENDENCY = 3

RECALL_KS = (50, 100, 200)
NDCG_K = 100


def _require_patent_intel() -> None:
    try:
        import patent_intel  # noqa: F401
    except ImportError:
        print(
            "[FATAL] tools/score_retrieval.py requires the patent_intel extension "
            "(metrics implementation lives there).\n"
            "        Install: pip install -e extensions/patent_intel --no-deps",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_DEPENDENCY) from None


def load_manifest(suite_dir: Path) -> dict[str, Any]:
    """Load and schema-validate manifest.json (stdlib validator: the schema subset we use)."""
    path = suite_dir / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"no manifest.json under {suite_dir}")
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate_manifest(data, path)
    return data


def _validate_manifest(data: Any, path: Path) -> None:
    """Minimal validator for the declared schema subset (keeps CI free of jsonschema).

    Anything ambiguous is a hard error — a malformed manifest must never produce a
    plausible-looking report.
    """
    err_prefix = f"{path}: "
    if not isinstance(data, dict):
        raise ValueError(err_prefix + "manifest must be an object")
    for key in ("suite", "version", "qrels_version", "gold_completeness", "topics"):
        if key not in data:
            raise ValueError(err_prefix + f"missing required key {key!r}")
    if data["gold_completeness"] not in ("complete", "pool_biased", "unknown"):
        raise ValueError(err_prefix + "gold_completeness must be complete|pool_biased|unknown")
    known_keys = {
        "suite", "version", "qrels_version", "gold_completeness", "license",
        "provenance", "families", "topics",
        # Phase V optional provenance keys (kept in lockstep with manifest.schema.json)
        "source_snapshot", "time_split", "leakage_report",
    }
    unknown = set(data) - known_keys
    if unknown:
        raise ValueError(err_prefix + f"unknown top-level keys: {sorted(unknown)}")
    families = data.get("families") or {}
    if not isinstance(families, dict) or not all(isinstance(v, str) and v for v in families.values()):
        raise ValueError(err_prefix + "'families' must map publication numbers to family IDs")
    if not isinstance(data["topics"], list) or not data["topics"]:
        raise ValueError(err_prefix + "'topics' must be a non-empty array")
    seen: set[str] = set()
    for topic in data["topics"]:
        if not isinstance(topic, dict) or "topic_id" not in topic or "split" not in topic:
            raise ValueError(err_prefix + "each topic needs topic_id and split")
        tid = topic["topic_id"]
        if not (isinstance(tid, str) and re.fullmatch(r"TP-[0-9]{4}", tid)):
            raise ValueError(err_prefix + f"bad topic_id {tid!r} (expected TP-NNNN)")
        if tid in seen:
            raise ValueError(err_prefix + f"duplicate topic_id {tid}")
        seen.add(tid)
        if topic["split"] not in ("train", "val", "test"):
            raise ValueError(err_prefix + f"topic {tid}: split must be train|val|test")
        topic_keys = {
            "topic_id", "split", "language", "domain", "in_domain_of_engine",
            "gold_families", "critical_families", "relevance_levels",
            "gold_known_incomplete", "adjudication", "license_note", "time_split_key",
            # Phase V optional provenance key (joins the topic to its local-only source row)
            "source_id",
        }
        t_unknown = set(topic) - topic_keys
        if t_unknown:
            raise ValueError(err_prefix + f"topic {tid}: unknown keys {sorted(t_unknown)}")
        for list_key in ("gold_families", "critical_families"):
            value = topic.get(list_key, [])
            if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
                raise ValueError(err_prefix + f"topic {tid}: {list_key} must be a list of non-empty strings")
        gold = topic.get("gold_families", [])
        if not gold and not topic.get("gold_known_incomplete", False):
            raise ValueError(
                err_prefix + f"topic {tid}: empty gold_families requires gold_known_incomplete=true "
                "(an empty gold must never default to a perfect score)"
            )


def load_runs(runs_dir: Path, manifest: dict[str, Any]) -> dict[str, list[tuple[int, str, dict[str, Any]]]]:
    """Parse run files into ``topic_id -> [(rank, family_id, entry)]`` sorted by rank.

    Publication-level entries are mapped via manifest['families']; several members of
    one family collapse to the family's best rank (duplicate families never inflate
    recall).
    """
    topics = {t["topic_id"]: t for t in manifest["topics"]}
    pub_to_family = manifest.get("families") or {}
    per_topic: dict[str, dict[int, tuple[str, dict[str, Any]]]] = {}
    seen_families: dict[str, set[str]] = {}
    run_files = sorted(runs_dir.glob("*.jsonl"))
    if not run_files:
        raise ValueError(f"no *.jsonl run files under {runs_dir}")
    for rf in run_files:
        with open(rf, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{rf}:{lineno}: invalid JSON: {exc}") from None
                tid = entry.get("topic_id")
                if tid not in topics:
                    raise ValueError(f"{rf}:{lineno}: unknown topic_id {tid!r}")
                rank = entry.get("rank")
                if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
                    raise ValueError(f"{rf}:{lineno}: rank must be a positive integer, got {rank!r}")
                if "family_id" in entry:
                    fam = entry["family_id"]
                elif "publication_number" in entry:
                    pub = entry["publication_number"]
                    fam = pub_to_family.get(pub)
                    if fam is None:
                        raise ValueError(
                            f"{rf}:{lineno}: publication {pub!r} not in manifest families table"
                        )
                else:
                    raise ValueError(f"{rf}:{lineno}: entry needs family_id or publication_number")
                slot = per_topic.setdefault(tid, {})
                if rank in slot and slot[rank][0] != fam:
                    raise ValueError(f"{rf}:{lineno}: duplicate rank {rank} for topic {tid}")
                seen_families.setdefault(tid, set())
                slot[rank] = (fam, entry)
    out: dict[str, list[tuple[int, str, dict[str, Any]]]] = {}
    for tid, slot in per_topic.items():
        fams: set[str] = set()
        ranked: list[tuple[int, str, dict[str, Any]]] = []
        for rank in sorted(slot):
            fam, entry = slot[rank]
            if fam in fams:
                continue  # second member of an already-ranked family: skip, keep best rank
            fams.add(fam)
            ranked.append((rank, fam, entry))
        out[tid] = ranked
    return out


def score_suite(
    manifest: dict[str, Any],
    runs: dict[str, list[tuple[int, str, dict[str, Any]]]],
    *,
    split: str | None = None,
    bootstrap_n: int = 10_000,
    seed: int = 20261028,
) -> dict[str, Any]:
    """Compute the full metric report. All metric math delegates to patent_intel."""
    from patent_intel.retrieval import metrics as M

    topics = manifest["topics"]
    if split:
        topics = [t for t in topics if t["split"] == split]
        if not topics:
            raise ValueError(f"no topics in split {split!r}")

    gold_zero: list[str] = []
    evaluated: list[str] = []
    recall_ks = {k: [] for k in RECALL_KS}
    ndcg_vals: list[float] = []
    mrr_vals: list[float] = []
    critical_vals: list[float] = []
    per_topic_rows: list[dict[str, Any]] = []
    coverage: dict[str, dict[str, list[str]]] = {"language": {}, "domain": {}}
    family_hits: dict[str, int] = {}
    requests_by_topic: dict[str, int] = {}

    for topic in topics:
        tid = topic["topic_id"]
        gold = set(topic.get("gold_families") or [])
        ranked_entries = runs.get(tid, [])
        ranked = [fam for _, fam, _ in ranked_entries]
        requests_by_topic[tid] = len(ranked_entries)
        for fam in ranked:
            family_hits[fam] = family_hits.get(fam, 0) + 1
        row: dict[str, Any] = {"topic_id": tid, "gold_size": len(gold), "ranked_size": len(ranked)}
        if not gold:
            gold_zero.append(tid)
            row["note"] = "gold_known_incomplete: excluded from recall denominator"
            per_topic_rows.append(row)
            continue
        evaluated.append(tid)
        row["recall"] = {}
        for k in RECALL_KS:
            value = M.family_recall_at_k(ranked, gold, k)
            recall_ks[k].append(value)
            row["recall"][str(k)] = value
        rr = M.reciprocal_rank(ranked, gold)
        mrr_vals.append(rr)
        row["mrr"] = rr
        levels = topic.get("relevance_levels") or {}
        if levels and any(v > 0 for v in levels.values()):
            ndcg = M.ndcg_at_k(ranked, levels, NDCG_K)
            ndcg_vals.append(ndcg)
            row[f"ndcg@{NDCG_K}"] = ndcg
        critical = topic.get("critical_families") or []
        if critical:
            # Critical prior-art recall: fraction of human-confirmed critical families
            # found anywhere in the returned list (not a K-cut metric).
            cval = len(set(ranked) & set(critical)) / len(set(critical))
            critical_vals.append(cval)
            row["critical_recall"] = cval
        for cov_key, cov_field in (("language", "language"), ("domain", "domain")):
            label = topic.get(cov_field) or "unspecified"
            coverage[cov_key].setdefault(label, []).append(tid)
        row["recall_hits"] = len(set(ranked) & gold)
        per_topic_rows.append(row)

    if not evaluated:
        raise ValueError(
            "every topic has an empty gold set — nothing to evaluate; refusing to emit a report"
        )

    def mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    report: dict[str, Any] = {
        "tool": "score_retrieval",
        "suite": manifest["suite"],
        "version": manifest["version"],
        "qrels_version": manifest["qrels_version"],
        "split": split or "all",
        "gold_completeness": manifest["gold_completeness"],
        "topics_evaluated": len(evaluated),
        "topics_gold_zero": gold_zero,
        "recall_at_k": {str(k): mean(v) for k, v in recall_ks.items()},
        "ndcg_at_k": {str(NDCG_K): mean(ndcg_vals)} if ndcg_vals else {},
        "mrr": mean(mrr_vals),
        "critical_recall": {
            "value": mean(critical_vals),
            "n_topics": len(critical_vals),
            "caveat": None
            if manifest["gold_completeness"] == "complete"
            else (
                f"gold_completeness={manifest['gold_completeness']}: gold may be an "
                "incomplete prior-art set (pool-biased proxy labels); critical recall "
                "is a lower bound, not proof of completeness"
            ),
        },
        "per_topic": per_topic_rows,
        "coverage": {
            key: {label: {"topics": tids, "mean_recall_at_100": _slice_recall(per_topic_rows, tids)}
                  for label, tids in sorted(groups.items())}
            for key, groups in coverage.items()
        },
        "audit": {
            "run_entries": sum(len(v) for v in runs.values()),
            "unique_family_hits": len(family_hits),
            "requests_total": sum(requests_by_topic.values()),
            "yield_per_100_requests": M.unique_relevant_yield(
                [row.get("recall_hits", 0) for row in per_topic_rows if "recall_hits" in row],
                total_requests=max(1, sum(requests_by_topic.values())),
            ),
        },
    }

    recall_by_topic = {
        row["topic_id"]: row["recall"]["100"]
        for row in per_topic_rows
        if "recall" in row
    }
    ci = M.bootstrap_ci_by_topic(recall_by_topic, n_resamples=bootstrap_n, seed=seed)
    report["ci"] = {
        "method": "bootstrap-by-topic",
        "target": "family_recall_at_100 (macro)",
        **ci,
    }
    return report


def _slice_recall(rows: list[dict[str, Any]], topic_ids: list[str]) -> float | None:
    wanted = set(topic_ids)
    vals = [row["recall"]["100"] for row in rows if row["topic_id"] in wanted and "recall" in row]
    return sum(vals) / len(vals) if vals else None


def _pin_utf8_stdio() -> None:
    # Em-dashes in report banners/messages crashed parent test harnesses on
    # cp1252 CI runners: the subprocess reader thread died mid-decode and
    # stdout/stderr came back as None. Tools own their output encoding.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(
        prog="score_retrieval",
        description="Score retrieval runs against a benchmark suite manifest (family-level metrics).",
    )
    parser.add_argument("--suite", required=True, metavar="DIR", help="suite directory containing manifest.json")
    parser.add_argument("--runs", required=True, metavar="DIR", help="directory of *.jsonl run files")
    parser.add_argument("--split", choices=("train", "val", "test"), default=None)
    parser.add_argument("--bootstrap-n", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    args = parser.parse_args(argv)

    _require_patent_intel()

    suite_dir = Path(args.suite)
    runs_dir = Path(args.runs)
    if not suite_dir.is_dir() or not runs_dir.is_dir():
        print(f"[FATAL] suite/runs directory missing: {suite_dir} / {runs_dir}", file=sys.stderr)
        return EXIT_USAGE

    try:
        manifest = load_manifest(suite_dir)
        runs = load_runs(runs_dir, manifest)
        report = score_suite(
            manifest, runs, split=args.split, bootstrap_n=args.bootstrap_n, seed=args.seed
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return EXIT_AUDIT

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _render(report)
    return EXIT_OK


def _render(report: dict[str, Any]) -> None:
    print(f"suite {report['suite']} v{report['version']} (qrels {report['qrels_version']}, split={report['split']})")
    print(f"topics: {report['topics_evaluated']} evaluated, {len(report['topics_gold_zero'])} gold-zero (excluded)")
    for k, v in report["recall_at_k"].items():
        print(f"  Family Recall@{k}: {v:.4f}")
    if report["ndcg_at_k"]:
        for k, v in report["ndcg_at_k"].items():
            print(f"  nDCG@{k}: {v:.4f}")
    print(f"  MRR: {report['mrr']:.4f}")
    cr = report["critical_recall"]
    if cr["n_topics"]:
        print(f"  Critical prior-art recall: {cr['value']:.4f} ({cr['n_topics']} topics)")
    ci = report["ci"]
    if ci.get("degenerate"):
        print(f"  CI: degenerate ({ci['n_topics']} topic) — point estimate only")
    else:
        print(f"  CI@{ci['level']:.2f} for Recall@100: [{ci['lower']:.4f}, {ci['upper']:.4f}]")
    print(f"  audit: {report['audit']['run_entries']} entries, "
          f"{report['audit']['yield_per_100_requests']:.2f} relevant families / 100 requests")


if __name__ == "__main__":
    sys.exit(main())
