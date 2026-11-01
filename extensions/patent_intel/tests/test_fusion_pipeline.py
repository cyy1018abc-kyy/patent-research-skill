"""WP-L1 tests: multi-channel fusion pipeline (roadmap Phase 4 wiring).

Acceptance anchors: determinism, single-channel identity, errored/absent channels
recorded and never zero-filled, family collapse semantics, and the fused score
being a ranking signal only.
"""

from __future__ import annotations

import pytest

from patent_intel.retrieval.fusion_pipeline import (
    ChannelResult,
    FusionError,
    FusionPipeline,
)
from patent_intel.retrieval.hybrid import rrf_fuse
from patent_intel.retrieval.lexical import BM25Index, CorpusDoc
from patent_intel.retrieval.query_plan import QuerySpec
from patent_intel.retrieval import reporting


def _spec(qid: str) -> QuerySpec:
    return QuerySpec(
        owner="WP-A", query_id=qid, axis_id="N1@TGT-0001", terms=["信标"], language="zh",
        query_type="single_feature", source="multi",
    )


# ── weighted RRF (hybrid.rrf_fuse) ───────────────────────────────────


def test_weighted_rrf_dominates_and_stays_deterministic() -> None:
    rankings = {"lexical": ["D1", "D2", "D3"], "dense": ["D3", "D1", "D2"]}
    heavy_dense = rrf_fuse(rankings, k=60, weights={"dense": 10.0})
    assert heavy_dense[0][0] == "D3"  # heavy dense channel pulls its top up
    assert rrf_fuse(rankings, k=60, weights={"dense": 10.0}) == heavy_dense  # deterministic
    # no weights → the pre-L1 behaviour is unchanged
    assert rrf_fuse(rankings, k=60) == rrf_fuse(rankings, k=60)


def test_rrf_single_channel_preserves_order() -> None:
    ranked = rrf_fuse({"only": ["D2", "D1", "D3"]}, k=60)
    assert [doc for doc, _ in ranked] == ["D2", "D1", "D3"]


# ── FusionPipeline ───────────────────────────────────────────────────


def test_pipeline_fuses_two_channels_and_collapses_families() -> None:
    pipeline = FusionPipeline(k=60)
    result = pipeline.fuse(
        [
            ChannelResult("lexical_bm25", ["D1", "D2", "D3"]),
            ChannelResult("dense", ["D3", "D4", "D1"]),
        ],
        family_of={"D1": "FAM-1", "D2": "FAM-1", "D3": "FAM-2"},
    )
    fused_ids = [doc for doc, _ in result.fused]
    assert fused_ids[0] == "D1"  # present near top of both channels
    assert "D2" not in fused_ids  # collapsed into FAM-1 (D1 kept, best position)
    assert "D4" in fused_ids  # unknown family stays independent
    assert result.channels == {"lexical_bm25": ["D1", "D2", "D3"], "dense": ["D3", "D4", "D1"]}
    described = result.describe()
    assert described["channels_present"] == {"lexical_bm25": 3, "dense": 3}
    assert "排序信号" in described["note"]


def test_pipeline_records_errored_and_absent_channels() -> None:
    pipeline = FusionPipeline()
    result = pipeline.fuse(
        [
            ChannelResult("lexical_bm25", ["D1", "D2"]),
            ChannelResult("dense", [], error="RuntimeError: dense extra missing"),
        ],
        family_of={},
        absent={"citation": "not configured for this run"},
    )
    assert [doc for doc, _ in result.fused] == ["D1", "D2"]  # lexical-only, order preserved
    assert result.channels_errored == {"dense": "RuntimeError: dense extra missing"}
    assert result.channels_absent == {"citation": "not configured for this run"}


def test_pipeline_refuses_to_fabricate_without_channels() -> None:
    pipeline = FusionPipeline()
    with pytest.raises(FusionError, match="refusing to fabricate"):
        pipeline.fuse([ChannelResult("dense", [], error="extra missing")], family_of={})
    with pytest.raises(FusionError, match="refusing to fabricate"):
        pipeline.fuse([], family_of={}, absent={"lexical_bm25": "index not built"})


