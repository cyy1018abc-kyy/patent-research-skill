"""Citation-chain expansion tasks (blueprint A-05, WP-A + WP-B execution).

Produces *proposals* for follow-up retrieval: follow a record's citation links
(cites / cited-by / family) within explicit budget limits. Data comes from what a
source actually reported — the model never invents citation facts, and a task is
only created when the underlying field exists in the record (no fabricated links).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["CitationTask", "CitationExpansionError", "plan_citation_expansion"]

_OWNER = "WP-A"


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
