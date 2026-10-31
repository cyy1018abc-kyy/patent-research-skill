"""Adaptive retrieval Task 6 (Stage 3) tests: hybrid corpus lifecycle.

Acceptance anchors (roadmap Stage 3): incremental imports are idempotent, snapshots
are content-addressed and restorable, evaluation corpora are frozen and isolated,
and a failed index build never invalidates the previous active index.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from patent_intel.corpus import (
    CorpusManager,
    CorpusUpdate,
    EvaluationCorpus,
    IndexManifest,
    IndexStatus,
    UpdateMode,
)
from patent_intel.contracts import RecordValidationError


def _records(*numbers: str) -> list[dict[str, object]]:
    return [
        {
            "publication_number": number,
            "title": f"publication {number}",
            "source_refs": [{"source": "local", "raw_ref": f"raw/{number}.json"}],
        }
        for number in numbers
    ]


# ── incremental import (idempotent) ──────────────────────────────────


def test_import_counts_and_is_idempotent(tmp_path: Path) -> None:
    manager = CorpusManager(tmp_path / "state")
    first = manager.import_records(_records("CN119000001A", "EP1234567A1", "junk-no-number"), source="local-import")
    assert (first.records_seen, first.records_added, first.records_failed) == (3, 2, 1)
    assert manager.record_count() == 2

    second = manager.import_records(_records("CN119000001A", "EP1234567A1"), source="local-import")
    assert (second.records_added, second.records_skipped) == (0, 2)  # idempotent replay

    changed = manager.import_records(
        [{"publication_number": "CN119000001A", "title": "revised title",
          "source_refs": [{"source": "ops", "raw_ref": "raw/ops.json"}]}],
        source="ops",
    )
    assert changed.records_updated == 1
    assert manager.get_record("CN119000001A")["title"] == "revised title"
    assert len(manager.update_history()) == 3


def test_corpus_update_contract_round_trip() -> None:
    update = CorpusUpdate(
        owner="WP-A", update_id="CU-1", corpus="production", source="ops",
        mode=UpdateMode.INCREMENTAL, records_seen=10, records_added=4, records_updated=1,
        records_skipped=5, records_failed=0,
    )
    restored = CorpusUpdate.from_dict(update.to_dict())
    assert restored.records_added == 4
    with pytest.raises(RecordValidationError, match="mode"):
        CorpusUpdate(owner="WP-A", update_id="CU-2", corpus="production", source="x", mode="yolo")
    with pytest.raises(RecordValidationError, match="records_seen"):
        CorpusUpdate(owner="WP-A", update_id="CU-3", corpus="production", source="x",
                     mode="full", records_seen=-1)


# ── snapshots ────────────────────────────────────────────────────────


def test_snapshot_content_addressed_and_restorable(tmp_path: Path) -> None:
    manager = CorpusManager(tmp_path / "state")
    manager.import_records(_records("CN119000001A", "EP1234567A1"), source="local-import")
    snap1 = manager.create_snapshot(label="baseline")
    snap2 = manager.create_snapshot()  # idempotent: same content → same id
    assert snap1.snapshot_id == snap2.snapshot_id
    assert snap1.record_count == 2

    manager.import_records(_records("US202600100000A1"), source="local-import")
    drift = manager.verify_snapshot(snap1.snapshot_id)
    assert drift["ok"] is False and drift["drifted_records"] == 1

    restored = manager.restore_snapshot(snap1.snapshot_id)
    assert restored["restored_records"] == 2 and restored["verified"] is True
    assert manager.record_count() == 2 and manager.get_record("US202600100000A1") is None


# ── evaluation corpus (frozen + isolated) ────────────────────────────


def test_evaluation_corpus_registration_is_frozen_and_isolated(tmp_path: Path) -> None:
    state = tmp_path / "state"
    eval_dir = tmp_path / "eval-corpus-v1"
    (eval_dir / "queries").mkdir(parents=True)
    (eval_dir / "topics.jsonl").write_text('{"topic": "T-1"}\n', encoding="utf-8")
    (eval_dir / "queries" / "q1.txt").write_text("信标 时刻估计\n", encoding="utf-8")

    manager = CorpusManager(state)
    entry = manager.register_evaluation_corpus(
        name="dapfam-smoke", version="v1", source="hf-mirror", license_note="CC-BY-NC-SA",
        snapshot_dir=eval_dir, query_set_hash="a" * 64,
    )
    assert entry.corpus_id == "EC-dapfam-smoke-v1"
    assert set(entry.file_manifest) == {"topics.jsonl", "queries/q1.txt"}

    again = manager.register_evaluation_corpus(
        name="dapfam-smoke", version="v1", source="hf-mirror", license_note="CC-BY-NC-SA",
        snapshot_dir=eval_dir,
    )
    assert again.corpus_id == entry.corpus_id  # idempotent

    (eval_dir / "topics.jsonl").write_text('{"topic": "T-1"}\n{"topic": "T-2"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="frozen"):
        manager.register_evaluation_corpus(
            name="dapfam-smoke", version="v1", source="hf-mirror",
            license_note="CC-BY-NC-SA", snapshot_dir=eval_dir,
        )

    results = manager.verify_evaluation_corpus("EC-dapfam-smoke-v1")
    drift = [r for r in results if not r["ok"]]
    assert drift and drift[0]["reason"] == "hash_drift"

    # structural isolation: evaluation sets cannot live inside the corpus store
    with pytest.raises(ValueError, match="isolated"):
        manager.register_evaluation_corpus(
            name="inside-job", version="v1", source="x", license_note="y",
            snapshot_dir=state / "corpus",
        )
    with pytest.raises(RecordValidationError, match="sha256"):
        EvaluationCorpus(
            owner="WP-A", corpus_id="EC-x-v1", name="x", version="v1", source="s",
            license="l", snapshot_dir="/tmp/x", file_manifest={"a.json": "nothex"},
        )


def test_evaluation_corpus_requires_files(tmp_path: Path) -> None:
    manager = CorpusManager(tmp_path / "state")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no files"):
        manager.register_evaluation_corpus(
            name="empty", version="v1", source="s", license_note="l", snapshot_dir=empty,
        )


# ── index manifests (failure rollback) ───────────────────────────────


def test_index_build_binds_manifest_to_snapshot_and_versions(tmp_path: Path) -> None:
    manager = CorpusManager(tmp_path / "state")
    manager.import_records(_records("CN119000001A", "EP1234567A1", "US202600100000A1"), source="local-import")
    manifest = manager.build_index(
        index_kind="bm25f",
        index_version="bm25f-1",
        engine_version="patent_intel 0.1.0",
        parser_version="lexical-1",
        parameters={"k1": 1.5, "b": 0.75},
        build=lambda m: 3,
    )
    assert manifest.status == IndexStatus.ACTIVE
    assert manifest.corpus_snapshot_id.startswith("CS-")
    assert manifest.doc_count == 3
    active = manager.active_index_manifest("bm25f")
    assert active is not None and active.manifest_id == manifest.manifest_id


def test_failed_build_keeps_previous_active_manifest(tmp_path: Path) -> None:
    manager = CorpusManager(tmp_path / "state")
    manager.import_records(_records("CN119000001A"), source="local-import")
    good = manager.build_index(index_kind="bm25f", index_version="bm25f-1",
                               engine_version="e1", build=lambda m: 1)

    def boom(manifest: IndexManifest) -> int:
        raise RuntimeError("disk full mid-build")

    with pytest.raises(RuntimeError, match="disk full"):
        manager.build_index(index_kind="bm25f", index_version="bm25f-2",
                            engine_version="e2", build=boom)

    # the failed build is recorded with its snapshot binding…
    history = manager.list_index_manifests("bm25f")
    statuses = {m["index_version"]: m["status"] for m in history}
    assert statuses == {"bm25f-1": "active", "bm25f-2": "failed"}
    # …and the previous active manifest is untouched — the old index still resolves
    active = manager.active_index_manifest("bm25f")
    assert active is not None and active.manifest_id == good.manifest_id
    assert active.engine_version == "e1"
