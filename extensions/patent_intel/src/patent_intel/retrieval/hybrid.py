"""Hybrid ranking: RRF fusion and family-aware collapse (blueprint A-04).

* :func:`rrf_fuse` — Reciprocal Rank Fusion over multiple ranked lists, fully
  deterministic (ties by stable key order).
* :func:`family_collapse` — one family occupies one ranking slot; same-family
  documents never masquerade as independent hits (UT-S03 / interface rule 4).
* :class:`DenseRetriever` — optional (`dense` extra); degrades with an honest
  error naming the missing dependency. No model download happens implicitly.
"""

from __future__ import annotations

from typing import Any

__all__ = ["rrf_fuse", "family_collapse", "DenseRetriever"]


def rrf_fuse(rankings: dict[str, list[str]], *, k: int = 60, top: int | None = None) -> list[tuple[str, float]]:
    """Fuse named rankings into one list by RRF: score = Σ 1/(k + rank_i).

    Deterministic: equal fused scores break by doc id ascending; input list order
    is also a tiebreaker (dict insertion order), so identical inputs give identical
    outputs (UT-R01).
    """
    if k <= 0:
        raise ValueError("k must be positive")
    scores: dict[str, float] = {}
    for source_name in rankings:
        for rank, doc_id in enumerate(rankings[source_name], start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    fused = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return fused[:top] if top else fused


def family_collapse(
    ranked: list[tuple[str, float]],
    family_of: dict[str, str],
) -> list[tuple[str, float]]:
    """Collapse ranked docs to one representative per family (best position kept).

    Docs without a family mapping stay independent — unknown family relations are
    never invented here (that merging belongs to kernel census, G-S-04).
    """
    seen_families: set[str] = set()
    out: list[tuple[str, float]] = []
    for doc_id, score in ranked:
        family = family_of.get(doc_id)
        if family is not None:
            if family in seen_families:
                continue
            seen_families.add(family)
        out.append((doc_id, score))
    return out


class DenseRetriever:
    """Optional dense retrieval. Requires the `dense` extra; no implicit downloads."""

    def __init__(self, model_id: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_id = model_id
        self._model: Any = None

    def _require_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "dense retrieval requires the optional 'dense' extra: "
                    "pip install 'patent_intel[dense]' (installs numpy+sentence-transformers); "
                    "until then ranking degrades to BM25-only"
                ) from exc
            self._model = SentenceTransformer(self.model_id)
        return self._model

    def rank(self, query: str, docs: list[tuple[str, str]], *, top: int = 10) -> list[tuple[str, float]]:
        """Rank (doc_id, text) pairs by cosine similarity. Deterministic per model."""
        import numpy as np  # provided by the dense extra

        model = self._require_model()
        doc_ids = [d[0] for d in docs]
        embeddings = model.encode([query] + [d[1] for d in docs], normalize_embeddings=True)
        q = np.asarray(embeddings[0])
        matrix = np.asarray(embeddings[1:])
        sims = matrix @ q
        order = sorted(range(len(doc_ids)), key=lambda i: (-float(sims[i]), doc_ids[i]))
        return [(doc_ids[i], float(sims[i])) for i in order[:top]]
