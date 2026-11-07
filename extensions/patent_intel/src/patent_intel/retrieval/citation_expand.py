"""Citation-chain expansion tasks (blueprint A-05, WP-A + WP-B execution).

Produces *proposals* for follow-up retrieval: follow a record's citation links
(cites / cited-by / family) within explicit budget limits. Data comes from what a
source actually reported — the model never invents citation facts, and a task is
only created when the underlying field exists in the record (no fabricated links).

Roadmap 41B-2 adds the budget layer: :func:`allocate_citation_layers` admits the
three expansion directions (cites / cited_by / family) into the *unified*
controller budget by marginal benefit (new refs first), prunes zero-yield
directions with an explicit reason, and refuses unbounded citation walks —
planning beyond the depth ceiling is an error, deeper layers only ever come from
feeding fetched records back in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from patent_intel.contracts import QuerySpec, QueryType

__all__ = [
    "CitationTask",
    "CitationExpansionError",
    "plan_citation_expansion",
    "CitationDirectionAccount",
    "CitationBudgetPlan",
    "allocate_citation_layers",
    "citation_tasks_to_query_specs",
]

_OWNER = "WP-A"

#: expansion directions, in deterministic tie-break order
DIRECTIONS = ("cites", "cited_by", "family")

#: hard ceiling on planned depth — unbounded citation walks are not supported
#: (41B-2: 无限层路径移除); deeper layers only come from feeding fetched
#: records back through :func:`plan_citation_expansion` / this allocator.
MAX_DEPTH_CEILING = 3

#: provenance_field per direction (audit trail, mirrors plan_citation_expansion)
_DIRECTION_FIELDS = {"cites": "citations", "cited_by": "cited_by", "family": "family_refs"}


class CitationExpansionError(ValueError):
    """Invalid citation expansion request."""


@dataclass(frozen=True)
class CitationTask:
    """One follow-up retrieval task (a proposal for the controller/source layer)."""

    origin_id: str
    direction: str  # "cites" | "cited_by" | "family"
    target_ref: str
    depth: int
    reason: str
    #: the record field this task derives from (audit trail)
    provenance_field: str


def plan_citation_expansion(
    records: list[dict[str, Any]],
    *,
    max_depth: int = 1,
    max_tasks: int = 20,
    seen_refs: set[str] | None = None,
) -> list[CitationTask]:
    """Derive single-hop citation-expansion tasks from record citation fields.

    Fields honoured (when present, honestly empty otherwise):
    * ``cited_by`` — list of citing publication numbers
    * ``citations`` — list of cited publication numbers
    * ``family_refs`` — family membership refs [{family_id}] (WP-B family view)

    Depth semantics: this plans the *next* hop from the records given. Deeper
    expansion is achieved by feeding the fetched results back in (``seen_refs``
    prevents revisiting) — the planner never speculates about records it has not
    seen. A record without citation metadata yields no tasks: missing family
    metadata never triggers a speculative merge.
    """
    if max_depth < 1:
        raise CitationExpansionError("max_depth must be >= 1")
    if max_tasks < 0:
        raise CitationExpansionError("max_tasks must be >= 0")
    seen = seen_refs or set()
    tasks: list[CitationTask] = []

    for rec in records:
        if len(tasks) >= max_tasks:
            break
        origin = str(rec.get("id") or rec.get("publication_number") or "")
        if not origin:
            continue
        taken = {(t.target_ref, t.direction) for t in tasks}
        for key, direction in (("cited_by", "cited_by"), ("citations", "cites")):
            for target in rec.get(key) or []:
                target = str(target)
                if not target or target in seen or (target, direction) in taken:
                    continue
                tasks.append(
                    CitationTask(
                        origin_id=origin,
                        direction=direction,
                        target_ref=target,
                        depth=1,
                        reason=f"direct {direction} of {origin} reported by source",
                        provenance_field=key,
                    )
                )
                taken.add((target, direction))
                if len(tasks) >= max_tasks:
                    break
            if len(tasks) >= max_tasks:
                break
        for ref in rec.get("family_refs") or []:
            family_id = ref.get("family_id") if isinstance(ref, dict) else str(ref)
            if not family_id or family_id in seen or (family_id, "family") in taken:
                continue
            tasks.append(
                CitationTask(
                    origin_id=origin,
                    direction="family",
                    target_ref=str(family_id),
                    depth=1,
                    reason=f"family membership of {origin} reported by source",
                    provenance_field="family_refs",
                )
            )
            taken.add((family_id, "family"))
            if len(tasks) >= max_tasks:
                break
    return tasks


_ = field  # keep dataclass import explicit


# ── 41B-2: marginal-benefit budget allocation over expansion directions ──


@dataclass(frozen=True)
class CitationDirectionAccount:
    """Per-direction admission record (the "layer" of 41B-2)."""

    direction: str
    #: refs the source actually reported for this direction (first-seen order)
    reported: int
    #: refs not in ``seen_refs`` — the marginal-benefit estimate
    new_refs: int
    #: tasks admitted into the unified budget
    admitted: int
    #: "admitted" | "zero_yield_pruned" | "budget_exhausted" | "task_cap"
    status: str
    reason: str
    tasks: tuple[CitationTask, ...]

    def describe(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "reported": self.reported,
            "new_refs": self.new_refs,
            "admitted": self.admitted,
            "status": self.status,
            "reason": self.reason,
            "provenance_field": _DIRECTION_FIELDS.get(self.direction, ""),
            "task_refs": [t.target_ref for t in self.tasks],
        }


@dataclass(frozen=True)
class CitationBudgetPlan:
    """Result of :func:`allocate_citation_layers` — what the unified budget admits."""

    accounts: tuple[CitationDirectionAccount, ...]
    stop_reason: str
    budget_requests_before: int
    budget_cost_before: float
    cost_per_task: float

    @property
    def tasks(self) -> list[CitationTask]:
        """Admitted tasks in admission order (marginal-benefit order)."""
        return [t for account in self.accounts for t in account.tasks]

    def describe(self) -> dict[str, Any]:
        return {
            "stop_reason": self.stop_reason,
            "budget_before": {
                "requests": self.budget_requests_before,
                "cost": self.budget_cost_before,
            },
            "cost_per_task": self.cost_per_task,
            "tasks_admitted": len(self.tasks),
            "depth_ceiling": MAX_DEPTH_CEILING,
            "directions": [account.describe() for account in self.accounts],
            "caveat": "citation targets are proposals from reported fields; admission "
            "orders directions by marginal benefit and never implies the walk is exhaustive",
        }


def _direction_targets(
    records: list[dict[str, Any]], direction: str
) -> list[tuple[str, str]]:
    """First-seen ``(target_ref, origin_id)`` pairs for one direction, deterministic."""
    key = _DIRECTION_FIELDS[direction]
    pairs: list[tuple[str, str]] = []
    taken: set[str] = set()
    for rec in records:
        origin = str(rec.get("id") or rec.get("publication_number") or "")
        if not origin:
            continue
        if direction == "family":
            raw_refs = rec.get(key) or []
            refs = [
                ref.get("family_id") if isinstance(ref, dict) else str(ref)
                for ref in raw_refs
            ]
        else:
            refs = [str(t) for t in rec.get(key) or []]
        for ref in refs:
            target = str(ref) if ref is not None else ""
            if not target or target in taken:
                continue
            taken.add(target)
            pairs.append((target, origin))
    return pairs


def allocate_citation_layers(
    records: list[dict[str, Any]],
    *,
    seen_refs: set[str] | None = None,
    budget_requests: int = 0,
    budget_cost: float = 0.0,
    cost_per_task: float = 2.0,
    max_depth: int = 1,
    max_tasks_per_direction: int = 10,
) -> CitationBudgetPlan:
    """Admit the three expansion directions into the unified retrieval budget.

    Marginal benefit = reported refs not in ``seen_refs``. Directions are admitted
    in benefit order (ties broken by :data:`DIRECTIONS`); a direction with zero
    new refs is pruned without consuming budget (``zero_yield_pruned``); admission
    stops at the request or cost budget (``budget_exhausted``) or at the per-
    direction task cap (``task_cap``). ``max_depth`` beyond
    :data:`MAX_DEPTH_CEILING` is refused — unbounded citation walks do not exist
    here; deeper layers must come from feeding fetched records back in.
    """
    if budget_requests < 0 or budget_cost < 0:
        raise CitationExpansionError("budgets must be non-negative")
    if cost_per_task < 0:
        raise CitationExpansionError("cost_per_task must be non-negative")
    if max_tasks_per_direction < 0:
        raise CitationExpansionError("max_tasks_per_direction must be >= 0")
    if max_depth < 1:
        raise CitationExpansionError("max_depth must be >= 1")
    if max_depth > MAX_DEPTH_CEILING:
        raise CitationExpansionError(
            f"max_depth {max_depth} exceeds the citation-walk ceiling {MAX_DEPTH_CEILING}; "
            "unbounded citation walks are not supported — feed fetched records back instead"
        )

    seen = set(seen_refs or ())
    collected = {direction: _direction_targets(records, direction) for direction in DIRECTIONS}
    benefit = {
        direction: sum(1 for target, _ in pairs if target not in seen)
        for direction, pairs in collected.items()
    }
    # marginal-benefit order, deterministic tie-break by DIRECTIONS
    ordered = sorted(DIRECTIONS, key=lambda d: (-benefit[d], DIRECTIONS.index(d)))

    accounts: list[CitationDirectionAccount] = []
    requests_left = budget_requests
    cost_left = budget_cost
    stop_reason = "all_directions_accounted"

    for direction in ordered:
        pairs = collected[direction]
        new_pairs = [(target, origin) for target, origin in pairs if target not in seen]
        if not new_pairs:
            accounts.append(
                CitationDirectionAccount(
                    direction=direction,
                    reported=len(pairs),
                    new_refs=0,
                    admitted=0,
                    status="zero_yield_pruned",
                    reason="no unseen refs reported for this direction",
                    tasks=(),
                )
            )
            continue
        if requests_left <= 0 or cost_left < cost_per_task:
            accounts.append(
                CitationDirectionAccount(
                    direction=direction,
                    reported=len(pairs),
                    new_refs=len(new_pairs),
                    admitted=0,
                    status="budget_exhausted",
                    reason="unified budget exhausted before this direction",
                    tasks=(),
                )
            )
            stop_reason = "budget_exhausted"
            continue

        by_requests = requests_left
        by_cost = int(cost_left // cost_per_task) if cost_per_task > 0 else new_pairs.__len__()
        cap = min(max_tasks_per_direction, by_requests, by_cost, len(new_pairs))
        admitted_pairs = new_pairs[:cap]
        tasks = tuple(
            CitationTask(
                origin_id=origin,
                direction=direction,
                target_ref=target,
                depth=1,
                reason=f"marginal-benefit {direction} expansion of {origin} reported by source",
                provenance_field=_DIRECTION_FIELDS[direction],
            )
            for target, origin in admitted_pairs
        )
        requests_left -= len(tasks)
        cost_left -= len(tasks) * cost_per_task
        status = "admitted"
        reason = "admitted by marginal benefit"
        if cap < len(new_pairs):
            status = "task_cap"
            reason = "per-direction task cap or budget truncated this direction"
            stop_reason = "task_cap"
        accounts.append(
            CitationDirectionAccount(
                direction=direction,
                reported=len(pairs),
                new_refs=len(new_pairs),
                admitted=len(tasks),
                status=status,
                reason=reason,
                tasks=tasks,
            )
        )

    return CitationBudgetPlan(
        accounts=tuple(accounts),
        stop_reason=stop_reason,
        budget_requests_before=budget_requests,
        budget_cost_before=budget_cost,
        cost_per_task=cost_per_task,
    )


def citation_tasks_to_query_specs(
    tasks: list[CitationTask],
    *,
    language: str = "en",
    source: str = "multi",
    owner: str = _OWNER,
) -> list[QuerySpec]:
    """Turn admitted citation tasks into ``citation_expand`` QuerySpec proposals.

    The specs are proposals (``approved=False``); when appended to a plan they
    flow through ``AdaptiveController.run_plan`` and consume the same request
    and cost budget as every other query — the unified budget, not a side door.
    ``feature_ids`` stays empty (a citation hop has no resolvable technical
    feature → unknown coverage, never fabricated zero coverage).
    """
    specs: list[QuerySpec] = []
    for task in tasks:
        specs.append(
            QuerySpec(
                owner=owner,
                query_id=f"cite-{task.direction}-{task.target_ref}",
                axis_id="citation",
                terms=[task.target_ref],
                language=language,
                query_type=QueryType.CITATION_EXPAND,
                source=source,
                feature_ids=[],
                filters={
                    "origin_id": task.origin_id,
                    "direction": task.direction,
                    "target_ref": task.target_ref,
                    "depth": task.depth,
                },
                provenance=[
                    {
                        # a citation hop has no resolvable technical feature —
                        # UT-Q03 requires the key; None keeps coverage unknown
                        "feature_id": None,
                        "kind": "citation_task",
                        "origin_id": task.origin_id,
                        "direction": task.direction,
                        "target_ref": task.target_ref,
                        "depth": task.depth,
                        "field": task.provenance_field,
                        "reason": task.reason,
                    }
                ],
                approved=False,
                rendered={},
            )
        )
    return specs
