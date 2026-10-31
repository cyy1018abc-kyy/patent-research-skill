"""Offline recall pipeline over a kernel workspace (blueprint A-06/A-07, `recall report`).

Ties the WP-A loop together **fully offline**: read glossary axes via the kernel
bridge → extract features → build query plan → run the AdaptiveController over a
local BM25 corpus (kernel candidates + raw captures) → coverage + yield report.

Everything writes only to the sidecar (`reports/`); the kernel workspace is read-only.
The report is a diagnostic: it never asserts recall completeness.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from patent_intel.contracts import QuerySpec
from patent_intel.io.safe_io import write_json_atomic
from patent_intel.kernel_bridge import read_axes, read_candidates
from patent_intel.retrieval.controller import AdaptiveController, Cancelled, FamilyBasis, RunOutcome
from patent_intel.retrieval.features import extract_features
from patent_intel.retrieval.lexical import BM25Index, CorpusDoc, corpus_from_candidates
from patent_intel.retrieval.query_plan import QueryPlanBuilder

__all__ = ["build_workspace_corpus", "recall_report"]

_OWNER = "WP-A"


def build_workspace_corpus(workspace: Path) -> list[CorpusDoc]:
    """Corpus = kernel candidates (title/summary/tags). Raw text captures are added
    by callers that need them; the candidate list is the stable core."""
    return corpus_from_candidates(read_candidates(workspace))


def _axes_texts(workspace: Path) -> dict[str, str]:
    axes = read_axes(workspace)
    out: dict[str, str] = {}
    for axis_id, info in axes.items():
        title = str((info or {}).get("title_zh") or (info or {}).get("title_en") or "").strip()
        if title:
            out[axis_id] = title
    return out


def _runner_for(index: BM25Index, corpus_docs: list[CorpusDoc], *, k: int = 20) -> Any:
    family_of = {doc.doc_id: doc.family_id for doc in corpus_docs}

    def runner(query: QuerySpec) -> RunOutcome:
        text = " ".join(query.terms)
        ranked = index.search(text, k=k)
        hits = [doc_id for doc_id, _ in ranked]
        # Family ids only from corpus-reported family relations; documents without one
        # stay document-level evidence — a document id never masquerades as a family
        # id (adaptive roadmap Task 1 / UT-S03).
        fams: list[str] = []
        for doc_id in hits:
            fam = family_of.get(doc_id)
            if fam and fam not in fams:
                fams.append(fam)
        basis = FamilyBasis.REPORTED if fams else FamilyBasis.UNKNOWN
        return RunOutcome(
            query_id=query.query_id, hits=hits, families=fams, new_families=[], family_basis=basis
        )

    return runner


def recall_report(
    workspace: Path,
    state_dir: Path,
    *,
    max_requests: int = 20,
    zero_gain_rounds: int = 3,
) -> dict[str, Any]:
    """Run the offline recall diagnostic. Returns the report dict (also written to
    the sidecar reports/ directory with a timestamped name)."""
    started = time.time()
    workspace = Path(workspace)
    corpus_docs = build_workspace_corpus(workspace)
    index = BM25Index(corpus_docs)

    axes = _axes_texts(workspace)
    concepts_by_axis: dict[str, list[str]] = {}
    queries: list[QuerySpec] = []
    builder = QueryPlanBuilder()
    for axis_id, title in sorted(axes.items()):
        bundle = extract_features([title], axis_id=axis_id, source_tag="glossary-axis")
        plan = builder.build(bundle)
        queries.extend(plan.queries)
        concepts_by_axis[axis_id] = [f.feature_id for f in bundle.features]

    controller = AdaptiveController(
        _runner_for(index, corpus_docs),
        max_requests=max_requests,
        zero_gain_rounds=zero_gain_rounds,
        concepts_by_axis=concepts_by_axis,
    )
    try:
        run = controller.run_plan(queries)
    except Cancelled:  # pragma: no cover - offline runner never cancels
        run = controller.run_plan([])

    ledger = controller.ledger.describe()

    report: dict[str, Any] = {
        "tool": "patent_intel recall",
        "mode": "offline (BM25 over workspace candidates)",
        "workspace": str(workspace),
        "corpus_size": len(index),
        "axes": sorted(axes),
        "queries_planned": len(queries),
        "run": run.describe(),
        "ledger": ledger,
        "elapsed_sec": round(time.time() - started, 3),
        "caveat": (
            "offline diagnostic over the workspace's own candidate corpus — "
            "it measures coverage of THAT corpus, not external databases; "
            "停止/未覆盖 ≠ 查全或查无"
        ),
    }
    write_json_atomic(
        Path(state_dir) / "reports" / f"recall_{time.strftime('%Y%m%d_%H%M%S')}.json",
        report,
    )
    return report
