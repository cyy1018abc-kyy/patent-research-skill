"""Reranking interface (adaptive roadmap WP-L2 / Phase 4 stage 2).

Phase 4 ordering: per-channel RRF fusion → family collapse → **rerank of the fused
top-N**. This module defines the contract and the deterministic default; a
model-backed Cross-Encoder implementation is deliberately *not* shipped here —
model selection waits for smoke data (landing plan WP-L2), and until then the
identity reranker is the honest "no reranking" answer.

Discipline:

* a reranker reorders the candidates it was given — it never invents or drops
  candidates (documented contract; the pipeline splices only the top segment back);
* a failing reranker degrades to the pre-rerank ranking with the error recorded —
  degradation is visible in the fusion account, never silent;
* rerank scores are ranking signals, not evidence strengths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

__all__ = ["Reranker", "IdentityReranker", "RerankAccount", "empty_rerank_account"]

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
