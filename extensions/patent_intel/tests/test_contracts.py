"""Contract record tests: roundtrips, validation, schema discipline (blueprint F-03)."""

from __future__ import annotations

import pytest

from patent_intel.contracts import (
    AnchorVerification,
    AdvisoryProposal,
    ContractError,
    DocumentAnchor,
    EvaluationReport,
    EvidenceProjection,
    FeatureSpec,
    PatentRecord,
    QuerySpec,
    RawArtifactRef,
    RecordValidationError,
    Requiredness,
    RetrievalRun,
    Relation,
    ReviewState,
    SearchRun,
    UnsupportedSchemaError,
    utc_now_iso,
)

OWNER = "WP-0"


def _roundtrip(rec, cls):  # type: ignore[no-untyped-def]
    data = rec.to_dict()
    restored = cls.from_dict(data)
    assert restored.to_dict() == data
    return restored


# ── FeatureSpec ───────────────────────────────────────────────────────


def test_feature_spec_roundtrip_with_extra_preserved():
    rec = FeatureSpec(
        owner="WP-A",
        feature_id="F-001",
        statement="信标发送时刻估计",
        source_refs=["glossary:N1@TGT-0001"],
        requiredness=Requiredness.REQUIRED,
        axis_id="N1@TGT-0001",
        extra={"future_field": "kept"},
    )
    restored = _roundtrip(rec, FeatureSpec)
    assert restored.extra["future_field"] == "kept"
    assert restored.statement == "信标发送时刻估计"


def test_feature_spec_missing_required_rejected():
    data = {
        "schema_version": 1,
        "record_type": "feature_spec",
        "owner": "WP-A",
        "created_at": utc_now_iso(),
        "statement": "no feature_id here",
        "source_refs": ["x"],
        "requiredness": "required",
    }
    with pytest.raises(RecordValidationError, match="feature_id"):
        FeatureSpec.from_dict(data)


def test_feature_spec_negation_consistency():
    with pytest.raises(RecordValidationError, match="negation"):
        FeatureSpec(
            owner=OWNER,
            feature_id="F-002",
            statement="不含漂移补偿",
            source_refs=["glossary:N2@TGT-0001"],
            requiredness=Requiredness.NEGATION,
            negation=False,
        )


def test_feature_spec_unknown_requiredness_rejected():
    with pytest.raises(RecordValidationError, match="requiredness"):
        FeatureSpec(
            owner=OWNER,
            feature_id="F-003",
            statement="x",
            source_refs=["s"],
            requiredness="kind_of_important",
        )


# ── QuerySpec ─────────────────────────────────────────────────────────


def _query_spec_data(**overrides: object) -> dict:
    data = {
        "schema_version": 1,
        "record_type": "query_spec",
        "owner": "WP-A",
        "created_at": utc_now_iso(),
        "query_id": "Q-0001",
        "axis_id": "N1@TGT-0001",
        "terms": ["信标", "beacon timing"],
        "language": "zh+en",
        "query_type": "single_feature",
        "source": "espacenet",
        "provenance": [{"feature_id": "F-001", "reason": "core axis term"}],
    }
    data.update(overrides)
    return data


def test_query_spec_roundtrip():
    rec = QuerySpec.from_dict(_query_spec_data())
    _roundtrip(rec, QuerySpec)


def test_query_spec_without_provenance_feature_id_rejected():
    """UT-Q03: every term must trace to a source feature, else it is unverified."""
    data = _query_spec_data(provenance=[{"reason": "LLM guessed this"}])
    with pytest.raises(RecordValidationError, match="feature_id"):
        QuerySpec.from_dict(data)


def test_query_spec_empty_terms_rejected():
    data = _query_spec_data(terms=[])
    with pytest.raises(RecordValidationError, match="term"):
        QuerySpec.from_dict(data)


def test_query_spec_unknown_query_type_rejected():
    data = _query_spec_data(query_type="vibes")
    with pytest.raises(RecordValidationError, match="query_type"):
        QuerySpec.from_dict(data)


# ── SearchRun (interface rule 3: hits ≠ fetched) ──────────────────────


