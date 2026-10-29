"""CLI tests: --help/--version, doctor exit codes, JSON contract (F-02 acceptance)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from patent_intel.cli import main

PYTHON = sys.executable


def _run_module(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "patent_intel", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(cwd) if cwd else None,
        timeout=120,
        check=False,
    )


def test_help_works() -> None:
    proc = _run_module("--help")
    assert proc.returncode == 0
    assert "doctor" in proc.stdout
    assert "patentkit" in proc.stdout  # boundary statement visible in help


def test_version_flag() -> None:
    from patent_intel import __version__

    proc = _run_module("--version")
    assert proc.returncode == 0
    assert __version__ in proc.stdout


def test_doctor_no_workspace_ok(tmp_path: Path) -> None:
    proc = _run_module("doctor", cwd=tmp_path)
    assert proc.returncode == 0
    assert not proc.stdout.strip().startswith("{")  # text mode: no JSON on stdout


def test_doctor_with_fixture_workspace(gold_workspace: Path) -> None:
    proc = _run_module("doctor", "--root", str(gold_workspace), "--json")
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    assert report["ok"] is True
    assert report["checks"]["workspace"]["found"] is True
    assert report["checks"]["kernel"]["importable"] is True
    assert report["checks"]["network"]["default"] == "offline"


def test_doctor_json_is_single_document(gold_workspace: Path) -> None:
    """--json stdout must be exactly one JSON document (kernel _env.py contract)."""
    proc = _run_module("doctor", "--root", str(gold_workspace), "--json")
    json.loads(proc.stdout)  # raises on trailing garbage / double documents


def test_doctor_bad_root_exit_2(tmp_path: Path) -> None:
    proc = _run_module("doctor", "--root", str(tmp_path / "missing"), "--json")
    assert proc.returncode == 2
    report = json.loads(proc.stdout)
    assert report["ok"] is False


def test_doctor_non_workspace_root_exit_2(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = _run_module("doctor", "--root", str(empty), "--json")
    assert proc.returncode == 2
    report = json.loads(proc.stdout)
    assert "not a patentkit workspace" in report["checks"]["workspace"]["error"]


def test_doctor_inprocess_exit_codes(gold_workspace: Path, tmp_path: Path) -> None:
    assert main(["doctor", "--root", str(gold_workspace), "--json"]) == 0
    assert main(["doctor", "--root", str(tmp_path / "nope")]) == 2


def test_doctor_text_mode_mentions_offline(gold_workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor", "--root", str(gold_workspace)]) == 0
    out = capsys.readouterr().out
    assert "offline" in out
    assert "patentkit" in out


def test_no_subcommand_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "doctor" in capsys.readouterr().out
