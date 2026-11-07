"""Fixed-query-set regression for the V2 ladder semantics (4.2 / W4-EVAL).

Locks the exact ranking bytes of the preregistered request-construction and
merge semantics (protocol-prereg-v2.md §3) on a tiny synthetic corpus:
V2-0 mechanical max-merge, V2-1 feature-request max-merge, V2-2 RRF fusion.
Any engine or merge-order drift breaks these literals — exactly the point.
Cross-domain expansion (V2-3) is gated on the mining artifact and stays in the
benchmark harness (see run_v2_ladder.py); this file pins the shared semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from patent_intel.retrieval.lexical import BM25Index, CorpusDoc

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "benchmarks" / "retrieval"))

run_benchmark = pytest.importorskip("run_benchmark")  # noqa: E402  (benchmarks helper module)
run_ablation = pytest.importorskip("run_ablation")  # noqa: E402

_DOCS = [
    ("FAM-90001", "frame sync timing marker"),
    ("FAM-90002", "frame sync protocol handshake"),
    ("FAM-90003", "timing recovery loop filter"),
    ("FAM-90004", "water pump pressure valve"),
    ("FAM-90005", "chemical composition catalyst"),
    ("FAM-90006", "frame timing drift"),
]
_TOPICS = [
    {"topic_id": "TP-9001", "source_id": "q1"},
    {"topic_id": "TP-9002", "source_id": "q2"},
]
_QUERIES = {
    "q1": {"title_en": "frame sync timing", "abstract_en": "", "claims_text": ""},
    "q2": {"title_en": "catalyst", "abstract_en": "chemical composition", "claims_text": "catalyst composition"},
}

#: recorded 2026-11-07 from the preregistered semantics on the corpus above
_EXPECTED = {
    "V2-0": [
        {"topic_id": "TP-9001", "family_id": "FAM-90001", "rank": 1},
        {"topic_id": "TP-9001", "family_id": "FAM-90002", "rank": 2},
        {"topic_id": "TP-9001", "family_id": "FAM-90006", "rank": 3},
        {"topic_id": "TP-9001", "family_id": "FAM-90003", "rank": 4},
        {"topic_id": "TP-9002", "family_id": "FAM-90005", "rank": 1},
    ],
    "V2-1": [
        {"topic_id": "TP-9001", "family_id": "FAM-90001", "rank": 1},
        {"topic_id": "TP-9001", "family_id": "FAM-90002", "rank": 2},
        {"topic_id": "TP-9001", "family_id": "FAM-90006", "rank": 3},
        {"topic_id": "TP-9001", "family_id": "FAM-90003", "rank": 4},
        {"topic_id": "TP-9002", "family_id": "FAM-90005", "rank": 1},
    ],
    "V2-2": [
        {"topic_id": "TP-9001", "family_id": "FAM-90001", "rank": 1},
        {"topic_id": "TP-9001", "family_id": "FAM-90002", "rank": 2},
        {"topic_id": "TP-9001", "family_id": "FAM-90006", "rank": 3},
        {"topic_id": "TP-9001", "family_id": "FAM-90003", "rank": 4},
        {"topic_id": "TP-9002", "family_id": "FAM-90005", "rank": 1},
    ],
}


def _index() -> BM25Index:
    return BM25Index(
        [CorpusDoc(doc_id=d, text=t, family_id=d) for d, t in _DOCS],
        k1=1.5,
        b=0.75,
    )


def _rows(config: str) -> list[dict]:
    index = _index()
    rows: list[dict] = []
    for topic in _TOPICS:
        if config == "V2-0":
            texts = run_benchmark.topic_query_texts(topic, _QUERIES)
            score_maps = [dict(index.search(texts[name], k=5)) for name in ("tac", "ta", "claims")]
            merged = run_benchmark.merge_rankings(score_maps, 5)
        else:
            requests = run_ablation.feature_requests(topic, _QUERIES)
            if config == "V2-1":
                score_maps = [dict(index.search(" ".join(t), k=5)) for t in requests]
                merged = run_benchmark.merge_rankings(score_maps, 5)
            else:  # V2-2: RRF
                rankings = {
                    f"req{i}": [d for d, _ in index.search(" ".join(t), k=5)]
                    for i, t in enumerate(requests, start=1)
                }
                merged = run_ablation.rrf_merge(rankings, 5) if rankings else []
        for rank, (fam, _score) in enumerate(merged, start=1):
            rows.append({"topic_id": topic["topic_id"], "family_id": fam, "rank": rank})
    return rows


@pytest.mark.parametrize("config", ["V2-0", "V2-1", "V2-2"])
def test_v2_semantics_byte_regression(config: str) -> None:
    assert _rows(config) == _EXPECTED[config]


def test_v2_semantics_deterministic_across_instances() -> None:
    assert _rows("V2-2") == _rows("V2-2")
