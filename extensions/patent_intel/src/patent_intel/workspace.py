"""Sidecar state-dir layout for patent_intel (blueprint F-04/F-05, ADR 0002).

Everything this extension persists lives under one root (the *state dir*) in
predictable subdirectories. The layout is intentionally flat and file-based
(JSON + SQLite later per blueprint §2) so the whole cache is trivially deletable
and rebuildable — it is never a second source of truth for kernel facts.

    <state_dir>/
    ├── manifest.json      # sidecar metadata (workspace binding, version)
    ├── config.json        # user configuration (optional)
    ├── features/          # FeatureSpec records            (WP-A)
    ├── queries/           # QuerySpec proposals + approvals (WP-A)
    ├── runs/              # SearchRun state machines + checkpoints (WP-B)
    ├── index/             # normalized PatentRecord index   (WP-B)
    ├── anchors/           # DocumentAnchor records          (WP-C)
    ├── evidence/          # EvidenceProjection views        (WP-D)
    ├── advisory/          # AdvisoryProposal records        (WP-D)
    ├── reports/           # recall/coverage/landscape reports
    ├── audit/             # acquisition ledgers, hashes     (WP-B)
    └── tmp/               # scratch space (safe to purge)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from patent_intel import __version__
from patent_intel.contracts import ContractError
from patent_intel.io.safe_io import read_json_limited, write_json_atomic

__all__ = ["SIDECAR_SUBDIRS", "SidecarLayout", "SidecarManifestError"]

SIDECAR_SUBDIRS = (
    "features",
    "queries",
    "runs",
    "index",
    "anchors",
    "evidence",
    "advisory",
    "reports",
    "audit",
    "tmp",
)

_MANIFEST_NAME = "manifest.json"


class SidecarManifestError(ContractError):
    """The sidecar manifest is missing fields or binds a different workspace."""


@dataclass
class SidecarLayout:
    """Typed accessor for the sidecar directory tree."""

    state_dir: Path

    def __post_init__(self) -> None:
        self.state_dir = Path(self.state_dir)

    # -- typed directories ---------------------------------------------

    def dir(self, name: str) -> Path:
        if name not in SIDECAR_SUBDIRS:
            raise SidecarManifestError(
                f"unknown sidecar subdirectory {name!r} (known: {SIDECAR_SUBDIRS})"
            )
        return self.state_dir / name

    @property
    def features(self) -> Path:
        return self.dir("features")

    @property
    def queries(self) -> Path:
        return self.dir("queries")

    @property
    def runs(self) -> Path:
        return self.dir("runs")

    @property
    def index(self) -> Path:
        return self.dir("index")

    @property
    def anchors(self) -> Path:
        return self.dir("anchors")

    @property
    def evidence(self) -> Path:
        return self.dir("evidence")

    @property
    def advisory(self) -> Path:
        return self.dir("advisory")

    @property
    def reports(self) -> Path:
        return self.dir("reports")

    @property
    def audit(self) -> Path:
        return self.dir("audit")

    @property
    def tmp(self) -> Path:
        return self.dir("tmp")

    # -- manifest ------------------------------------------------------

    def ensure(self, *, workspace: Path | None = None) -> None:
        """Create the directory tree and (re)write the manifest binding the workspace."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        for name in SIDECAR_SUBDIRS:
            (self.state_dir / name).mkdir(exist_ok=True)
        manifest = {
            "manifest_version": 1,
            "patent_intel_version": __version__,
            "workspace": str(Path(workspace).resolve()) if workspace else None,
            "deletable": True,
        }
        write_json_atomic(self.state_dir / _MANIFEST_NAME, manifest)

    def check_binding(self, workspace: Path) -> None:
        """Refuse to run against a sidecar that belongs to a different workspace."""
        path = self.state_dir / _MANIFEST_NAME
        if not path.is_file():
            return  # fresh sidecar; ensure() will bind it
        data = read_json_limited(path)
        bound = data.get("workspace")
        if bound and Path(bound).resolve() != Path(workspace).resolve():
            raise SidecarManifestError(
                f"state dir {self.state_dir} is bound to workspace {bound}, "
                f"not {Path(workspace).resolve()}; pass a different --state-dir or delete this sidecar"
            )

    def exists(self) -> bool:
        return self.state_dir.is_dir() and (self.state_dir / _MANIFEST_NAME).is_file()

    def purge_scratch(self) -> int:
        """Remove tmp/ contents; return the number of files removed. Never touches kernel files."""
        n = 0
        if self.tmp.is_dir():
            for p in sorted(self.tmp.iterdir()):
                if p.is_file():
                    p.unlink()
                    n += 1
        return n

    def summary(self) -> dict[str, object]:
        """Per-subdirectory record counts for `doctor` (read-only)."""
        out: dict[str, object] = {}
        for name in SIDECAR_SUBDIRS:
            d = self.state_dir / name
            if not d.is_dir():
                out[name] = None
                continue
            out[name] = {
                "json_files": len(list(d.glob("*.json"))),
                "jsonl_files": len(list(d.glob("*.jsonl"))),
            }
        manifest_path = self.state_dir / _MANIFEST_NAME
        if manifest_path.is_file():
            try:
                out["manifest"] = read_json_limited(manifest_path)
            except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - doctor reports, never crashes
                out["manifest"] = {"error": str(exc)}
        return out
