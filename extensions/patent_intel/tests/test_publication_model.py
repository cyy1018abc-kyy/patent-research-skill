"""Adaptive retrieval Task 5 tests: PublicationRecord, field conflicts, family refs.

Contract discipline: one publication = 公开号 + kind code; multilingual fields are
language-tagged maps; missing ≠ nonexistent; conflicts are kept with their sources;
uncertain family relations are deferred for review, never auto-merged.
"""

from __future__ import annotations

import pytest

from patent_intel.contracts import (
    FieldPresence,
    IdentifierConfidence,
    PublicationRecord,
    RecordValidationError,
)
from patent_intel.normalization import FieldConflictLog
from patent_intel.sources.family import FamilyView


def _record(**overrides: object) -> PublicationRecord:
    base: dict[str, object] = {
        "owner": "WP-B",
        "publication_id": "P-CN119000001A",
        "publication_number": "CN119000001A",
        "identifier_confidence": IdentifierConfidence.EXACT,
        "source_refs": [{"source": "cnipa", "raw_ref": "02_search_logs/raw/N1_page-1.csv"}],
        "title": {"zh": "一种多阀协同控制方法", "en": "Multi-valve coordinated control method"},
        "field_completeness": {"abstract": FieldPresence.OBTAINED, "claims": FieldPresence.UNKNOWN},
    }
    base.update(overrides)
    return PublicationRecord(**base)  # type: ignore[arg-type]


# ── PublicationRecord contract ───────────────────────────────────────


def test_publication_record_round_trip() -> None:
    record = _record()
    restored = PublicationRecord.from_dict(record.to_dict())
    assert restored.title == record.title
    assert restored.field_completeness["claims"] == FieldPresence.UNKNOWN


def test_publication_record_requires_traceable_source_refs() -> None:
    with pytest.raises(RecordValidationError, match="source_ref"):
        PublicationRecord(
            owner="WP-B", publication_id="P-1", publication_number="CN1A",
            identifier_confidence="exact", source_refs=[{"source": "ops"}],
        )


def test_multilingual_fields_must_be_language_tagged() -> None:
    with pytest.raises(RecordValidationError, match="non-empty string"):
        _record(title={"zh": "", "en": "x"})  # empty placeholder forbidden
    with pytest.raises(RecordValidationError, match="non-empty string"):
        _record(title={"zh": 42})  # type: ignore[dict-item]
    with pytest.raises(RecordValidationError, match="language tags"):
        _record(title={"": "orphan text"})


def test_field_completeness_vocabulary_is_closed() -> None:
    with pytest.raises(RecordValidationError, match="field_completeness"):
        _record(field_completeness={"claims": "probably fine"})


def test_family_refs_need_source_and_confidence_is_graded() -> None:
    with pytest.raises(RecordValidationError, match="family_ref"):
        _record(family_refs=[{"family_id": "FAM-1"}])  # no source
    with pytest.raises(RecordValidationError, match="confidence"):
        _record(family_refs=[{"family_id": "FAM-1", "source": "ops", "confidence": "sure"}])
    ok = _record(family_refs=[
        {"family_id": "FAM-1", "source": "ops", "confidence": IdentifierConfidence.EXACT}
    ])
    assert ok.family_refs[0]["confidence"] == "exact"


# ── FieldConflictLog ─────────────────────────────────────────────────


def test_conflict_log_keeps_every_source_value() -> None:
    log = FieldConflictLog()
    log.record("P-1", "title", source="cnipa", value="多阀协同控制", raw_ref="raw/cn.xml")
    log.record("P-1", "title", source="ops", value="Multi-valve control", raw_ref="raw/ops.json")
    resolved = log.resolve("P-1", "title", priority={"ops": 1, "cnipa": 2})
    assert resolved.value == "Multi-valve control"
    assert resolved.decided_by == "priority"
    assert resolved.conflicts  # both values kept, conflict reported not erased
    assert len(log.values("P-1", "title")) == 2


def test_conflict_log_single_source_needs_no_priority() -> None:
    log = FieldConflictLog()
    log.record("P-1", "assignee", source="ops", value="ACME", raw_ref="raw/ops.json")
    resolved = log.resolve("P-1", "assignee")
    assert resolved.decided_by == "single" and resolved.value == "ACME"
    assert log.conflicts("P-1") == []


def test_confirmed_value_beats_priority_and_survives_resync() -> None:
    log = FieldConflictLog()
    log.record("P-1", "title", source="ops", value="Wrong EN title", raw_ref="raw/ops.json")
    log.confirm("P-1", "title", source="human", value="Correct EN title")
    # a later automatic record must not overturn the human confirmation
    log.record("P-1", "title", source="cnipa", value="中文标题", raw_ref="raw/cn.xml")
    resolved = log.resolve("P-1", "title", priority={"cnipa": 1, "ops": 2, "human": 9})
    assert resolved.value == "Correct EN title"
    assert resolved.decided_by == "confirmed"


def test_same_source_contradicting_itself_is_a_conflict_not_an_update() -> None:
    log = FieldConflictLog()
    log.record("P-1", "publication_date", source="ops", value="2026-01-15", raw_ref="raw/p1.json")
    log.record("P-1", "publication_date", source="ops", value="2026-01-16", raw_ref="raw/p2.json")
    assert len(log.values("P-1", "publication_date")) == 2
    assert log.conflicts("P-1")  # both kept; resolution picks, history remains
    assert log.resolve("P-1", "publication_date", priority={"ops": 1}).conflicts


def test_empty_values_are_never_recorded() -> None:
    log = FieldConflictLog()
    with pytest.raises(ValueError, match="empty"):
        log.record("P-1", "title", source="ops", value="", raw_ref="raw/ops.json")


# ── family views: uncertain refs deferred, never merged ──────────────


def test_family_view_merges_reported_refs_but_defers_uncertain_ones() -> None:
    view = FamilyView()
    g1 = view.add({"publication_number": "EP1000001A1",
                   "family_refs": [{"family_id": "FAM-1", "source": "ops"}]})
    g2 = view.add({"publication_number": "EP1000002A1",
                   "family_refs": [{"family_id": "FAM-1", "source": "ops"}]})
    assert g1.family_id == g2.family_id == "FAM-1"  # reported refs merge as before

    gu = view.add({"publication_number": "US9999999A1",
                   "family_refs": [{"family_id": "FAM-1", "source": "guess", "confidence": "uncertain"}]})
    assert gu.family_id is None  # uncertain ref must NOT merge into FAM-1
    assert gu.family_status == "unknown"
    assert gu.deferred_family_refs == [
        {"family_id": "FAM-1", "source": "guess", "confidence": "uncertain"}
    ]
    assert gu.describe()["deferred_family_refs"] == 1


def test_family_view_still_keeps_unknown_and_conflicts() -> None:
    view = FamilyView()
    view.add({"publication_number": "EP1000003A1", "title": "t"})
    view.add({"publication_number": "EP1000003A1", "title": "different"})
    described = view.describe()
    assert described["unknown_family_groups"] == 1
    assert described["conflict_count"] == 1
