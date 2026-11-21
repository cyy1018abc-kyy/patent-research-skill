#!/usr/bin/env python3
"""CE1 smoke runner (4.3 W1) — Cross-Encoder rerank over fused V2-2 candidates.

Reorders the fused top-50 of the preregistered V2 smoke set (24 test topics,
identical selection to run_v2_ladder --limit 24) with the G3-ruled
bge-reranker-v2-m3 cross-encoder, and reports ranking-sensitive metrics the
@100 axis cannot see: family recall@10, MRR@10, plus a recall@100
non-degradation check (rerank reshuffles only the top segment; ranks 51-100
keep fused order).

Zero test-set contamination: uses the SAME preregistered 24-topic smoke subset
as V2 (no gate, no claim). Zero network: weights load from the local _models
snapshot with offline env pinned.

Usage:
    python benchmarks/retrieval/run_ce_smoke.py [--limit 24] [--top 50]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))
import run_benchmark as rb  # noqa: E402  (load_topics, CORPUS_DIR, sha256_file)

# corpus/ is gitignored; fresh worktrees ship without it. CE_CORPUS_DIR points
# this runner at a read-only canonical snapshot (default: _wt-quality copy).
CORPUS_DIR = Path(os.environ.get("CE_CORPUS_DIR", str(rb.CORPUS_DIR)))

DEFAULT_RUNS = Path("F:/GitHub项目合集/专利调研与润色/_wt-quality/benchmarks/retrieval/runs/v2-V2-2.jsonl")
DEFAULT_MODEL = Path("F:/GitHub项目合集/专利调研与润色/_models/bge-reranker-v2-m3")


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def load_doc_texts(doc_ids: set[str]) -> dict[str, str]:
    """title+abstract text for the needed doc ids from the frozen parquet."""
    import pyarrow.parquet as pq

    table = pq.read_table(CORPUS_DIR / "corpus.parquet",
                          columns=["relevant_id", "title_en", "abstract_en"])
    cols = table.to_pydict()
    del table
    texts: dict[str, str] = {}
    for i, fam in enumerate(cols["relevant_id"]):
        if fam in doc_ids:
            texts[fam] = " ".join(x for x in (cols["title_en"][i], cols["abstract_en"][i]) if x)
    missing = doc_ids - set(texts)
    if missing:
        raise SystemExit(f"[FATAL] {len(missing)} candidate ids absent from corpus, first: {sorted(missing)[0]}")
    return texts


def metrics(ranked: list[str], gold: set[str]) -> dict:
    """recall@10, MRR@10, recall@100 for one family ranking (rank = position)."""
    def recall_at(k: int) -> float:
        top = ranked[:k]
        return len(set(top) & gold) / len(gold) if gold else 0.0

    rr = 0.0
    for pos, fam in enumerate(ranked[:10], start=1):
        if fam in gold:
            rr = 1.0 / pos
            break
    return {"recall@10": round(recall_at(10), 6), "mrr@10": round(rr, 6),
            "recall@100": round(recall_at(100), 6)}


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=24, help="preregistered smoke=24")
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--runs", default=str(DEFAULT_RUNS))
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    topics, _manifest = rb.load_topics("test")
    topics = topics[: args.limit]
    topic_ids = {t["topic_id"] for t in topics}
    print(f"[topics] preregistered smoke subset: {len(topics)} topics (test[:24], identical to V2 smoke)")

    fused: dict[str, list[str]] = {}
    with open(args.runs, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            tid = row["topic_id"]
            if tid in topic_ids and row["rank"] <= 100:
                fused.setdefault(tid, []).append(row["family_id"])
    for tid in topic_ids:
        if len(fused.get(tid, [])) < 100:
            raise SystemExit(f"[FATAL] fused rows incomplete for {tid}: {len(fused.get(tid, []))}")
    print(f"[runs] fused V2-2 rows loaded from {args.runs}")

    needed = {fam for tid in topic_ids for fam in fused[tid]}
    texts = load_doc_texts(needed)
    print(f"[texts] {len(texts)} doc texts (title+abstract)")

    from patent_intel.retrieval.reranker import CrossEncoderReranker

    t0 = time.time()
    reranker = CrossEncoderReranker(texts, model_path=args.model)
    device = "cuda" if os.environ.get("CE_FORCE_CPU") != "1" and _cuda_available() else "cpu"
    print(f"[model] {reranker.name} loading on {device} …", flush=True)
    reranker._device = device  # set before first load
    reranker._require_model()
    print(f"[model] loaded in {time.time() - t0:.0f}s", flush=True)

    rows: list[dict] = []
    t0 = time.time()
    for n, topic in enumerate(topics, start=1):
        gold = set(topic["gold_families"])
        full_fused = fused[topic["topic_id"]]
        top_segment = full_fused[: args.top]
        tail = full_fused[args.top:]
        candidates = [(fam, float(len(top_segment) - i)) for i, fam in enumerate(top_segment)]
        reranked = reranker.rerank(_query_text(topic), candidates)
        before = metrics(full_fused, gold)
        after_fused = [fam for fam, _ in reranked] + tail
        after = metrics(after_fused, gold)
        rows.append({"topic_id": topic["topic_id"], "before": before, "after": after,
                     "recall@100_non_degraded": after["recall@100"] >= before["recall@100"]})
        print(f"  [{n}/{len(topics)}] {topic['topic_id']} "
              f"r@10 {before['recall@10']}→{after['recall@10']} "
              f"mrr {before['mrr@10']}→{after['mrr@10']} "
              f"({time.time() - t0:.0f}s)", flush=True)

    def mean(key: str) -> dict:
        out = {}
        for side in ("before", "after"):
            vals = [r[side][key] for r in rows]
            out[side] = round(sum(vals) / len(vals), 6)
        return out

    report = {
        "report_type": "ce-smoke",
        "date": "2026-11-20",
        "smoke": True,
        "gate": False,
        "model_path": str(args.model),
        "reranker_name": reranker.name,
        "device": device,
        "max_length": 512,
        "top_segment": args.top,
        "runs_source": str(args.runs),
        "topics": len(rows),
        "query_view": "tac (title+abstract+claims of query family)",
        "metrics_mean": {
            "recall@10": mean("recall@10"),
            "mrr@10": mean("mrr@10"),
            "recall@100": mean("recall@100"),
        },
        "recall@100_all_non_degraded": all(r["recall@100_non_degraded"] for r in rows),
        "elapsed_seconds": round(time.time() - t0, 1),
        "network_requests": 0,
        "topics_detail": rows,
    }
    out = Path(args.out) if args.out else BASE / "results" / "ce-smoke-2026-11-20.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {out}")
    print(f"[summary] recall@10 {report['metrics_mean']['recall@10']['before']}→"
          f"{report['metrics_mean']['recall@10']['after']}  "
          f"MRR@10 {report['metrics_mean']['mrr@10']['before']}→"
          f"{report['metrics_mean']['mrr@10']['after']}  "
          f"recall@100 {report['metrics_mean']['recall@100']['before']}→"
          f"{report['metrics_mean']['recall@100']['after']}  "
          f"non-degraded={report['recall@100_all_non_degraded']}")
    return 0


def _query_text(topic: dict) -> str:
    """The TAC query text for one topic (same view as the V2 mechanical requests)."""
    import pyarrow.parquet as pq

    cache = getattr(main, "_qcache", None)
    if cache is None:
        table = pq.read_table(CORPUS_DIR / "queries.parquet",
                              columns=["query_id", "title_en", "abstract_en", "claims_text"]).to_pydict()
        cache = {qid: {"title_en": table["title_en"][i], "abstract_en": table["abstract_en"][i],
                       "claims_text": table["claims_text"][i]}
                 for i, qid in enumerate(table["query_id"])}
        main._qcache = cache
    q = cache[topic["source_id"]]
    return " ".join(x for x in (q["title_en"], q["abstract_en"], q["claims_text"]) if x)


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


if __name__ == "__main__":
    sys.exit(main())
