"""A-07: research/scripts/recall.py — thin wrapper integration (blueprint O-02 adjacent).

The wrapper must forward to the extension CLI when present and degrade with
exit 3 + install hints when the extension is missing (the plain research workflow
never breaks).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RECALL = REPO_ROOT / "research" / "scripts" / "recall.py"
GOLD = REPO_ROOT / "benchmarks" / "cases" / "bm01-timesync" / "gold"


def _run(ws: Path, *args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = None
    if env_extra:
        import os

        env = {**os.environ, **env_extra}
    return subprocess.run(
        [sys.executable, str(RECALL), *args],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(REPO_ROOT), timeout=180, check=False, env=env,
    )


def test_recall_plan_forwards_to_extension(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    shutil.copytree(GOLD, ws)
    proc = _run(ws, "plan", "--root", str(ws), "--axis", "N1")
    assert proc.returncode == 0, proc.stderr
    assert "Q-N1-SF-001" in proc.stdout
    assert "proposals only" in proc.stdout


def test_recall_report_writes_sidecar_only(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    shutil.copytree(GOLD, ws)
    proc = _run(ws, "report", "--root", str(ws), "--json")
    assert proc.returncode == 0, proc.stderr
    payload = __import__("json").loads(proc.stdout)
    assert payload["ok"] is True
    report = payload["report"]
    assert report["mode"].startswith("offline")
    assert "corpus_size" in report
    # kernel workspace files untouched; sidecar report created
    assert (ws / ".patent-intel" / "reports").is_dir()


def test_recall_wrapper_degrades_without_extension(tmp_path: Path) -> None:
    """Missing extension → exit 3 with actionable install hints (not a traceback)."""
    blocker = tmp_path / "blocker"
    blocker.mkdir()
    (blocker / "patent_intel.py").write_text(
        "raise ImportError('simulated missing extension')\n", encoding="utf-8"
    )
    ws = tmp_path / "ws"
    shutil.copytree(GOLD, ws)
    proc = _run(
        ws, "report", "--root", str(ws),
        env_extra={"PYTHONPATH": str(blocker)},
    )
    assert proc.returncode == 3
    assert "not installed" in proc.stderr
    assert "patent_intel" in proc.stderr
    assert "Traceback" not in proc.stderr
