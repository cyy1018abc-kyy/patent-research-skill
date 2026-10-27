"""Kernel boundary machine checks (ADR 0001/0002, blueprint F-01/F-05 acceptance).

Three properties, enforced in CI without relying on reviewer memory:

1. the extension's source never writes into kernel workspace paths, and
   ``kernel_bridge.py`` — the only module allowed to touch the kernel at all — contains
   zero filesystem-mutation calls;
2. the bridge can only dispatch kernel verbs on the read-only allowlist and refuses
   every write-enabling flag;
3. the sidecar state dir is invisible to the kernel: with a sidecar present, kernel
   ``check --json`` output is byte-identical to the pre-sidecar run, and deleting the
   sidecar changes nothing (cache-rebuildability guarantee).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXT_SRC = REPO_ROOT / "extensions" / "patent_intel" / "src" / "patent_intel"

#: Kernel workspace locations the extension must treat as read-only (ADR 0001 §2).
PROTECTED_KERNEL_PATHS = (
    "00_methodology",
    "01_search_plan",
    "02_search_logs",
    "03_candidates",
    "04_comparative_analysis",
    "05_novelty_conclusions",
    "06_citation_management",
    "07_delivery",
    "workspace.yml",
)

#: Filesystem-mutation call sites. kernel_bridge.py must contain none of these.
MUTATION_PATTERNS = (
    r"\.write_text\(",
    r"\.write_bytes\(",
    r"\.mkdir\(",
    r"os\.replace\(",
    r"\.unlink\(",
    r"shutil\.",
    r"open\([^)]*['\"][wab]",
)

REAL_KERNEL_COMMANDS = {
    # Subset of `python -m patentkit --help` verbs (kernel cli PASSTHROUGH + SPECIAL).
    "validate", "gates", "migrate", "index", "report", "ingest", "bibsync", "attest",
    "review", "backfill", "fetch-crossref", "backfill-doi", "fetch-bigquery",
    "provenance", "figures", "export-docx", "deadlines", "map", "layout", "ledger",
    "queryplan", "revise", "chain", "upgrade", "intake", "discovery", "draft",
    "deliver", "status", "doctor", "search-plan", "init", "fetch-cnipa", "check", "mcp",
}


def _bridge_source() -> str:
    return (EXT_SRC / "kernel_bridge.py").read_text(encoding="utf-8")


def _all_extension_sources() -> list[Path]:
    return sorted(EXT_SRC.rglob("*.py"))


def test_allowlist_verbs_are_real_kernel_commands() -> None:
    from patent_intel.kernel_allowlist import READONLY_VERBS

    assert READONLY_VERBS, "allowlist must not be empty"
    unknown = READONLY_VERBS - REAL_KERNEL_COMMANDS
    assert not unknown, f"allowlist contains non-existent kernel verbs: {sorted(unknown)}"


def test_allowlist_verbs_are_read_only_by_default() -> None:
    """Each allowlisted verb must be documented as read-only; mutation verbs are banned.

    Kernel mutation commands (fetch-*/ingest/revise/…) must never appear, even though
    some have read-only modes — the allowlist stays conservative on purpose.
    """
    from patent_intel.kernel_allowlist import READONLY_VERBS

    banned = {"fetch-cnipa", "fetch-crossref", "fetch-bigquery", "ingest", "revise",
              "draft", "deliver", "attest", "bibsync", "backfill", "backfill-doi", "migrate"}
    assert not (READONLY_VERBS & banned)


def test_bridge_source_contains_no_filesystem_mutation() -> None:
    src = _bridge_source()
    for pattern in MUTATION_PATTERNS:
        assert not re.search(pattern, src), (
            f"kernel_bridge.py must not contain {pattern!r}; it is a read-only module"
        )


def test_bridge_only_imports_read_kernel_api() -> None:
    src = _bridge_source()
    # Only these patentkit submodules may be imported by the bridge.
    allowed_imports = {"patentkit", "patentkit.assessment", "patentkit.model", "patentkit.paths"}
    for mod in re.findall(r"from (patentkit[\w.]*) import|import (patentkit[\w.]*)", src):
        name = mod[0] or mod[1]
        assert name in allowed_imports, f"bridge imports non-allowlisted kernel module: {name}"


def test_extension_sources_never_reference_protected_paths_for_writing() -> None:
    """No extension module may write into a protected kernel location.

    Scan is line-granular: a line that both names a protected path AND contains a
    filesystem-mutation call is a violation. Mentioning ``workspace.yml`` inside a
    user-facing error message is fine; ``root / "03_candidates"`` next to a write
    call is not. kernel_bridge.py additionally gets the stricter whole-file check
    above (it may contain no mutation calls at all).
    """
    for path in _all_extension_sources():
        if path.name == "kernel_bridge.py":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not any(protected in line for protected in PROTECTED_KERNEL_PATHS):
                continue
            for pattern in MUTATION_PATTERNS:
                assert not re.search(pattern, line), (
                    f"{path.name}:{lineno} looks like it writes a protected kernel path: {line.strip()!r}"
                )


def test_sidecar_is_invisible_to_kernel_check(tmp_path: Path) -> None:
    """F-05 acceptance: sidecar present → kernel check unchanged; deleted → still unchanged."""
    gold = REPO_ROOT / "benchmarks" / "cases" / "bm01-timesync" / "gold"
    ws = tmp_path / "ws"
    shutil.copytree(gold, ws)

    def kernel_check() -> str:
        proc = subprocess.run(
            [sys.executable, "-m", "patentkit", "check", "--json"],
            cwd=str(ws), capture_output=True, text=True, encoding="utf-8", timeout=180, check=False,
        )
        assert proc.returncode in (0, 1, 2), f"kernel check failed unexpectedly: {proc.stderr[:500]}"
        # normalize run timestamps so successive runs are comparable
        return re.sub(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)",
            "<TS>",
            proc.stdout,
        )

    baseline = kernel_check()

    # create a sidecar with content that would break a naive workspace scanner
    sidecar = ws / ".patent-intel"
    (sidecar / "index").mkdir(parents=True)
    (sidecar / "audit").mkdir()
    (sidecar / "index" / "stub.json").write_text('{"record_type": "patent_record"}', encoding="utf-8")
    (sidecar / "audit" / "ledger.jsonl").write_text('{"k": "v"}\n', encoding="utf-8")

    with_sidecar = kernel_check()
    assert with_sidecar == baseline, "kernel check output changed while a sidecar existed"

    shutil.rmtree(sidecar)
    after_removal = kernel_check()
    assert after_removal == baseline, "kernel check output changed after sidecar removal"


def test_kernel_cli_help_lists_allowlist_verbs() -> None:
    """Guard against kernel renames: every allowlisted verb must still exist upstream."""
    from patent_intel.kernel_allowlist import READONLY_VERBS

    proc = subprocess.run(
        [sys.executable, "-m", "patentkit", "--help"],
        capture_output=True, text=True, encoding="utf-8", timeout=120, check=False,
    )
    assert proc.returncode == 0
    missing = {verb for verb in READONLY_VERBS if verb not in proc.stdout}
    assert not missing, f"kernel no longer exposes allowlisted verbs: {sorted(missing)}"
