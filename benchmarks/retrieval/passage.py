"""Passage chunking and family-level aggregation (4.3 P0-GAP).

Gap-closure basis: the DAPFAM reference results (Ayaou et al., 2025,
arXiv:2506.22141) show passage-level BM25 consistently outperforming
document-level (best OUT recall@100 0.1521 passage vs 0.1368 doc), with the
OUT-recall-bearing content living in long full-text passages. Our 4.2 baseline
indexes a TAC document view and scores OUT at 0.0 — this module supplies the
two missing pieces:

* :func:`chunk_words` — deterministic fixed-size word chunking with a stride,
  approximating the paper's token windows (8192 BPE tokens ≈ 6100 English
  words at ~0.75 words/token; the conversion is recorded in every report);
* :func:`aggregate_passage_hits` — fold passage-level BM25 hits back to family
  rankings via maxP (paper: best BM25 aggregator) or avg_top3 (paper: best
  dense aggregator, kept for the 4.3 dense step).

Determinism: chunk boundaries depend only on the input text and parameters;
aggregation breaks score ties by family id ascending. No I/O, no model, no
network.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

__all__ = ["chunk_words", "aggregate_passage_hits", "WORDS_PER_TOKEN_DOC_NOTE"]

# The paper's best BM25 window is 8192 BPE tokens. English patent text runs
# ~0.75 words per token, so the window ≈ 6144 words; we round to 6100 words and
# record the approximation in every smoke report (no tokenizer dependency).
WORDS_PER_TOKEN_DOC_NOTE = "8192 BPE tokens ≈ 6100 words at ~0.75 words/token (approximation, no tokenizer)"


def chunk_words(
    text: str,
    *,
    max_words: int = 6100,
    stride: int | None = None,
    min_words: int = 50,
) -> list[str]:
    """Split ``text`` into deterministic word chunks.

    ``stride`` defaults to ``max_words`` (non-overlapping chunks) — the smoke
    configuration; a smaller stride yields overlapping windows like the paper's
    setup at double the passage count. Chunks shorter than ``min_words`` are
    dropped (paper: consistent filtering), except that a document's only chunk
    is always kept. Empty/whitespace input yields ``[]``.
    """
    if max_words <= 0:
        raise ValueError("max_words must be positive")
    if stride is None:
        stride = max_words
    if stride <= 0 or stride > max_words:
        raise ValueError("stride must be in (0, max_words]")
    words = text.split()
    if not words:
        return []
    # A full-size window must never be filtered: clamp the floor to max_words so
    # small-window/strided configurations don't have every chunk eaten by the
    # default tail filter (paper intent: drop tiny trailing fragments only).
    min_words = min(min_words, max_words)
    chunks: list[str] = []
    start = 0
    while start < len(words):
        piece = words[start : start + max_words]
        if len(piece) >= min_words or start == 0:
            chunks.append(" ".join(piece))
        if start + max_words >= len(words):
            break
        start += stride
    return chunks


def aggregate_passage_hits(
    hits: Iterable[tuple[str, float]],
    *,
    method: str = "maxp",
) -> list[tuple[str, float]]:
    """Fold passage-level hits (``family#pNNNN`` doc ids) into family rankings.

    ``maxp`` keeps each family's best passage score; ``avg_top3`` averages the
    family's top-3 passage scores (families with fewer passages use what they
    have). Output is sorted by score descending, ties by family id ascending —
    the same tie discipline as the engine. Input need not be pre-sorted.
    """
    if method not in ("maxp", "avg_top3"):
        raise ValueError(f"unknown aggregation method: {method!r}")
    by_family: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for passage_id, score in hits:
        family, sep, _part = passage_id.partition("#")
        if not sep:  # defensive: a non-passage id is its own family
            family = passage_id
        by_family[family].append((score, passage_id))
    out: list[tuple[str, float]] = []
    for family, scored in by_family.items():
        scored.sort(key=lambda x: (-x[0], x[1]))
        if method == "maxp":
            value = scored[0][0]
        else:  # avg_top3
            top = scored[:3]
            value = sum(s for s, _ in top) / len(top)
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            raise ValueError(f"non-finite aggregate score for family {family!r}")
        out.append((family, value))
    out.sort(key=lambda x: (-x[1], x[0]))
    return out
