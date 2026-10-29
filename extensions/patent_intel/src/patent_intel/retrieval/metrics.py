"""Retrieval evaluation metrics (blueprint §12; scored by tools/score_retrieval.py).

Conventions:

* inputs are **family-level**: a ranked list of family IDs and a gold set of family
  IDs. Publication-level runs must be mapped to families by the caller (the scorer
  does it via the manifest's ``families`` table) — a family must never be counted
  twice because two of its members ranked (UT-S03 discipline);
* an empty gold set is an **error**, never an automatic perfect score
  (T-02 acceptance; "Gold=0 主题单独报告且不参加 Recall 分母" is handled by the
  scorer, which excludes such topics and reports them separately);
* all functions are deterministic; the only randomness is in
  :func:`bootstrap_ci_by_topic`, which takes an explicit seed.

Standard-library only — no numpy required (UT-R01: fixed sample + fixed parameters
must give identical results on any platform).
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping, Sequence

__all__ = [
    "MetricError",
    "family_recall_at_k",
    "precision_at_k",
    "reciprocal_rank",
    "ndcg_at_k",
    "average_precision",
    "bootstrap_ci_by_topic",
    "unique_relevant_yield",
]


class MetricError(ValueError):
    """Raised on metric-contract violations (empty gold, bad K, negative ranks…)."""


def _check_ranked(ranked: Sequence[str]) -> None:
    if len(set(ranked)) != len(ranked):
        dupes = sorted({x for x in ranked if ranked.count(x) > 1})
        raise MetricError(f"ranked list contains duplicate families: {dupes[:5]}")


def family_recall_at_k(ranked: Sequence[str], gold: Iterable[str], k: int) -> float:
    """|top-K ranked ∩ gold| / |gold|. Raises on empty gold (never a free 1.0)."""
    gold_set = set(gold)
    if not gold_set:
        raise MetricError("empty gold set: recall is undefined, not perfect")
    if k <= 0:
        raise MetricError(f"k must be positive, got {k}")
    _check_ranked(list(ranked))
    top_k = set(ranked[:k])
    return len(top_k & gold_set) / len(gold_set)


def precision_at_k(ranked: Sequence[str], gold: Iterable[str], k: int) -> float:
    """|top-K ranked ∩ gold| / K (K capped at list length)."""
    gold_set = set(gold)
    if k <= 0:
        raise MetricError(f"k must be positive, got {k}")
    _check_ranked(list(ranked))
    if not ranked:
        return 0.0
    top_k = ranked[:k]
    return len(set(top_k) & gold_set) / min(k, len(ranked))


def reciprocal_rank(ranked: Sequence[str], gold: Iterable[str]) -> float:
    """1 / first relevant rank, 0 if none present."""
    gold_set = set(gold)
    if not gold_set:
        raise MetricError("empty gold set: MRR is undefined")
    for i, item in enumerate(ranked, start=1):
        if item in gold_set:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[str], gains: Mapping[str, float], k: int) -> float:
    """Graded nDCG@K with linear gain (gain_i = relevance level). Unjudged = 0.

    Raises when ``gains`` has no positive entries — an all-zero qrels document is a
    data error, not a zero-score run.
    """
    if k <= 0:
        raise MetricError(f"k must be positive, got {k}")
    if not any(g > 0 for g in gains.values()):
        raise MetricError("gains contain no positive relevance level")
    _check_ranked(list(ranked))
    dcg = 0.0
    for i, item in enumerate(ranked[:k], start=1):
        rel = float(gains.get(item, 0.0))
        dcg += (2.0**rel - 1.0) / math.log2(i + 1)
    ideal = sorted(gains.values(), reverse=True)[:k]
    idcg = sum((2.0**float(rel) - 1.0) / math.log2(i + 1) for i, rel in enumerate(ideal, start=1))
    if idcg <= 0.0:
        raise MetricError("non-positive IDCG: inconsistent gains")
    return dcg / idcg


def average_precision(ranked: Sequence[str], gold: Iterable[str]) -> float:
    """Mean-precision-at-hit; the topic-level building block of MAP."""
    gold_set = set(gold)
    if not gold_set:
        raise MetricError("empty gold set")
    hits = 0
    total = 0.0
    for i, item in enumerate(ranked, start=1):
        if item in gold_set:
            hits += 1
            total += hits / i
    return total / len(gold_set)


def bootstrap_ci_by_topic(
    per_topic: Mapping[str, float],
    *,
    n_resamples: int = 10_000,
    level: float = 0.95,
    seed: int = 20261028,
) -> dict[str, float]:
    """Percentile bootstrap over **topics** (macro style): resample topic IDs with
    replacement, average the metric each time, take empirical percentiles.

    Deterministic given (per_topic keys+values, n_resamples, seed). Fewer than 2
    topics → no CI (report the point estimate only; blueprint §12: 数据量不足时不得
    宣称统计成立).
    """
    if not per_topic:
        raise MetricError("no topic values to bootstrap")
    if n_resamples <= 0:
        raise MetricError("n_resamples must be positive")
    if not 0.0 < level < 1.0:
        raise MetricError("level must be in (0, 1)")
    values = [float(v) for v in per_topic.values()]
    if len(values) < 2:
        return {"level": level, "n_topics": len(values), "lower": values[0], "upper": values[0], "degenerate": True}
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        means.append(sum(sample) / len(sample))
    means.sort()
    alpha = (1.0 - level) / 2.0
    lower_idx = max(0, math.floor(alpha * len(means)) - 1)
    upper_idx = min(len(means) - 1, math.ceil((1 - alpha) * len(means)) - 1)
    return {
        "level": level,
        "n_topics": len(values),
        "lower": means[lower_idx],
        "upper": means[upper_idx],
        "degenerate": False,
    }


def unique_relevant_yield(
    relevant_by_request: Sequence[int],
    *,
    total_requests: int,
) -> float:
    """New relevant families found per 100 effective requests (blueprint §12).

    ``relevant_by_request[i]`` = number of *previously unseen* relevant families
    discovered by request i+1. ``total_requests`` counts every request actually issued
    (including zero-yield ones) — the denominator of honest cost accounting.
    """
    if total_requests <= 0:
        raise MetricError("total_requests must be positive")
    if any(v < 0 for v in relevant_by_request):
        raise MetricError("yields must be non-negative")
    return 100.0 * sum(relevant_by_request) / total_requests
