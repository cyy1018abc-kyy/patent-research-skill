#!/usr/bin/env python3
"""Build the DAPFAM-derived public topic set (Phase V / V1-3).

Reads the frozen parquet snapshot (local-only, gitignored) and emits
``topics/public/manifest.json`` (schema-compliant, metadata only — no corpus
text, no qrels negatives) plus ``topics/public/domain_map.json`` (per-pair
IN/OUT labels for group reporting). Deterministic: same snapshot bytes ⇒ same
manifest bytes.

Split rule (preregistered in gate.yaml): order topics by
``(earliest_claim_date, query_id)``, first 60% train / next 15% val /
last 25% test; boundary dates recorded in ``time_split``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
CORPUS_DIR = BASE / "corpus" / "dapfam"
OUT_DIR = BASE / "topics" / "public"

SCHEMA_VERSION = 2
SUITE = "dapfam-derived"
QRELS_VERSION = "dapfam-qrels-2026-10-29"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def split_topics(topics: list[dict]) -> tuple[list[dict], dict]:
    ordered = sorted(topics, key=lambda t: (t.pop("_sort_date"), t["topic_id"]))
    n = len(ordered)
    train_end = round(n * 0.60)
    val_end = round(n * 0.75)
    for i, topic in enumerate(ordered):
        topic["split"] = "train" if i < train_end else ("val" if i < val_end else "test")
    boundary = {
        "key": "earliest_claim_date",
        "rule": "order by (earliest_claim_date, query_id); first 60% train / next 15% val / last 25% test",
        "train_last_date": ordered[train_end - 1]["_date_iso"],
        "val_last_date": ordered[val_end - 1]["_date_iso"],
        "test_first_date": ordered[val_end]["_date_iso"],
    }
    for topic in ordered:
        topic.pop("_date_iso", None)
    return ordered, boundary


def domain_scope(domains: set[str]) -> str:
    """Topic-level IN/OUT/MIXED group label (preregistered definition)."""
    if not domains:
        return "UNKNOWN"
    if domains == {"IN"}:
        return "IN"
    if domains == {"OUT"}:
        return "OUT"
    return "MIXED"


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus-dir", type=Path, default=CORPUS_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("[FATAL] pyarrow required: pip install pyarrow", file=sys.stderr)
        return 2

    cdir = args.corpus_dir
    qrels = pq.read_table(cdir / "qrels_all.parquet").to_pydict()
    queries = pq.read_table(cdir / "queries.parquet").to_pydict()

    gold: dict[str, list[str]] = {}
    gold_domains: dict[str, dict[str, str]] = {}
    for qid, fid, score, dom in zip(qrels["query_id"], qrels["relevant_id"],
                                    qrels["relevance_score"], qrels["domain_rel"]):
        if score == 1.0:
            gold.setdefault(qid, []).append(fid)
            gold_domains.setdefault(qid, {})[fid] = dom
    domain_map = {qid: doms for qid, doms in gold_domains.items()}

    topics: list[dict] = []
    for i in range(len(queries["query_id"])):
        qid = queries["query_id"][i]
        fams = sorted(gold.get(qid, []))
        date = queries["earliest_claim_date"][i]
        domains = {domain_map.get(qid, {}).get(f, "") for f in fams}
        topics.append({
            "topic_id": "",  # assigned after the deterministic ordering (TP-####)
            "_sort_date": (date.isoformat() if date else "", qid),
            "_date_iso": date.isoformat() if date else "",
            "language": "en",
            "domain": domain_scope(domains),
            "in_domain_of_engine": domains == {"IN"},
            "gold_families": fams,
            "gold_known_incomplete": True,
            "time_split_key": date.isoformat() if date else "",
            "source_id": qid,
        })
    ordered, boundary = split_topics(topics)
    for seq, topic in enumerate(ordered, start=1):
        topic["topic_id"] = f"TP-{seq:04d}"

    manifest = {
        "suite": SUITE,
        "version": "1.0.0",
        "qrels_version": QRELS_VERSION,
        "gold_completeness": "pool_biased",
        "license": "DAPFAM (CC-BY-NC-SA-4.0) — metadata-only derivation (family IDs + dates); corpus/query text never distributed",
        "provenance": "Topics = DAPFAM query families (Ayaou et al., 2025, arXiv:2506.22141); gold = citation-proxy positives from qrels_all (sampled negatives exist -> pool_biased); split drawn chronologically, IDs assigned TP-#### in that order; generated by benchmarks/retrieval/build_topics.py from the frozen snapshot below.",
        "source_snapshot": {name: sha256_file(cdir / name) for name in sorted(p.name for p in cdir.glob("*.parquet"))},
        "time_split": boundary,
        "topics": ordered,
    }
    import sys as _sys  # noqa: PLC0415 - sibling module
    _sys.path.insert(0, str(BASE))
    from check_leakage import leakage_report  # noqa: PLC0415 - sibling module
    manifest["leakage_report"] = leakage_report(manifest)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "manifest.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    with open(out / "domain_map.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(domain_map, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")

    counts = {}
    for topic in ordered:
        counts[topic["split"]] = counts.get(topic["split"], 0) + 1
    zero_gold = sum(1 for t in ordered if not t["gold_families"])
    print(f"[topics] total={len(ordered)} splits={counts} zero_gold={zero_gold} "
          f"positives={sum(len(t['gold_families']) for t in ordered)}")
    print(f"[topics] {out / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
