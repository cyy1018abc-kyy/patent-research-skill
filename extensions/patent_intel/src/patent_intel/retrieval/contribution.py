"""Per-query contribution ledger (roadmap 41A-2 / P1-A2): which query contributes new
families, which query repeats work already done.

Read-only derivation: the input is an existing
:class:`~patent_intel.retrieval.controller.ControllerReport`; this module only reads
``ControllerReport.outcomes`` (per-query cost/hits/families/error and the recorded
``new_families``/``new_documents``) — it never mutates the controller, the ledger or
the outcomes, and it never re-runs queries.

Accounting discipline:

* first-seen families/documents are **recomputed** by walking outcomes in execution
  order with :class:`~patent_intel.retrieval.coverage.QueryYieldLedger` semantics —
  families deduped globally, documents deduped independently, the two dimensions
  recorded side by side (UT-S03: a document id never masquerades as a family id);
* recorded ``RunOutcome.new_families`` / ``new_documents`` fields are cross-checked
  when non-empty; disagreement is reported as a problem (hand-built reports often
  leave them stale), never silently trusted or silently ignored;
* ``marginal_benefit`` = 新增候选族 + 新增文档 — the same two dimensions the
  controller's zero-gain streak resets on. These are **candidate** counts:
  candidate ≠ relevant, no relevance judgement is implied;
* a query is **duplicate labor (重复劳动)** when it executed cleanly, returned
  something, and added neither a new candidate family nor a new document — every
  family/document it returned had already been seen from an earlier query. A clean
  query that found nothing at all is an empty result, not a duplicate;
* errored outcomes contribute nothing to the seen-sets (unreliable data must not
  poison the derivation), are flagged, and are never classified as duplicates;
* zero or negative cost ⇒ ``yield_per_cost`` is ``None`` — undefined, never a faked
  ``0.0``/``inf`` (no division by zero, mirroring the evaluator's ratio guards);
* determinism: rows sort by contribution with query-id/execution-index tiebreaks;
  ``describe_json()`` emits canonical JSON — same input, same bytes (UT-R01 spirit).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from patent_intel.retrieval.controller import ControllerReport

__all__ = ["QueryContribution", "ContributionReport"]

_OWNER = "WP-A"


@dataclass
class QueryContribution:
    """One executed query's contribution row — all values derived, none invented."""

    query_id: str
    #: position in ``ControllerReport.outcomes`` (execution order)
    execution_index: int
    cost: float
    #: raw document hits as the runner returned them (总命中, not deduped)
    total_hits: int
    #: distinct family ids hit (family identity discipline: a family counts once)
    family_hits: int
    #: first-seen candidate families brought by this query (in-hit order)
    new_families: list[str] = field(default_factory=list)
    #: first-seen documents brought by this query (in-hit order)
    new_documents: list[str] = field(default_factory=list)
    #: already-seen families re-hit by this query (sorted)
    repeated_families: list[str] = field(default_factory=list)
    #: already-seen documents re-hit by this query (sorted)
    repeated_documents: list[str] = field(default_factory=list)
    #: 新增候选族 + 新增文档 (the two ledger dimensions, side by side; candidate ≠ relevant)
    marginal_benefit: int = 0
    #: marginal_benefit per unit cost; None when cost <= 0 (undefined, not zero)
    yield_per_cost: float | None = None
    #: 重复劳动: clean run, returned something, added nothing new on either dimension
    duplicate: bool = False
    error: str | None = None

    @property
    def errored(self) -> bool:
        return self.error is not None

    def describe(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "execution_index": self.execution_index,
            "cost": round(self.cost, 4),
            "total_hits": self.total_hits,
            "family_hits": self.family_hits,
            "new_families": len(self.new_families),
            "new_family_ids": list(self.new_families),
            "new_documents": len(self.new_documents),
            "new_document_ids": list(self.new_documents),
            "repeated_families": list(self.repeated_families),
            "repeated_documents": list(self.repeated_documents),
            "marginal_benefit": self.marginal_benefit,
            "yield_per_cost": self.yield_per_cost,
            "duplicate": self.duplicate,
            "errored": self.errored,
            "error": self.error,
        }


