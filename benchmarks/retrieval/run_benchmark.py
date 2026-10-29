#!/usr/bin/env python3
"""Deterministic retrieval benchmark runner (Phase V / V3-2).

Runs the preregistered comparison on the frozen DAPFAM snapshot, fully offline:

* ``baseline``  — 3 fixed mechanical BM25 requests per topic
  (full TAC / title+abstract / claims), no adaptivity;
* ``extension`` — the patent_intel retrieval pipeline (feature extraction →
  query plan → AdaptiveController) issuing at most the same request budget per
  topic, choosing its queries by marginal yield.

Both sides share ONE BM25Index instance over the identical corpus view, so the
engine is never a confound. Output: ``runs/<side>.jsonl`` (score_retrieval
format: topic_id/family_id/rank) + ``runs/meta-<side>.json`` (budget ledger,
engine params, snapshot hashes — the Audit Integrity evidence).

Preregistration: benchmarks/retrieval/gate.yaml — do not change parameters here
without re-registering. Same snapshot + same manifest + same code = same bytes.

Usage:
    python benchmarks/retrieval/run_benchmark.py --side baseline --split test
    python benchmarks/retrieval/run_benchmark.py --side extension --split test
    python benchmarks/retrieval/run_benchmark.py --side baseline --limit 3   # wiring smoke
"""

from __future__ import annotations

import argparse
import json
import hashlib
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))

TOPICS_MANIFEST = BASE / "topics" / "public" / "manifest.json"
CORPUS_DIR = BASE / "corpus" / "dapfam"
RUNS_DIR = BASE / "runs"
K_PER_REQUEST = 200
BUDGET_REQUESTS = 3  # gate.yaml: baseline fixed 3 / extension max 3
ENGINE_PARAMS = {"k1": 1.5, "b": 0.75, "k_per_request": K_PER_REQUEST}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def load_topics(split: str) -> list[dict]:
    manifest = json.loads(TOPICS_MANIFEST.read_text(encoding="utf-8"))
    return [t for t in manifest["topics"] if t.get("split") == split], manifest


