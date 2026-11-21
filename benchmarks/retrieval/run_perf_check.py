#!/usr/bin/env python3
"""PERF re-measurement (4.3 W1) — 41A-1 single-request gate + batch throughput.

Re-measures the "single request ≤ 1 s" engine gate (41A-1, code-complete since
4.1; deterministic side-evidence was ABL-1 A0 byte-reproduction) and the A5
batch-processing entry on the frozen TAC snapshot. Numbers land in the W1
closure report; docs refresh belongs to W3-DOCS.

Usage:
    python benchmarks/retrieval/run_perf_check.py --requests 10 --batch-topics 8
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))
import run_benchmark as rb  # noqa: E402  (load_topics, CORPUS_DIR, ENGINE_PARAMS, K_PER_REQUEST)

# corpus/ is gitignored — same override pattern as run_gap_smoke.py.
CORPUS_DIR = Path(os.environ.get("GAP_CORPUS_DIR", str(rb.CORPUS_DIR)))


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
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--batch-topics", type=int, default=8)
    args = parser.parse_args()

    try:
        import patent_intel  # noqa: F401
        import pyarrow.parquet as pq  # noqa: F401
    except ImportError as exc:
        print(f"[FATAL] missing dependency: {exc}", file=sys.stderr)
        return 2

    from patent_intel.retrieval.lexical import BM25Index

    t0 = time.time()
    index = BM25Index(rb.iter_corpus_docs(CORPUS_DIR),
                      k1=rb.ENGINE_PARAMS["k1"], b=rb.ENGINE_PARAMS["b"])
    build_s = time.time() - t0
    print(f"[index] {len(index)} docs in {build_s:.0f}s")

    topics, _m = rb.load_topics("test")
    topics = topics[: max(args.requests, args.batch_topics)]
    qtable = pq.read_table(CORPUS_DIR / "queries.parquet",
                           columns=["query_id", "title_en", "abstract_en", "claims_text"]).to_pydict()
    queries_by_id = {qid: {"title_en": qtable["title_en"][i], "abstract_en": qtable["abstract_en"][i],
                           "claims_text": qtable["claims_text"][i]}
                     for i, qid in enumerate(qtable["query_id"])}
    del qtable
    texts = [rb.topic_query_texts(t, queries_by_id)["tac"] for t in topics]

    k = rb.K_PER_REQUEST
    latencies: list[float] = []
    for text in texts[: args.requests]:
        t1 = time.time()
        index.search(text, k=k)
        latencies.append(time.time() - t1)
    gate = "PASS" if max(latencies) <= 1.0 else "FAIL"
    print(f"[single-request] n={len(latencies)} median={statistics.median(latencies)*1000:.0f}ms "
          f"max={max(latencies)*1000:.0f}ms gate(≤1s)={gate}")

    from patent_intel.retrieval.batch import BatchConfig, run_batch
    cfg = BatchConfig(side="baseline", engine_params=dict(rb.ENGINE_PARAMS))
    t2 = time.time()
    result = run_batch(topics[: args.batch_topics], queries_by_id, index, cfg, batch_mode="perf-check")
    batch_s = time.time() - t2
    n_req = args.batch_topics * 3
    print(f"[batch] topics={args.batch_topics} requests={n_req} elapsed={batch_s:.1f}s "
          f"throughput={n_req / batch_s:.1f} req/s per_request_avg={batch_s / n_req * 1000:.0f}ms")

    print(f"[summary] build={build_s:.0f}s single_request_max={max(latencies)*1000:.0f}ms gate={gate} "
          f"batch={batch_s:.1f}s/{n_req}req")
    return 0


if __name__ == "__main__":
    sys.exit(main())