def test_pipeline_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError, match="k must be positive"):
        FusionPipeline(k=0)


# ── reporting integration (fused runner) ─────────────────────────────


def _corpus() -> list[CorpusDoc]:
    return [
        CorpusDoc("D1", "信标发送时刻估计 beacon timing", family_id="FAM-1"),
        CorpusDoc("D2", "信标周期调整 beacon period adaptation", family_id="FAM-1"),
        CorpusDoc("D3", "电池管理 state of charge", family_id="FAM-2"),
        CorpusDoc("D4", "信标漂移 beacon drift", family_id=None),
    ]


class _FakeDense:
    """Deterministic fake dense channel (no extra, no model, no network)."""

    def __init__(self, ranked_by_query: dict[str, list[str]]) -> None:
        self._ranked = ranked_by_query

    def rank(self, query: str, docs: list[tuple[str, str]], *, top: int = 10) -> list[tuple[str, float]]:
        ranked = self._ranked.get(query, [])
        return [(doc_id, 1.0 / (i + 1)) for i, doc_id in enumerate(ranked[:top])]


class _BrokenDense:
    def rank(self, query: str, docs: list[tuple[str, str]], *, top: int = 10) -> list[tuple[str, float]]:
        raise RuntimeError("the 'dense' extra is required: pip install 'patent_intel[dense]'")


def test_fused_runner_default_matches_bm25_and_records_channels() -> None:
    index = BM25Index(_corpus())
    runner = reporting._runner_for(index, _corpus(), k=5)
    bm25_order = [doc for doc, _ in index.search("信标 beacon", k=5)]
    outcome = runner(_spec("Q1"))
    # single channel preserves BM25 order *modulo family collapse* (Phase 4 semantics):
    # D2 ranks above D1, so FAM-1 keeps D2 as its representative
    assert bm25_order.index("D2") < bm25_order.index("D1")
    assert outcome.hits == ["D4", "D2"]
    assert "D2" not in outcome.families and "FAM-1" in outcome.families
    assert "D4" in outcome.hits and "D4" not in outcome.families  # familyless stays doc-level
    assert outcome.channel_report is not None
    assert outcome.channel_report["channels_present"] == {"lexical_bm25": 3}  # raw channel size (pre-collapse)
    assert outcome.channel_report["channels_absent"]["dense"].startswith("not enabled")


def test_fused_runner_merges_dense_channel_and_survives_its_failure() -> None:
    index = BM25Index(_corpus())
    dense = _FakeDense({"信标 beacon": ["D4", "D3", "D1"]})  # dense loves the familyless doc
    runner = reporting._runner_for(index, _corpus(), k=5, dense_retriever=dense)
    outcome = runner(_spec("Q1"))
    report = outcome.channel_report
    assert set(report["channels_present"]) == {"lexical_bm25", "dense"}
    assert report["channels_errored"] == {}
    assert "D4" in outcome.hits[:2]  # dense pull-up is visible in the fused order

    broken_runner = reporting._runner_for(index, _corpus(), k=5, dense_retriever=_BrokenDense())
    degraded = broken_runner(_spec("Q1"))
    assert degraded.hits  # lexical-only ranking survives
    assert "dense" in degraded.channel_report["channels_errored"]
    assert "RuntimeError" in degraded.channel_report["channels_errored"]["dense"]


def test_recall_report_carries_fusion_account(gold_workspace, tmp_path) -> None:
    report = reporting.recall_report(gold_workspace, tmp_path / "sidecar")
    assert report["fusion"]["channels_present"] == ["lexical_bm25"]
    assert "dense" in report["fusion"]["channels_absent"]
    assert report["run"]["outcomes"]


