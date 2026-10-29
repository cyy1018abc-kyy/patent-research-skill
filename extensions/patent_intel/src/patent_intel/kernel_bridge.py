"""Read-only bridge to the `patentkit` kernel (blueprint F-04, ADR 0001).

Hard rules, enforced here and machine-checked by ``tests/test_kernel_boundary.py``:

1. **This module never writes to the kernel workspace.** Every function below either
   reads via the kernel's own public API, or invokes the kernel CLI as a subprocess
   with explicitly read-only arguments (never ``--apply``, never ``--run``).
2. Kernel import is lazy and optional: the base wheel works without it and ``doctor``
   reports actionable guidance (blueprint F-02 acceptance: empty-env ``--help``).
3. Compat floor: ``patentkit >= 0.8.0`` and assessment protocol 1 (the same probe the
   skill scripts use). A mismatch is a hard, explained error — never a silent guess.
4. All reads go through the kernel's public helpers (``paths``, ``model``) so the
   extension automatically follows kernel-side contract changes instead of re-parsing
   workspace files with drifted assumptions.
"""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "KernelNotAvailableError",
    "KernelCompatError",
    "KernelInfo",
    "kernel_info",
    "require_kernel",
    "is_kernel_workspace",
    "find_kernel_workspace",
    "read_glossary",
    "read_axes",
    "read_search_logs",
    "read_candidates",
    "run_kernel_readonly",
    "MIN_KERNEL_VERSION",
]

#: Compat floor from blueprint F-04 (released kernel when 4.0 was designed).
MIN_KERNEL_VERSION = (0, 8, 0)


class KernelNotAvailableError(Exception):
    """patentkit is not importable. Carries actionable install guidance."""


class KernelCompatError(Exception):
    """patentkit is importable but too old / protocol-incompatible."""


@dataclass(frozen=True)
class KernelInfo:
    importable: bool
    version: str | None
    version_tuple: tuple[int, ...] | None
    protocol_version: int | None
    error: str | None = None

    def compatible(self) -> bool:
        if not self.importable or self.version_tuple is None:
            return False
        if self.version_tuple < MIN_KERNEL_VERSION:
            return False
        if self.protocol_version is not None and self.protocol_version != 1:
            return False
        return True


def _parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in version.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) or (0,)


def kernel_info() -> KernelInfo:
    """Probe kernel availability and compatibility. Never raises."""
    try:
        import patentkit  # noqa: F401
    except ImportError as exc:
        return KernelInfo(
            importable=False,
            version=None,
            version_tuple=None,
            protocol_version=None,
            error=f"patentkit is not installed ({exc}); install with: pip install patentkit",
        )
    try:
        version = importlib.metadata.version("patentkit")
    except importlib.metadata.PackageNotFoundError:
        version = None
    protocol: int | None = None
    proto_error: str | None = None
    try:
        from patentkit.assessment import PROTOCOL_VERSION

        protocol = int(PROTOCOL_VERSION)
    except ImportError:
        proto_error = "assessment protocol probe unavailable (kernel < 0.8.0?)"
    return KernelInfo(
        importable=True,
        version=version,
        version_tuple=_parse_version(version) if version else None,
        protocol_version=protocol,
        error=proto_error,
    )


def require_kernel() -> KernelInfo:
    """Return kernel info or raise with actionable guidance (exit-code 3 semantics upstream)."""
    info = kernel_info()
    if not info.importable:
        raise KernelNotAvailableError(info.error or "patentkit is not installed")
    if info.version_tuple is not None and info.version_tuple < MIN_KERNEL_VERSION:
        raise KernelCompatError(
            f"patentkit {info.version} is too old; patent_intel requires >= "
            f"{'.'.join(map(str, MIN_KERNEL_VERSION))}"
        )
    if info.protocol_version is not None and info.protocol_version != 1:
        raise KernelCompatError(
            f"unsupported assessment protocol {info.protocol_version}; patent_intel requires protocol 1"
        )
    return info


# ── Workspace discovery (mirrors patentkit.paths semantics) ───────────


