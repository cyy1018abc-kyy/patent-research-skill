"""Corpus data models (adaptive roadmap Stage 3 / Task 6).

Versioned records for the hybrid local corpus:

* :class:`CorpusUpdate` — one import/incremental/verify run over one corpus
  (records seen/added/updated/skipped/failed are counted separately — 命中数
  不冒充入库数);
* :class:`CorpusSnapshot` — content-addressed corpus state for reproducibility
  (Research Mode requires a fixed snapshot; Live Search Mode records what changed);
* :class:`IndexManifest` — one derived index build bound to a corpus snapshot and
  engine/parser versions (indexes are never evidence and never outlive their
  manifest);
* :class:`EvaluationCorpus` — the frozen evaluation corpus registration, isolated
  from the production corpus (评测集不随生产语料更新而变化).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from patent_intel.contracts import Record, RecordValidationError

__all__ = [
    "CorpusUpdate",
    "CorpusSnapshot",
    "IndexManifest",
    "EvaluationCorpus",
    "IndexStatus",
    "UpdateMode",
]

_OWNER = "WP-A"


class UpdateMode:
    FULL = "full"
    INCREMENTAL = "incremental"
    VERIFY = "verify"

    ALL = (FULL, INCREMENTAL, VERIFY)


class IndexStatus:
    BUILDING = "building"
    ACTIVE = "active"
    FAILED = "failed"
    RETIRED = "retired"

    ALL = (BUILDING, ACTIVE, FAILED, RETIRED)


@dataclass(kw_only=True)
class CorpusUpdate(Record):
    RECORD_TYPE = "corpus_update"
    SPEC = {
        "update_id": str,
        "corpus": str,
        "source": str,
        "mode": str,
        "records_seen": int,
        "records_added": int,
        "records_updated": int,
        "records_skipped": int,
        "records_failed": int,
        "raw_artifact_refs": list,
        "index_manifest_id": str,
    }
    REQUIRED = ("update_id", "corpus", "source", "mode")

    update_id: str
    corpus: str
    source: str
    mode: str
    records_seen: int = 0
    records_added: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    raw_artifact_refs: list[dict[str, Any]] | None = None
    index_manifest_id: str | None = None

    def validate(self) -> None:
        super().validate()
        if self.mode not in UpdateMode.ALL:
            raise RecordValidationError(f"mode {self.mode!r} not in {UpdateMode.ALL}")
        for name in (
            "records_seen", "records_added", "records_updated", "records_skipped", "records_failed"
        ):
            value = getattr(self, name)
            if value < 0:
                raise RecordValidationError(f"{name} must be >= 0")


@dataclass(kw_only=True)
class CorpusSnapshot(Record):
    RECORD_TYPE = "corpus_snapshot"
    SPEC = {
        "snapshot_id": str,
        "corpus": str,
        "record_count": int,
        "content_sha256": str,
        "label": str,
    }
    REQUIRED = ("snapshot_id", "corpus", "record_count", "content_sha256")

    snapshot_id: str
    corpus: str
    record_count: int
    content_sha256: str
    label: str | None = None

    def validate(self) -> None:
        super().validate()
        if self.record_count < 0:
            raise RecordValidationError("record_count must be >= 0")
        if not _is_sha256(self.content_sha256):
            raise RecordValidationError("content_sha256 must be 64 lowercase hex chars")


@dataclass(kw_only=True)
class IndexManifest(Record):
    RECORD_TYPE = "index_manifest"
    SPEC = {
        "manifest_id": str,
        "corpus": str,
        "corpus_snapshot_id": str,
        "index_kind": str,
        "index_version": str,
        "engine_version": str,
        "parser_version": str,
        "parameters": dict,
        "doc_count": int,
        "status": str,
    }
    REQUIRED = (
        "manifest_id", "corpus", "corpus_snapshot_id", "index_kind", "index_version", "engine_version",
    )

    manifest_id: str
    corpus: str
    corpus_snapshot_id: str
    index_kind: str
    index_version: str
    engine_version: str
    parser_version: str | None = None
    parameters: dict[str, Any] | None = None
    doc_count: int = 0
    status: str = IndexStatus.BUILDING

    def validate(self) -> None:
        super().validate()
        if self.status not in IndexStatus.ALL:
            raise RecordValidationError(f"status {self.status!r} not in {IndexStatus.ALL}")
        if self.doc_count < 0:
            raise RecordValidationError("doc_count must be >= 0")


@dataclass(kw_only=True)
class EvaluationCorpus(Record):
    RECORD_TYPE = "evaluation_corpus"
    SPEC = {
        "corpus_id": str,
        "name": str,
        "version": str,
        "source": str,
        "license": str,
        "downloaded_at": str,
        "snapshot_dir": str,
        "file_manifest": dict,
        "query_set_hash": str,
    }
    REQUIRED = ("corpus_id", "name", "version", "source", "license", "snapshot_dir", "file_manifest")

    corpus_id: str
    name: str
    version: str
    source: str
    license: str
    snapshot_dir: str
    file_manifest: dict[str, str]
    downloaded_at: str | None = None
    query_set_hash: str | None = None

    def validate(self) -> None:
        super().validate()
        for rel, sha in self.file_manifest.items():
            if not _is_sha256(sha):
                raise RecordValidationError(
                    f"file_manifest[{rel!r}] is not a sha256 digest — the evaluation corpus "
                    "manifest must register every file's content hash"
                )


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))
