#!/usr/bin/env python3
"""V2 ladder runner (4.2 / W4-EVAL, 41A-3) — preregistered in gate-v2.yaml.

Configs (protocol-prereg-v2.md §3, frozen):

* ``V2-0`` — BM25 uniform baseline: 3 mechanical requests, per-document max
  merge (byte-reproduction gate against the archived Phase V baseline);
* ``V2-1`` — same uniform index; the 3 mechanical requests replaced by
  feature-derived single_feature requests (max merge);
* ``V2-2`` — V2-1's requests fused by RRF (k=60, equal weights);
* ``V2-3`` — V2-2 + at most ONE cross-domain request: the plan's cross_domain
  query expanded through the mined co-occurrence table (dictionary fallback is
  part of the config); RRF over all (≤4) channels.

Discipline: the V2-3 feature requests are built with the DEFAULT builder so
they are identical to V2-1/V2-2 — the mining table only feeds the extra XD
request (step isolation). Zero network; same frozen snapshot as ABL-1.

Usage:
    python benchmarks/retrieval/run_v2_ladder.py --config V2-0 --split test
    python benchmarks/retrieval/run_v2_ladder.py --config V2-1 --limit 24   # preregistered smoke
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))
import run_benchmark as rb  # noqa: E402  (load_topics, iter_corpus_docs, topic_query_texts, merge_rankings, K_PER_REQUEST, ENGINE_PARAMS, write_run, sha256_file)
import run_ablation as ra  # noqa: E402  (feature_requests, rrf_merge, RRF_K — frozen ABL-1 constants reused per protocol §3)

CONFIGS = ("V2-0", "V2-1", "V2-2", "V2-3")
MINING_ARTIFACT = BASE / "topics" / "public" / "cooccurrence.json"


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def xd_request(topic: dict, queries_by_id: dict, mining_table) -> list[str] | None:
    """The ≤1 cross-domain request of V2-3 (mining-expanded XD query).

    Built with the mining-aware builder; the CrossDomainExpander delegates to
    the dictionary path and appends mined candidates — no mined entry means the
    dictionary fallback runs (that IS the preregistered config, not a defect).
    Returns ``None`` when the plan carries no cross_domain query at all.
    """
    from patent_intel.retrieval.features import extract_features
    from patent_intel.retrieval.query_plan import QueryPlanBuilder

    q = queries_by_id[topic["source_id"]]
    statements = [q["title_en"] or "", q["abstract_en"] or ""]
    bundle = extract_features(statements, axis_id=f"N1@{topic['topic_id']}",
                              source_tag="dapfam-v2", approved=True)
    plan = QueryPlanBuilder(mining_table=mining_table).build(bundle)
    xds = [query for query in plan.queries if query.query_type == "cross_domain"]
    return list(xds[0].terms) if xds else None


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", choices=CONFIGS, required=True)
    parser.add_argument("--split", default="test", choices=("train", "val", "test"))
    parser.add_argument("--limit", type=int, default=0, help="前 N 个主题（预注册 smoke=24，不进评测）")
    args = parser.parse_args()
    if args.limit and args.split != "test":
        raise SystemExit("--limit 仅用于 test 冒烟")
    if args.config == "V2-0" and args.limit:
        print("[note] V2-0 smoke exists for wiring only; byte-reproduction check always runs full")

    try:
        import patent_intel  # noqa: F401
        import pyarrow.parquet as pq  # noqa: F401
    except ImportError as exc:
        print(f"[FATAL] missing dependency: {exc}", file=sys.stderr)
        return 2

    mining_table = None
    meta_mining: dict = {}
    if args.config == "V2-3":
        if not MINING_ARTIFACT.is_file():
            print(f"[FATAL] mining artifact missing: {MINING_ARTIFACT} "
                  "(gate: mine first, leakage gate must pass before scoring)", file=sys.stderr)
            return 2
        from patent_intel.retrieval.cooccurrence import MiningTable

        mining_table = MiningTable.from_dict(json.loads(MINING_ARTIFACT.read_text(encoding="utf-8")))
        meta_mining = {
            "mining_artifact_sha256": hashlib.sha256(MINING_ARTIFACT.read_bytes()).hexdigest(),
            "mining_digest": mining_table.digest,
        }
        print(f"[mining] artifact loaded (digest {mining_table.digest[:12]}…)")

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
    k = rb.K_PER_REQUEST

    # ONE uniform BM25 index family instance for every config (engine is never a confound)
    print("[index] building BM25 uniform index…")
    from patent_intel.retrieval.lexical import BM25Index

    index = BM25Index(rb.iter_corpus_docs(rb.CORPUS_DIR), k1=rb.ENGINE_PARAMS["k1"], b=rb.ENGINE_PARAMS["b"])
    print(f"[index] {len(index)} docs in {time.time() - t0:.0f}s")

    for n, topic in enumerate(topics, start=1):
        if args.config == "V2-0":
            texts = rb.topic_query_texts(topic, queries_by_id)
            score_maps = []
            for name in ("tac", "ta", "claims"):
                hits = index.search(texts[name], k=k)
                requests_total += 1
                score_maps.append(dict(hits))
            merged = rb.merge_rankings(score_maps, k)
        else:
            request_terms = ra.feature_requests(topic, queries_by_id)  # identical to V2-1 in ALL steps
            if args.config == "V2-1":
                score_maps = []
                for terms in request_terms:
                    hits = index.search(" ".join(terms), k=k)
                    requests_total += 1
                    score_maps.append(dict(hits))
                merged = rb.merge_rankings(score_maps, k)
            else:  # V2-2 / V2-3: RRF fusion
                rankings: dict[str, list[str]] = {}
                for i, terms in enumerate(request_terms, start=1):
                    hits = index.search(" ".join(terms), k=k)
                    requests_total += 1
                    rankings[f"req{i}"] = [doc_id for doc_id, _ in hits]
                if args.config == "V2-3":
                    extra = xd_request(topic, queries_by_id, mining_table)
                    if extra:
                        hits = index.search(" ".join(extra), k=k)
                        requests_total += 1
                        rankings["xd"] = [doc_id for doc_id, _ in hits]
                merged = ra.rrf_merge(rankings, k) if rankings else []
        for rank, (fam, _score) in enumerate(merged, start=1):
            rows.append({"topic_id": topic["topic_id"], "family_id": fam, "rank": rank})
        if n % 20 == 0:
            print(f"  [{args.config}] {n}/{len(topics)} ({time.time() - t0:.0f}s)", flush=True)

    meta: dict = {
        "engine": "BM25Index",
        "engine_params": dict(rb.ENGINE_PARAMS),
        "config": args.config,
        "gate_v2_yaml_sha256": rb.sha256_file(BASE / "gate-v2.yaml"),
        "protocol_v2_sha256": rb.sha256_file(BASE / "protocol-prereg-v2.md"),
        "snapshot_sha256": {p.name: rb.sha256_file(rb.CORPUS_DIR / p.name) for p in sorted(rb.CORPUS_DIR.glob("*.parquet"))},
        "manifest_sha256": rb.sha256_file(rb.TOPICS_MANIFEST),
        "split": args.split,
        "topics_run": len(topics),
        "requests_total": requests_total,
        "elapsed_seconds": round(time.time() - t0, 1),
        "network_requests": 0,
        "smoke": bool(args.limit),
    }
    if args.config in ("V2-1", "V2-2", "V2-3"):
        meta["feature_source"] = "extract_features(title_en, abstract_en) + DictionaryExpander defaults"
        meta["max_feature_requests"] = 3
    if args.config in ("V2-2", "V2-3"):
        meta["rrf_k"] = ra.RRF_K
    if args.config == "V2-3":
        meta.update(meta_mining)
        meta["max_xd_requests"] = 1
    rb.write_run(f"v2-{args.config}", rows, meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