@dataclass
class ContributionReport:
    """Derived per-query contribution ledger over a :class:`ControllerReport`.

    Build once via :meth:`from_report`; all views (``summary``, ``describe``,
    ``describe_json``) are deterministic functions of the walked outcomes.
    """

    #: contribution rows, sorted by contribution (new families → new documents →
    #: total hits → query id → execution index); use :meth:`rows_in_execution_order`
    #: for the append-order ledger view
    rows: list[QueryContribution] = field(default_factory=list)
    #: contracts-style problems list: inconsistent input the walk refused to trust
    problems: list[str] = field(default_factory=list)
    #: family id → query id that first discovered it (candidate level)
    family_first_found: dict[str, str] = field(default_factory=dict)
    #: document id → query id that first retrieved it
    document_first_found: dict[str, str] = field(default_factory=dict)

    # -- construction ------------------------------------------------------

    @classmethod
    def from_report(cls, report: ControllerReport) -> "ContributionReport":
        """Derive the ledger from an existing controller report (read-only)."""
        seen_families: dict[str, str] = {}
        seen_documents: dict[str, str] = {}
        seen_query_ids: set[str] = set()
        computed_families_by_query: dict[str, set[str]] = {}
        problems: list[str] = []
        rows: list[QueryContribution] = []

        if report.queries_run and len(report.queries_run) != len(report.outcomes):
            problems.append(
                f"queries_run({len(report.queries_run)}) and outcomes({len(report.outcomes)}) "
                "disagree — contribution rows follow outcomes order"
            )

        for index, outcome in enumerate(report.outcomes):
            query_id = outcome.query_id
            families = list(dict.fromkeys(outcome.families))
            documents = list(dict.fromkeys(outcome.hits))
            errored = outcome.error is not None

            if outcome.cost < 0:
                problems.append(
                    f"outcome[{index}] {query_id!r}: negative cost {outcome.cost!r} — "
                    "cost accounting is poisoned; yield_per_cost stays undefined"
                )
            if query_id in seen_query_ids:
                problems.append(
                    f"outcome[{index}] {query_id!r}: query_id already executed earlier in "
                    "this report — per-query accounting may double-count"
                )
            seen_query_ids.add(query_id)
            if errored and (families or documents):
                problems.append(
                    f"outcome[{index}] {query_id!r}: errored outcome carries "
                    f"{len(families)} family / {len(documents)} document hits — ignored for "
                    "contribution accounting (unreliable data must not poison the ledger)"
                )

            if errored:
                new_families: list[str] = []
                new_documents: list[str] = []
                repeated_families: list[str] = []
                repeated_documents: list[str] = []
            else:
                new_families = [fam for fam in families if fam not in seen_families]
                repeated_families = sorted(fam for fam in families if fam in seen_families)
                new_documents = [doc for doc in documents if doc not in seen_documents]
                repeated_documents = sorted(doc for doc in documents if doc in seen_documents)
                for fam in new_families:
                    seen_families[fam] = query_id
                for doc in new_documents:
                    seen_documents[doc] = query_id

            if outcome.new_families and set(outcome.new_families) != set(new_families):
                problems.append(
                    f"outcome[{index}] {query_id!r}: recorded new_families disagrees with the "
                    "first-seen derivation from families (stale or inconsistent field)"
                )
            if outcome.new_documents and set(outcome.new_documents) != set(new_documents):
                problems.append(
                    f"outcome[{index}] {query_id!r}: recorded new_documents disagrees with the "
                    "first-seen derivation from hits (stale or inconsistent field)"
                )

            duplicate = (
                not errored
                and bool(families or documents)
                and not new_families
                and not new_documents
            )
            benefit = len(new_families) + len(new_documents)
            rows.append(
                QueryContribution(
                    query_id=query_id,
                    execution_index=index,
                    cost=outcome.cost,
                    total_hits=len(outcome.hits),
                    family_hits=len(families),
                    new_families=new_families,
                    new_documents=new_documents,
                    repeated_families=repeated_families,
                    repeated_documents=repeated_documents,
                    marginal_benefit=benefit,
                    yield_per_cost=round(benefit / outcome.cost, 4) if outcome.cost > 0 else None,
                    duplicate=duplicate,
                    error=outcome.error,
                )
            )
            computed_families_by_query[query_id] = set(new_families)

        if report.ledger is not None:
            if report.ledger.total_new_families != len(seen_families):
                problems.append(
                    f"ledger.total_new_families({report.ledger.total_new_families}) disagrees "
                    f"with the recomputed first-seen families({len(seen_families)}) — outcomes "
                    "and ledger are out of sync"
                )
            for query_id in sorted(computed_families_by_query):
                if set(report.ledger.yield_of(query_id)) != computed_families_by_query[query_id]:
                    problems.append(
                        f"ledger.yield_of({query_id!r}) disagrees with the first-seen "
                        "derivation — outcomes and ledger are out of sync"
                    )

        problems.sort()
        rows.sort(
            key=lambda row: (
                -len(row.new_families),
                -len(row.new_documents),
                -row.total_hits,
                row.query_id,
                row.execution_index,
            )
        )
        return cls(
            rows=rows,
            problems=problems,
            family_first_found=seen_families,
            document_first_found=seen_documents,
        )

    # -- views -------------------------------------------------------------

    @property
    def duplicate_rows(self) -> list[QueryContribution]:
        """Queries identified as duplicate labor (same order as :attr:`rows`)."""
        return [row for row in self.rows if row.duplicate]

    @property
    def rows_in_execution_order(self) -> list[QueryContribution]:
        return sorted(self.rows, key=lambda row: row.execution_index)

    def first_finder_of(self, family_id: str) -> str | None:
        """Query id that first discovered ``family_id`` (candidate level), or None."""
        return self.family_first_found.get(family_id)

    @property
    def summary(self) -> dict[str, Any]:
        rows = self.rows_in_execution_order  # float sums follow execution order
        cost_total = sum(row.cost for row in rows)
        benefit_total = sum(row.marginal_benefit for row in rows)
        return {
            "queries_total": len(self.rows),
            "queries_contributing": sum(1 for row in self.rows if row.marginal_benefit > 0),
            "queries_duplicate": len(self.duplicate_rows),
            "queries_errored": sum(1 for row in self.rows if row.errored),
            "queries_empty_result": sum(
                1 for row in self.rows if not row.errored and row.total_hits == 0 and row.family_hits == 0
            ),
            "queries_nonpositive_cost": sum(1 for row in self.rows if row.cost <= 0),
            "hits_total": sum(row.total_hits for row in self.rows),
            "family_hits_total": sum(row.family_hits for row in self.rows),
            "repeated_family_hits_total": sum(len(row.repeated_families) for row in self.rows),
            "repeated_document_hits_total": sum(len(row.repeated_documents) for row in self.rows),
            "new_families_total": sum(len(row.new_families) for row in self.rows),
            "new_documents_total": sum(len(row.new_documents) for row in self.rows),
            "unique_families_total": len(self.family_first_found),
            "marginal_benefit_total": benefit_total,
            "cost_total": round(cost_total, 4),
            "yield_per_cost_total": round(benefit_total / cost_total, 4) if cost_total > 0 else None,
        }

    def describe(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "queries": [row.describe() for row in self.rows],
            "duplicates": [self._duplicate_detail(row) for row in self.duplicate_rows],
            "problems": list(self.problems),
            "note": (
                "contribution is candidate-level accounting (candidate ≠ relevant); "
                "重复劳动 = 零新增且全部重复命中; marginal_benefit = 新增候选族 + 新增文档"
            ),
        }

    def describe_json(self) -> str:
        """Canonical JSON of :meth:`describe` — same input, same bytes."""
        return json.dumps(
            self.describe(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    def _duplicate_detail(self, row: QueryContribution) -> dict[str, Any]:
        detail = row.describe()
        detail["family_first_found_by"] = {
            fam: self.family_first_found.get(fam, "") for fam in row.repeated_families
        }
        detail["document_first_found_by"] = {
            doc: self.document_first_found.get(doc, "") for doc in row.repeated_documents
        }
        return detail