def is_kernel_workspace(path: Path) -> bool:
    """True if ``path`` is a kernel workspace. Works without patentkit (marker-file check)."""
    path = Path(path)
    if (path / "workspace.yml").is_file():
        return True
    markers = (
        path / "00_methodology" / "glossary.yml",
        path / "03_candidates",
        path / "02_search_logs",
    )
    return all(m.exists() for m in markers)


def find_kernel_workspace(start: Path | None = None) -> Path:
    """Search upward for a kernel workspace; raise FileNotFoundError with fixes if absent."""
    cur = (start or Path.cwd()).resolve()
    for candidate in (cur, *cur.parents):
        if is_kernel_workspace(candidate):
            return candidate
    raise FileNotFoundError(
        f"no patentkit workspace found upward from {cur}; "
        "pass --root pointing at the directory containing workspace.yml"
    )


# ── Read-only accessors (lazy kernel imports) ──────────────────────────


def _load_yaml(text: str) -> Any:
    try:
        import yaml  # noqa: PLC0415 - optional; bundled with patentkit
    except ImportError:
        raise KernelNotAvailableError(
            "PyYAML is required to read the kernel glossary; install with: pip install 'patent_intel[kernel]'"
        ) from None
    return yaml.safe_load(text)


def read_glossary(workspace: Path) -> dict[str, Any]:
    """Parse the workspace glossary (single source of truth for axes/targets). Read-only."""
    path = Path(workspace) / "00_methodology" / "glossary.yml"
    if not path.is_file():
        raise FileNotFoundError(f"glossary not found: {path}")
    data = _load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"glossary is not a mapping: {path}")
    return data


def read_axes(workspace: Path) -> dict[str, dict[str, Any]]:
    """Return the technical axes as ``{axis_id: {...}}`` (IDs are target-qualified, e.g. N1@TGT-0001)."""
    glossary = read_glossary(workspace)
    axes = glossary.get("axes") or {}
    if not isinstance(axes, dict):
        raise ValueError("glossary 'axes' is not a mapping")
    return axes


def read_search_logs(workspace: Path) -> list[dict[str, Any]]:
    """Read every ``02_search_logs/*.log.json`` via the kernel's own loader. Read-only."""
    require_kernel()
    from patentkit.model import load_logs

    return [log.data for log in load_logs(Path(workspace))]


def read_candidates(workspace: Path) -> list[dict[str, Any]]:
    """Read every ``03_candidates/*.json`` candidate record via the kernel's loader. Read-only."""
    require_kernel()
    from patentkit.model import load_candidates

    return [cand.data for cand in load_candidates(Path(workspace))]


def run_kernel_readonly(
    args: list[str],
    *,
    workspace: Path,
    timeout: int = 120,
) -> dict[str, Any]:
    """Invoke ``python -m patentkit <args> --json`` in a subprocess and return parsed stdout.

    Guardrails:
    * the verb must be on the read-only allowlist (refuses fetch-*/ingest/revise/... at
      the type level — this is the machine-checked half of the boundary rule);
    * refuses args that enable kernel-side writes (``--apply``, ``--run``, ``--force``);
    * ``--json`` is always appended so stdout is exactly one JSON document.
    """
    from patent_intel.kernel_allowlist import READONLY_VERBS, FORBIDDEN_FLAGS

    if not args:
        raise ValueError("empty kernel command")
    verb = args[0]
    if verb not in READONLY_VERBS:
        raise ValueError(
            f"kernel verb {verb!r} is not on the read-only allowlist {sorted(READONLY_VERBS)}; "
            "the extension may not drive kernel mutations"
        )
    for flag in FORBIDDEN_FLAGS:
        if flag in args:
            raise ValueError(f"flag {flag!r} enables kernel-side writes and is refused by the bridge")
    cmd = [sys.executable, "-m", "patentkit", *args, "--json"]
    proc = subprocess.run(
        cmd,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"kernel command {' '.join(args)} exited {proc.returncode}: {proc.stderr.strip()[:2000]}"
        )
    return json.loads(proc.stdout)
