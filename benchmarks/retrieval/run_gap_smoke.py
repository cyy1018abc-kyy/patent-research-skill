#!/usr/bin/env python3
"""P0-GAP smoke runner (4.3 W1) — field coverage × passage chunking × k1.

Basis (deep research r2, plan §0.5 F1/F2): the DAPFAM reference paper reports
BM25 OUT recall@100 of 0.1368 (doc) / 0.1521 (passage) on this corpus, while
our 4.2 engine scores OUT 0.0. The three identified deltas: description_en
excluded from the index, document-level only (no passages), k1=1.5 vs 1.2.

Configs (smoke only — NOT an evaluation, no gate):

* ``A`` — TAC doc-level, k1=1.5 (reference replication of the V2-0 engine path);
* ``B`` — TACD doc-level (title+abstract+claims+description), k1=1.5;
* ``C`` — TACD passage 6100-word windows, maxP aggregation, k1=1.2;
* ``D`` — same passages, k1=1.5.

Topic sets (zero test contact): OUT uses train+val (24 topics); IN and MIXED
use the first 24 train topics each (sorted by topic_id). Metrics: family
recall@100 per topic and per group. Zero network; frozen snapshot only.

Usage:
    python benchmarks/retrieval/run_gap_smoke.py --configs A,B,C,D
    python benchmarks/retrieval/run_gap_smoke.py --configs A --max-topics 8
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))
import run_benchmark as rb  # noqa: E402  (load_topics, merge_rankings, write_run, sha256_file, K_PER_REQUEST, ENGINE_PARAMS, CORPUS_DIR)

# corpus/ is gitignored, so fresh worktrees ship without the 1.2GB frozen
# snapshot. GAP_CORPUS_DIR points this runner at a read-only canonical copy
# (default: the _wt-quality snapshot); sameness is proven by the sha256s in the
# report, which must match the canonical corpus hashes.
CORPUS_DIR = Path(os.environ.get("GAP_CORPUS_DIR", str(rb.CORPUS_DIR)))

sys.path.insert(0, str(REPO_ROOT / "benchmarks" / "retrieval"))
from passage import WORDS_PER_TOKEN_DOC_NOTE  # noqa: E402  (chunk/aggregate live in passage.py; deferred to EVAL3 engine decision)

CONFIGS = ("A", "B", "D")
CONFIG_PARAMS = {
    "A": {"view": "tac-doc", "k1": 1.5},
    "B": {"view": "tacd-head-doc", "k1": 1.5},
    "D": {"view": "tacd-head-doc", "k1": 1.2},
}
# Full-TACD indexing is memory-infeasible on this engine/machine (measured:
# ~500M token occurrences → ~30GB of dict postings alone; MemoryError observed
# on the first full attempt). The smoke therefore caps description to its first
# DESC_CAP_WORDS words — approximately the paper's best 8192-token window's
# head — which fits comfortably (~165M occurrences, ~12GB peak). The passage
# axis (chunk+maxP) is engineered in passage.py and unit-tested, but full-text
# passage indexing needs the same memory headroom and is DEFERRED to the
# EVAL3 engine decision (disk-backed postings / mmap), recorded honestly here.
DESC_CAP_WORDS = 2500
MAX_WORDS = 6100  # ≈ 8192 BPE tokens (see WORDS_PER_TOKEN_DOC_NOTE)
SMOKE_N = {"OUT": 24, "IN": 24, "MIXED": 24}


def _cap_description(text: str, max_words: int) -> str:
    if not text:
        return text
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words])


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _iter_tacd_docs(columns_needed: tuple[str, ...], desc_cap_words: int | None = None):
    """Stream TACD (or TAC) doc-level CorpusDocs from the frozen parquet.

    Local replica of run_benchmark.iter_corpus_docs — this runner must not
    modify the shared module. ``desc_cap_words`` truncates description_en to its
    first N words (memory-feasibility cap; recorded in every report).
    """
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        print(f"[FATAL] pyarrow required: {exc}", file=sys.stderr)
        raise SystemExit(2)
    from patent_intel.retrieval.lexical import CorpusDoc

    table = pq.read_table(CORPUS_DIR / "corpus.parquet", columns=list(columns_needed))
    cols = table.to_pydict()
    del table
    print(f"[index-source] rows={len(cols['relevant_id'])} fields={'+'.join(columns_needed[1:])}"
          + (f" desc_cap_words={desc_cap_words}" if desc_cap_words else ""), file=sys.stderr, flush=True)
    n = len(cols["relevant_id"])
    for i in range(n):
        parts = [cols[c][i] for c in columns_needed[1:]]
        if desc_cap_words and parts:
            parts[-1] = _cap_description(parts[-1], desc_cap_words)
        text = " ".join(x for x in parts if x)
        yield cols["relevant_id"][i], text


def _build_index(config: str):
    """Build the BM25Index for one smoke config (k1 is fixed at build time)."""
    from patent_intel.retrieval.lexical import BM25Index, CorpusDoc

    params = CONFIG_PARAMS[config]
    k1, b = params["k1"], rb.ENGINE_PARAMS["b"]
    t0 = time.time()
    if params["view"] == "tac-doc":
        stream = (CorpusDoc(doc_id=fam, text=text, family_id=fam)
                  for fam, text in _iter_tacd_docs(("relevant_id", "title_en", "abstract_en", "claims_text")))
    else:  # tacd-head-doc
        stream = (CorpusDoc(doc_id=fam, text=text, family_id=fam)
                  for fam, text in _iter_tacd_docs(
                      ("relevant_id", "title_en", "abstract_en", "claims_text", "description_en"),
                      desc_cap_words=DESC_CAP_WORDS))
    index = BM25Index(stream, k1=k1, b=b)
    print(f"[index] config {config}: {len(index)} docs in {time.time() - t0:.0f}s", flush=True)
    return index


def _select_topics(topics: list[dict]) -> dict[str, list[dict]]:
    """Zero-test-contact smoke sets: OUT train+val; IN/MIXED first-N train."""
    by_group: dict[str, list[dict]] = {"OUT": [], "IN": [], "MIXED": []}
    for topic in topics:
        domain = topic["domain"]
        if domain == "OUT":
            if topic["split"] in ("train", "val"):
                by_group["OUT"].append(topic)
        elif topic["split"] == "train":
            by_group[domain].append(topic)
    for domain, group in by_group.items():
        group.sort(key=lambda t: t["topic_id"])
        by_group[domain] = group[: SMOKE_N[domain]]
    return by_group


def _recall_at_100(top100: list[str], gold_families: list[str]) -> float:
    if not gold_families:
        return 0.0
    hits = len(set(top100) & set(gold_families))
    return hits / len(gold_families)


def run_config(config: str, topics_by_group: dict[str, list[dict]], queries_by_id: dict, k: int) -> dict:
    index = _build_index(config)
    rows: list[dict] = []
    t0 = time.time()
    total = sum(len(g) for g in topics_by_group.values())
    done = 0
    for domain, group in topics_by_group.items():
        for topic in group:
            texts = rb.topic_query_texts(topic, queries_by_id)
            family_score_maps: list[dict[str, float]] = []
            for name in ("tac", "ta", "claims"):
                if not texts[name]:
                    continue
                hits = index.search(texts[name], k=k)
                family_score_maps.append(dict(hits))
            merged = rb.merge_rankings(family_score_maps, k)
            top100 = [fam for fam, _ in merged[:100]]
            recall = _recall_at_100(top100, topic["gold_families"])
            rows.append({"topic_id": topic["topic_id"], "domain": domain,
                         "recall@100": round(recall, 6), "gold_n": len(topic["gold_families"])})
            done += 1
            if done % 8 == 0 or done == total:
                print(f"  [{config}] {done}/{total} ({time.time() - t0:.0f}s)", flush=True)
    by_group: dict[str, list[float]] = {}
    for row in rows:
        by_group.setdefault(row["domain"], []).append(row["recall@100"])
    summary = {domain: {"n": len(v), "mean_recall@100": round(sum(v) / len(v), 6) if v else None}
               for domain, v in by_group.items()}
    return {"config": config, "params": dict(CONFIG_PARAMS[config]), "summary": summary, "topics": rows}


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--configs", default="A,B,C,D", help="逗号分隔的配置子集")
    parser.add_argument("--max-topics", type=int, default=0, help="调试：每组再截前 N 题")
    parser.add_argument("--k-per-request", type=int, default=0, help="默认 rb.K_PER_REQUEST=200")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    configs = tuple(c.strip().upper() for c in args.configs.split(",") if c.strip())
    if any(c not in CONFIGS for c in configs):
        raise SystemExit(f"unknown configs: {configs} (valid: {CONFIGS})")

    try:
        import patent_intel  # noqa: F401
        import pyarrow.parquet as pq  # noqa: F401
    except ImportError as exc:
        print(f"[FATAL] missing dependency: {exc}", file=sys.stderr)
        return 2

    _all_topics, manifest = rb.load_topics("train")  # loader needs a split; we select manually below
    all_topics = manifest["topics"]
    topics_by_group = _select_topics(all_topics)
    if args.max_topics:
        topics_by_group = {d: g[: args.max_topics] for d, g in topics_by_group.items()}
    counts = {d: len(g) for d, g in topics_by_group.items()}
    print(f"[topics] smoke sets (zero test contact): {counts}")

    qtable = pq.read_table(CORPUS_DIR / "queries.parquet",
                           columns=["query_id", "title_en", "abstract_en", "claims_text"]).to_pydict()
    queries_by_id = {
        qid: {"title_en": qtable["title_en"][i], "abstract_en": qtable["abstract_en"][i],
              "claims_text": qtable["claims_text"][i]}
        for i, qid in enumerate(qtable["query_id"])
    }
    del qtable

    k = args.k_per_request or rb.K_PER_REQUEST
    t0 = time.time()
    results = [run_config(c, topics_by_group, queries_by_id, k) for c in configs]

    report = {
        "report_type": "gap-smoke",
        "date": "2026-11-20",
        "smoke": True,
        "gate": False,
        "topic_sets": counts,
        "desc_cap_words": DESC_CAP_WORDS,
        "memory_note": "full-TACD (~500M token occurrences, ~30GB postings) MemoryError on first attempt; desc capped to first 2500 words (~165M occ, feasible); passage axis (chunk+maxP, engineered+tested in passage.py) deferred to EVAL3 engine decision (disk-backed postings)",
        "word_token_note": WORDS_PER_TOKEN_DOC_NOTE,
        "k_per_request": k,
        "b": rb.ENGINE_PARAMS["b"],
        "engine": "BM25Index",
        "snapshot_sha256": {p.name: rb.sha256_file(CORPUS_DIR / p.name) for p in sorted(CORPUS_DIR.glob("*.parquet"))},
        "manifest_sha256": rb.sha256_file(rb.TOPICS_MANIFEST),
        "elapsed_seconds": round(time.time() - t0, 1),
        "network_requests": 0,
        "results": results,
    }
    out = Path(args.out) if args.out else BASE / "results" / "gap-smoke-2026-11-20.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {out}")
    for r in results:
        print(f"[summary] {r['config']}: " + " / ".join(
            f"{d}={v['mean_recall@100']}" for d, v in r["summary"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
