"""Unified raw-artifact registry (adaptive roadmap Task 4).

CNIPA raw pages live in the kernel workspace ``02_search_logs/raw/`` (the kernel
owns that evidence chain); OPS pages live in the Patent Intel sidecar ``raw/``;
local imports land wherever the operator put them. This registry does **not**
move, copy or rewrite any of them — 原始数据可以分区存储，引用和审计必须统一.
It gives every artifact one deterministic, content-addressed id, one registration
record (path, SHA-256, bytes, MIME, source, query/run ids, ingest status) and one
verification entry point that checks the file still exists and still hashes to the
registered digest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from patent_intel.contracts import IngestStatus, RawArtifactRef, utc_now_iso
from patent_intel.io.safe_io import write_json_atomic

__all__ = ["RawArtifactRegistry", "RegistrationError", "infer_mime"]

#: suffix → MIME (best-effort; unknown suffixes are octet-stream, never guessed further)
_MIME_BY_SUFFIX = {
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".xml": "application/xml",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
}


class RegistrationError(Exception):
    """A raw artifact could not be registered honestly (missing file, hash drift)."""


def infer_mime(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")


def _sha256_file(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


class RawArtifactRegistry:
    """Content-addressed registration index over raw artifacts from every source.

    ``index_path`` (optional) persists the registrations as a JSON sidecar so a new
    registry instance resumes the same audit trail. Paths may be absolute or
    relative to ``base_dir`` (typically the kernel workspace or the sidecar root).
    """

    def __init__(self, *, base_dir: Path | None = None, index_path: Path | None = None) -> None:
        self._base_dir = Path(base_dir).resolve() if base_dir else None
        self._index_path = Path(index_path) if index_path else None
        self._entries: dict[str, RawArtifactRef] = {}
        if self._index_path and self._index_path.is_file():
            self._load_index()

    # -- registration -----------------------------------------------------

    @staticmethod
    def artifact_id_for(source: str, sha256: str) -> str:
        """Deterministic, content-addressed id: same source + same bytes = same artifact."""
        return f"RA-{source}-{sha256[:16]}"

    def register(self, ref: RawArtifactRef, *, verify: bool = True) -> RawArtifactRef:
        """Register (or idempotently re-register) one raw artifact.

        ``verify=True`` (default) refuses registration when the file is missing or
        no longer hashes to the registered digest — an unverifiable pointer is not
        an audit entry. The file itself is never touched.
        """
        path = self._resolve(ref.path)
        if verify:
            if not path.is_file():
                raise RegistrationError(f"raw artifact missing on disk: {ref.path}")
            actual_sha, actual_bytes = _sha256_file(path)
            if actual_sha != ref.sha256:
                raise RegistrationError(
                    f"sha256 mismatch for {ref.path}: registered {ref.sha256[:12]}…, "
                    f"on disk {actual_sha[:12]}… — refusing to register drifted data"
                )
            if actual_bytes != ref.bytes:
                raise RegistrationError(
                    f"byte size mismatch for {ref.path}: registered {ref.bytes}, on disk {actual_bytes}"
                )
        expected_id = self.artifact_id_for(ref.source, ref.sha256)
        if ref.artifact_id is not None and ref.artifact_id != expected_id:
            raise RegistrationError(
                f"artifact_id {ref.artifact_id!r} does not match the content-addressed "
                f"id {expected_id!r} (ids are derived, never chosen)"
            )
        ref.artifact_id = expected_id
        if ref.ingest_status is None:
            ref.ingest_status = IngestStatus.REGISTERED
        self._entries[expected_id] = ref
        self._save_index()
        return ref

    def register_kernel_raw(
        self,
        *,
        workspace: Path,
        raw_export: str,
        source: str,
        query_id: str | None = None,
        run_id: str | None = None,
        captured_at: str | None = None,
    ) -> RawArtifactRef:
        """Register a kernel-written raw artifact (``02_search_logs/raw/`` area).

        ``raw_export`` is the kernel log's ``result.raw_export`` value, relative to
        the workspace's ``02_search_logs`` directory. The digest is computed from
        the file — the kernel already owns the capture; we only reference it.
        """
        path = Path(workspace) / "02_search_logs" / raw_export
        if not path.is_file():
            raise RegistrationError(f"kernel raw artifact missing: {path}")
        sha, size = _sha256_file(path)
        stored_path = path.resolve().relative_to(Path(workspace).resolve()).as_posix()
        return self.register(
            RawArtifactRef(
                owner="WP-B",
                path=stored_path,
                sha256=sha,
                mime=infer_mime(path),
                bytes=size,
                source=source,
                captured_at=captured_at or utc_now_iso(),
                query_id=query_id,
                run_id=run_id,
            )
        )

    def register_from_refs(
        self,
        refs: list[dict[str, Any]],
        *,
        source: str,
        base_dir: Path,
        query_id: str | None = None,
        run_id: str | None = None,
        captured_at: str | None = None,
    ) -> list[RawArtifactRef]:
        """Register from ``AcquisitionResult.raw_refs``-shaped dicts.

        Handles both adapter shapes honestly: kernel refs carry ``{path, bytes,
        source}`` (digest computed from the file); OPS page refs carry
        ``{raw_ref, sha256, bytes_written}``. Fields a ref cannot honestly provide
        are derived from the file, never invented.
        """
        registered: list[RawArtifactRef] = []
        for item in refs:
            raw_name = item.get("path") or item.get("raw_ref")
            if not raw_name:
                raise RegistrationError(
                    f"raw ref {item!r} carries neither 'path' nor 'raw_ref' — cannot register"
                )
            path = (Path(base_dir) / raw_name)
            if not path.is_file():
                raise RegistrationError(f"raw artifact missing: {path}")
            sha = item.get("sha256")
            if sha is None:
                sha, _ = _sha256_file(path)
            size = item.get("bytes", item.get("bytes_written"))
            if size is None:
                _, size = _sha256_file(path)
            registered.append(
                self.register(
                    RawArtifactRef(
                        owner="WP-B",
                        path=Path(raw_name).as_posix(),
                        sha256=sha,
                        mime=infer_mime(path),
                        bytes=size,
                        source=item.get("source") or source,
                        captured_at=captured_at or utc_now_iso(),
                        query_id=query_id,
                        run_id=run_id,
                    )
                )
            )
        return registered

    # -- lifecycle ---------------------------------------------------------

    def mark_ingested(
        self, artifact_id: str, *, normalized_record_refs: list[dict[str, Any]] | None = None
    ) -> RawArtifactRef:
        ref = self._entries[artifact_id]
        ref.ingest_status = IngestStatus.INGESTED
        if normalized_record_refs:
            merged = list(ref.normalized_record_refs or [])
            merged.extend(r for r in normalized_record_refs if r not in merged)
            ref.normalized_record_refs = merged
        self._save_index()
        return ref

    def mark_failed(self, artifact_id: str, *, reason: str) -> RawArtifactRef:
        ref = self._entries[artifact_id]
        ref.ingest_status = IngestStatus.FAILED
        ref.normalized_record_refs = list(ref.normalized_record_refs or []) + [
            {"error": reason, "recorded_at": utc_now_iso()}
        ]
        self._save_index()
        return ref

    def get(self, artifact_id: str) -> RawArtifactRef:
        return self._entries[artifact_id]

    def entries(self) -> list[RawArtifactRef]:
        return list(self._entries.values())

    def verify_all(self) -> list[dict[str, Any]]:
        """Re-verify every registration against the file on disk (audit entry point)."""
        results: list[dict[str, Any]] = []
        for artifact_id, ref in sorted(self._entries.items()):
            path = self._resolve(ref.path)
            if not path.is_file():
                results.append({"artifact_id": artifact_id, "ok": False, "reason": "missing"})
                continue
            actual_sha, actual_bytes = _sha256_file(path)
            if actual_sha != ref.sha256 or actual_bytes != ref.bytes:
                results.append(
                    {"artifact_id": artifact_id, "ok": False, "reason": "hash_or_size_drift"}
                )
            else:
                results.append({"artifact_id": artifact_id, "ok": True, "reason": None})
        return results

    def describe(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for ref in self._entries.values():
            status = ref.ingest_status or IngestStatus.REGISTERED
            by_status[status] = by_status.get(status, 0) + 1
        return {
            "artifact_count": len(self._entries),
            "by_ingest_status": by_status,
            "artifacts": [ref.to_dict() for ref in self._entries.values()],
        }

    # -- persistence ---------------------------------------------------------

    def _resolve(self, path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path
        if self._base_dir is None:
            raise RegistrationError(
                f"relative path {path_value!r} requires the registry base_dir"
            )
        return self._base_dir / path

    def _save_index(self) -> None:
        if self._index_path is None:
            return
        payload = {aid: ref.to_dict() for aid, ref in sorted(self._entries.items())}
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self._index_path, payload)

    def _load_index(self) -> None:
        assert self._index_path is not None
        data = json.loads(self._index_path.read_text(encoding="utf-8"))
        for artifact_id, payload in data.items():
            ref = RawArtifactRef.from_dict(payload)
            if artifact_id != ref.artifact_id:  # pragma: no cover - corrupted index
                raise RegistrationError(
                    f"index key {artifact_id!r} does not match ref artifact_id {ref.artifact_id!r}"
                )
            self._entries[artifact_id] = ref
