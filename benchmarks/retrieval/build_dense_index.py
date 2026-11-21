#!/usr/bin/env python3
"""DE1 (4.3) persistent dense embedding index builder for the frozen DAPFAM corpus.

Streams ``benchmarks/retrieval/corpus/dapfam/corpus.parquet`` (parquet column
projection — claims/description are never read unless requested), embeds the
selected fields with **snowflake-arctic-embed-m-v2.0** via fastembed ONNX
(G3 route B), and writes a float32 matrix + ids (``.npz``) with a sidecar
manifest JSON to ``E:/tmp-pk/dense-idx/`` by default.

Index artifacts are runtime outputs and never enter git. The corpus directory is
gitignored per the DAPFAM license boundary (CC-BY-NC-SA-4.0): ``--corpus``
overrides everything; otherwise a worktree-local frozen copy is used when
present, else the read-only frozen snapshot held by the quality worktree.

No model download happens here: fastembed runs ``local_files_only`` against the
local weights snapshot (default
``F:\\GitHub项目合集\\专利调研与润色\\_models\\snowflake-arctic-embed-m-v2.0``,
override with ``PATENT_INTEL_DENSE_MODEL_DIR``). A missing/failed snapshot aborts
with materialization instructions instead of touching the network.

Usage:
    python benchmarks/retrieval/build_dense_index.py --limit 5000 --index-name dense-smoke-5000
    python benchmarks/retrieval/build_dense_index.py --full
    python benchmarks/retrieval/build_dense_index.py --full --corpus <path>/corpus.parquet

Subset selection (``--limit N``) is deterministic without RNG: the N evenly
spaced row indices over parquet file order (``int(i * total / N)``), documented
in the manifest. ``--full`` embeds every row.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(REPO_ROOT / "extensions" / "patent_intel" / "src"))

from patent_intel.retrieval.hybrid import (  # noqa: E402  (path set above)
    DENSE_FASTEMBED_ALIAS,
    DENSE_MODEL_ID,
    DenseIndex,
    DenseRetriever,
)

DEFAULT_OUT_DIR = Path(r"E:/tmp-pk/dense-idx")
DEFAULT_CORPUS = BASE / "corpus" / "dapfam" / "corpus.parquet"
FIELD_COLUMNS = {
    "title": "title_en",
    "abstract": "abstract_en",
    "claims": "claims_text",
    "description": "description_en",
}
# Read-only frozen snapshot (main-session environment fact): corpus/ is
# gitignored in every worktree, so the shared snapshot in the quality worktree
# is the default fallback when no worktree-local copy exists.
FROZEN_CORPUS = Path(
    "F:/GitHub项目合集/专利调研与润色/_wt-quality/benchmarks/retrieval/corpus/dapfam/corpus.parquet"
)


def resolve_corpus(explicit: str | None) -> Path:
    """Resolve the corpus parquet: ``--corpus`` override wins; then the
    worktree-local frozen copy if present; finally the read-only frozen
    snapshot (consumed read-only — never written)."""
    if explicit:
        return Path(explicit)
    if DEFAULT_CORPUS.is_file():
        return DEFAULT_CORPUS
    return FROZEN_CORPUS


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def parse_fields(raw: str) -> list[str]:
    fields = [f.strip().lower() for f in raw.split(",") if f.strip()]
    if not fields:
        raise SystemExit("[FATAL] --fields must name at least one of: " + ", ".join(FIELD_COLUMNS))
    unknown = [f for f in fields if f not in FIELD_COLUMNS]
    if unknown:
        raise SystemExit(f"[FATAL] unknown field(s) {unknown}; choose from: {list(FIELD_COLUMNS)}")
    return fields


def select_rows(total: int, limit: int, full: bool) -> tuple[str, list[int] | None]:
    """Return (selector_description, sorted row indices or None for all rows)."""
    if full:
        return "all rows", None
    if limit <= 0:
        raise SystemExit("[FATAL] give --limit N or --full (refusing to guess a subset)")
    if limit >= total:
        return f"all rows (limit {limit} >= total {total})", None
    # Deterministic evenly spaced sample over file order — no RNG involved.
    selected = sorted({min(total - 1, int(i * total / limit)) for i in range(limit)})
    return f"evenly-spaced stride over file order ({len(selected)} of {total} rows)", selected


def stream_texts(corpus: Path, fields: list[str], selected: list[int] | None):
    """Yield (relevant_id, text) for the selected rows, streaming the parquet.

    Column projection keeps description/claims out of memory unless requested.
    """
    try:
        import pyarrow.parquet as pq
    except ImportError:
        raise SystemExit("[FATAL] pyarrow required: pip install pyarrow") from None
    columns = ["relevant_id"] + [FIELD_COLUMNS[f] for f in fields]
    pf = pq.ParquetFile(corpus)
    wanted = set(selected) if selected is not None else None
    pointer = 0  # global row index (iter_batches preserves file order)
    for batch in pf.iter_batches(batch_size=4096, columns=columns):
        cols = batch.to_pydict()
        for j in range(batch.num_rows):
            if wanted is None or pointer in wanted:
                text = " ".join(x for x in (cols[c][j] for c in columns[1:]) if x)
                yield cols["relevant_id"][j], text
            pointer += 1


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
    parser.add_argument("--corpus", default=None,
                        help="frozen corpus.parquet (read-only); default: worktree-local copy, "
                             "else the frozen snapshot")
    parser.add_argument("--limit", type=int, default=0, help="deterministic evenly-spaced subset of N rows")
    parser.add_argument("--full", action="store_true", help="embed every corpus row")
    parser.add_argument("--fields", default="title,abstract",
                        help="comma list from: title,abstract,claims,description")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--index-name", default=None, help="defaults to dense-limit<N> / dense-full")
    parser.add_argument("--batch-size", type=int, default=16,
                        help="fastembed batch size (16 tuned on this CPU: sorted-length batches)")
    parser.add_argument("--chunk", type=int, default=2048,
                        help="documents per encode pass (progress granularity)")
    parser.add_argument("--threads", type=int, default=8,
                        help="onnxruntime session threads (0 = onnxruntime default)")
    args = parser.parse_args()

    corpus = resolve_corpus(args.corpus)
    if not corpus.is_file():
        raise SystemExit(
            f"[FATAL] corpus not found: {corpus}\n"
            "The corpus directory is gitignored (CC-BY-NC-SA-4.0); point --corpus at a "
            f"worktree holding the frozen snapshot, e.g. {FROZEN_CORPUS}"
        )
    fields = parse_fields(args.fields)
    index_name = args.index_name or ("dense-full" if args.full else f"dense-limit{args.limit}")

    # Resolve the backend BEFORE touching the 1 GB parquet: a missing weights
    # snapshot must abort here with materialization instructions (never download).
    retriever = DenseRetriever(threads=args.threads if args.threads > 0 else None,
                               batch_size=max(1, args.batch_size))
    t_warm = time.perf_counter()
    retriever.encode_query("warmup")  # fail fast; excluded from build_seconds
    print(f"[model] {DENSE_MODEL_ID} loaded from {retriever.model_dir} "
          f"({time.perf_counter() - t_warm:.1f}s, local_files_only — nothing downloaded)", flush=True)

    import pyarrow.parquet as pq

    total = pq.ParquetFile(corpus).metadata.num_rows
    t0 = time.perf_counter()
    corpus_sha = sha256_file(corpus)
    print(f"[corpus] {corpus} rows={total} sha256={corpus_sha[:16]}… "
          f"({time.perf_counter() - t0:.1f}s)", flush=True)

    selector, selected = select_rows(total, args.limit, args.full)

    import numpy as np

    ids: list[str] = []
    texts: list[str] = []
    t0 = time.perf_counter()
    for doc_id, text in stream_texts(corpus, fields, selected):
        ids.append(doc_id)
        texts.append(text)
    read_seconds = time.perf_counter() - t0
    print(f"[read] {len(ids)} rows selected ({selector}) in {read_seconds:.1f}s", flush=True)

    matrix = None
    t_embed = time.perf_counter()
    chunk = max(1, args.chunk)
    for start in range(0, len(texts), chunk):
        stop = min(start + chunk, len(texts))
        chunk_texts = texts[start:stop]
        # Length-sorted batches cut ONNX padding waste (~2.5x on this corpus);
        # results are mapped back to file order, so ids stay deterministic.
        order = sorted(range(len(chunk_texts)), key=lambda i: len(chunk_texts[i]))
        part_sorted = retriever.encode_documents([chunk_texts[i] for i in order],
                                                 batch_size=max(1, args.batch_size))
        if matrix is None:
            matrix = np.zeros((len(texts), part_sorted.shape[1]), dtype=np.float32)
        part = np.empty_like(part_sorted)
        for pos, idx in enumerate(order):
            part[idx] = part_sorted[pos]
        matrix[start:stop] = part
        rate = stop / max(1e-9, time.perf_counter() - t_embed)
        eta = (len(texts) - stop) / max(1e-9, rate)
        print(f"[embed] {stop}/{len(texts)} ({rate:.0f} docs/s, ETA {eta / 60:.1f} min)", flush=True)
    if matrix is None:
        matrix = np.zeros((0, 0), dtype=np.float32)
    build_seconds = time.perf_counter() - t_embed

    index = DenseIndex(
        ids=ids,
        vectors=matrix,
        model_id=DENSE_MODEL_ID,
        corpus_sha256=corpus_sha,
        encoder=retriever.encode_query,
    )
    manifest = index.save(
        args.out_dir,
        index_name,
        extra={
            "corpus_file": str(corpus),
            "corpus_rows_total": total,
            "row_selector": selector,
            "fields": fields,
            "field_columns": [FIELD_COLUMNS[f] for f in fields],
            "build_seconds": build_seconds,
            "read_seconds": read_seconds,
            "mode": "full" if args.full else "limit",
            "batch_size": args.batch_size,
            "threads": args.threads,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model_dir": str(retriever.model_dir),
            "model_source": "local snapshot via fastembed specific_model_path "
                            "(local_files_only=True; zero downloads)",
            "fastembed_alias": DENSE_FASTEMBED_ALIAS,
        },
    )
    manifest_path = Path(args.out_dir) / f"{index_name}.manifest.json"
    print("[done] index  :", manifest["index_file"], "sha256", manifest["index_sha256"][:16] + "…", flush=True)
    print("[done] manifest:", manifest_path, flush=True)
    print("[done] manifest sha256:", sha256_file(manifest_path), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