def test_search_run_partial_requires_complete_false_and_reason():
    rec = SearchRun(
        owner="WP-B",
        run_id="R-001",
        query_id="Q-0001",
        source="ops",
        executed_at=utc_now_iso(),
        status="partial",
        hits_reported=1000,
        records_fetched=3,
        complete=False,
        incomplete_reason="limited",
        error=None,
    )
    _roundtrip(rec, SearchRun)
    assert rec.hits_reported == 1000
    assert rec.records_fetched == 3


def test_search_run_complete_false_without_reason_rejected():
    with pytest.raises(RecordValidationError, match="incomplete_reason"):
        SearchRun(
            owner="WP-B",
            run_id="R-002",
            query_id="Q-0001",
            source="ops",
            executed_at=utc_now_iso(),
            status="partial",
            complete=False,
        )


def test_search_run_partial_without_complete_flag_rejected():
    with pytest.raises(RecordValidationError, match="complete"):
        SearchRun(
            owner="WP-B",
            run_id="R-003",
            query_id="Q-0001",
            source="ops",
            executed_at=utc_now_iso(),
            status="partial",
        )


def test_search_run_failed_requires_error():
    with pytest.raises(RecordValidationError, match="error"):
        SearchRun(
            owner="WP-B",
            run_id="R-004",
            query_id="Q-0001",
            source="ops",
            executed_at=utc_now_iso(),
            status="failed",
        )


def test_search_run_negative_hits_rejected():
    with pytest.raises(RecordValidationError, match="hits_reported"):
        SearchRun(
            owner="WP-B",
            run_id="R-005",
            query_id="Q-0001",
            source="ops",
            executed_at=utc_now_iso(),
            status="complete",
            hits_reported=-1,
            records_fetched=0,
            complete=True,
        )


# ── RawArtifactRef ────────────────────────────────────────────────────


def test_raw_artifact_ref_roundtrip():
    rec = RawArtifactRef(
        owner="WP-B",
        path="02_search_logs/raw/N1_page-1.csv",
        sha256="a" * 64,
        mime="text/csv",
        bytes=120,
        source="espacenet",
        captured_at=utc_now_iso(),
        source_record_id="N1",
    )
    _roundtrip(rec, RawArtifactRef)


def test_raw_artifact_ref_bad_sha256_rejected():
    with pytest.raises(RecordValidationError, match="sha256"):
        RawArtifactRef(
            owner="WP-B",
            path="raw/x.csv",
            sha256="XYZ",
            mime="text/csv",
            bytes=1,
            source="ops",
            captured_at=utc_now_iso(),
        )


# ── PatentRecord ──────────────────────────────────────────────────────


def test_patent_record_source_refs_shape_enforced():
    """Interface rule 4: candidates must reference raw sources to stay traceable."""
    with pytest.raises(RecordValidationError, match="source_ref"):
        PatentRecord(
            owner="WP-B",
            publication_number="EP1234567A1",
            source_refs=[{"source": "ops"}],  # missing raw_ref
            identifier_confidence="normalized",
        )


def test_patent_record_roundtrip_preserves_original_ids():
    rec = PatentRecord(
        owner="WP-B",
        publication_number="CN 119 000 001 A",
        application_number="202610000000.1",
        source_refs=[{"source": "cnipa", "raw_ref": "raw/p1.json", "original_id": "CN119000001A"}],
        identifier_confidence="exact",
        title="一种时间同步方法",
    )
    restored = _roundtrip(rec, PatentRecord)
    assert restored.publication_number == "CN 119 000 001 A"  # original form kept verbatim


# ── DocumentAnchor ────────────────────────────────────────────────────


def test_document_anchor_roundtrip_and_enum():
    rec = DocumentAnchor(
        owner="WP-C",
        raw_sha256="b" * 64,
        source_document="raw/ZZ900011A1.md",
        paragraph="0012",
        text_hash="c" * 64,
        parser_version="patent_intel.documents 0.1.0",
        verification_status=AnchorVerification.MACHINE_PARSED,
        page=3,
        bbox=[1.0, 2.0, 3.0, 4.0],
    )
    _roundtrip(rec, DocumentAnchor)


