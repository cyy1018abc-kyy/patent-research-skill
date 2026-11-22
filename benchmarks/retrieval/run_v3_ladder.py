#!/usr/bin/env python3
"""V3 ladder runner (4.3 / W3-EVAL) — preregistered in gate-v3.yaml.

Configs (protocol-prereg-v3.md §2, frozen):

* ``V3-0`` — anchor, identical to V2-0 / ABL-1 A0: BM25 uniform fields over the
  TAC view, 3 mechanical requests, per-document max merge; byte-reproduction
  gate against the archived Phase V baseline;
* ``V3-1`` — index swapped to TACD-head (description capped to first 2500
  whitespace words); requests/merge/params otherwise identical to V3-0 —
  isolates field coverage;
* ``V3-2`` — V3-1's 3 lexical rankings + 1 dense ranking (persisted DenseIndex,
  query text = query-family title+abstract); RRF fusion (k=60, equal weights)
  over ≤4 channels.

Zero network (hard gate). The dense channel consumes the persisted index built
2026-11-21 on the same frozen snapshot; its manifest sha256 and corpus_sha256
match are recorded in the V3-2 run meta. Index sharing: V3-1 and V3-2 use the
same TACD-head index — built once per invocation when either is requested.

Usage:
    python benchmarks/retrieval/run_v3_ladder.py --config V3-0 --split test
    python benchmarks/retrieval/run_v3_ladder.py --config V3-1 --limit 24   # wiring smoke
    python benchmarks/retrieval/run_v3_ladder.py --configs V3-0,V3-1,V3-2   # full ladder, shared indices
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))
import run_benchmark as rb  # noqa: E402  (load_topics, iter_corpus_docs, topic_query_texts, merge_rankings, K_PER_REQUEST, ENGINE_PARAMS, write_run, sha256_file)
import run_ablation as ra  # noqa: E402  (rrf_merge, RRF_K — frozen ABL-1 constants reused per protocol §2)

CONFIGS = ("V3-0", "V3-1", "V3-2")
BUDGET_PER_TOPIC = {"V3-0": 3, "V3-1": 3, "V3-2": 4}
DESC_CAP_WORDS = 2500  # TACD-head cap (protocol §2; memory ceiling recorded in gap-smoke report)
DENSE_INDEX_DIR_DEFAULT = "E:/tmp-pk/dense-idx"
DENSE_INDEX_NAME_DEFAULT = "dense-full"


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _iter_tacd_head_docs():
    """Stream TACD-head CorpusDocs (description capped to first 2500 words)."""
    import pyarrow.parquet as pq

    from patent_intel.retrieval.lexical import CorpusDoc

    table = pq.read_table(rb.CORPUS_DIR / "corpus.parquet",
                          columns=["relevant_id", "title_en", "abstract_en", "claims_text", "description_en"])
    cols = table.to_pydict()
    del table
    print(f"[index-source] rows={len(cols['relevant_id'])} fields=TACD-head desc_cap_words={DESC_CAP_WORDS}",
          file=sys.stderr, flush=True)
    n = len(cols["relevant_id"])
    for i in range(n):
        desc = cols["description_en"][i] or ""
        words = desc.split()
        if len(words) > DESC_CAP_WORDS:
            desc = " ".join(words[:DESC_CAP_WORDS])
        text = " ".join(x for x in (cols["title_en"][i], cols["abstract_en"][i],
                                    cols["claims_text"][i], desc) if x)
        yield cols["relevant_id"][i], text


def _build_index(view: str) -> "object":
    from patent_intel.retrieval.lexical import BM25Index, CorpusDoc

    t0 = time.time()
    k1, b = rb.ENGINE_PARAMS["k1"], rb.ENGINE_PARAMS["b"]
    if view == "tac":
        index = BM25Index(rb.iter_corpus_docs(rb.CORPUS_DIR), k1=k1, b=b)
    else:  # tacd-head
        index = BM25Index((CorpusDoc(doc_id=fam, text=text, family_id=fam)
                           for fam, text in _iter_tacd_head_docs()), k1=k1, b=b)
    print(f"[index] view={view}: {len(index)} docs in {time.time() - t0:.0f}s", flush=True)
    return index


def _load_dense_index(index_dir: str, index_name: str):
    from patent_intel.retrieval.hybrid import DenseIndex, DenseRetriever

    dense = DenseRetriever()
    index = DenseIndex.load(index_dir, index_name)
    index.encoder = dense.encode_query
    return index


def _dense_query_text(topic: dict, queries_by_id: dict) -> str:
    """Dense channel query = query-family title+abstract (aligned with the index doc view)."""
    q = queries_by_id[topic["source_id"]]
    return " ".join(x for x in (q["title_en"], q["abstract_en"]) if x)


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", choices=CONFIGS, default=None)
    parser.add_argument("--configs", default=None, help="comma-separated subset; indices shared where possible")
    parser.add_argument("--split", default="test", choices=("train", "val", "test"))
    parser.add_argument("--limit", type=int, default=0, help="前 N 个主题（预注册 smoke=24，不进评测）")
    parser.add_argument("--dense-index-dir", default=DENSE_INDEX_DIR_DEFAULT)
    parser.add_argument("--dense-index-name", default=DENSE_INDEX_NAME_DEFAULT)
    args = parser.parse_args()
    if args.configs:
        configs = tuple(c.strip().upper() for c in args.configs.split(",") if c.strip())
    elif args.config:
        configs = (args.config,)
    else:
        raise SystemExit("pass --config or --configs")
    if any(c not in CONFIGS for c in configs):
        raise SystemExit(f"unknown configs: {configs} (valid: {CONFIGS})")
    if args.limit and args.split != "test":
        raise SystemExit("--limit 仅用于 test 冒烟")

    try:
        import patent_intel  # noqa: F401
        import pyarrow.parquet as pq  # noqa: F401
    except ImportError as exc:
        print(f"[FATAL] missing dependency: {exc}", file=sys.stderr)
        return 2

    topics, _manifest = rb.load_topics(args.split)
    if args.limit:
        topics = topics[: args.limit]
    print(f"[topics] split={args.split} n={len(topics)} configs={configs}")

    qtable = pq.read_table(rb.CORPUS_DIR / "queries.parquet",
                           columns=["query_id", "title_en", "abstract_en", "claims_text"]).to_pydict()
    queries_by_id = {
        qid: {"title_en": qtable["title_en"][i], "abstract_en": qtable["abstract_en"][i],
              "claims_text": qtable["claims_text"][i]}
        for i, qid in enumerate(qtable["query_id"])
    }
    del qtable

    # index plan: V3-0 needs the TAC index; V3-1/V3-2 share one TACD-head index
    tac_index = None
    tacd_index = None
    dense_index = None
    if "V3-0" in configs:
        print("[index] building TAC index (V3-0)…", flush=True)
        tac_index = _build_index("tac")
    if "V3-1" in configs or "V3-2" in configs:
        print("[index] building TACD-head index (V3-1/V3-2 shared)…", flush=True)
        tacd_index = _build_index("tacd-head")
    if "V3-2" in configs:
        t0 = time.time()
        dense_index = _load_dense_index(args.dense_index_dir, args.dense_index_name)
        manifest = getattr(dense_index, "manifest", {})
        print(f"[dense] {manifest.get('count')} docs / {manifest.get('dims')} dims loaded in {time.time() - t0:.0f}s",
              flush=True)
        if manifest.get("corpus_sha256") and manifest["corpus_sha256"] != rb.sha256_file(rb.CORPUS_DIR / "corpus.parquet"):
            raise SystemExit("[FATAL] dense index corpus_sha256 does not match the frozen snapshot — "
                             "protocol §1 hard gate (本轮作废)")

    k = rb.K_PER_REQUEST
    for config in configs:
        rows: list[dict] = []
        requests_total = 0
        t0 = time.time()
        for n, topic in enumerate(topics, start=1):
            texts = rb.topic_query_texts(topic, queries_by_id)
            score_maps: list[dict[str, float]] = []
            rankings: dict[str, list[str]] = {}
            for name in ("tac", "ta", "claims"):
                if not texts[name]:
                    continue
                index = tac_index if config == "V3-0" else tacd_index
                hits = index.search(texts[name], k=k)
                requests_total += 1
                if config == "V3-2":
                    rankings[f"req_{name}"] = [doc_id for doc_id, _ in hits]
                else:
                    score_maps.append(dict(hits))
            if config == "V3-2":
                dense_hits = dense_index.search(_dense_query_text(topic, queries_by_id), top=k)
                requests_total += 1
                rankings["dense"] = [doc_id for doc_id, _ in dense_hits]
                merged = ra.rrf_merge(rankings, k) if rankings else []
            else:
                merged = rb.merge_rankings(score_maps, k)
            for rank, (fam, _score) in enumerate(merged, start=1):
                rows.append({"topic_id": topic["topic_id"], "family_id": fam, "rank": rank})
            if n % 20 == 0:
                print(f"  [{config}] {n}/{len(topics)} ({time.time() - t0:.0f}s)", flush=True)

        meta: dict = {
            "engine": "BM25Index",
            "engine_params": dict(rb.ENGINE_PARAMS),
            "config": config,
            "gate_v3_yaml_sha256": rb.sha256_file(BASE / "gate-v3.yaml"),
            "protocol_v3_sha256": rb.sha256_file(BASE / "protocol-prereg-v3.md"),
            "snapshot_sha256": {p.name: rb.sha256_file(rb.CORPUS_DIR / p.name)
                                for p in sorted(rb.CORPUS_DIR.glob("*.parquet"))},
            "manifest_sha256": rb.sha256_file(rb.TOPICS_MANIFEST),
            "split": args.split,
            "topics_run": len(topics),
            "requests_total": requests_total,
            "request_budget_max": BUDGET_PER_TOPIC[config],
            "elapsed_seconds": round(time.time() - t0, 1),
            "network_requests": 0,
            "smoke": bool(args.limit),
        }
        if config == "V3-1":
            meta["index_view"] = "tacd-head"
            meta["desc_cap_words"] = DESC_CAP_WORDS
        if config == "V3-2":
            manifest = getattr(dense_index, "manifest", {})
            meta["index_view"] = "tacd-head"
            meta["desc_cap_words"] = DESC_CAP_WORDS
            meta["dense_channel"] = {
                "model_id": manifest.get("model_id"),
                "dims": manifest.get("dims"),
                "count": manifest.get("count"),
                "corpus_sha256": manifest.get("corpus_sha256"),
                "index_manifest_sha256": rb.sha256_file(
                    Path(args.dense_index_dir) / f"{args.dense_index_name}.manifest.json"),
                "index_dir": args.dense_index_dir,
                "index_name": args.dense_index_name,
                "rrf_k": ra.RRF_K,
            }
        rb.write_run(f"v3-{config}", rows, meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