def iter_corpus_docs(corpus_dir: Path):
    """Stream CorpusDoc over the frozen parquet (TAC view, description excluded)."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("[FATAL] pyarrow required: pip install pyarrow", file=sys.stderr)
        raise SystemExit(2)
    from patent_intel.retrieval.lexical import CorpusDoc
    table = pq.read_table(corpus_dir / "corpus.parquet",
                          columns=["relevant_id", "title_en", "abstract_en", "claims_text"])
    cols = table.to_pydict()
    del table
    print(f"[index-source] rows={len(cols['relevant_id'])}", file=sys.stderr, flush=True)
    for i in range(len(cols["relevant_id"])):
        text = " ".join(x for x in (cols["title_en"][i], cols["abstract_en"][i], cols["claims_text"][i]) if x)
        yield CorpusDoc(doc_id=cols["relevant_id"][i], text=text, family_id=cols["relevant_id"][i])


def topic_query_texts(topic: dict, queries_by_id: dict) -> dict[str, str]:
    """The three mechanical baseline request texts for one topic (preregistered)."""
    q = queries_by_id[topic["source_id"]]
    tac = " ".join(x for x in (q["title_en"], q["abstract_en"], q["claims_text"]) if x)
    ta = " ".join(x for x in (q["title_en"], q["abstract_en"]) if x)
    return {"tac": tac, "ta": ta, "claims": q["claims_text"] or ""}


def merge_rankings(score_maps: list[dict[str, float]], k: int) -> list[tuple[str, float]]:
    merged: dict[str, float] = {}
    for scores in score_maps:
        for doc_id, score in scores.items():
            if score > merged.get(doc_id, float("-inf")):
                merged[doc_id] = score
    ranked = sorted(merged.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:k]


def write_run(side: str, rows: list[dict], meta: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RUNS_DIR / f"{side}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    meta["side"] = side
    with open(RUNS_DIR / f"meta-{side}.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"[run] {side}: {len(rows)} entries, {meta['requests_total']} requests, "
          f"{meta['topics_run']} topics -> {RUNS_DIR / (side + '.jsonl')}")


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
    parser.add_argument("--side", choices=("baseline", "extension"), required=True)
    parser.add_argument("--split", default="test", choices=("train", "val", "test"))
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 个主题（布线冒烟，不进评测）")
    args = parser.parse_args()
    if args.limit and args.split != "test":
        raise SystemExit("--limit 仅用于 test 冒烟")

    try:
        import patent_intel  # noqa: F401
    except ImportError:
        print("[FATAL] patent_intel extension required (shared BM25 engine)", file=sys.stderr)
        return 3

    topics, manifest = load_topics(args.split)
    if args.limit:
        topics = topics[: args.limit]
    print(f"[topics] split={args.split} n={len(topics)}")

    try:
        import pyarrow.parquet as pq  # noqa: F401
    except ImportError:
        print("[FATAL] pyarrow required", file=sys.stderr)
        return 2

    print("[index] building shared BM25 index over frozen corpus (TAC view)…")
    t0 = time.time()
    from patent_intel.retrieval.lexical import BM25Index
    # NOTE: do NOT clear index.docs to save RAM — idf() derives corpus size N from
    # len(self.docs); an emptied docs dict floors every idf at 0.0 and silently
    # yields zero-hit searches (caught by the 1-topic smoke run: 45k docs, 0 entries).
    index = BM25Index(iter_corpus_docs(CORPUS_DIR), k1=ENGINE_PARAMS["k1"], b=ENGINE_PARAMS["b"])
    print(f"[index] {len(index)} docs in {time.time() - t0:.0f}s")

    qtable = pq.read_table(CORPUS_DIR / "queries.parquet",
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

    if args.side == "baseline":
        for n, topic in enumerate(topics, start=1):
            texts = topic_query_texts(topic, queries_by_id)
            score_maps = []
            for name in ("tac", "ta", "claims"):  # preregistered fixed variants
                hits = index.search(texts[name], k=K_PER_REQUEST)
                requests_total += 1
                score_maps.append(dict(hits))
            for rank, (fam, _score) in enumerate(merge_rankings(score_maps, K_PER_REQUEST), start=1):
                rows.append({"topic_id": topic["topic_id"], "family_id": fam, "rank": rank})
            if n % 50 == 0:
                print(f"  [baseline] {n}/{len(topics)} ({time.time() - t0:.0f}s)")
        meta = {"engine": "BM25Index", "engine_params": ENGINE_PARAMS, "requests_total": requests_total,
                "topics_run": len(topics), "budget": "3 fixed requests (tac/ta/claims)"}
    else:
        from patent_intel.retrieval.controller import AdaptiveController, RunOutcome
        from patent_intel.retrieval.features import extract_features
        from patent_intel.retrieval.query_plan import QueryPlanBuilder

        def run_topic(topic: dict) -> tuple[list[dict], int]:
            q = queries_by_id[topic["source_id"]]
            statements = [q["title_en"] or "", q["abstract_en"] or ""]
            statements += [c.strip() for c in (q["claims_text"] or "").splitlines() if c.strip()]
            bundle = extract_features(statements, axis_id=f"N1@{topic['topic_id']}",
                                      source_tag="dapfam-benchmark", approved=True)
            plan = QueryPlanBuilder().build(bundle)
            # gate.yaml declares benchmark-mode auto-approval: this evaluates the retrieval
            # layer, not the human-approval workflow — in workspace flows these plans stay
            # unapproved proposals (query_plan.py hard-codes approved=False).
            for query_spec in plan.queries:
                query_spec.approved = True
            pending = plan.approved_queries()
            if not pending:
                return [], 0
            score_maps: list[dict[str, float]] = []
            executed = 0

            def runner(query_spec):  # injected search executor (offline BM25)
                nonlocal executed
                executed += 1
                hits = index.search(" ".join(query_spec.terms), k=K_PER_REQUEST)
                score_maps.append(dict(hits))
                return RunOutcome(query_id=query_spec.query_id,
                                  hits=[h[0] for h in hits], families=[h[0] for h in hits],
                                  cost=1.0)

            controller = AdaptiveController(runner, max_requests=BUDGET_REQUESTS, max_cost=float(BUDGET_REQUESTS))
            report = controller.run_plan(pending)
            merged = merge_rankings(score_maps, K_PER_REQUEST)
            return [{"topic_id": topic["topic_id"], "family_id": fam, "rank": rank}
                    for rank, (fam, _score) in enumerate(merged, start=1)], executed

        for n, topic in enumerate(topics, start=1):
            topic_rows, used = run_topic(topic)
            rows.extend(topic_rows)
            requests_total += used
            if n % 20 == 0:
                print(f"  [extension] {n}/{len(topics)} ({time.time() - t0:.0f}s)")
        meta = {"engine": "BM25Index", "engine_params": ENGINE_PARAMS, "requests_total": requests_total,
                "topics_run": len(topics),
                "budget": f"AdaptiveController max {BUDGET_REQUESTS} requests/topic",
                "patent_intel_version": patent_intel.__version__}

    meta.update({
        "snapshot_sha256": {p.name: sha256_file(CORPUS_DIR / p.name) for p in sorted(CORPUS_DIR.glob("*.parquet"))},
        "manifest_sha256": sha256_file(TOPICS_MANIFEST),
        "gate_yaml_sha256": sha256_file(BASE / "gate.yaml"),
        "split": args.split,
        "elapsed_seconds": round(time.time() - t0, 1),
        "network_requests": 0,
    })
    write_run(args.side, rows, meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
