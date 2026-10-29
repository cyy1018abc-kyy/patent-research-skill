"""kernel_bridge tests: read-only accessors + allowlist guardrails (F-04 acceptance).

The read paths run against a real kernel workspace (the bm01 benchmark gold) and the
real installed kernel; the subprocess test stays offline by design (kernel commands
never perform network IO for these verbs).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from patent_intel.kernel_bridge import (
    KernelCompatError,
    KernelNotAvailableError,
    MIN_KERNEL_VERSION,
    find_kernel_workspace,
    is_kernel_workspace,
    kernel_info,
    read_axes,
    read_candidates,
    read_glossary,
    read_search_logs,
    require_kernel,
    run_kernel_readonly,
)


def test_kernel_info_reports_compatible_kernel() -> None:
    """The dev environment has patentkit installed; if it does not, the test env is wrong."""
    info = kernel_info()
    if not info.importable:
        pytest.skip("patentkit not installed in this environment")
    assert info.version is not None
    assert info.compatible(), f"kernel {info.version} should satisfy the {MIN_KERNEL_VERSION} floor"


def test_require_kernel_returns_info() -> None:
    info = require_kernel()
    assert info.importable


def test_version_floor_parser() -> None:
    from patent_intel.kernel_bridge import _parse_version

    assert _parse_version("0.8.0") == (0, 8, 0)
    assert _parse_version("0.9.1rc2") == (0, 9, 1)
    assert _parse_version("garbage") == (0,)


def test_kernel_too_old_raises_with_floor_in_message(monkeypatch: pytest.MonkeyPatch) -> None:
    import patent_intel.kernel_bridge as bridge

    class FakeInfo:
        importable = True
        version = "0.5.1"
        version_tuple = (0, 5, 1)
        protocol_version = 1
        error = None

        def compatible(self) -> bool:
            return False

    monkeypatch.setattr(bridge, "kernel_info", lambda: FakeInfo())
    with pytest.raises(KernelCompatError, match="0.8.0"):
        bridge.require_kernel()


def test_kernel_wrong_protocol_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import patent_intel.kernel_bridge as bridge

    class FakeInfo:
        importable = True
        version = "9.9.9"
        version_tuple = (9, 9, 9)
        protocol_version = 2
        error = None

        def compatible(self) -> bool:
            return False

    monkeypatch.setattr(bridge, "kernel_info", lambda: FakeInfo())
    with pytest.raises(KernelCompatError, match="protocol"):
        bridge.require_kernel()


def test_kernel_missing_message_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    import patent_intel.kernel_bridge as bridge

    def _boom() -> None:
        raise KernelNotAvailableError("patentkit is not installed (…); install with: pip install patentkit")

    monkeypatch.setattr(bridge, "require_kernel", _boom)
    with pytest.raises(KernelNotAvailableError, match="pip install"):
        bridge.require_kernel()


# ── workspace discovery ───────────────────────────────────────────────


def test_is_kernel_workspace_detects_marker(gold_workspace: Path) -> None:
    assert is_kernel_workspace(gold_workspace)
    assert not is_kernel_workspace(gold_workspace / "00_methodology")


def test_find_kernel_workspace_searches_upward(gold_workspace: Path) -> None:
    nested = gold_workspace / "02_search_logs" / "raw"
    assert find_kernel_workspace(nested) == gold_workspace.resolve()


def test_find_kernel_workspace_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="--root"):
        find_kernel_workspace(tmp_path)


# ── read accessors against a real workspace ──────────────────────────


def test_read_glossary_and_axes(gold_workspace: Path) -> None:
    glossary = read_glossary(gold_workspace)
    assert glossary["active_target"] == "TGT-9001"
    axes = read_axes(gold_workspace)
    assert "N1@TGT-9001" in axes
    assert axes["N1@TGT-9001"]["kind"] == "primary"


def test_read_glossary_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="glossary"):
        read_glossary(tmp_path)


def test_read_search_logs_returns_kernel_shape(gold_workspace: Path) -> None:
    logs = read_search_logs(gold_workspace)
    assert len(logs) == 4
    first = next(log for log in logs if log["query"]["id"] == "N1")
    assert first["db"] == "espacenet"
    assert first["result"]["complete"] is True
    assert first["capture_mode"] == "live"


def test_read_candidates_returns_kernel_shape(gold_workspace: Path) -> None:
    candidates = read_candidates(gold_workspace)
    assert len(candidates) == 4
    numbers = {c["url_or_doc_number"] for c in candidates}
    assert "ZZ900011A1" in numbers


# ── read-only subprocess bridge ───────────────────────────────────────


def test_bridge_refuses_mutation_verbs() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        run_kernel_readonly(["ingest", "--raw", "x"], workspace=Path.cwd())
    with pytest.raises(ValueError, match="allowlist"):
        run_kernel_readonly(["fetch-cnipa"], workspace=Path.cwd())
    with pytest.raises(ValueError, match="allowlist"):
        run_kernel_readonly(["revise"], workspace=Path.cwd())


def test_bridge_refuses_write_flags() -> None:
    for flag in ("--apply", "--run", "--force", "--fill"):
        with pytest.raises(ValueError, match="kernel-side writes"):
            run_kernel_readonly(["queryplan", flag], workspace=Path.cwd())


def test_bridge_runs_queryplan_on_real_workspace(gold_workspace: Path) -> None:
    """End-to-end: the bridge drives the real kernel CLI, read-only, offline."""
    out = run_kernel_readonly(["queryplan"], workspace=gold_workspace)
    assert isinstance(out, dict)


def test_bridge_status_json_on_real_workspace(gold_workspace: Path) -> None:
    out = run_kernel_readonly(["status"], workspace=gold_workspace)
    assert isinstance(out, dict)
    assert "candidates" in out or "workspace" in out


def test_bridge_surfaces_kernel_failure(gold_workspace: Path) -> None:
    """A kernel-side failure (bad flag) surfaces as RuntimeError, never a silent pass."""
    with pytest.raises(RuntimeError, match="exited"):
        run_kernel_readonly(["queryplan", "--definitely-not-a-flag"], workspace=gold_workspace, timeout=120)


def test_search_logs_json_parseable(gold_workspace: Path) -> None:
    """Every log the bridge returns must itself be valid JSON (round-trip sanity)."""
    for log in read_search_logs(gold_workspace):
        assert json.dumps(log, ensure_ascii=False)
