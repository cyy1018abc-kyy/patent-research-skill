"""Config loading and state-dir resolution tests (blueprint F-03)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from patent_intel.config import (
    ConfigError,
    ENV_STATE_DIR,
    PatentIntelConfig,
    load_config,
    resolve_state_dir,
)
from patent_intel.workspace import SidecarLayout


# ── resolve_state_dir precedence ─────────────────────────────────────


def test_explicit_arg_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_STATE_DIR, str(tmp_path / "from-env"))
    got = resolve_state_dir(tmp_path / "ws", explicit=tmp_path / "from-arg")
    assert got == (tmp_path / "from-arg").resolve()


def test_env_beats_workspace_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_STATE_DIR, str(tmp_path / "from-env"))
    got = resolve_state_dir(tmp_path / "ws")
    assert got == (tmp_path / "from-env").resolve()


def test_workspace_default_uses_sidecar_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_STATE_DIR, raising=False)
    got = resolve_state_dir(tmp_path / "ws")
    assert got == (tmp_path / "ws" / ".patent-intel").resolve()


def test_no_inputs_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_STATE_DIR, raising=False)
    with pytest.raises(ConfigError, match="state dir"):
        resolve_state_dir(None)


# ── load_config ──────────────────────────────────────────────────────


def test_missing_config_file_yields_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config.network_consent is False  # offline by default
    assert config.allowed_sources == []
    assert config.budgets.max_requests > 0


def test_config_file_roundtrip(tmp_path: Path) -> None:
    config = PatentIntelConfig(network_consent=True, allowed_sources=["ops"])
    (tmp_path / "config.json").write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    loaded = load_config(tmp_path)
    assert loaded.network_consent is True
    assert loaded.allowed_sources == ["ops"]
    assert loaded.budgets.max_requests == config.budgets.max_requests


def test_corrupt_config_fails_loudly(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid UTF-8 JSON"):
        load_config(tmp_path)


def test_unsupported_config_schema_rejected(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(ConfigError, match="schema_version"):
        load_config(tmp_path)


def test_cli_overrides_apply(tmp_path: Path) -> None:
    config = load_config(tmp_path, overrides={"seed": 42})
    assert config.seed == 42


def test_negative_budget_rejected() -> None:
    from patent_intel.config import Budgets

    with pytest.raises(Exception, match="non-negative"):
        Budgets(max_requests=-5)


# ── sidecar layout + binding ─────────────────────────────────────────


def test_layout_creates_tree_and_binds_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    layout = SidecarLayout(tmp_path / "sidecar")
    assert not layout.exists()
    layout.ensure(workspace=ws)
    assert layout.exists()
    for name in ("features", "queries", "runs", "index", "anchors", "evidence", "advisory", "reports", "audit", "tmp"):
        assert (tmp_path / "sidecar" / name).is_dir()
    layout.check_binding(ws)  # same workspace: fine


def test_layout_refuses_foreign_workspace(tmp_path: Path) -> None:
    ws_a = tmp_path / "ws-a"
    ws_b = tmp_path / "ws-b"
    ws_a.mkdir()
    ws_b.mkdir()
    layout = SidecarLayout(tmp_path / "sidecar")
    layout.ensure(workspace=ws_a)
    with pytest.raises(Exception, match="bound to workspace"):
        layout.check_binding(ws_b)


def test_unknown_subdirectory_refused(tmp_path: Path) -> None:
    layout = SidecarLayout(tmp_path)
    with pytest.raises(Exception, match="unknown sidecar subdirectory"):
        layout.dir("kernel_workspace")


def test_purge_scratch_only_touches_tmp(tmp_path: Path) -> None:
    layout = SidecarLayout(tmp_path / "sidecar")
    layout.ensure(workspace=tmp_path)
    (layout.tmp / "scratch.txt").write_text("x", encoding="utf-8")
    (layout.features / "keep.json").write_text("{}", encoding="utf-8")
    assert layout.purge_scratch() == 1
    assert not (layout.tmp / "scratch.txt").exists()
    assert (layout.features / "keep.json").exists()
