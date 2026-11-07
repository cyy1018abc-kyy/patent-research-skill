#!/usr/bin/env python3
"""Mine cross-domain co-occurrence terms from train/val topics (roadmap 41A-3).

Reads the frozen topic manifest, the queries parquet (topic seed text) and the
frozen corpus parquet, mines corpus co-occurrence via
``patent_intel.retrieval.cooccurrence.CooccurrenceMiner`` and writes
``topics/public/cooccurrence.json`` — a deterministic, digest-stamped mining
table the CrossDomainExpander consumes at plan time.

Leakage discipline (hard, not convention):

* ``--splits`` accepts only ``train`` / ``val`` — a test request is refused
  before anything is read;
* mining input = topic TEXT of the selected topics + corpus snapshot; gold
  families are never read here (not even train-side gold);
* the miner itself re-validates every topic's split label, and
  ``check_leakage.py --cooccurrence`` re-checks the written artifact against
  the manifest (test topic ids mixed into the mining input = exit 1).

Same manifest + same parquet snapshot + same parameters ⇒ same artifact bytes
(no wall-clock anywhere in the output; the manifest's own source-snapshot
hashes are carried into the artifact provenance).

Usage:
    python benchmarks/retrieval/mine_cooccurrence.py --splits train,val
    python benchmarks/retrieval/mine_cooccurrence.py --splits train --limit 20   # wiring smoke
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
TOPICS_MANIFEST = BASE / "topics" / "public" / "manifest.json"
CORPUS_DIR = BASE / "corpus" / "dapfam"
OUT_PATH = BASE / "topics" / "public" / "cooccurrence.json"

#: mining seed view: title + abstract of the topic's own query (claims excluded:
#: boilerplate legalese would flood the seed token space; TAC remains the scored
#: query view — mining seeds are train-side data preparation, not scored requests)
SEED_VIEW = "title_en+abstract_en"
ALLOWED_MINING_SPLITS = ("train", "val")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def load_topic_texts(queries_path: Path) -> dict[str, str]:
    """source_id -> seed text (title + abstract) from the frozen queries parquet."""
    import pyarrow.parquet as pq

    table = pq.read_table(queries_path, columns=["query_id", "title_en", "abstract_en"])
    cols = table.to_pydict()
    del table
    texts: dict[str, str] = {}
    for i in range(len(cols["query_id"])):
        parts = [cols["title_en"][i] or "", cols["abstract_en"][i] or ""]
        text = " ".join(part.strip() for part in parts if part and part.strip())
        if text:
            texts[cols["query_id"][i]] = text
    return texts


def iter_corpus_docs(corpus_dir: Path):
    """Stream CorpusDoc over the frozen parquet (TAC view, description excluded)."""
    import pyarrow.parquet as pq

    from patent_intel.retrieval.lexical import CorpusDoc

    table = pq.read_table(corpus_dir / "corpus.parquet",
                          columns=["relevant_id", "title_en", "abstract_en", "claims_text"])
    cols = table.to_pydict()
    del table
    print(f"[index-source] rows={len(cols['relevant_id'])}", file=sys.stderr, flush=True)
    for i in range(len(cols["relevant_id"])):
        text = " ".join(x for x in (cols["title_en"][i], cols["abstract_en"][i], cols["claims_text"][i]) if x)
        yield CorpusDoc(doc_id=cols["relevant_id"][i], text=text, family_id=cols["relevant_id"][i])


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
    parser.add_argument("--manifest", type=Path, default=TOPICS_MANIFEST)
    parser.add_argument("--corpus-dir", type=Path, default=CORPUS_DIR)
    parser.add_argument("--queries", type=Path, default=None,
                        help="queries parquet（默认 <corpus-dir>/queries.parquet）")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--splits", default="train,val",
                        help="挖掘输入的 split（仅允许 train/val；test 会被拒绝）")
    parser.add_argument("--min-cooccurrence", type=int, default=2)
    parser.add_argument("--min-lift", type=float, default=2.0)
    parser.add_argument("--min-df", type=int, default=2)
    parser.add_argument("--max-df-ratio", type=float, default=0.05)
    parser.add_argument("--max-terms-per-seed", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="每 split 前 N 个主题（wiring smoke，不进评测）")
    args = parser.parse_args()

    splits = tuple(s.strip() for s in args.splits.split(",") if s.strip())
    if not splits:
        print("[FATAL] --splits 为空；须显式声明挖掘 split", file=sys.stderr)
        return 2
    for split in splits:
        if split not in ALLOWED_MINING_SPLITS:
            print(f"[FATAL] split {split!r} 不允许进入挖掘输入（允许 {ALLOWED_MINING_SPLITS}）"
                  "——test 主题永远不得参与挖掘", file=sys.stderr)
            return 2

    try:
        from patent_intel.retrieval.cooccurrence import (
            CooccurrenceMiner,
            MiningInputError,
            MiningParams,
            TopicSeed,
        )
    except ImportError as exc:
        print(f"[FATAL] missing dependency: {exc} "
              f"(hint: PYTHONPATH=<repo>/extensions/patent_intel/src)", file=sys.stderr)
        return 2

    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    queries_path = args.queries or (args.corpus_dir / "queries.parquet")

    topics_by_split: dict[str, list[dict]] = {}
    for topic in manifest["topics"]:
        split = topic.get("split")
        if split in splits:
            topics_by_split.setdefault(split, []).append(topic)

    seeds: list[TopicSeed] = []
    skipped = 0
    texts = load_topic_texts(queries_path)
    for split in splits:
        taken = 0
        for topic in topics_by_split.get(split, []):
            if args.limit and taken >= args.limit:
                break
            text = texts.get(topic.get("source_id"), "")
            if not text:
                skipped += 1  # query text absent in the frozen parquet — recorded, never faked
                continue
            seeds.append(TopicSeed(topic_id=topic["topic_id"], split=split, text=text))
            taken += 1
    if not seeds:
        print("[FATAL] 挖掘输入为空（所选 split 无带文本的主题）；拒绝生成空表", file=sys.stderr)
        return 2

    params = MiningParams(
        min_cooccurrence=args.min_cooccurrence,
        min_lift=args.min_lift,
        min_df=args.min_df,
        max_df_ratio=args.max_df_ratio,
        max_terms_per_seed=args.max_terms_per_seed,
    )
    try:
        table = CooccurrenceMiner(params).mine(seeds, iter_corpus_docs(args.corpus_dir), splits=splits)
    except MiningInputError as exc:
        print(f"[FATAL] 挖掘输入被拒绝: {exc}", file=sys.stderr)
        return 2

    artifact = table.to_dict()
    artifact["provenance"] = {
        "generated_by": "benchmarks/retrieval/mine_cooccurrence.py",
        "suite": manifest.get("suite"),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "manifest_file": args.manifest.name,
        "source_snapshot": manifest.get("source_snapshot", {}),
        "seed_view": SEED_VIEW,
        "limit": args.limit,
        "skipped_topics": skipped,
    }
    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(artifact, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    n_terms = sum(len(entries) for entries in table.entries.values())
    print(f"[cooccurrence] splits={list(table.splits)} topics={len(table.topic_ids)} "
          f"(skipped={skipped}) corpus_docs={table.corpus_docs} seeds={len(table.entries)} terms={n_terms}")
    print(f"[cooccurrence] digest={table.digest[:16]} params={json.dumps(params.to_dict())}")
    print(f"[cooccurrence] {out}")
    print("[next] python benchmarks/retrieval/check_leakage.py --manifest "
          f"{args.manifest} --cooccurrence {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
