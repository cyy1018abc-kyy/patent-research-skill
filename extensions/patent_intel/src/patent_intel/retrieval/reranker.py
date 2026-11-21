"""Reranking interface (adaptive roadmap WP-L2 / Phase 4 stage 2).

Phase 4 ordering: per-channel RRF fusion → family collapse → **rerank of the fused
top-N**. This module defines the contract, the deterministic default, and (4.3,
G3-ruled) a model-backed Cross-Encoder implementation for the evaluation lane.

Discipline:

* a reranker reorders the candidates it was given — it never invents or drops
  candidates (documented contract; the pipeline splices only the top segment back);
* a failing reranker degrades to the pre-rerank ranking with the error recorded —
  degradation is visible in the fusion account, never silent;
* rerank scores are ranking signals, not evidence strengths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

__all__ = ["Reranker", "IdentityReranker", "CrossEncoderReranker", "RerankAccount", "empty_rerank_account"]

_OWNER = "WP-A"


class Reranker(Protocol):
    """Reorder fused candidates for one query.

    Contract: ``candidates`` is the fused (family-collapsed) top-N as
    ``(doc_id, fused_score)`` pairs; the return value must reorder the *same*
    candidates — same ids, same length. Scores in the return value are advisory;
    the pipeline keeps the fused score of untouched tail segments.
    """

    name: str

    def rerank(
        self, query: str, candidates: list[tuple[str, float]]
    ) -> list[tuple[str, float]]: ...


@dataclass(frozen=True)
class IdentityReranker:
    """Order-preserving no-op — the deterministic default and honest fallback."""

    name: str = "identity"

    def rerank(
        self, query: str, candidates: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        return list(candidates)


class CrossEncoderReranker:
    """Model-backed cross-encoder reranker (4.3 CE1; model ruled at G3-2:
    BAAI/bge-reranker-v2-m3, Apache-2.0, weights materialized offline in
    ``_models/`` — evaluation-lane implementation; the shipped-skill rerank path
    stays ``identity`` until an ONNX lane exists, so import failure here is an
    honest RuntimeError, never a silent downgrade).

    Contract notes:

    * ``texts`` maps doc_id → document text (e.g. title+abstract). A candidate
      with no text is a corpus/manifest mismatch: raise loudly (the fusion
      pipeline records the error and keeps the pre-rerank order) instead of
      silently reshuffling half the list.
    * Ordering: score descending, ties by doc_id ascending — same tie
      discipline as the engine; identical inputs give identical outputs.
    * No network: weights are loaded from the local path only
      (``HF_HUB_OFFLINE`` is forced in this process scope).
    """

    def __init__(
        self,
        texts: Mapping[str, str],
        *,
        model_path: str | Path = Path("F:/GitHub项目合集/专利调研与润色/_models/bge-reranker-v2-m3"),
        max_length: int = 512,
        device: str | None = None,
        batch_size: int = 8,
    ) -> None:
        self._texts = dict(texts)
        self._model_path = Path(model_path)
        self._max_length = max_length
        self._device = device
        self._batch_size = batch_size
        self._model: Any = None
        self.name = f"cross-encoder:{self._model_path.name}"

    def _require_model(self) -> Any:
        if self._model is None:
            if not self._model_path.is_dir():
                raise RuntimeError(
                    f"cross-encoder weights missing: {self._model_path} — materialize offline "
                    "(huggingface_hub snapshot_download via hf-mirror) or point the model_path "
                    "at an existing local snapshot; no implicit download happens here"
                )
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "CrossEncoderReranker requires the evaluation lane runtime "
                    "(torch + sentence-transformers); the shipped skill path stays "
                    "identity — install into the eval venv only"
                ) from exc
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            self._model = CrossEncoder(
                str(self._model_path),
                max_length=self._max_length,
                device=self._device,
            )
        return self._model

    def rerank(
        self, query: str, candidates: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        if not candidates:
            return []
        missing = [doc_id for doc_id, _ in candidates if doc_id not in self._texts]
        if missing:
            raise ValueError(
                f"rerank text provider missing {len(missing)} candidate(s), "
                f"first: {missing[0]!r} — corpus/manifest mismatch, refusing to reorder"
            )
        model = self._require_model()
        pairs = [(query, self._texts[doc_id]) for doc_id, _ in candidates]
        scores = model.predict(
            pairs,
            batch_size=self._batch_size,
            show_progress_bar=False,
        )
        scored = sorted(
            ((doc_id, float(score)) for (doc_id, _), score in zip(candidates, scores)),
            key=lambda x: (-x[1], x[0]),
        )
        return scored


@dataclass(frozen=True)
class RerankAccount:
    """What the rerank stage actually did for one query (always recorded)."""

    reranker: str | None
    applied: bool
    error: str | None = None
    top: int | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "reranker": self.reranker,
            "applied": self.applied,
            "error": self.error,
            "top": self.top,
        }


def empty_rerank_account() -> RerankAccount:
    return RerankAccount(reranker=None, applied=False)
