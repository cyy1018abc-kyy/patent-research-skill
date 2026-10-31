"""Adaptive query controller (blueprint A-06): pick the next query by expected yield,
stop honestly.

Stop conditions (all recorded, none claim completeness):
* plan exhausted / budget exhausted / no incremental candidate yield for N rounds /
  manual cancel (exception). The report always carries ``stop_reason`` and the explicit
  statement that **stopping is not proof of exhaustive recall** (UT-R02).

Identity & accounting discipline (adaptive roadmap Task 1):

* ``RunOutcome.families`` carries **family ids only** — a runner that cannot resolve
  family relations leaves it empty and declares ``family_basis="unknown"``; document
  ids are counted document-level (``new_documents``), never promoted into the family
  dimension (a document id must not masquerade as a family id, UT-S03);
* candidate new families / suspected relevant / confirmed relevant are three separate
  buckets; the controller never upgrades candidates to relevant on its own;
* coverage is recorded per technical **feature id** (``QuerySpec.feature_ids``), with
  the axis dimension limited to "did this sub-area see any family".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Callable

from patent_intel.contracts import QuerySpec
from patent_intel.retrieval.coverage import CoverageTracker, QueryYieldLedger
from patent_intel.retrieval.policy import (
    GapFirstPolicy,
    PolicyState,
    RetrievalPolicy,
    TypeStats,
)
from patent_intel.retrieval.query_plan import effective_feature_ids

__all__ = [
    "RunOutcome",
    "ControllerReport",
    "AdaptiveController",
    "StopReason",
    "FamilyBasis",
]

_OWNER = "WP-A"


class StopReason:
    PLAN_EXHAUSTED = "plan_exhausted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ZERO_GAIN = "zero_gain_rounds"
    MANUAL = "manual_cancel"
    #: the policy declined to continue (expected marginal gain below cost) — soft stop,
    #: recorded with an explicit reason; NEVER presented as exhaustion of the space
    SOFT_STOP = "soft_stop_policy"


class FamilyBasis:
    """What backs the family ids in ``RunOutcome.families`` (Task 1 identity discipline).

    * ``reported``          — the source/corpus explicitly reported these family ids;
    * ``publication_number`` — derived by an identifier resolver (reserved for the
      publication/family resolver; never a fallback for bare document ids);
    * ``unknown``           — family relations are unreported; ``families`` must be
      empty and yield is counted document-level only.
    """

    REPORTED = "reported"
    PUBLICATION_NUMBER = "publication_number"
    UNKNOWN = "unknown"

    ALL = (REPORTED, PUBLICATION_NUMBER, UNKNOWN)


class Cancelled(Exception):
    """Raised by a runner on user interruption; the controller records it."""


@dataclass
class RunOutcome:
    """Result of one executed query (whatever the runner returned)."""

    query_id: str
    hits: list[str] = field(default_factory=list)  # document ids
    #: family ids as resolved by the runner — NEVER document ids (see family_basis)
    families: list[str] = field(default_factory=list)
    new_families: list[str] = field(default_factory=list)
    cost: float = 0.0
    error: str | None = None
    family_basis: str = FamilyBasis.REPORTED
    #: document ids that were genuinely new (filled by the controller's ledger)
    new_documents: list[str] = field(default_factory=list)
    #: runner/evaluator-suspected relevant families — subset of ``families``; never inferred
    suspected_relevant: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.family_basis not in FamilyBasis.ALL:
            raise ValueError(
                f"family_basis {self.family_basis!r} not in {FamilyBasis.ALL}"
            )
        if self.family_basis == FamilyBasis.UNKNOWN and self.families:
            raise ValueError(
                "family_basis='unknown' refuses family ids: unreported family relations must "
                "not be invented (UT-S03) — leave families empty and count document-level yield"
            )
        if not set(self.suspected_relevant) <= set(self.families):
            raise ValueError("suspected_relevant must be a subset of families")


@dataclass
class ControllerReport:
    queries_run: list[str] = field(default_factory=list)
    outcomes: list[RunOutcome] = field(default_factory=list)
    stop_reason: str = ""
    budget_spent: float = 0.0
    #: candidate new families (NOT relevance-filtered — see family_accounting)
    total_new_families: int = 0
    coverage: dict[str, Any] = field(default_factory=dict)
    total_new_documents: int = 0
    #: per-query policy decisions (selection reason + utility) — roadmap Task 3 record
    decisions: list[dict[str, Any]] = field(default_factory=list)
    #: set when stop_reason == soft_stop_policy: the policy's explicit decline reason
    soft_stop_reason: str = ""
    #: live ledger view — relevance marking after the run stays visible in the report
    ledger: QueryYieldLedger | None = field(default=None, repr=False, compare=False)
    #: live coverage tracker (feature/axis state) for downstream evaluators
    coverage_tracker: CoverageTracker | None = field(default=None, repr=False, compare=False)

    @property
    def family_accounting(self) -> dict[str, Any]:
        """Three-bucket accounting (candidates/suspected/confirmed), computed live."""
        if self.ledger is None:
            return {}
        return self.ledger.accounting()

    @property
    def relevant_families(self) -> list[str]:
        """Confirmed relevant family ids — empty unless explicitly marked; never auto-filled."""
        if self.ledger is None:
            return []
        return sorted(self.ledger.confirmed_relevant)

    def describe(self) -> dict[str, Any]:
        return {
            "queries_run": self.queries_run,
            "stop_reason": self.stop_reason,
            "soft_stop_reason": self.soft_stop_reason,
            "decisions": list(self.decisions),
            "budget_spent": self.budget_spent,
            "total_new_families": self.total_new_families,
            "total_new_documents": self.total_new_documents,
            "family_accounting": self.family_accounting,
            "relevant_families": self.relevant_families,
            "outcomes": [
                {
                    "query_id": o.query_id,
                    "hits": len(o.hits),
                    "new_families": len(o.new_families),
                    "new_documents": len(o.new_documents),
                    "family_basis": o.family_basis,
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
        policy: RetrievalPolicy | None = None,
    ) -> None:
        if max_requests < 0 or max_cost < 0:
            raise ValueError("budgets must be non-negative")
        self.runner = runner
        self.max_requests = max_requests
        self.max_cost = max_cost
        self.zero_gain_rounds = zero_gain_rounds
        self.concepts_by_axis = concepts_by_axis or {}
        #: selection policy — GapFirstPolicy keeps the legacy deterministic order;
        #: MarginalUtilityPolicy adds benefit-driven selection with soft stops
        self.policy: RetrievalPolicy = policy or GapFirstPolicy()
        self.ledger = QueryYieldLedger()
        self.coverage = CoverageTracker()
        self._executed_types: dict[str, str] = {}

    def run_plan(self, queries: list[QuerySpec]) -> ControllerReport:
        """Execute queries in the policy's order until a stop condition fires."""
        report = ControllerReport()
        pending = list(queries)
        zero_gain_streak = 0
        axes = sorted({q.axis_id for q in queries})
        self._executed_types = {}

        while pending:
            if report.budget_spent >= self.max_cost or len(report.queries_run) >= self.max_requests:
                report.stop_reason = StopReason.BUDGET_EXHAUSTED
                break
            decision = self.policy.select_next(pending, self._policy_state(report))
            if decision.query is None:
                report.stop_reason = StopReason.SOFT_STOP
                report.soft_stop_reason = decision.reason
                break
            next_query = decision.query
            self._executed_types[next_query.query_id] = next_query.query_type
            report.decisions.append({
                "query_id": next_query.query_id,
                "policy": type(self.policy).__name__,
                "reason": decision.reason,
                "utility": decision.utility,
            })
            try:
                outcome = self.runner(next_query)
            except Cancelled:
                report.stop_reason = StopReason.MANUAL
                break
            except Exception as exc:  # noqa: BLE001 - runner failure = zero-gain round, recorded
                outcome = RunOutcome(query_id=next_query.query_id, error=f"{type(exc).__name__}: {exc}")

            report.queries_run.append(next_query.query_id)
            report.outcomes.append(outcome)
            report.budget_spent += outcome.cost
            # feature attempts are recorded regardless of outcome — an executed query
            # that found nothing is not_found evidence; an errored one stays unknown
            query_feature_ids = self._feature_ids_of(next_query)
            for feature_id in query_feature_ids:
                self.coverage.record_feature_attempt(
                    feature_id, query_id=next_query.query_id, axis_id=next_query.axis_id
                )
            new_families = self.ledger.record(next_query.query_id, outcome.families)
            outcome.new_families = new_families
            if outcome.suspected_relevant:
                self.ledger.mark_suspected(outcome.suspected_relevant)
            new_documents = self.ledger.record_documents(next_query.query_id, outcome.hits)
            outcome.new_documents = new_documents
            for feature_id in query_feature_ids:
                for fam in new_families:
                    self.coverage.record_feature_hit(
                        feature_id, fam, query_id=next_query.query_id, axis_id=next_query.axis_id
                    )
            for fam in new_families:
                self.coverage.record_axis_family(next_query.axis_id, fam)
            if new_families or new_documents:
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
        report.total_new_documents = self.ledger.total_new_documents
        report.ledger = self.ledger
        report.coverage_tracker = self.coverage
        report.coverage = self.coverage.report(axes, self.concepts_by_axis).describe()
        return report

    def mark_relevant(self, family_ids: Iterable[str], *, suspected: bool = False) -> list[str]:
        """Explicitly mark ledger-seen families as (suspected|confirmed) relevant.

        The controller never performs this upgrade itself — callers (evaluator or
        human review) own the judgement; this only forwards it to the ledger.
        """
        if suspected:
            return self.ledger.mark_suspected(family_ids)
        return self.ledger.mark_confirmed(family_ids)

    def _policy_state(self, report: ControllerReport) -> PolicyState:
        """Snapshot of the run state a policy may inspect — deterministic inputs only
        (coverage, ledger, budget, per-type observed history). No wall clock, no RNG.
        """
        acc: dict[str, dict[str, Any]] = {}
        confirmed = self.ledger.confirmed_relevant
        for outcome in report.outcomes:
            query_type = self._executed_types.get(outcome.query_id)
            if query_type is None:  # pragma: no cover - outcomes always come from this run
                continue
            bucket = acc.setdefault(
                query_type, {"runs": 0, "new_families": 0, "cost": 0.0, "suspected": 0, "confirmed": 0}
            )
            bucket["runs"] += 1
            bucket["new_families"] += len(outcome.new_families)
            bucket["cost"] += outcome.cost
            bucket["suspected"] += len(outcome.suspected_relevant)
            bucket["confirmed"] += sum(
                1 for fam in self.ledger.yield_of(outcome.query_id) if fam in confirmed
            )
        return PolicyState(
            coverage=self.coverage,
            ledger=self.ledger,
            budget_spent=report.budget_spent,
            max_cost=self.max_cost,
            queries_run=list(report.queries_run),
            type_history={name: TypeStats(**values) for name, values in acc.items()},
        )

    @staticmethod
    def _feature_ids_of(query: QuerySpec) -> list[str]:
        """Authoritative feature dimension (shared helper — see query_plan)."""
        return effective_feature_ids(query)
