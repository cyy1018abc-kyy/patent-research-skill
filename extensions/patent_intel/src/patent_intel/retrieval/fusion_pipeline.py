"""Multi-channel fusion pipeline (adaptive roadmap WP-L1 / Phase 4).

Wires the existing pieces into one honest per-query fusion step:

* per-channel rankings (:class:`ChannelResult`) — a channel that failed carries its
  error; a channel that was never configured is recorded **absent with a reason**.
  Neither is ever silently treated as an empty (zero-score) channel;
* :func:`patent_intel.retrieval.hybrid.rrf_fuse` across the present channels —
  different channels' scores are never added directly, only rank-fused
  (roadmap Phase 4: 不同检索通道的分数不能直接相加);
* :func:`patent_intel.retrieval.hybrid.family_collapse` on the fused ranking —
  one family occupies one slot, unknown family relations stay independent;

the fused score is a *ranking signal*, not an evidence strength — reports keep the
standing caveat. Refuses to fabricate a fusion when no channel produced a ranking.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from patent_intel.retrieval.hybrid import family_collapse, rrf_fuse

__all__ = ["ChannelResult", "FusionResult", "FusionPipeline", "FusionError"]

_OWNER = "WP-A"


class FusionError(ValueError):
    """Fusion refused — no usable channel ranking (never fabricate an ordering)."""


@dataclass(frozen=True)
class ChannelResult:
    """One channel's ranking for one query, or its failure."""

    name: str
    ranked: list[str]
    error: str | None = None


@dataclass(frozen=True)
class FusionResult:
    """Fused ranking plus the full channel account (present / errored / absent)."""

    fused: list[tuple[str, float]]  # after family collapse
    fused_pre_collapse: list[tuple[str, float]]
    channels: dict[str, list[str]]
    channels_errored: dict[str, str]
    channels_absent: dict[str, str]
    k: int
    weights: dict[str, float]

    def describe(self) -> dict[str, Any]:
        return {
            "fused": [[doc_id, round(score, 6)] for doc_id, score in self.fused],
            "channels_present": {name: len(ranked) for name, ranked in self.channels.items()},
            "channels_errored": dict(self.channels_errored),
            "channels_absent": dict(self.channels_absent),
            "k": self.k,
            "weights": dict(self.weights),
            "note": (
                "RRF 融合分数是排序信号，不是证据强度 (fusion score is a ranking "
                "signal, not evidence strength)"
            ),
        }


@dataclass
class FusionPipeline:
    """Per-query RRF fusion with family collapse and honest channel accounting."""

    k: int = 60
    weights: dict[str, float] = field(default_factory=dict)
    top: int | None = None

    def __post_init__(self) -> None:
        if self.k <= 0:
            raise ValueError("k must be positive")

    def fuse(
        self,
        channels: list[ChannelResult],
        *,
        family_of: Mapping[str, str | None],
        absent: Mapping[str, str] | None = None,
    ) -> FusionResult:
        present = {c.name: list(c.ranked) for c in channels if c.error is None}
        errored = {c.name: c.error for c in channels if c.error is not None}
        if not present:
            raise FusionError(
                f"no channel produced a ranking (errored: {sorted(errored)}, "
                f"absent: {sorted(absent or {})}) — refusing to fabricate a fusion"
            )
        fused_pre = rrf_fuse(present, k=self.k, weights=self.weights or None, top=self.top)
        fused = family_collapse(fused_pre, {d: f for d, f in family_of.items() if f})
        return FusionResult(
            fused=fused,
            fused_pre_collapse=fused_pre,
            channels=present,
            channels_errored=errored,
            channels_absent=dict(absent or {}),
            k=self.k,
            weights=dict(self.weights),
        )
