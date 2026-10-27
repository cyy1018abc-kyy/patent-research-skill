"""Sidecar configuration for patent_intel (blueprint F-03).

Ownership rules (docs/adr/0002-state-dir.md):

* the state dir is the *only* place patent_intel writes; it defaults to
  ``<workspace>/.patent-intel`` and can be moved with ``--state-dir`` or
  ``PATENT_INTEL_STATE_DIR``;
* everything inside is a rebuildable cache/index — deleting it must leave kernel
  validation results unchanged (tested in tests/test_workspace.py);
* network access is denied by default. Live acquisition needs both a config flag and a
  per-command ``--confirm-network`` (interface rule 1).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from patent_intel.contracts import ContractError, RecordValidationError

__all__ = ["STATE_DIR_NAME", "ENV_STATE_DIR", "PatentIntelConfig", "resolve_state_dir", "load_config"]

STATE_DIR_NAME = ".patent-intel"
ENV_STATE_DIR = "PATENT_INTEL_STATE_DIR"

#: Hard ceiling on config size — the config file is ours, but a corrupted/huge file must
#: fail loudly rather than be trusted (supply-chain rule 9).
_MAX_CONFIG_BYTES = 1_000_000


class ConfigError(ContractError):
    """The config file exists but cannot be parsed or violates the schema."""


@dataclass
class Budgets:
    """Acquisition budgets (blueprint §5: requests, money, tokens, time)."""

    max_requests: int = 200
    max_cost_usd: float = 5.0
    max_tokens: int = 0  # 0 = not tracked (offline commands never consume tokens)
    max_minutes: int = 30

    def __post_init__(self) -> None:
        if self.max_requests < 0 or self.max_tokens < 0 or self.max_minutes < 0:
            raise RecordValidationError("budgets must be non-negative")
        if self.max_cost_usd < 0:
            raise RecordValidationError("budgets must be non-negative")


@dataclass
class PatentIntelConfig:
    """Resolved configuration. Construct with :func:`load_config` for file support."""

    schema_version: int = 1
    owner: str = "WP-0"
    #: Explicit network consent. Stored *only* in the config file written by the user —
    #: never flipped implicitly by a command (interface rule 1).
    network_consent: bool = False
    #: Sources allowed for live acquisition; empty means none even with consent.
    allowed_sources: list[str] = field(default_factory=list)
    budgets: Budgets = field(default_factory=Budgets)
    #: Deterministic ranking parameters (UT-R01: fixed sample + fixed parameters = fixed result).
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    rrf_k: int = 60
    seed: int = 20261028
    #: Accept lower schema majors? Reserved for future migrations; today exact match only.
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["budgets"] = asdict(self.budgets)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatentIntelConfig":
        if not isinstance(data, dict):
            raise ConfigError("config must be a JSON object")
        version = data.get("schema_version", 1)
        if version != 1:
            raise ConfigError(f"config schema_version {version} not supported (understand 1)")
        known = {k: v for k, v in data.items() if k not in ("schema_version", "owner", "budgets")}
        config = cls(**known)
        if "budgets" in data:
            budgets = data["budgets"]
            if not isinstance(budgets, dict):
                raise ConfigError("'budgets' must be an object")
            config.budgets = Budgets(**{k: v for k, v in budgets.items() if k in Budgets.__dataclass_fields__})
        return config


def resolve_state_dir(workspace: Path | None, explicit: str | Path | None = None) -> Path:
    """Resolve the sidecar state dir: explicit arg → env var → ``<workspace>/.patent-intel``.

    A wrong explicit value is reported, never silently swapped for the default —
    same discipline as the kernel's ``--root`` handling.
    """
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get(ENV_STATE_DIR)
    if env:
        return Path(env).expanduser().resolve()
    if workspace is not None:
        return (Path(workspace) / STATE_DIR_NAME).resolve()
    raise ConfigError(
        "no state dir resolvable: pass --state-dir, set "
        f"{ENV_STATE_DIR}, or provide a workspace root"
    )


def load_config(
    state_dir: Path,
    *,
    overrides: dict[str, Any] | None = None,
) -> PatentIntelConfig:
    """Load ``config.json`` from the state dir if present, apply CLI overrides, return config.

    Missing file → pure defaults (the sidecar may not exist yet). Corrupt file →
    :class:`ConfigError` — never silently ignore a config the user wrote.
    """
    path = Path(state_dir) / "config.json"
    config = PatentIntelConfig()
    if path.is_file():
        size = path.stat().st_size
        if size > _MAX_CONFIG_BYTES:
            raise ConfigError(f"config file is {size} bytes (limit {_MAX_CONFIG_BYTES})")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ConfigError(f"config file {path} is not valid UTF-8 JSON: {exc}") from None
        config = PatentIntelConfig.from_dict(data)
    if overrides:
        allowed = {k: v for k, v in overrides.items() if v is not None and k in PatentIntelConfig.__dataclass_fields__}
        for key, value in allowed.items():
            setattr(config, key, value)
        if overrides.get("budgets") is not None:
            config.budgets = Budgets(**overrides["budgets"])
    return config
