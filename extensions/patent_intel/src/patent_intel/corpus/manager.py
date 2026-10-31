"""Corpus manager (adaptive roadmap Stage 3 / Task 6): hybrid local corpus lifecycle.

Two deliberately isolated corpora:

* **production** — the searchable corpus, fed by incremental imports (kernel raw
  captures, OPS sidecar data, local exports). Updates are idempotent and counted
  honestly (seen/added/updated/skipped/failed);
* **evaluation** — frozen, versioned, hash-manifested; never touched by production
  imports (评测集不随生产语料更新而变化).

Derived state is rebuildable and always bound to provenance: every index build is
manifested against a content-addressed corpus snapshot with engine/parser versions,
and a failed build leaves the previous active manifest (and index) intact —
索引构建失败不破坏旧索引. Single-machine local-first: JSON stores with atomic
writes; scale upgrades (SQLite etc.) replace the storage layer, not the contracts.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from patent_intel.contracts import utc_now_iso
from patent_intel.corpus.models import (
    CorpusSnapshot,
    CorpusUpdate,
    EvaluationCorpus,
    IndexManifest,
    IndexStatus,
    UpdateMode,
)
from patent_intel.io.safe_io import write_json_atomic
from patent_intel.sources.normalize import normalize_publication_number

__all__ = ["CorpusManager"]

_OWNER = "WP-A"

_PRODUCTION = "production"


def _canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_key(record: Mapping[str, Any]) -> str | None:
    """Identity = normalized publication number, **only when confidently parsed**.

    Numbers the normalizer cannot parse confidently (``uncertain``) yield no key at
    all — such records are counted as failed by the importer and stay available in
    their raw artifact for manual review. They are never silently keyed on the raw
    string: an unguessable identity must not pollute the corpus namespace.
    """
    raw = record.get("publication_number")
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = normalize_publication_number(raw)
    if normalized.confidence == "uncertain":
        return None
    return normalized.normalized


class CorpusManager:
    """JSON-backed corpus lifecycle over one sidecar state directory."""

    OWNER = _OWNER
    PRODUCTION = _PRODUCTION

    def __init__(self, state_dir: Path) -> None:
        self._state = Path(state_dir)
        self._records_path = self._state / "corpus" / "production_records.json"
        self._updates_path = self._state / "corpus" / "production_updates.json"
        self._evaluation_path = self._state / "corpus" / "evaluation_corpora.json"
        self._snapshots_dir = self._state / "corpus" / "snapshots"
        self._manifests_dir = self._state / "corpus" / "manifests"
        for directory in (self._snapshots_dir, self._manifests_dir):
            directory.mkdir(parents=True, exist_ok=True)

    # -- production corpus -------------------------------------------------

    def _load_records(self) -> dict[str, dict[str, Any]]:
        if not self._records_path.is_file():
            return {}
        return json.loads(self._records_path.read_text(encoding="utf-8"))

    def _save_records(self, records: dict[str, dict[str, Any]]) -> None:
        write_json_atomic(self._records_path, records)

    def import_records(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        source: str,
        mode: str = UpdateMode.INCREMENTAL,
        raw_artifact_refs: list[dict[str, Any]] | None = None,
    ) -> CorpusUpdate:
        """Import records idempotently; count seen/added/updated/skipped/failed.

        A record is *skipped* when an identical one exists (content hash equal),
        *updated* when the key exists with different content, *failed* when it has
        no usable identity — failures never abort the batch.
        """
        store = self._load_records()
        seen = added = updated = skipped = failed = 0
        for record in records:
            seen += 1
            key = _record_key(record)
            if key is None:
                failed += 1
                continue
            payload = dict(record)
            digest = _canonical_hash(payload)
            existing = store.get(key)
            if existing is not None:
                if existing.get("_content_sha256") == digest:
                    skipped += 1
                    continue
                updated += 1
            else:
                added += 1
            payload["_content_sha256"] = digest
            store[key] = payload
        self._save_records(store)
        update = CorpusUpdate(
            owner=_OWNER,
            update_id=f"CU-{time.strftime('%Y%m%d%H%M%S')}-{_canonical_hash([source, seen, added, updated, skipped, failed])[:8]}",
            corpus=_PRODUCTION,
            source=source,
            mode=mode,
            records_seen=seen,
            records_added=added,
            records_updated=updated,
            records_skipped=skipped,
            records_failed=failed,
            raw_artifact_refs=raw_artifact_refs,
        )
        self._append_update(update)
        return update

    def _append_update(self, update: CorpusUpdate) -> None:
        history: list[dict[str, Any]] = []
        if self._updates_path.is_file():
            history = json.loads(self._updates_path.read_text(encoding="utf-8"))
        history.append(update.to_dict())
        write_json_atomic(self._updates_path, history)

    def update_history(self) -> list[dict[str, Any]]:
        if not self._updates_path.is_file():
            return []
        return json.loads(self._updates_path.read_text(encoding="utf-8"))

    def record_count(self) -> int:
        return len(self._load_records())

    def get_record(self, publication_number: str) -> dict[str, Any] | None:
        key = _record_key({"publication_number": publication_number})
        return self._load_records().get(key or "")

    # -- snapshots ---------------------------------------------------------

    def create_snapshot(self, *, label: str | None = None) -> CorpusSnapshot:
        """Content-addressed snapshot of the production corpus (idempotent)."""
        store = self._load_records()
        content_sha = _canonical_hash(sorted(store.items()))
        snapshot_id = f"CS-{content_sha[:16]}"
        path = self._snapshots_dir / f"{snapshot_id}.json"
        if not path.is_file():
            write_json_atomic(path, {"records": store, "content_sha256": content_sha})
        snapshot = CorpusSnapshot(
            owner=_OWNER, snapshot_id=snapshot_id, corpus=_PRODUCTION,
            record_count=len(store), content_sha256=content_sha, label=label,
        )
        return snapshot

    def verify_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """Is the current corpus still the snapshot? (drift is reported, never hidden)"""
        path = self._snapshots_dir / f"{snapshot_id}.json"
        if not path.is_file():
            raise KeyError(f"unknown snapshot {snapshot_id!r}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        current = self._load_records()
        current_sha = _canonical_hash(sorted(current.items()))
        return {
            "snapshot_id": snapshot_id,
            "ok": current_sha == payload["content_sha256"],
            "current_sha256": current_sha,
            "snapshot_sha256": payload["content_sha256"],
            "drifted_records": len(current) - len(payload["records"]),
        }

    def restore_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """Restore the production corpus to a snapshot (atomic replace)."""
        path = self._snapshots_dir / f"{snapshot_id}.json"
        if not path.is_file():
            raise KeyError(f"unknown snapshot {snapshot_id!r}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        restored = {k: dict(v) for k, v in payload["records"].items()}
        self._save_records(restored)
        return {
            "snapshot_id": snapshot_id,
            "restored_records": len(restored),
            "verified": self.verify_snapshot(snapshot_id)["ok"],
        }

    # -- evaluation corpus (isolated) ---------------------------------------

    def register_evaluation_corpus(
        self,
        *,
        name: str,
        version: str,
        source: str,
        license_note: str,
        snapshot_dir: Path,
        downloaded_at: str | None = None,
        query_set_hash: str | None = None,
    ) -> EvaluationCorpus:
        """Register a frozen evaluation corpus by hashing every file under
        ``snapshot_dir``. Re-registering the identical snapshot is idempotent; any
        content change is refused — the evaluation corpus is fixed by design
        (不得因新算法表现不佳而随意调整测试集)."""
        snapshot_dir = Path(snapshot_dir)
        if not snapshot_dir.is_dir():
            raise ValueError(f"evaluation snapshot dir missing: {snapshot_dir}")
        if self._state.resolve() in snapshot_dir.resolve().parents:
            raise ValueError(
                "evaluation corpus must not live inside the corpus state directory — "
                "evaluation and production stores are structurally isolated"
            )
        manifest: dict[str, str] = {}
        for file_path in sorted(snapshot_dir.rglob("*")):
            if file_path.is_file():
                rel = file_path.relative_to(snapshot_dir).as_posix()
                manifest[rel] = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if not manifest:
            raise ValueError("evaluation snapshot dir contains no files")
        corpus_id = f"EC-{re.sub(r'[^a-zA-Z0-9_-]+', '-', name)}-{version}"
        store = self._load_evaluation()
        existing = store.get(corpus_id)
        if existing is not None:
            if existing["file_manifest"] != manifest:
                raise ValueError(
                    f"evaluation corpus {corpus_id!r} already registered with different "
                    "content — frozen evaluation sets never change (register a new version)"
                )
            return EvaluationCorpus.from_dict(existing)
        entry = EvaluationCorpus(
            owner=_OWNER,
            corpus_id=corpus_id,
            name=name,
            version=version,
            source=source,
            license=license_note,
            snapshot_dir=str(snapshot_dir),
            file_manifest=manifest,
            downloaded_at=downloaded_at or utc_now_iso(),
            query_set_hash=query_set_hash,
        )
        store[corpus_id] = entry.to_dict()
        write_json_atomic(self._evaluation_path, store)
        return entry

    def verify_evaluation_corpus(self, corpus_id: str) -> list[dict[str, Any]]:
        entry = self._load_evaluation().get(corpus_id)
        if entry is None:
            raise KeyError(f"unknown evaluation corpus {corpus_id!r}")
        results: list[dict[str, Any]] = []
        snapshot_dir = Path(entry["snapshot_dir"])
        for rel, sha in sorted(entry["file_manifest"].items()):
            path = snapshot_dir / rel
            if not path.is_file():
                results.append({"file": rel, "ok": False, "reason": "missing"})
            elif hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                results.append({"file": rel, "ok": False, "reason": "hash_drift"})
            else:
                results.append({"file": rel, "ok": True, "reason": None})
        return results

    def _load_evaluation(self) -> dict[str, dict[str, Any]]:
        if not self._evaluation_path.is_file():
            return {}
        return json.loads(self._evaluation_path.read_text(encoding="utf-8"))

    # -- index manifests -----------------------------------------------------

    def build_index(
        self,
        *,
        index_kind: str,
        index_version: str,
        engine_version: str,
        parser_version: str | None = None,
        parameters: dict[str, Any] | None = None,
        build: Callable[[IndexManifest], int],
    ) -> IndexManifest:
        """Build a derived index against a fresh corpus snapshot.

        ``build(manifest)`` performs the actual indexing and returns the document
        count. Only a successful build activates its manifest; a raising build is
        recorded as ``failed`` and re-raised while the previous active manifest for
        this index kind stays active — the old index is never invalidated by a new
        build's failure.
        """
        snapshot = self.create_snapshot(label=f"index-build {index_kind} {index_version}")
        manifest = IndexManifest(
            owner=_OWNER,
            manifest_id=f"IM-{index_kind}-{index_version}-{snapshot.snapshot_id[:12]}",
            corpus=_PRODUCTION,
            corpus_snapshot_id=snapshot.snapshot_id,
            index_kind=index_kind,
            index_version=index_version,
            engine_version=engine_version,
            parser_version=parser_version,
            parameters=parameters,
            status=IndexStatus.BUILDING,
        )
        try:
            manifest.doc_count = build(manifest)
            manifest.status = IndexStatus.ACTIVE
        except Exception:
            manifest.status = IndexStatus.FAILED
            self._write_manifest(manifest)
            raise
        self._write_manifest(manifest)
        return manifest

    def active_index_manifest(self, index_kind: str) -> IndexManifest | None:
        """The most recent *active* manifest for this index kind (or None)."""
        candidates = [
            m for m in self._load_manifests()
            if m["index_kind"] == index_kind and m["status"] == IndexStatus.ACTIVE
        ]
        if not candidates:
            return None
        return IndexManifest.from_dict(candidates[-1])

    def list_index_manifests(self, index_kind: str | None = None) -> list[dict[str, Any]]:
        return [
            m for m in self._load_manifests()
            if index_kind is None or m["index_kind"] == index_kind
        ]

    def _load_manifests(self) -> list[dict[str, Any]]:
        if not (self._manifests_dir / "manifests.json").is_file():
            return []
        return json.loads((self._manifests_dir / "manifests.json").read_text(encoding="utf-8"))

    def _write_manifest(self, manifest: IndexManifest) -> None:
        history = self._load_manifests()
        history = [m for m in history if m["manifest_id"] != manifest.manifest_id]
        history.append(manifest.to_dict())
        write_json_atomic(self._manifests_dir / "manifests.json", history)
