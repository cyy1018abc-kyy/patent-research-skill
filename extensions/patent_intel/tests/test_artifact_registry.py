"""Adaptive retrieval Task 4 tests: the unified raw-artifact registry.

Key discipline: registration unifies references and audit across sources while
physical paths stay untouched (kernel workspace vs OPS sidecar vs local imports).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from patent_intel.artifacts import RawArtifactRegistry, RegistrationError, infer_mime
from patent_intel.contracts import IngestStatus, RawArtifactRef


def _write_raw(root: Path, rel: str, content: str = '{"hits": 1}') -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _ref_for(path: Path, rel: str, source: str = "ops") -> RawArtifactRef:
    data = path.read_bytes()
    return RawArtifactRef(
        owner="WP-B", path=rel, sha256=hashlib.sha256(data).hexdigest(),
        mime=infer_mime(path), bytes=len(data), source=source, captured_at="2026-11-01T00:00:00+00:00",
    )


# ── registration + verification ──────────────────────────────────────


def test_register_verifies_existence_hash_and_size(tmp_path: Path) -> None:
    raw = _write_raw(tmp_path, "raw/page-1.json")
    registry = RawArtifactRegistry(base_dir=tmp_path)
    ref = registry.register(_ref_for(raw, "raw/page-1.json"), verify=True)
    assert ref.artifact_id == f"RA-ops-{ref.sha256[:16]}"
    assert ref.ingest_status == IngestStatus.REGISTERED

    # a drifted file is refused, never registered
    drifted = _ref_for(raw, "raw/page-1.json")
    drifted.sha256 = "0" * 64
    with pytest.raises(RegistrationError, match="sha256 mismatch"):
        registry.register(drifted)

    # a missing file is refused
    ghost = RawArtifactRef(
        owner="WP-B", path="raw/ghost.json", sha256="a" * 64, mime="application/json",
        bytes=3, source="ops", captured_at="2026-11-01T00:00:00+00:00",
    )
    with pytest.raises(RegistrationError, match="missing"):
        registry.register(ghost)


def test_registration_never_moves_or_copies_the_file(tmp_path: Path) -> None:
    raw = _write_raw(tmp_path, "02_search_logs/raw/N1_page-1.csv", "a,b\n1,2\n")
    before = raw.read_bytes()
    registry = RawArtifactRegistry(base_dir=tmp_path)
    registry.register(_ref_for(raw, "02_search_logs/raw/N1_page-1.csv", source="cnipa"))
    assert raw.read_bytes() == before  # physical path untouched
    assert raw.is_file() and not (tmp_path / "artifacts").exists()


def test_artifact_id_is_content_addressed_and_reregistration_idempotent(tmp_path: Path) -> None:
    raw = _write_raw(tmp_path, "raw/a.json")
    registry = RawArtifactRegistry(base_dir=tmp_path)
    first = registry.register(_ref_for(raw, "raw/a.json"))
    second = registry.register(_ref_for(raw, "raw/a.json"))
    assert first.artifact_id == second.artifact_id
    assert len(registry.entries()) == 1

    # a ref carrying a hand-picked id is refused — ids are derived, never chosen
    forced = _ref_for(raw, "raw/a.json")
    forced.artifact_id = "RA-ops-pretty-name"
    with pytest.raises(RegistrationError, match="derived"):
        registry.register(forced)


def test_verify_all_detects_missing_and_drifted_files(tmp_path: Path) -> None:
    ok_raw = _write_raw(tmp_path, "raw/ok.json")
    drift_raw = _write_raw(tmp_path, "raw/drift.json", "v1")
    registry = RawArtifactRegistry(base_dir=tmp_path)
    ok_ref = registry.register(_ref_for(ok_raw, "raw/ok.json"))
    drift_ref = registry.register(_ref_for(drift_raw, "raw/drift.json", "v1"))
    drift_raw.write_text("v2-changed", encoding="utf-8")  # tamper after registration
    ok_raw.unlink()
    results = {r["artifact_id"]: r for r in registry.verify_all()}
    assert results[ok_ref.artifact_id]["ok"] is False
    assert results[ok_ref.artifact_id]["reason"] == "missing"
    assert results[drift_ref.artifact_id]["ok"] is False
    assert results[drift_ref.artifact_id]["reason"] == "hash_or_size_drift"


# ── adapter-shape helpers ────────────────────────────────────────────


def test_register_kernel_raw_computes_digest_and_relative_path(tmp_path: Path) -> None:
    raw = _write_raw(tmp_path, "02_search_logs/raw/N1_page-1.csv", "pub,title\nZZ1,x\n")
    registry = RawArtifactRegistry(base_dir=tmp_path)
    ref = registry.register_kernel_raw(
        workspace=tmp_path, raw_export="raw/N1_page-1.csv", source="cnipa", query_id="Q1",
    )
    assert ref.path == "02_search_logs/raw/N1_page-1.csv"
    assert ref.sha256 == hashlib.sha256(raw.read_bytes()).hexdigest()
    assert ref.mime == "text/csv"
    assert ref.query_id == "Q1"
    with pytest.raises(RegistrationError, match="missing"):
        registry.register_kernel_raw(
            workspace=tmp_path, raw_export="raw/none.csv", source="cnipa",
        )


def test_register_from_refs_handles_kernel_and_ops_shapes(tmp_path: Path) -> None:
    kernel_raw = _write_raw(tmp_path, "02_search_logs/raw/x.csv", "a\n1\n")
    ops_raw = _write_raw(tmp_path, "raw/ops_p1.json", '{"results": []}')
    registry = RawArtifactRegistry(base_dir=tmp_path)
    kernel_refs = [{"path": "02_search_logs/raw/x.csv", "bytes": len(kernel_raw.read_bytes()), "source": "cnipa"}]
    ops_sha = hashlib.sha256(ops_raw.read_bytes()).hexdigest()
    ops_refs = [{"raw_ref": "raw/ops_p1.json", "sha256": ops_sha, "bytes_written": ops_raw.stat().st_size}]
    registered = registry.register_from_refs(kernel_refs, source="cnipa", base_dir=tmp_path, query_id="Q1")
    registered += registry.register_from_refs(ops_refs, source="ops", base_dir=tmp_path, query_id="Q1")
    assert [r.source for r in registered] == ["cnipa", "ops"]
    assert registered[0].sha256 == hashlib.sha256(kernel_raw.read_bytes()).hexdigest()
    assert registered[1].sha256 == ops_sha

    with pytest.raises(RegistrationError, match="neither 'path' nor 'raw_ref'"):
        registry.register_from_refs([{"foo": 1}], source="ops", base_dir=tmp_path)


# ── index persistence + lifecycle ────────────────────────────────────


def test_index_persistence_round_trip(tmp_path: Path) -> None:
    raw = _write_raw(tmp_path, "raw/page-1.json")
    index_path = tmp_path / "state" / "raw_registry.json"
    registry = RawArtifactRegistry(base_dir=tmp_path, index_path=index_path)
    ref = registry.register(_ref_for(raw, "raw/page-1.json"), verify=True)
    assert index_path.is_file()

    reloaded = RawArtifactRegistry(base_dir=tmp_path, index_path=index_path)
    assert [r.artifact_id for r in reloaded.entries()] == [ref.artifact_id]
    reloaded.mark_ingested(ref.artifact_id, normalized_record_refs=[{"publication_id": "P-1"}])
    again = RawArtifactRegistry(base_dir=tmp_path, index_path=index_path)
    restored = again.get(ref.artifact_id)
    assert restored.ingest_status == IngestStatus.INGESTED
    assert restored.normalized_record_refs == [{"publication_id": "P-1"}]


def test_mark_failed_records_reason_but_keeps_data(tmp_path: Path) -> None:
    raw = _write_raw(tmp_path, "raw/page-1.json")
    registry = RawArtifactRegistry(base_dir=tmp_path, index_path=tmp_path / "idx.json")
    ref = registry.register(_ref_for(raw, "raw/page-1.json"))
    registry.mark_failed(ref.artifact_id, reason="parser v3 crashed")
    stored = registry.get(ref.artifact_id)
    assert stored.ingest_status == IngestStatus.FAILED
    assert stored.normalized_record_refs[-1]["error"] == "parser v3 crashed"
    assert raw.is_file()  # data kept, only the status moved


def test_describe_counts_by_status(tmp_path: Path) -> None:
    a = _write_raw(tmp_path, "raw/a.json", "1")
    b = _write_raw(tmp_path, "raw/b.json", "2")
    registry = RawArtifactRegistry(base_dir=tmp_path)
    ra = registry.register(_ref_for(a, "raw/a.json"))
    rb = registry.register(_ref_for(b, "raw/b.json"))
    registry.mark_ingested(ra.artifact_id)
    described = registry.describe()
    assert described["artifact_count"] == 2
    assert described["by_ingest_status"] == {"registered": 1, "ingested": 1}


def test_contract_ingest_status_validation_and_round_trip(tmp_path: Path) -> None:
    raw = _write_raw(tmp_path, "raw/a.json")
    ref = _ref_for(raw, "raw/a.json")
    ref.ingest_status = "vibes"
    with pytest.raises(Exception, match="ingest_status"):
        ref.validate()
    ref.ingest_status = IngestStatus.REGISTERED
    ref.query_id = "Q-1"
    restored = RawArtifactRef.from_dict(ref.to_dict())
    assert restored.query_id == "Q-1" and restored.ingest_status == IngestStatus.REGISTERED
    # legacy refs without registry fields still round-trip
    legacy = RawArtifactRef.from_dict(json.loads(json.dumps({
        "schema_version": 1, "record_type": "raw_artifact_ref", "owner": "WP-B",
        "path": "raw/old.json", "sha256": "b" * 64, "mime": "application/json", "bytes": 5,
        "source": "ops", "captured_at": "2026-01-01T00:00:00+00:00",
    })))
    assert legacy.artifact_id is None and legacy.ingest_status is None
