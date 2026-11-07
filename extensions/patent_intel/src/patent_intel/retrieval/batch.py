"""First-class batch retrieval entry (roadmap 41A-5).

One auditable library call for "corpus snapshot + topic manifest + config →
result rows": the preregistered benchmark loops (``benchmarks/retrieval/
run_benchmark.py``) become a thin shell over :func:`run_batch`, and any other
caller gets the exact same deterministic semantics instead of re-implementing
the loop.

Discipline carried over from the preregistered runner:

* **byte-identical** — same topics + same index + same config → same rows bytes
  (the rows are the preregistered artifact shape: ``topic_id``/``family_id``/
  ``rank``);
* **explicit batch mode** — ``batch_mode`` is stamped into the meta, a batch run
  never masquerades as an interactive run;
* **explicit auto-approval** — the extension side marks planned queries approved
  ONLY when ``BatchConfig.approve_queries`` is set. Benchmark mode auto-approves
  (gate.yaml declares it: the retrieval layer is under test, not the human
  approval workflow); workspace flows keep the default ``False``, where plans
  stay unapproved proposals and the batch yields nothing rather than sneaking
  past the approval gate.

No wall clock, no RNG, no network; standard-library only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from patent_intel.retrieval.lexical import BM25Index

__all__ = [
    "BatchConfig",
    "BatchResult",
    "run_batch",
    "merge_rankings",
    "topic_query_texts",
    "BatchError",
]

_OWNER = "WP-A"

_SIDES = ("baseline", "extension")


class BatchError(ValueError):
    """Invalid batch request (bad side, meaningless flags, non-positive limits)."""


@dataclass(frozen=True)
class BatchConfig:
    """Explicit knobs for one batch run — nothing is inferred from the environment."""

    side: str  # "baseline" | "extension"
    k_per_request: int = 200
    #: per-topic request budget for the extension side (gate.yaml: 3)
    budget_requests: int = 3
    #: engine parameters reported verbatim in the meta (the caller builds the index)
    engine_params: Mapping[str, Any] = field(default_factory=dict)
    #: 41A-5: benchmark-mode auto-approval is now an explicit flag, not a silent
    #: offset. ``False`` (default) keeps plans unapproved — an unapproved batch
    #: yields zero rows instead of bypassing the approval gate.
    approve_queries: bool = False

    def __post_init__(self) -> None:
        if self.side not in _SIDES:
            raise BatchError(f"side must be one of {_SIDES}, got {self.side!r}")
        if self.k_per_request <= 0:
            raise BatchError(f"k_per_request must be positive, got {self.k_per_request}")
        if self.budget_requests < 0:
            raise BatchError(f"budget_requests must be non-negative, got {self.budget_requests}")
        if self.approve_queries and self.side != "extension":
            raise BatchError("approve_queries applies to the extension side only")


class BatchResult:
    """Rows + honest accounting for one batch run (immutable view)."""

    def __init__(self, *, rows: list[dict[str, Any]], requests_total: int, meta: dict[str, Any]) -> None:
        self.rows = rows
        self.requests_total = requests_total
        self.meta = meta

    def describe(self) -> dict[str, Any]:
        return {
            "meta": dict(self.meta),
            "rows_count": len(self.rows),
            "requests_total": self.requests_total,
        }


def merge_rankings(score_maps: list[dict[str, float]], k: int) -> list[tuple[str, float]]:
    """Per-document max-merge of score maps, best-first, ties by id ascending."""
    merged: dict[str, float] = {}
    for scores in score_maps:
        for doc_id, score in scores.items():
            if score > merged.get(doc_id, float("-inf")):
                merged[doc_id] = score
    ranked = sorted(merged.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:k]


def topic_query_texts(topic: Mapping[str, Any], queries_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """The three mechanical baseline request texts for one topic (preregistered)."""
    q = queries_by_id[topic["source_id"]]
    tac = " ".join(x for x in (q["title_en"], q["abstract_en"], q["claims_text"]) if x)
    ta = " ".join(x for x in (q["title_en"], q["abstract_en"]) if x)
    return {"tac": tac, "ta": ta, "claims": q["claims_text"] or ""}


def run_batch(
    topics: Sequence[Mapping[str, Any]],
    queries_by_id: Mapping[str, Mapping[str, Any]],
    index: BM25Index,
    config: BatchConfig,
    *,
    batch_mode: str = "manual",
    progress: Callable[[int, int], None] | None = None,
) -> BatchResult:
    """Run one side over ``topics`` against a shared BM25 index.

    ``batch_mode`` is stamped into the meta verbatim. ``progress`` (if given) is
    called as ``(completed, total)`` after every topic; the library itself prints
    nothing — output belongs to the shell.
    """
    rows: list[dict[str, Any]] = []
    requests_total = 0

    if config.side == "baseline":
        for completed, topic in enumerate(topics, start=1):
            texts = topic_query_texts(topic, queries_by_id)
            score_maps = []
            for name in ("tac", "ta", "claims"):  # preregistered fixed variants
                hits = index.search(texts[name], k=config.k_per_request)
                requests_total += 1
                score_maps.append(dict(hits))
            for rank, (fam, _score) in enumerate(merge_rankings(score_maps, config.k_per_request), start=1):
                rows.append({"topic_id": topic["topic_id"], "family_id": fam, "rank": rank})
            if progress is not None:
                progress(completed, len(topics))
        meta = {
            "engine": "BM25Index",
            "engine_params": dict(config.engine_params),
            "requests_total": requests_total,
            "topics_run": len(topics),
            "budget": f"{config.budget_requests} fixed requests (tac/ta/claims)",
        }
    else:
        rows, requests_total = _run_extension(topics, queries_by_id, index, config, progress)
        import patent_intel

        meta = {
            "engine": "BM25Index",
            "engine_params": dict(config.engine_params),
            "requests_total": requests_total,
            "topics_run": len(topics),
            "budget": f"AdaptiveController max {config.budget_requests} requests/topic",
            "patent_intel_version": patent_intel.__version__,
        }
    meta["batch_mode"] = batch_mode
    return BatchResult(rows=rows, requests_total=requests_total, meta=meta)


def _run_extension(
    topics: Sequence[Mapping[str, Any]],
    queries_by_id: Mapping[str, Mapping[str, Any]],
    index: BM25Index,
    config: BatchConfig,
    progress: Callable[[int, int], None] | None,
) -> tuple[list[dict[str, Any]], int]:
    from patent_intel.retrieval.controller import AdaptiveController, RunOutcome
    from patent_intel.retrieval.features import extract_features
    from patent_intel.retrieval.query_plan import QueryPlanBuilder

    rows: list[dict[str, Any]] = []
    requests_total = 0

    def run_topic(topic: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int]:
        q = queries_by_id[topic["source_id"]]
        statements = [q["title_en"] or "", q["abstract_en"] or ""]
        statements += [c.strip() for c in (q["claims_text"] or "").splitlines() if c.strip()]
        bundle = extract_features(statements, axis_id=f"N1@{topic['topic_id']}",
                                  source_tag="dapfam-benchmark", approved=True)
        plan = QueryPlanBuilder().build(bundle)
        # gate.yaml declares benchmark-mode auto-approval — and 41A-5 makes that
        # an explicit flag instead of a silent offset (see BatchConfig).
        if config.approve_queries:
            for query_spec in plan.queries:
                query_spec.approved = True
        pending = plan.approved_queries()
        if not pending:
            return [], 0
        score_maps: list[dict[str, float]] = []
        executed = 0

        def runner(query_spec):  # injected search executor (offline BM25)
            nonlocal executed
            executed += 1
            hits = index.search(" ".join(query_spec.terms), k=config.k_per_request)
            score_maps.append(dict(hits))
            return RunOutcome(query_id=query_spec.query_id,
                              hits=[h[0] for h in hits], families=[h[0] for h in hits],
                              cost=1.0)

        controller = AdaptiveController(
            runner, max_requests=config.budget_requests, max_cost=float(config.budget_requests)
        )
        report = controller.run_plan(pending)
        merged = merge_rankings(score_maps, config.k_per_request)
        return [{"topic_id": topic["topic_id"], "family_id": fam, "rank": rank}
                for rank, (fam, _score) in enumerate(merged, start=1)], executed

    for completed, topic in enumerate(topics, start=1):
        topic_rows, used = run_topic(topic)
        rows.extend(topic_rows)
        requests_total += used
        if progress is not None:
            progress(completed, len(topics))
    return rows, requests_total
