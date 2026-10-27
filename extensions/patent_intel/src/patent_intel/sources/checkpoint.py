"""Acquisition checkpoints (blueprint B-04/B-05): resumable, idempotent, crash-safe.

A checkpoint is one JSON file per run in the sidecar ``runs/`` directory:

    {schema_version, run_id, query_id, source, status, request_fingerprint,
     pages_done: [{fingerprint, raw_ref, sha256, bytes}], updated_at}

Rules (interface rule 8):
* resuming never overwrites existing raw artifacts (ref fingerprints already on
  disk are skipped, not re-fetched);
* the same ``request_fingerprint`` recorded ``complete`` makes a re-run a no-op
  (idempotent replay);
* state transitions follow the SearchRun state machine; crash mid-page loses at
  most that page because the checkpoint is written after each flushed artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from patent_intel.contracts import RunStatus, SearchRun, utc_now_iso
from patent_intel.io.safe_io import read_json_limited, write_json_atomic

__all__ = ["Checkpoint", "CheckpointStore", "CheckpointError"]

_OWNER = "WP-B"


class CheckpointError(ValueError):
    """Invalid checkpoint state transition or malformed file."""


class Checkpoint:
    """In-memory state of one acquisition run."""

    def __init__(
        self,
        *,
        run_id: str,
        query_id: str,
        source: str,
        request_fingerprint: str,
        status: str = RunStatus.PLANNED,
        pages_done: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        if status not in RunStatus.ALL:
            raise CheckpointError(f"bad status {status!r}")
        self.run_id = run_id
        self.query_id = query_id
        self.source = source
        self.request_fingerprint = request_fingerprint
        self.status = status
        self.pages_done: list[dict[str, Any]] = pages_done or []
        self.error = error

    @property
    def fingerprints_done(self) -> set[str]:
        return {page["fingerprint"] for page in self.pages_done if "fingerprint" in page}

    def is_complete_replay(self) -> bool:
        return self.status == RunStatus.COMPLETE

    def transition(self, new_status: str, *, error: str | None = None) -> None:
        """Validate the state machine before applying."""
        allowed: dict[str, tuple[str, ...]] = {
            RunStatus.PLANNED: (RunStatus.RUNNING, RunStatus.CANCELLED),
            RunStatus.RUNNING: (RunStatus.PARTIAL, RunStatus.COMPLETE, RunStatus.FAILED, RunStatus.CANCELLED),
            RunStatus.PARTIAL: (RunStatus.RUNNING, RunStatus.COMPLETE, RunStatus.FAILED, RunStatus.CANCELLED),
            RunStatus.FAILED: (RunStatus.RUNNING,),  # retry = fresh attempt
            RunStatus.COMPLETE: (),  # terminal: idempotent no-op afterwards
            RunStatus.CANCELLED: (RunStatus.RUNNING,),  # resume
        }
        if new_status not in allowed.get(self.status, ()):
            raise CheckpointError(f"illegal transition {self.status} -> {new_status}")
        if new_status == RunStatus.FAILED and not error:
            raise CheckpointError("failed transition requires error")
        self.status = new_status
        self.error = error

    def record_page(self, *, fingerprint: str, raw_ref: str, sha256: str, bytes_written: int) -> None:
        if fingerprint in self.fingerprints_done:
            return  # idempotent: page already flushed
        self.pages_done.append(
            {
                "fingerprint": fingerprint,
                "raw_ref": raw_ref,
                "sha256": sha256,
                "bytes": bytes_written,
                "recorded_at": utc_now_iso(),
            }
        )

    def to_search_run(self) -> SearchRun:
        complete = self.status == RunStatus.COMPLETE
        reason = None
        if not complete and self.status in (RunStatus.PARTIAL, RunStatus.FAILED, RunStatus.CANCELLED):
            reason = self.error or "unknown"
        return SearchRun(
            owner=_OWNER,
            run_id=self.run_id,
            query_id=self.query_id,
            source=self.source,
            executed_at=utc_now_iso(),
            status=self.status,
            request_fingerprint=self.request_fingerprint,
            records_fetched=len(self.pages_done),
            complete=complete if self.status in (RunStatus.COMPLETE, RunStatus.PARTIAL) else None,
            incomplete_reason=reason,
            artifact_refs=list(self.pages_done),
            error=self.error,
        )


class CheckpointStore:
    """JSON persistence in the sidecar runs/ dir (atomic write per update)."""

    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in run_id)
        return self.runs_dir / f"{safe}.ckpt.json"

    def save(self, cp: Checkpoint) -> Path:
        payload = {
            "schema_version": 1,
            "owner": _OWNER,
            "run_id": cp.run_id,
            "query_id": cp.query_id,
            "source": cp.source,
            "request_fingerprint": cp.request_fingerprint,
            "status": cp.status,
            "pages_done": cp.pages_done,
            "error": cp.error,
            "updated_at": utc_now_iso(),
        }
        path = self._path(cp.run_id)
        write_json_atomic(path, payload)
        return path

    def load(self, run_id: str) -> Checkpoint:
        path = self._path(run_id)
        if not path.is_file():
            raise FileNotFoundError(f"no checkpoint for run {run_id!r}")
        data = read_json_limited(path)
        try:
            return Checkpoint(
                run_id=data["run_id"],
                query_id=data["query_id"],
                source=data["source"],
                request_fingerprint=data["request_fingerprint"],
                status=data["status"],
                pages_done=data.get("pages_done") or [],
                error=data.get("error"),
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise CheckpointError(f"malformed checkpoint {path}: {exc}") from None

    def find_resumable(self, request_fingerprint: str) -> Checkpoint | None:
        """Return an incomplete checkpoint for this request fingerprint, if any."""
        for path in sorted(self.runs_dir.glob("*.ckpt.json")):
            try:
                data = read_json_limited(path)
            except (OSError, json.JSONDecodeError):
                continue
            if (
                data.get("request_fingerprint") == request_fingerprint
                and data.get("status") not in (RunStatus.COMPLETE,)
            ):
                return self.load(data["run_id"])
        return None
