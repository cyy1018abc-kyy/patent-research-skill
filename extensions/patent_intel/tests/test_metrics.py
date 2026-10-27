"""Metric unit tests (T-03): hand-computed values, determinism, contract refusals (UT-R01)."""

from __future__ import annotations

import pytest

from patent_intel.retrieval.metrics import (
    MetricError,
    average_precision,
    bootstrap_ci_by_topic,
    family_recall_at_k,
    ndcg_at_k,
    precision_at_k,
    reciprocal_rank,
    unique_relevant_yield,
)


def test_family_recall_at_k_hand_computed() -> None:
    ranked = ["F-A", "F-B", "F-C", "F-D"]
    gold = {"F-B", "F-D"}
    assert family_recall_at_k(ranked, gold, 1) == 0.0
    assert family_recall_at_k(ranked, gold, 2) == 0.5
    assert family_recall_at_k(ranked, gold, 4) == 1.0


def test_family_recall_empty_gold_is_error_not_perfect() -> None:
    with pytest.raises(MetricError, match="empty gold"):
        family_recall_at_k(["F-A"], set(), 10)


def test_family_recall_rejects_duplicate_families() -> None:
    with pytest.raises(MetricError, match="duplicate"):
        family_recall_at_k(["F-A", "F-A", "F-B"], {"F-B"}, 3)


def test_family_recall_rejects_bad_k() -> None:
    with pytest.raises(MetricError, match="k must be positive"):
        family_recall_at_k(["F-A"], {"F-A"}, 0)


def test_precision_at_k() -> None:
    assert precision_at_k(["F-A", "F-B", "F-C"], {"F-A", "F-C"}, 3) == pytest.approx(2 / 3)
    assert precision_at_k([], {"F-A"}, 3) == 0.0


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(["F-A", "F-B", "F-C"], {"F-C"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(["F-A"], {"F-Z"}) == 0.0
    with pytest.raises(MetricError, match="empty gold"):
        reciprocal_rank([], set())


def test_ndcg_hand_computed() -> None:
    gains = {"F-A": 3, "F-B": 2}
    # ideal order [A,B]: DCG == IDCG -> 1.0
    assert ndcg_at_k(["F-A", "F-B"], gains, 2) == pytest.approx(1.0)
    # swapped order: (2^2-1)/1 + (2^3-1)/log2(3) over ideal 7 + 3/log2(3)
    import math

    dcg = 3.0 + 7.0 / math.log2(3)
    idcg = 7.0 + 3.0 / math.log2(3)
    assert ndcg_at_k(["F-B", "F-A"], gains, 2) == pytest.approx(dcg / idcg)


def test_ndcg_unjudged_items_score_zero() -> None:
    gains = {"F-A": 3}
    # unjudged items contribute gain 0, so ranking the relevant item first is strictly better
    assert ndcg_at_k(["F-A", "F-Z"], gains, 2) > ndcg_at_k(["F-Z", "F-A"], gains, 2)
    # a list containing only unjudged items scores 0 (denominator comes from ideal gains)
    assert ndcg_at_k(["F-Z", "F-Y"], gains, 2) == 0.0


def test_ndcg_all_zero_gains_is_error() -> None:
    with pytest.raises(MetricError, match="no positive"):
        ndcg_at_k(["F-A"], {"F-A": 0}, 1)


def test_average_precision_hand_computed() -> None:
    # hits at rank 1 (P=1) and rank 3 (P=2/3); AP = (1 + 2/3) / 2
    assert average_precision(["F-A", "F-B", "F-C"], {"F-A", "F-C"}) == pytest.approx((1.0 + 2 / 3) / 2)


def test_bootstrap_ci_deterministic_and_sane() -> None:
    per_topic = {"TP-0001": 0.8, "TP-0002": 0.6, "TP-0003": 0.4, "TP-0004": 0.9}
    a = bootstrap_ci_by_topic(per_topic, n_resamples=2000, seed=42)
    b = bootstrap_ci_by_topic(per_topic, n_resamples=2000, seed=42)
    assert a == b  # same seed -> identical CI (UT-R01)
    mean = sum(per_topic.values()) / len(per_topic)
    assert a["lower"] <= mean <= a["upper"]
    assert a["degenerate"] is False
    # different seed may differ but must stay ordered
    c = bootstrap_ci_by_topic(per_topic, n_resamples=2000, seed=7)
    assert c["lower"] <= c["upper"]


def test_bootstrap_ci_degenerate_for_single_topic() -> None:
    ci = bootstrap_ci_by_topic({"TP-0001": 0.7}, seed=1)
    assert ci["degenerate"] is True
    assert ci["lower"] == ci["upper"] == 0.7


def test_bootstrap_ci_rejects_empty_and_bad_args() -> None:
    with pytest.raises(MetricError):
        bootstrap_ci_by_topic({}, seed=1)
    with pytest.raises(MetricError):
        bootstrap_ci_by_topic({"A": 1.0}, n_resamples=0, seed=1)
    with pytest.raises(MetricError):
        bootstrap_ci_by_topic({"A": 1.0}, level=1.5, seed=1)


def test_unique_relevant_yield() -> None:
    # 5 new relevant families over 10 effective requests -> 50 per 100 requests
    assert unique_relevant_yield([2, 0, 3], total_requests=10) == pytest.approx(50.0)
    with pytest.raises(MetricError):
        unique_relevant_yield([1], total_requests=0)
    with pytest.raises(MetricError):
        unique_relevant_yield([-1], total_requests=5)
