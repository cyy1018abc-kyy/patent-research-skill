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
from patent_intel.retrieval.fusion_pipeline import ChannelResult, FusionPipeline
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


def _runner_for(
    index: BM25Index,
    corpus_docs: list[CorpusDoc],
    *,
    k: int = 20,
    dense_retriever: Any | None = None,
    fuse_k: int = 60,
    fuse_top: int | None = None,
    reranker: Any | None = None,
    rerank_top: int = 50,
) -> Any:
    """Fused per-query runner (WP-L1/L2): lexical BM25 always present, dense and
    rerank optional.

    Family ids only from corpus-reported family relations; documents without one
    stay document-level evidence — a document id never masquerades as a family id
    (adaptive roadmap Task 1 / UT-S03). A single configured channel degenerates to
    the identical ranking (RRF over one list is order-preserving); a failing dense
    or rerank stage degrades with the reason recorded.
    """
    family_of = {doc.doc_id: doc.family_id for doc in corpus_docs}
    known_families = {doc_id: fam for doc_id, fam in family_of.items() if fam}
    doc_texts = [(doc.doc_id, doc.text) for doc in corpus_docs]
    pipeline = FusionPipeline(
        k=fuse_k, top=fuse_top, reranker=reranker, rerank_top=rerank_top
    )
    absent: dict[str, str] = {} if dense_retriever is not None else {
        "dense": "not enabled (enable_dense/--dense; requires the 'dense' extra)"
    }

    def runner(query: QuerySpec) -> RunOutcome:
        text = " ".join(query.terms)
        channels = [ChannelResult("lexical_bm25", [doc_id for doc_id, _ in index.search(text, k=k)])]
        if dense_retriever is not None:
            try:
                dense_ranked = [doc_id for doc_id, _ in dense_retriever.rank(text, doc_texts, top=k)]
                channels.append(ChannelResult("dense", dense_ranked))
            except Exception as exc:  # noqa: BLE001 - channel failure is recorded, never silent
                channels.append(
                    ChannelResult("dense", [], error=f"{type(exc).__name__}: {exc}")
                )
        fusion = pipeline.fuse(channels, family_of=known_families, absent=absent, query=text)
        hits = [doc_id for doc_id, _score in fusion.fused]
        fams: list[str] = []
        for doc_id in hits:
            fam = known_families.get(doc_id)
            if fam and fam not in fams:
                fams.append(fam)
        basis = FamilyBasis.REPORTED if fams else FamilyBasis.UNKNOWN
        return RunOutcome(
            query_id=query.query_id,
            hits=hits,
            families=fams,
            new_families=[],
            family_basis=basis,
            channel_report=fusion.describe(),
        )

    return runner


def recall_report(
    workspace: Path,
    state_dir: Path,
    *,
    max_requests: int = 20,
    zero_gain_rounds: int = 3,
    enable_dense: bool = False,
) -> dict[str, Any]:
    """Run the offline recall diagnostic. Returns the report dict (also written to
    the sidecar reports/ directory with a timestamped name).

    ``enable_dense`` adds the dense channel (requires the ``dense`` extra); its
    failure is recorded per query and fusion degrades to lexical-only — a channel
    is never silently missing (WP-L1)."""
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

    dense_retriever = None
    if enable_dense:
        from patent_intel.retrieval.hybrid import DenseRetriever

        dense_retriever = DenseRetriever()
    controller = AdaptiveController(
        _runner_for(index, corpus_docs, dense_retriever=dense_retriever),
        max_requests=max_requests,
        zero_gain_rounds=zero_gain_rounds,
        concepts_by_axis=concepts_by_axis,
    )
    try:
        run = controller.run_plan(queries)
    except Cancelled:  # pragma: no cover - offline runner never cancels
        run = controller.run_plan([])

    ledger = controller.ledger.describe()

    # fusion account: union of per-query channel states (never inferred, always recorded)
    present: set[str] = set()
    errored: dict[str, str] = {}
    absent: dict[str, str] = {}
    for outcome in run.outcomes:
        channel_report = outcome.channel_report or {}
        present.update(channel_report.get("channels_present", {}))
        errored.update(channel_report.get("channels_errored", {}))
        absent.update(channel_report.get("channels_absent", {}))
    fusion_summary = {
        "channels_present": sorted(present),
        "channels_errored": errored,
        "channels_absent": absent,
        "note": (
            "RRF 融合分数是排序信号，不是证据强度；通道缺席/失败留痕，"
            "不当 0 分通道混入 (absent/errored channels are recorded, never zero-filled)"
        ),
    }

    report: dict[str, Any] = {
        "tool": "patent_intel recall",
        "mode": "offline (BM25 over workspace candidates)",
        "workspace": str(workspace),
        "corpus_size": len(index),
        "axes": sorted(axes),
        "queries_planned": len(queries),
        "run": run.describe(),
        "ledger": ledger,
        "fusion": fusion_summary,
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
