"""Acquisition audit ledgers (blueprint B-05).

Two append-only JSONL ledgers in the sidecar ``audit/`` directory:

* ``raw_ledger.jsonl`` — one entry per captured raw artifact: path, SHA-256, size,
  source, request fingerprint. "每个成功采集页有原始文件与校验哈希" is checkable
  from this file alone.
* ``failure_ledger.jsonl`` — aborted/failed batches: what was attempted, what was
  preserved, why it stopped (403/429/timeout/network).

Append semantics with crash safety: entries are appended with a single atomic
rewrite of the (bounded) file — sidecar ledgers stay small; the append operation
itself is serialized by :func:`patent_intel.io.safe_io.file_lock`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from patent_intel.io.safe_io import file_lock, write_text_atomic

__all__ = ["AuditLedger", "LedgerError"]

_OWNER = "WP-B"

_RAW_LEDGER = "raw_ledger.jsonl"
_FAILURE_LEDGER = "failure_ledger.jsonl"
_MAX_LEDGER_BYTES = 32 * 1024 * 1024  # refuse runaway ledgers


class LedgerError(RuntimeError):
    """Ledger append or verification failed."""


class AuditLedger:
    def __init__(self, audit_dir: Path) -> None:
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    # -- raw artifact ledger -------------------------------------------

    def append_raw(
        self,
        *,
        path: str,
        sha256: str,
        bytes_written: int,
        source: str,
        request_fingerprint: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "kind": "raw_artifact",
            "owner": _OWNER,
            "path": path,
            "sha256": sha256,
            "bytes": bytes_written,
            "source": source,
            "request_fingerprint": request_fingerprint,
            **(extra or {}),
        }
        self._append(_RAW_LEDGER, entry)
        return entry

    def raw_entries(self) -> list[dict[str, Any]]:
        return self._read(_RAW_LEDGER)

    def verify_raw_files(self, base_dir: Path) -> dict[str, Any]:
        """Re-hash every logged raw artifact under ``base_dir`` and report mismatches.

        This is the Audit Integrity metric input (blueprint §12): hash/log 一致率.
        """
        import hashlib

        checked = 0
        missing = 0
        mismatched: list[str] = []
        for entry in self.raw_entries():
            path = Path(base_dir) / entry["path"]
            if not path.is_file():
                missing += 1
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            checked += 1
            if digest != entry["sha256"]:
                mismatched.append(entry["path"])
        return {"checked": checked, "missing": missing, "mismatched": mismatched}

    # -- failure ledger ------------------------------------------------

    def append_failure(
        self,
        *,
        source: str,
        run_id: str,
        stop_reason: str,
        preserved_pages: int,
        detail: str = "",
    ) -> dict[str, Any]:
        entry = {
            "kind": "acquisition_failure",
            "owner": _OWNER,
            "source": source,
            "run_id": run_id,
            "stop_reason": stop_reason,
            "preserved_pages": preserved_pages,
            "detail": detail[:2000],
        }
        self._append(_FAILURE_LEDGER, entry)
        return entry

    def failure_entries(self) -> list[dict[str, Any]]:
        return self._read(_FAILURE_LEDGER)

    # -- plumbing ------------------------------------------------------

    def _append(self, name: str, entry: dict[str, Any]) -> None:
        path = self.audit_dir / name
        with file_lock(self.audit_dir / f".{name}.lock"):
            existing = self._read(name)
            if path.exists() and path.stat().st_size > _MAX_LEDGER_BYTES:
                raise LedgerError(f"{name} exceeds {_MAX_LEDGER_BYTES} bytes; rotate it first")
            existing.append(entry)
            text = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in existing)
            write_text_atomic(path, text)

    def _read(self, name: str) -> list[dict[str, Any]]:
        path = self.audit_dir / name
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise LedgerError(f"{name}:{lineno}: corrupt ledger line: {exc}") from None
        return out
