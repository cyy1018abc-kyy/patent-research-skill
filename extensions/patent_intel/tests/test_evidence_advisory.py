"""WP-D tests (D-01..D-05): projections, coverage matrix, impact, claim chart,
amendment policy (UT-E01/UT-E02)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from patent_intel.advisory.amendment_proposal import build_amendment_proposal, target_fingerprint_from_claims
from patent_intel.advisory.claim_chart import build_claim_chart
from patent_intel.advisory.gap_analysis import analyze_gaps
from patent_intel.advisory.policy import AdvisoryPolicyError, ensure_proposal_policy
from patent_intel.contracts import AdvisoryProposal, EvidenceProjection, ReviewState, Relation
from patent_intel.documents.claims import parse_claim_dependencies
from patent_intel.documents.patent_xml import parse_patent_xml
from patent_intel.evidence.coverage_matrix import build_coverage_matrix
from patent_intel.evidence.graph import EvidenceGraphBuilder, export_projections, fingerprint_record
from patent_intel.evidence.impact import preview_fingerprint_change

GOLD = Path(__file__).resolve().parents[3] / "benchmarks" / "cases" / "bm01-timesync" / "gold"

FEATURES = [
    {"feature_id": "FEAT-N1-001", "statement": "信标发送时刻估计", "axis_id": "N1@TGT-9001"},
    {"feature_id": "FEAT-N2-001", "statement": "漂移估计与补偿", "axis_id": "N2@TGT-9001"},
    {"feature_id": "FEAT-N3-001", "statement": "动态信标周期", "axis_id": "N3@TGT-9001"},
    {"feature_id": "FEAT-N5-001", "statement": "重同步请求", "axis_id": "N5@TGT-9001"},
]


@pytest.fixture()
def gold_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    shutil.copytree(GOLD, ws)
    return ws


# ── D-01: projections ────────────────────────────────────────────────


def test_projection_build_from_kernel_candidates(gold_ws: Path) -> None:
    projections = EvidenceGraphBuilder(features=FEATURES).build_from_workspace(gold_ws)
    assert projections, "bm01 gold has reviewed candidates on N1/N2 axes"
    # every projection traces to a kernel candidate fingerprint and stays pending
    assert all(p.source_fingerprint for p in projections)
    assert all(p.review_state == ReviewState.PENDING for p in projections)
    relations = {p.relation for p in projections}
    assert relations <= {Relation.DISCLOSES, Relation.PARTIALLY_DISCLOSES, Relation.CITED_BY}


def test_projection_rebuild_deterministic_and_cache_free(gold_ws: Path, tmp_path: Path) -> None:
    builder = EvidenceGraphBuilder(features=FEATURES)
    first = [p.to_dict() for p in builder.build_from_workspace(gold_ws)]
    # cache → delete → rebuild must be identical (cache-deletion invariant)
    out_dir = tmp_path / "evidence"
    path = export_projections(builder.build_from_workspace(gold_ws), out_dir)
    assert path.is_file()
    shutil.rmtree(out_dir)
    second = [p.to_dict() for p in builder.build_from_workspace(gold_ws)]
    assert first == second


def test_fingerprint_changes_when_record_changes() -> None:
    rec = {"id": "P-1", "title": "a"}
    fp1 = fingerprint_record(rec)
    rec2 = {"id": "P-1", "title": "b"}
    assert fingerprint_record(rec2) != fp1
    assert fingerprint_record(rec) == fp1  # stable


# ── D-02: coverage matrix ────────────────────────────────────────────


def test_matrix_cells_explicit(gold_ws: Path) -> None:
    projections = EvidenceGraphBuilder(features=FEATURES).build_from_workspace(gold_ws)
    from patent_intel.kernel_bridge import read_candidates

    candidates = read_candidates(gold_ws)
    matrix = build_coverage_matrix(FEATURES, candidates, projections)
    for row in matrix.rows:
        for cell in row["cells"].values():
            assert cell["status"] in {"supported", "linked", "no_evidence"}
    gaps = matrix.evidence_gaps()
    # FEAT-N5-001: no candidate is tagged N5 in bm01 gold → explicit no_evidence row
    assert "FEAT-N5-001" in gaps
    assert "FEAT-N1-001" not in gaps  # reviewed partial candidate with anchor exists
    assert 0.0 <= matrix.coverage_ratio <= 1.0


# ── D-03: impact preview (UT-E01) ────────────────────────────────────


def test_stale_marking_on_fingerprint_change() -> None:
    projections = [
        EvidenceProjection(
            owner="WP-D", feature_id="F1", candidate_id="P-1", relation=Relation.DISCLOSES,
            source_fingerprint="fp-old", review_state=ReviewState.APPROVED,
        )
    ]
    preview = preview_fingerprint_change(projections, {"P-1": "fp-new"})
    assert preview.unaffected_count == 0
    assert preview.stale_projections[0].review_state == ReviewState.STALE
    # approved review state does not survive a content change (UT-E01)


def test_stale_marking_on_deleted_candidate() -> None:
    projections = [
        EvidenceProjection(
            owner="WP-D", feature_id="F1", candidate_id="P-X", relation=Relation.DISCLOSES,
            source_fingerprint="fp", review_state=ReviewState.APPROVED,
        )
    ]
    preview = preview_fingerprint_change(projections, {})  # candidate gone
    assert preview.stale_projections and preview.changed_items == ["P-X"]


# ── D-04: claim chart + gaps (UT-E02) ────────────────────────────────


def test_claim_chart_separates_single_doc_from_combination(tmp_path: Path) -> None:
    """两篇各披露部分特征：不得输出"单篇覆盖全部"。"""
    doc = parse_patent_xml(Path(__file__).resolve().parent / "fixtures" / "documents" / "sample_exchange.xml")
    parse_claim_dependencies(doc)
    candidates = [
        {"id": "P-A", "novelty_check": "partial"},
        {"id": "P-B", "novelty_check": "partial"},
    ]
    matrix = build_coverage_matrix(FEATURES, candidates, [])
    chart = build_claim_chart(doc, matrix, candidates)
    described = chart.describe()
    assert described["single_doc_novelty_candidates"] == []
    assert described["combination_hypothesis"] is True  # flagged as hint only
    assert "not an inventive-step" in described["caveat"]
    # every cell is TBD for human mapping — no automatic disclosure claim
    for row in chart.rows:
        for cell in row["cells"].values():
            assert cell["disclosure_detail"].startswith("TBD")


def test_claim_chart_single_doc_novelty_from_kernel_review(tmp_path: Path) -> None:
    doc = parse_patent_xml(Path(__file__).resolve().parent / "fixtures" / "documents" / "sample_exchange.xml")
    parse_claim_dependencies(doc)
    candidates = [{"id": "P-K", "novelty_check": "blocking"}]
    matrix = build_coverage_matrix(FEATURES, candidates, [])
    chart = build_claim_chart(doc, matrix, candidates)
    assert chart.single_doc_novelty_candidates == ["P-K"]
    assert chart.combination_hypothesis is False


def test_gap_analysis_caveat(tmp_path: Path) -> None:
    candidates = [{"id": "P-A", "novelty_check": "partial"}]
    matrix = build_coverage_matrix(FEATURES, candidates, [])
    gaps = analyze_gaps(matrix, FEATURES)
    described = gaps.describe()
    assert described["no_evidence"] or described["structural_only"]
    assert "never support" in described["caveat"]


# ── D-05: amendment proposals ────────────────────────────────────────


def test_proposal_always_carries_kernel_gate_ref() -> None:
    proposal = build_amendment_proposal(
        proposal_id="AP-001",
        claims=[{"number": 1, "text": "一种方法"}],
        change_kind="claim_amendment",
        change_payload={"text": "…其特征在于…"},
        projections=[],
    )
    ensure_proposal_policy(proposal)
    assert proposal.requires_human_review is True
    assert "draft audit" in proposal.kernel_gate_ref


def test_proposal_rejects_unknown_evidence_candidate() -> None:
    projections = [
        EvidenceProjection(
            owner="WP-D", feature_id="F1", candidate_id="P-GHOST", relation=Relation.DISCLOSES,
            source_fingerprint="fp", review_state=ReviewState.PENDING,
        )
    ]
    with pytest.raises(AdvisoryPolicyError, match="known candidate"):
        build_amendment_proposal(
            proposal_id="AP-002",
            claims=[{"number": 1, "text": "c"}],
            change_kind="claim_amendment",
            change_payload={"text": "x"},
            projections=projections,
            known_candidate_ids={"P-REAL"},
        )


def test_proposal_without_gate_ref_violates_policy() -> None:
    proposal = AdvisoryProposal(
        owner="WP-D",
        proposal_id="AP-003",
        target_fingerprint="fp",
        change={"kind": "claim_amendment", "text": "x"},
        evidence_refs=[],
        requires_human_review=True,
        kernel_gate_ref=None,
    )
    with pytest.raises(AdvisoryPolicyError, match="kernel gate"):
        ensure_proposal_policy(proposal)


def test_target_fingerprint_stable_and_sensitive() -> None:
    claims = [{"number": 1, "text": "a"}, {"number": 2, "text": "b"}]
    fp1 = target_fingerprint_from_claims(claims)
    assert fp1 == target_fingerprint_from_claims(list(reversed(claims)))
    assert fp1 != target_fingerprint_from_claims([{"number": 1, "text": "a"}])