def test_document_anchor_bad_bbox_rejected():
    with pytest.raises(RecordValidationError, match="bbox"):
        DocumentAnchor(
            owner="WP-C",
            raw_sha256="b" * 64,
            source_document="raw/x.md",
            paragraph="0001",
            text_hash="c" * 64,
            parser_version="v0",
            verification_status=AnchorVerification.UNVERIFIED,
            bbox=[1.0, 2.0],
        )


# ── RetrievalRun / EvaluationReport ──────────────────────────────────


def test_retrieval_run_roundtrip():
    rec = RetrievalRun(
        owner="WP-F",
        run_id="EVAL-001",
        dataset_hash="d" * 64,
        query_set_hash="e" * 64,
        engine_version="patent_intel 0.1.0 lexical",
        seed=20261028,
        model_id=None,
        budget={"max_requests": 200},
    )
    _roundtrip(rec, RetrievalRun)


def test_evaluation_report_roundtrip():
    rec = EvaluationReport(
        owner="WP-F",
        qrels_version="qrels-v1",
        split="test",
        recall_at_k={"50": 0.61, "100": 0.72, "200": 0.80},
        ndcg_at_k={"100": 0.55},
        ci={"method": "bootstrap-by-topic", "level": 0.95, "lower": 0.02},
    )
    _roundtrip(rec, EvaluationReport)


# ── EvidenceProjection / AdvisoryProposal ────────────────────────────


def test_evidence_projection_relations_and_review_states():
    rec = EvidenceProjection(
        owner="WP-D",
        feature_id="F-001",
        candidate_id="P-001-zz900011a1",
        relation=Relation.PARTIALLY_DISCLOSES,
        source_fingerprint="fp-abc",
        review_state=ReviewState.PENDING,
        anchor={"raw_sha256": "b" * 64, "paragraph": "0012"},
    )
    _roundtrip(rec, EvidenceProjection)
    with pytest.raises(RecordValidationError, match="relation"):
        EvidenceProjection(
            owner="WP-D",
            feature_id="F-001",
            candidate_id="P-001",
            relation="smells_like",
            source_fingerprint="fp",
            review_state=ReviewState.PENDING,
        )


def test_advisory_proposal_always_requires_human_review():
    """Interface rule 7: a proposal claiming no human review is a contract violation."""
    with pytest.raises(RecordValidationError, match="human review"):
        AdvisoryProposal(
            owner="WP-D",
            proposal_id="AP-001",
            target_fingerprint="fp-001",
            change={"kind": "claim_amendment", "text": "…其特征在于…"},
            evidence_refs=[{"candidate_id": "P-001"}],
            requires_human_review=False,
        )


# ── Schema discipline ────────────────────────────────────────────────


def test_higher_schema_version_refused():
    data = _query_spec_data(schema_version=2)
    with pytest.raises(UnsupportedSchemaError, match="schema_version"):
        QuerySpec.from_dict(data)


def test_missing_schema_version_refused():
    data = _query_spec_data()
    del data["schema_version"]
    with pytest.raises(RecordValidationError, match="schema_version"):
        QuerySpec.from_dict(data)


def test_record_type_mismatch_refused():
    data = _query_spec_data(record_type="search_run")
    with pytest.raises(RecordValidationError, match="record_type"):
        QuerySpec.from_dict(data)


def test_bad_created_at_format_refused():
    data = _query_spec_data(created_at="2026-10-28 01:02:03")  # not ISO-8601 T/offset form
    with pytest.raises(RecordValidationError, match="created_at"):
        QuerySpec.from_dict(data)


def test_missing_owner_refused():
    data = _query_spec_data()
    del data["owner"]
    with pytest.raises(RecordValidationError, match="owner"):
        QuerySpec.from_dict(data)


def test_non_mapping_payload_refused():
    with pytest.raises(RecordValidationError):
        QuerySpec.from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_contract_error_hierarchy():
    assert issubclass(RecordValidationError, ContractError)
    assert issubclass(UnsupportedSchemaError, ContractError)
