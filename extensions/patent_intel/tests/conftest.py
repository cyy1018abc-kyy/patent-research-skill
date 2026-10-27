"""Shared fixtures for patent_intel tests.

Local Windows note (CJK username environment): run pytest with
``--basetemp=E:/tmp-pk/pytest`` (parent pre-created) so temp dirs never land in the
profile directory — see workspace memory notes.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

EXTENSION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXTENSION_ROOT.parents[1]
GOLD_WORKSPACE = REPO_ROOT / "benchmarks" / "cases" / "bm01-timesync" / "gold"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture()
def gold_workspace(tmp_path: Path) -> Path:
    """A fully valid kernel workspace (the bm01 benchmark gold), copied to tmp."""
    ws = tmp_path / "ws"
    shutil.copytree(GOLD_WORKSPACE, ws)
    return ws


def make_workspace(root: Path) -> Path:
    """Synthesize a minimal-but-valid workspace layout for negative tests.

    Not a *kernel-valid* workspace (no schema compliance) — tests use it to check
    that the bridge reads what exists and reports what does not, without invoking
    kernel commands.
    """
    (root / "00_methodology").mkdir(parents=True)
    (root / "01_search_plan").mkdir()
    (root / "02_search_logs" / "raw").mkdir(parents=True)
    (root / "03_candidates").mkdir()
    (root / "workspace.yml").write_text("version: 1\n", encoding="utf-8")
    (root / "00_methodology" / "glossary.yml").write_text(
        "\n".join(
            [
                "version: 1",
                "updated: '2026-01-01'",
                "active_target: TGT-0001",
                "targets:",
                "  TGT-0001:",
                "    title: '合成测试目标'",
                "    status: active",
                "axes:",
                "  N1@TGT-0001: { title_zh: '轴一', title_en: '', kind: primary }",
                "  N2@TGT-0001: { title_zh: '轴二', title_en: '', kind: primary }",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    log = {
        "db": "espacenet",
        "target": "TGT-0001",
        "actor": "test",
        "capture_mode": "live",
        "timestamp": "2026-02-01T08:00:00+00:00",
        "query": {"id": "N1", "axis": "N1@TGT-0001", "text": "abstract=(测试)"},
        "result": {"hit_count": 2, "raw_export": "raw/N1_page-1.csv", "complete": False},
    }
    (root / "02_search_logs" / "espacenet_2026-02-01_N1_1.log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "02_search_logs" / "raw" / "N1_page-1.csv").write_text(
        "publication_number,title\nZZ900099A1,测试文献\n", encoding="utf-8"
    )
    return root


@pytest.fixture()
def minimal_workspace(tmp_path: Path) -> Path:
    return make_workspace(tmp_path / "ws-min")


@pytest.fixture()
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard against accidental network use: block socket creation in-process.

    (Subprocess-based kernel calls stay allowed — they are local and offline commands
    only; IT-08 checks the offline property at the integration layer.)
    """
    import socket

    def _blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during an offline test")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked)
