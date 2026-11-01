"""Retrieval policies (adaptive roadmap Task 3): what to run next, and when to stop.

Two implementations ship:

* :class:`GapFirstPolicy` — the legacy deterministic selector (single-feature queries
  on the least-covered axes before broad/cross). It is the controller default: fully
  reproducible, never soft-stops, plan-exhausted semantics preserved.
* :class:`MarginalUtilityPolicy` — the roadmap's benefit-driven selector:
  ``U(q) = (w1·ΔC + w2·ΔR + w3·ΔD) / (λ1·cost + ε)`` with deterministic, explainable
  inputs (feature-coverage gaps, observed per-type relevance yield, axis gaps,
  observed/default costs) and a stable plan-order tiebreak. It soft-stops
  (``query=None`` decision) when the best remaining utility is below
  ``min_utility`` — 预计新增收益低于成本 — never claiming exhaustion of the space.

Discipline:

* every decision carries a human-readable ``reason`` (recorded by the controller);
* relevance yield ΔR counts only explicitly marked families — hit counts are never
  treated as relevance (candidate ≠ relevant);
* online sources are charged a higher default cost than local ones, so equal-utility
  plans prefer cheap local evidence first (先低成本检索，再依据缺口增强);
* all inputs derive from recorded run state — no wall-clock, no RNG, no model calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from patent_intel.contracts import QuerySpec
from patent_intel.retrieval.coverage import CoverageTracker, QueryYieldLedger
from patent_intel.retrieval.query_plan import effective_feature_ids

__all__ = [
    "PolicyDecision",
    "PolicyState",
    "TypeStats",
    "RetrievalPolicy",
    "GapFirstPolicy",
    "MarginalUtilityPolicy",
    "DEFAULT_TYPE_COSTS",
]

#: conservative default cost per query type when no run history exists yet
DEFAULT_TYPE_COSTS: dict[str, float] = {
    "single_feature": 1.0,
    "feature_cross": 1.5,
    "citation_expand": 2.0,
    "cross_domain": 2.0,
    "broad_recall": 3.0,
}
_DEFAULT_UNKNOWN_TYPE_COST = 2.5

#: source ids treated as local (free-ish) evidence; anything else is online
_LOCAL_SOURCES = frozenset({"multi", "local", "bm25"})


@dataclass(frozen=True)
class PolicyDecision:
    """What to run next — or ``query=None`` for a policy-initiated soft stop."""

    query: QuerySpec | None
    reason: str
    utility: float | None = None


@dataclass(frozen=True)
class TypeStats:
    """Observed per-query-type history (the policy's only memory of past yield)."""

    runs: int = 0
    new_families: int = 0
    cost: float = 0.0
    suspected: int = 0
    confirmed: int = 0

    @property
    def avg_cost(self) -> float:
        return self.cost / self.runs if self.runs else 0.0

    @property
    def relevance_per_run(self) -> float:
        """(suspected + confirmed) newly found per run — 0.0 before any marking."""
        return (self.suspected + self.confirmed) / self.runs if self.runs else 0.0


@dataclass(frozen=True)
class PolicyState:
    """Everything a policy may look at, snapshot per selection round."""

    coverage: CoverageTracker
    ledger: QueryYieldLedger
    budget_spent: float
    max_cost: float
    queries_run: list[str] = field(default_factory=list)
    type_history: dict[str, TypeStats] = field(default_factory=dict)


class RetrievalPolicy(Protocol):
    """Select the next query. Return a decision with ``query=None`` to soft-stop."""

    def select_next(self, pending: list[QuerySpec], state: PolicyState) -> PolicyDecision: ...


class GapFirstPolicy:
    """Legacy coverage-gap-first order, kept as the deterministic default.

    Score = (query-type priority, axis families asc, plan order) — identical to the
    pre-policy controller, so plans stay reproducible and never soft-stop.
    """

    _KIND_PRIORITY = {
        "single_feature": 0,
        "feature_cross": 1,
        "broad_recall": 2,
        "citation_expand": 3,
        "cross_domain": 4,
    }

    def select_next(self, pending: list[QuerySpec], state: PolicyState) -> PolicyDecision:
        def score(item: tuple[int, QuerySpec]) -> tuple[int, int, int]:
            index, q = item
            axis_fams = len(state.coverage.families.get(q.axis_id, set()))
            kind = self._KIND_PRIORITY.get(q.query_type, 9)
            return (kind, axis_fams, index)

        index, query = min(enumerate(pending), key=score)
        return PolicyDecision(
            query=query,
            reason=(
                f"gap-first: kind={query.query_type} priority, axis {query.axis_id} "
                f"has {len(state.coverage.families.get(query.axis_id, set()))} families so far"
            ),
        )


class MarginalUtilityPolicy:
    """Benefit-driven selector: U(q) = (w1·ΔC + w2·ΔR + w3·ΔD) / (λ1·cost + ε).

    * ΔC — targeted features still without any candidate family (coverage potential);
    * ΔR — observed relevance yield of this query type (marked families per run, 0
      before any marking — never inferred from raw hit counts);
    * ΔD — 1 when the query's axis has no families yet (domain/data-source gap);
    * cost — observed average cost of the type, else the conservative default
      (online sources pay more than local ones); divided with ε floor.
    """

    def __init__(
        self,
        *,
        w_coverage: float = 1.0,
        w_relevance: float = 2.0,
        w_domain: float = 0.5,
        lambda_cost: float = 1.0,
        epsilon: float = 1e-6,
        min_utility: float = 0.05,
        default_type_costs: dict[str, float] | None = None,
    ) -> None:
        if min_utility < 0:
            raise ValueError("min_utility must be non-negative")
        self.w_coverage = w_coverage
        self.w_relevance = w_relevance
        self.w_domain = w_domain
        self.lambda_cost = lambda_cost
        self.epsilon = epsilon
        self.min_utility = min_utility
        self.default_type_costs = default_type_costs or dict(DEFAULT_TYPE_COSTS)

    # -- estimation ------------------------------------------------------

    def _targeted_features(self, query: QuerySpec) -> list[str]:
        return effective_feature_ids(query)

    def _cost_of(self, query: QuerySpec, stats: TypeStats) -> float:
        if stats.runs:
            return stats.avg_cost
        cost = self.default_type_costs.get(query.query_type, _DEFAULT_UNKNOWN_TYPE_COST)
        if query.source not in _LOCAL_SOURCES:
            cost += 1.0  # online requests pay more than local evidence at equal utility
        return cost

    def estimate(self, query: QuerySpec, state: PolicyState) -> tuple[float, dict[str, Any]]:
        """Deterministic utility estimate plus its explainable components."""
        stats = state.type_history.get(query.query_type, TypeStats())
        targeted = self._targeted_features(query)
        delta_c = sum(
            1 for f in targeted if not state.coverage.feature_families.get(f)
        )
        delta_r = stats.relevance_per_run
        delta_d = 1 if not state.coverage.families.get(query.axis_id) else 0
        cost = self._cost_of(query, stats)
        numerator = self.w_coverage * delta_c + self.w_relevance * delta_r + self.w_domain * delta_d
        utility = numerator / (self.lambda_cost * cost + self.epsilon)
        return utility, {
            "delta_coverage": delta_c,
            "delta_relevance": round(delta_r, 4),
            "delta_domain": delta_d,
            "cost": round(cost, 4),
            "targeted_features": targeted,
        }

    # -- selection -------------------------------------------------------

    def select_next(self, pending: list[QuerySpec], state: PolicyState) -> PolicyDecision:
        estimates = [(self.estimate(q, state), index, q) for index, q in enumerate(pending)]
        # deterministic: best utility first, ties by original plan order
        best = max(estimates, key=lambda item: (item[0][0], -item[1]))
        (utility, components), index, query = best
        if utility < self.min_utility:
            ranked = sorted(
                ((u, i, q) for (u, _c), i, q in estimates), key=lambda item: (-item[0], item[1])
            )
            detail = "; ".join(
                f"{q.query_id}: U={u:.4f}" for u, _i, q in ranked[:3]
            )
            return PolicyDecision(
                query=None,
                reason=(
                    f"soft stop: best marginal utility {utility:.4f} < min_utility "
                    f"{self.min_utility} (expected gain below cost) [{detail}]"
                ),
                utility=utility,
            )
        return PolicyDecision(
            query=query,
            reason=(
                f"marginal utility U={utility:.4f} "
                f"(ΔC={components['delta_coverage']}, ΔR={components['delta_relevance']}, "
                f"ΔD={components['delta_domain']}, cost={components['cost']})"
            ),
            utility=utility,
        )
