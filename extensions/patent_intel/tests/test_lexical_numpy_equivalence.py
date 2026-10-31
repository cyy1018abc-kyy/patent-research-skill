"""4.1-A1: BM25 numpy fast path must be bit-identical to the pure-Python path.

The vectorized path exists for full-text corpora (24x measured speedup on 45k
docs); a rank or score divergence between the paths would silently change every
benchmark number, so equivalence is locked here on a deterministic synthetic
corpus — and on real data by the Phase V runner's archived smoke comparisons.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from patent_intel.retrieval.lexical import BM25Index, CorpusDoc

pytest.importorskip("numpy", reason="numpy fast path is the subject of this module")

_VOCAB = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "sensor", "device",
    "method", "apparatus", "measuring", "array", "calibration", "wireless",
    "protocol", "latency", "throughput", "encoder", "thermal", "optical",
]


def _synthetic_docs(n: int = 160) -> list[CorpusDoc]:
    docs = []
    for i in range(n):
        words = [_VOCAB[(i * 7 + j * 3) % len(_VOCAB)] for j in range(4 + (i % 9))]
        if i % 5 == 0:
            words.append("raretoken%03d" % i)  # near-unique terms exercise idf flooring
        docs.append(CorpusDoc(doc_id=f"D{i:04d}", text=" ".join(words) + " measuring device"))
    return docs


def _build_pair(force_py_env: bool) -> tuple[BM25Index, BM25Index]:
    docs = _synthetic_docs()
    idx_fast = BM25Index(docs)
    old = os.environ.get("PATENT_INTEL_BM25_FORCE_PY")
    if force_py_env:
        os.environ["PATENT_INTEL_BM25_FORCE_PY"] = "1"
    try:
        idx_py = BM25Index(docs)
    finally:
        if force_py_env:
            if old is None:
                os.environ.pop("PATENT_INTEL_BM25_FORCE_PY", None)
            else:
                os.environ["PATENT_INTEL_BM25_FORCE_PY"] = old
    return idx_fast, idx_py


_QUERIES = [
    "alpha measuring device",
    "beta gamma sensor array calibration",
    "the device method throughput",
    "raretoken007 raretoken042 wireless protocol",
    "zzz absent tokens only",
    "",
]


def test_numpy_path_identical_to_python_path() -> None:
    idx_fast, idx_py = _build_pair(force_py_env=True)
    assert idx_fast._np is not None and idx_py._np is None
    for query in _QUERIES:
        assert idx_fast.search(query, k=200) == idx_py.search(query, k=200), query


def test_numpy_ties_order_by_doc_id() -> None:
    docs = [CorpusDoc(doc_id=f"D{i}", text="same words everywhere identical") for i in range(6)]
    idx = BM25Index(docs)
    ranked = idx.search("same identical", k=6)
    assert [d for d, _s in ranked] == sorted(d for d, _s in ranked)


def test_explain_matches_between_paths(tmp_path: Path) -> None:
    idx_fast, idx_py = _build_pair(force_py_env=True)
    for doc_id in ("D0000", "D0007"):
        for query in _QUERIES[:3]:
            assert idx_fast.explain(doc_id, query) == idx_py.explain(doc_id, query)


def test_force_py_env_hides_numpy_path() -> None:
    os.environ["PATENT_INTEL_BM25_FORCE_PY"] = "1"
    try:
        idx = BM25Index(_synthetic_docs(20))
        assert idx._np is None
    finally:
        os.environ.pop("PATENT_INTEL_BM25_FORCE_PY", None)
