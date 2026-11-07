"""Tests for 41C-2: snapshot hash chain, staleness marking, rebuild recovery.

Full chain under test: corpus change → snapshot chain grows with verifiable
parentage → active index manifests get marked stale in the sidecar (manifest
history untouched) → rebuild recovers currency → restore flips staleness back
honestly. Anchor-side: a drifted or vanished corpus binding invalidates every
citation bound to the anchor (锚点失效即引用失效), unknown never passes as current.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from patent_intel.contracts import AnchorVerification, DocumentAnchor
from patent_intel.corpus.manager import CorpusManager
from patent_intel.documents.locators import anchor_staleness, make_anchor


def _records(*numbers: str) -> list[dict[str, object]]:
    return [
        {
            "publication_number": number,
            "title": f"publication {number}",
            "source_refs": [{"source": "local", "raw_ref": f"raw/{number}.json"}],
        }
        for number in numbers
    ]


def _record_sha(manager: CorpusManager, number: str) -> str:
    return manager.get_record(number)["_content_sha256"]  # type: ignore[index-return]


def _anchor(number: str, binding: str | None) -> DocumentAnchor:
    extra = {"record_content_sha256": binding} if binding else {}
    return DocumentAnchor(
        owner="WP-C",
        raw_sha256="a" * 64,
        source_document=number,
        paragraph="0012",
        text_hash="b" * 64,
        parser_version="test-parser-1",
        verification_status=AnchorVerification.MACHINE_PARSED,
        extra=extra,
    )


# ── snapshot hash chain ───────────────────────────────────────────────


class TestSnapshotChain:
    def test_chain_grows_with_verifiable_parentage(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        first = manager.create_snapshot()
        manager.import_records(_records("CN119000001A"), source="local-import")
        second = manager.create_snapshot()
        assert second.snapshot_id != first.snapshot_id

        chain = manager.snapshot_chain()
        assert [e["snapshot_id"] for e in chain] == [first.snapshot_id, second.snapshot_id]
        assert chain[0]["parent_snapshot_id"] is None
        assert chain[1]["parent_snapshot_id"] == first.snapshot_id
        assert chain[1]["parent_content_sha256"] == first.content_sha256
        assert manager.verify_snapshot_chain() == {"ok": True, "length": 2, "problems": []}

    def test_chain_append_is_idempotent(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        manager.import_records(_records("CN119000001A"), source="local-import")
        first = manager.create_snapshot()
        manager.create_snapshot()  # same content → no second chain entry
        assert len(manager.snapshot_chain()) == 1
        assert manager.snapshot_chain()[0]["snapshot_id"] == first.snapshot_id

    def test_tampered_blob_breaks_the_chain_report(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        manager.import_records(_records("CN119000001A"), source="local-import")
        snapshot = manager.create_snapshot()
        blob = tmp_path / "state" / "corpus" / "snapshots" / f"{snapshot.snapshot_id}.json"
        payload = json.loads(blob.read_text(encoding="utf-8"))
        payload["content_sha256"] = "f" * 64
        blob.write_text(json.dumps(payload), encoding="utf-8", newline="\n")

        report = manager.verify_snapshot_chain()
        assert report["ok"] is False
        assert any(snapshot.snapshot_id in problem for problem in report["problems"])

    def test_chain_is_fail_closed_on_missing_blob(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        manager.import_records(_records("CN119000001A"), source="local-import")
        snapshot = manager.create_snapshot()
        (tmp_path / "state" / "corpus" / "snapshots" / f"{snapshot.snapshot_id}.json").unlink()
        report = manager.verify_snapshot_chain()
        assert report["ok"] is False
        assert "missing" in report["problems"][0]


# ── index staleness marking & rebuild recovery ────────────────────────


class TestIndexStaleness:
    def _build(self, manager: CorpusManager, version: str) -> object:
        return manager.build_index(
            index_kind="lexical",
            index_version=version,
            engine_version="0.10.0",
            build=lambda manifest: 1,
        )

    def test_full_cycle_change_stale_rebuild_recover(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        manager.import_records(_records("CN119000001A"), source="local-import")
        manifest_v1 = self._build(manager, "lex-1")

        # fresh build is current
        report = manager.stale_index_manifests()
        assert report["manifests"][manifest_v1.manifest_id]["verdict"] == "current"
        assert (tmp_path / "state" / "corpus" / "staleness.json").is_file()

        # corpus changes → the active manifest goes stale, marked in the sidecar
        manager.import_records(_records("EP1234567A1"), source="local-import")
        report = manager.stale_index_manifests()
        entry = report["manifests"][manifest_v1.manifest_id]
        assert entry["verdict"] == "stale" and entry["stale"] is True
        assert entry["reason"] == "corpus content drifted since this snapshot"
        sidecar = json.loads(
            (tmp_path / "state" / "corpus" / "staleness.json").read_text(encoding="utf-8")
        )
        assert sidecar["manifests"][manifest_v1.manifest_id]["verdict"] == "stale"

        # rebuild against the new content → recovery; history stays intact
        manifest_v2 = self._build(manager, "lex-2")
        report = manager.stale_index_manifests(write_sidecar=False)
        assert report["manifests"][manifest_v2.manifest_id]["verdict"] == "current"
        assert report["manifests"][manifest_v1.manifest_id]["verdict"] == "stale"
        kinds = {m["manifest_id"] for m in manager.list_index_manifests("lexical")}
        assert kinds == {manifest_v1.manifest_id, manifest_v2.manifest_id}

        # restore flips staleness honestly in the other direction
        first_snapshot = manager.snapshot_chain()[0]["snapshot_id"]
        manager.restore_snapshot(first_snapshot)
        report = manager.stale_index_manifests(write_sidecar=False)
        assert report["manifests"][manifest_v1.manifest_id]["verdict"] == "current"
        assert report["manifests"][manifest_v2.manifest_id]["verdict"] == "stale"

    def test_missing_snapshot_blob_is_unknown_not_current(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        manager.import_records(_records("CN119000001A"), source="local-import")
        manifest = self._build(manager, "lex-1")
        snapshot_id = manifest.corpus_snapshot_id
        (tmp_path / "state" / "corpus" / "snapshots" / f"{snapshot_id}.json").unlink()
        report = manager.stale_index_manifests(write_sidecar=False)
        entry = report["manifests"][manifest.manifest_id]
        assert entry["verdict"] == "unknown" and entry["stale"] is None

    def test_report_is_deterministic(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        manager.import_records(_records("CN119000001A"), source="local-import")
        self._build(manager, "lex-1")
        first = json.dumps(manager.stale_index_manifests(write_sidecar=False), sort_keys=True)
        second = json.dumps(manager.stale_index_manifests(write_sidecar=False), sort_keys=True)
        assert first == second


# ── anchor staleness (C-04 extension) ─────────────────────────────────


class TestAnchorStaleness:
    def test_current_binding_passes(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        manager.import_records(_records("CN119000001A"), source="local-import")
        binding = _record_sha(manager, "CN119000001A")
        verdict = anchor_staleness(_anchor("CN119000001A", binding), manager._load_records())
        assert verdict == {
            "record_key": "CN119000001A",
            "verdict": "current",
            "stale": False,
            "reason": None,
        }

    def test_drifted_record_invalidates_the_anchor(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        manager.import_records(_records("CN119000001A"), source="local-import")
        binding = _record_sha(manager, "CN119000001A")
        manager.import_records(
            [{"publication_number": "CN119000001A", "title": "revised",
              "source_refs": [{"source": "ops", "raw_ref": "raw/ops.json"}]}],
            source="ops",
        )
        verdict = anchor_staleness(_anchor("CN119000001A", binding), manager._load_records())
        assert verdict["verdict"] == "drifted"
        assert verdict["stale"] is True

    def test_vanished_record_invalidates_the_anchor(self, tmp_path: Path) -> None:
        verdict = anchor_staleness(_anchor("EP1234567A1", "c" * 64), {"CN119000001A": {}})
        assert verdict["verdict"] == "missing"
        assert verdict["stale"] is True

    def test_no_binding_is_unknown_never_current(self) -> None:
        verdict = anchor_staleness(_anchor("CN119000001A", None), {"CN119000001A": {"_content_sha256": "c" * 64}})
        assert verdict["verdict"] == "unknown"
        assert verdict["stale"] is None

    def test_record_without_content_hash_is_unknown(self) -> None:
        verdict = anchor_staleness(_anchor("CN119000001A", "c" * 64), {"CN119000001A": {"title": "x"}})
        assert verdict["verdict"] == "unknown"
        assert verdict["stale"] is None

    def test_explicit_key_overrides_source_document(self, tmp_path: Path) -> None:
        manager = CorpusManager(tmp_path / "state")
        manager.import_records(_records("CN119000001A"), source="local-import")
        binding = _record_sha(manager, "CN119000001A")
        anchor = _anchor("display-id-1", binding)
        verdict = anchor_staleness(anchor, manager._load_records(), key="CN119000001A")
        assert verdict["verdict"] == "current"
        assert verdict["record_key"] == "CN119000001A"

    def test_make_anchor_carries_the_corpus_binding(self, tmp_path: Path) -> None:
        """make_anchor(record_content_sha256=...) stores the binding in extra."""
        from patent_intel.documents.schema import Paragraph, StructuredPatentDocument

        doc = StructuredPatentDocument(
            source_document="CN119000001A",
            raw_sha256="a" * 64,
            parser_version="test-parser-1",
            quality={"citable": True},
        )
        doc.paragraphs.append(
            Paragraph(
                para_id="0012",
                text="A timing frame carries a sync marker.",
                origin="native_xml",
                section="description",
                page=1,
            )
        )
        anchor = make_anchor(doc, "0012", record_content_sha256="c" * 64)
        assert anchor.extra["record_content_sha256"] == "c" * 64
        verdict = anchor_staleness(anchor, {"CN119000001A": {"_content_sha256": "c" * 64}})
        assert verdict["verdict"] == "current"

        unbound = make_anchor(doc, "0012")
        assert unbound.extra["record_content_sha256"] is None
        assert anchor_staleness(unbound, {})["verdict"] == "unknown"