def test_recall_report_dense_failure_is_recorded_not_fatal(
    gold_workspace, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from patent_intel.workspace import SidecarLayout
    from patent_intel.retrieval.hybrid import DenseRetriever

    def broken_rank(self, query, docs, *, top=10):  # pragma: no cover - monkeypatched
        raise RuntimeError("dense extra missing")

    monkeypatch.setattr(DenseRetriever, "rank", broken_rank)
    report = reporting.recall_report(
        gold_workspace, tmp_path / "sidecar", enable_dense=True
    )
    assert "dense" in report["fusion"]["channels_errored"]
    assert "lexical_bm25" in report["fusion"]["channels_present"]


# ── WP-L2: rerank stage ──────────────────────────────────────────────


class _ReverseTop2:
    """Reorders whatever top-N the pipeline hands it (contract-abiding)."""

    name = "fake-cross-encoder"

    def rerank(self, query: str, candidates: list[tuple[str, float]]) -> list[tuple[str, float]]:
        return list(reversed(candidates))


class _BrokenReranker:
    name = "broken-model"

    def rerank(self, query: str, candidates: list[tuple[str, float]]) -> list[tuple[str, float]]:
        raise RuntimeError("model files missing")


class _CheatingReranker:
    """Violates the contract: invents a candidate and drops another."""

    name = "cheater"

    def rerank(self, query: str, candidates: list[tuple[str, float]]) -> list[tuple[str, float]]:
        return [("D9", 1.0)]


def test_identity_reranker_preserves_order() -> None:
    from patent_intel.retrieval.reranker import IdentityReranker

    candidates = [("D2", 0.9), ("D1", 0.5), ("D3", 0.1)]
    assert IdentityReranker().rerank("q", candidates) == candidates


def test_pipeline_applies_reranker_to_top_n_and_keeps_tail() -> None:
    pipeline = FusionPipeline(k=60, reranker=_ReverseTop2(), rerank_top=2)
    result = pipeline.fuse(
        [ChannelResult("lexical_bm25", ["D1", "D2", "D3"])],
        family_of={},
        query="信标",
    )
    assert [doc for doc, _ in result.fused][:2] == ["D2", "D1"]  # top-2 reversed by reranker
    assert [doc for doc, _ in result.fused][2:] == ["D3"]  # tail keeps fused order
    account = result.rerank
    assert account.applied is True and account.reranker == "fake-cross-encoder"
    assert account.top == 2 and account.error is None
    assert result.describe()["rerank"]["applied"] is True


def test_pipeline_reranker_failure_degrades_with_account() -> None:
    pipeline = FusionPipeline(k=60, reranker=_BrokenReranker(), rerank_top=2)
    result = pipeline.fuse(
        [ChannelResult("lexical_bm25", ["D1", "D2", "D3"])], family_of={}, query="信标"
    )
    assert [doc for doc, _ in result.fused] == ["D1", "D2", "D3"]  # pre-rerank order kept
    assert result.rerank.applied is False
    assert result.rerank.error and "RuntimeError" in result.rerank.error


def test_pipeline_refuses_contract_violating_reranker() -> None:
    pipeline = FusionPipeline(k=60, reranker=_CheatingReranker(), rerank_top=2)
    result = pipeline.fuse(
        [ChannelResult("lexical_bm25", ["D1", "D2", "D3"])], family_of={}, query="信标"
    )
    assert [doc for doc, _ in result.fused] == ["D1", "D2", "D3"]  # untrusted, original kept
    assert result.rerank.applied is False
    assert "contract violation" in (result.rerank.error or "")


def test_runner_without_reranker_records_empty_account() -> None:
    index = BM25Index(_corpus())
    runner = reporting._runner_for(index, _corpus(), k=5)
    outcome = runner(_spec("Q1"))
    assert outcome.channel_report["rerank"] == {"reranker": None, "applied": False, "error": None, "top": None}


def test_runner_with_identity_reranker_leaves_fused_order_intact() -> None:
    from patent_intel.retrieval.reranker import IdentityReranker

    index = BM25Index(_corpus())
    plain = reporting._runner_for(index, _corpus(), k=5)
    reranked = reporting._runner_for(index, _corpus(), k=5, reranker=IdentityReranker())
    assert reranked(_spec("Q1")).hits == plain(_spec("Q1")).hits
