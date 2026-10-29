"""Adaptive query controller (blueprint A-06): pick the next query by expected yield,
stop honestly.

Stop conditions (all recorded, none claim completeness):
* plan exhausted / budget exhausted / zero incremental yield for N rounds / manual
  cancel (exception). The report always carries ``stop_reason`` and the explicit
  statement that **stopping is not proof of exhaustive recall** (UT-R02).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from patent_intel.contracts import QuerySpec
from patent_intel.retrieval.coverage import CoverageTracker, QueryYieldLedger

__all__ = ["RunOutcome", "ControllerReport", "AdaptiveController", "StopReason", "CANCELLED"]

_OWNER = "WP-A"


class StopReason:
    PLAN_EXHAUSTED = "plan_exhausted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ZERO_GAIN = "zero_gain_rounds"
    MANUAL = "manual_cancel"


class Cancelled(Exception):
    """Raised by a runner on user interruption; the controller records it."""


@dataclass
class RunOutcome:
    """Result of one executed query (whatever the runner returned)."""

    query_id: str
    hits: list[str]  # doc ids
    families: list[str]  # family ids (doc id when unknown)
    new_families: list[str]
    cost: float = 0.0
    error: str | None = None


@dataclass
class ControllerReport:
    queries_run: list[str] = field(default_factory=list)
    outcomes: list[RunOutcome] = field(default_factory=list)
    stop_reason: str = ""
    budget_spent: float = 0.0
    total_new_families: int = 0
    coverage: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "queries_run": self.queries_run,
            "stop_reason": self.stop_reason,
            "budget_spent": self.budget_spent,
            "total_new_families": self.total_new_families,
            "outcomes": [
                {
                    "query_id": o.query_id,
                    "hits": len(o.hits),
                    "new_families": len(o.new_families),
                    "error": o.error,
                }
                for o in self.outcomes
            ],
            "coverage": self.coverage,
            "caveat": (
                "adaptive stopping reflects budget/diminishing returns — "
                "停止不等同已查全 (stopping is NOT proof of exhaustive recall)"
            ),
        }


class AdaptiveController:
    """Runs a query plan offline/online, choosing next queries by marginal yield.

    ``runner`` executes one query and returns ``RunOutcome``-shaped data
    (hits, families). The controller is source-agnostic: offline it wraps the
    local BM25 index; online runners wrap WP-B adapters (each of which enforces
    its own consent gates).
    """

    def __init__(
        self,
        runner: Callable[[QuerySpec], RunOutcome],
        *,
        max_requests: int = 50,
        max_cost: float = 5.0,
        zero_gain_rounds: int = 3,
        concepts_by_axis: dict[str, list[str]] | None = None,
    ) -> None:
        if max_requests < 0 or max_cost < 0:
            raise ValueError("budgets must be non-negative")
        self.runner = runner
        self.max_requests = max_requests
        self.max_cost = max_cost
        self.zero_gain_rounds = zero_gain_rounds
        self.concepts_by_axis = concepts_by_axis or {}
        self.ledger = QueryYieldLedger()
        self.coverage = CoverageTracker()

    def run_plan(self, queries: list[QuerySpec]) -> ControllerReport:
        """Execute queries in marginal-yield order until a stop condition fires."""
        report = ControllerReport()
        pending = list(queries)
        zero_gain_streak = 0
        axes = sorted({q.axis_id for q in queries})

        while pending:
            if report.budget_spent >= self.max_cost or len(report.queries_run) >= self.max_requests:
                report.stop_reason = StopReason.BUDGET_EXHAUSTED
                break
            # deterministic selection: highest observed new-family yield first,
            # ties by original plan order (stable, reproducible)
            next_query = self._select(pending, report)
            try:
                outcome = self.runner(next_query)
            except Cancelled:
                report.stop_reason = StopReason.MANUAL
                break
            except Exception as exc:  # noqa: BLE001 - runner failure = zero-gain round, recorded
                outcome = RunOutcome(query_id=next_query.query_id, hits=[], families=[], new_families=[], error=f"{type(exc).__name__}: {exc}")

            report.queries_run.append(next_query.query_id)
            report.outcomes.append(outcome)
            report.budget_spent += outcome.cost
            new_families = self.ledger.record(next_query.query_id, outcome.families)
            outcome.new_families = new_families
            for fam in new_families:
                self.coverage.record_hit(next_query.axis_id, next_query.query_type, fam)
            if new_families:
                zero_gain_streak = 0
            else:
                zero_gain_streak += 1
            pending.remove(next_query)
            if zero_gain_streak >= self.zero_gain_rounds:
                report.stop_reason = StopReason.ZERO_GAIN
                break
        else:
            report.stop_reason = StopReason.PLAN_EXHAUSTED

        report.total_new_families = self.ledger.total_new_families
        report.coverage = self.coverage.report(axes, self.concepts_by_axis).describe()
        return report

    _KIND_PRIORITY = {
        "single_feature": 0,
        "feature_cross": 1,
        "broad_recall": 2,
        "citation_expand": 3,
        "cross_domain": 4,
    }

    def _select(self, pending: list[QuerySpec], report: ControllerReport) -> QuerySpec:
        """Coverage-gap-first selection: run single-feature queries on the least-covered
        axes before broad/cross queries. Fully deterministic (stable tiebreak = plan order).
        """
        def score(q: QuerySpec) -> tuple[int, int, int]:
            axis_fams = len(self.coverage.families.get(q.axis_id, set()))
            kind = self._KIND_PRIORITY.get(q.query_type, 9)
            return (kind, axis_fams, pending.index(q))

        return sorted(pending, key=score)[0]
