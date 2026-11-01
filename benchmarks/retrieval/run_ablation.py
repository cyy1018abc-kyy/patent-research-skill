#!/usr/bin/env python3
"""Ablation runner (Phase L3 / ABL-1) — preregistered in gate-ablation.yaml.

Configs (constants frozen in protocol-prereg-ablation.md §3; do not tune here):

* ``A0`` — BM25 uniform fields, 3 mechanical requests, per-doc max merge
  (byte-reproduction of the archived Phase V baseline);
* ``A1`` — BM25F field weights {title: 3.0, abstract: 2.0, claims: 2.0},
  same 3 mechanical requests scored on their field subsets, per-doc max merge;
* ``A2`` — A1 index + feature-derived single_feature queries (deterministic
  extract_features over topic title+abstract), first 3 by plan order, max merge;
* ``A3`` — A2 requests fused by RRF (k=60, equal weights) instead of max merge.

Fully offline; every executed request counts toward the ≤3/topic budget.
Usage:
    python benchmarks/retrieval/run_ablation.py --config A0 --split test
    python benchmarks/retrieval/run_ablation.py --config A1 --limit 24   # preregistered smoke
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))

import run_benchmark as rb  # noqa: E402  (reuses the Phase V machinery verbatim)

BM25F_WEIGHTS = {"title": 3.0, "abstract": 2.0, "claims": 2.0}  # protocol §3 — frozen
RRF_K = 60  # protocol §3 — frozen
SUBSET_FIELDS = {"tac": None, "ta": ["title", "abstract"], "claims": ["claims"]}


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def load_corpus_fields(corpus_dir: Path) -> dict[str, dict[str, str]]:
    """Read the frozen parquet into {doc_id: {title, abstract, claims}} (TAC view)."""
    import pyarrow.parquet as pq

    table = pq.read_table(
        corpus_dir / "corpus.parquet",
        columns=["relevant_id", "title_en", "abstract_en", "claims_text"],
    )
    cols = table.to_pydict()
    del table
    print(f"[index-source] rows={len(cols['relevant_id'])}", file=sys.stderr, flush=True)
    fields_by_doc: dict[str, dict[str, str]] = {}
    for i, doc_id in enumerate(cols["relevant_id"]):
        fields_by_doc[doc_id] = {
            "title": cols["title_en"][i] or "",
            "abstract": cols["abstract_en"][i] or "",
            "claims": cols["claims_text"][i] or "",
        }
    return fields_by_doc


def feature_requests(topic: dict, queries_by_id: dict, max_requests: int = 3) -> list[list[str]]:
    """Deterministic feature-derived requests (protocol §3 A2/A3).

    extract_features over [title, abstract] with default expanders; single_feature
    queries in plan order, first ``max_requests``; returns the token lists.
    """
    from patent_intel.retrieval.features import extract_features
    from patent_intel.retrieval.query_plan import QueryPlanBuilder

    q = queries_by_id[topic["source_id"]]
    statements = [q["title_en"] or "", q["abstract_en"] or ""]
    bundle = extract_features(statements, axis_id=f"N1@{topic['topic_id']}",
                              source_tag="dapfam-ablation", approved=True)
    plan = QueryPlanBuilder().build(bundle)
    singles = [query for query in plan.queries if query.query_type == "single_feature"]
    return [list(query.terms) for query in singles[:max_requests]]


def rrf_merge(rankings: dict[str, list[str]], k: int) -> list[tuple[str, float]]:
    from patent_intel.retrieval.hybrid import rrf_fuse

    return rrf_fuse(rankings, k=RRF_K)[:k]


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", choices=("A0", "A1", "A2", "A3"), required=True)
    parser.add_argument("--split", default="test", choices=("train", "val", "test"))
    parser.add_argument("--limit", type=int, default=0, help="前 N 个主题（预注册 smoke=24，不进评测）")
    args = parser.parse_args()
    if args.limit and args.split != "test":
        raise SystemExit("--limit 仅用于 test 冒烟")
    if args.config == "A0" and args.limit:
        print("[note] A0 smoke exists for wiring only; byte-reproduction check always runs full")

    try:
        import patent_intel  # noqa: F401
        import pyarrow.parquet as pq  # noqa: F401
    except ImportError as exc:
        print(f"[FATAL] missing dependency: {exc}", file=sys.stderr)
        return 2

    topics, _manifest = rb.load_topics(args.split)
    if args.limit:
        topics = topics[: args.limit]
    print(f"[topics] split={args.split} n={len(topics)} config={args.config}")

    qtable = pq.read_table(rb.CORPUS_DIR / "queries.parquet",
                           columns=["query_id", "title_en", "abstract_en", "claims_text"]).to_pydict()
    queries_by_id = {
        qid: {"title_en": qtable["title_en"][i], "abstract_en": qtable["abstract_en"][i],
              "claims_text": qtable["claims_text"][i]}
        for i, qid in enumerate(qtable["query_id"])
    }
    del qtable

    rows: list[dict] = []
    requests_total = 0
    t0 = time.time()

    if args.config == "A0":
        print("[index] building BM25 uniform index (A0)…")
        from patent_intel.retrieval.lexical import BM25Index

        index = BM25Index(rb.iter_corpus_docs(rb.CORPUS_DIR), k1=rb.ENGINE_PARAMS["k1"], b=rb.ENGINE_PARAMS["b"])
        print(f"[index] {len(index)} docs in {time.time() - t0:.0f}s")
        for n, topic in enumerate(topics, start=1):
            texts = rb.topic_query_texts(topic, queries_by_id)
            score_maps = []
            for name in ("tac", "ta", "claims"):
                hits = index.search(texts[name], k=rb.K_PER_REQUEST)
                requests_total += 1
                score_maps.append(dict(hits))
            for rank, (fam, _score) in enumerate(rb.merge_rankings(score_maps, rb.K_PER_REQUEST), start=1):
                rows.append({"topic_id": topic["topic_id"], "family_id": fam, "rank": rank})
            if n % 50 == 0:
                print(f"  [A0] {n}/{len(topics)} ({time.time() - t0:.0f}s)")
        meta: dict = {"engine": "BM25Index", "engine_params": dict(rb.ENGINE_PARAMS)}
    else:
        print(f"[index] building BM25F index ({args.config}), weights={BM25F_WEIGHTS}…")
        from patent_intel.retrieval.lexical import BM25FIndex

        fields_by_doc = load_corpus_fields(rb.CORPUS_DIR)
        bm25f = BM25FIndex(fields_by_doc, weights=BM25F_WEIGHTS, k1=rb.ENGINE_PARAMS["k1"], b=rb.ENGINE_PARAMS["b"])
        del fields_by_doc
        print(f"[index] {len(bm25f)} docs in {time.time() - t0:.0f}s")
        meta = {"engine": "BM25FIndex", "engine_params": dict(rb.ENGINE_PARAMS),
                "bm25f_weights": dict(BM25F_WEIGHTS)}

        for n, topic in enumerate(topics, start=1):
            if args.config == "A1":
                texts = rb.topic_query_texts(topic, queries_by_id)
                score_maps: list[dict[str, float]] = []
                for name in ("tac", "ta", "claims"):
                    hits = bm25f.search(texts[name], k=rb.K_PER_REQUEST, fields=SUBSET_FIELDS[name])
                    requests_total += 1
                    score_maps.append(dict(hits))
                merged = rb.merge_rankings(score_maps, rb.K_PER_REQUEST)
            else:
                request_terms = feature_requests(topic, queries_by_id)
                if args.config == "A2":
                    score_maps = []
                    for terms in request_terms:
                        hits = bm25f.search(" ".join(terms), k=rb.K_PER_REQUEST)
                        requests_total += 1
                        score_maps.append(dict(hits))
                    merged = rb.merge_rankings(score_maps, rb.K_PER_REQUEST)
                else:  # A3: RRF fusion of the same requests
                    rankings: dict[str, list[str]] = {}
                    for i, terms in enumerate(request_terms, start=1):
                        hits = bm25f.search(" ".join(terms), k=rb.K_PER_REQUEST)
                        requests_total += 1
                        rankings[f"req{i}"] = [doc_id for doc_id, _ in hits]
                    merged = rrf_merge(rankings, rb.K_PER_REQUEST) if rankings else []
            for rank, (fam, _score) in enumerate(merged, start=1):
                rows.append({"topic_id": topic["topic_id"], "family_id": fam, "rank": rank})
            if n % 20 == 0:
                print(f"  [{args.config}] {n}/{len(topics)} ({time.time() - t0:.0f}s)")
        if args.config == "A3":
            meta["rrf_k"] = RRF_K
        if args.config in ("A2", "A3"):
            meta["feature_source"] = "extract_features(title_en, abstract_en) + DictionaryExpander defaults"
            meta["max_feature_requests"] = 3

    meta.update({
        "config": args.config,
        "gate_ablation_yaml_sha256": rb.sha256_file(BASE / "gate-ablation.yaml"),
        "protocol_ablation_sha256": rb.sha256_file(BASE / "protocol-prereg-ablation.md"),
        "snapshot_sha256": {p.name: rb.sha256_file(rb.CORPUS_DIR / p.name) for p in sorted(rb.CORPUS_DIR.glob("*.parquet"))},
        "manifest_sha256": rb.sha256_file(rb.TOPICS_MANIFEST),
        "split": args.split,
        "topics_run": len(topics),
        "requests_total": requests_total,
        "elapsed_seconds": round(time.time() - t0, 1),
        "network_requests": 0,
        "smoke": bool(args.limit),
    })
    rb.write_run(f"ablation-{args.config}", rows, meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
