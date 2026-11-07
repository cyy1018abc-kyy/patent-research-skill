"""Source availability diagnostics backend (blueprint 41D-2).

A read-only, deterministic backend for a future ``doctor sources`` command (the CLI
wiring is a separate INT work package — this module never touches ``cli.py``). For
every registered source adapter it reports, in one pass:

* **config gates** — ``network_consent`` and per-source allowlist membership of the
  caller-supplied config object (the read-only mirror of the double gate in
  ``SourceAdapter.ensure_live_allowed``);
* **credential existence** — whether the environment variables a source needs are
  set (names only; values are never loaded into the report);
* **reachability** — *only* when explicitly opted in (``probe=True``) *and* the
  caller supplies a transport callable. Any HTTP answer counts as "reachable";
  reachability never implies authorization or quota.

Discipline:

* the default path is fully offline: no socket, no subprocess, no file IO;
* missing credentials are a ``skip`` verdict, never an exception — diagnostics
  reports, it does not fail (same spirit as the ``doctor`` command);
* a ``planned`` (design-only) adapter is never diagnosed as executable;
* probing a source whose config/credential gates are closed is refused work — the
  probe loop only touches sources whose gates are open (status ``ready``);
* the report carries no timestamps, paths or environment-dependent ordering, so
  the same inputs serialize to identical bytes (acceptance gate: determinism).

Status vocabulary (exactly one verdict per source):

| status  | meaning                                                       |
|---------|---------------------------------------------------------------|
| ready   | gates open; executable once ``--confirm-network`` is added     |
| blocked | credentials fine, but the config gate is closed                |
| skip    | credentials missing — not diagnosable further, not an error    |
| planned | design-only adapter (``support_level=planned``)                |
| unknown | credentials declared but no offline check known (honesty)      |

Gate order is fixed: ``planned`` → credentials → config consent → ``ready`` — a
closed earlier gate makes later ones moot, and closed-gate sources are never probed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from patent_intel.sources.base import SourceAdapter
from patent_intel.sources.registry import get_source, registry

__all__ = [
    "CREDENTIAL_ENV_VARS",
    "PROBE_TARGETS",
    "STATUSES",
    "DiagnosticsError",
    "SourceDiagnostic",
    "DiagnosticsReport",
    "diagnose_sources",
]

#: transport callable: ``(method, url, headers, timeout) -> ResponseLike`` — same
#: shape as the OPS adapter's injected transport, so one fake can serve both.
Transport = Callable[..., Any]

#: Environment variables each credential-bearing source reads. Names only — the
#: *values* are never read into a report. Keep aligned with the adapters; a
#: credential-bearing source without an entry here is reported ``unknown``
#: (honest) rather than guessed at.
CREDENTIAL_ENV_VARS: dict[str, tuple[str, ...]] = {
    # OpsAdapter._credentials reads exactly these two variables (sources/ops.py).
    "ops": ("OPS_OAUTH_KEY", "OPS_OAUTH_SECRET"),
}

#: Opt-in probe targets: ``(verb, url)`` per source. Any HTTP answer (401/403
#: included) proves reachability only — never authorization or quota. Probe
#: requests carry no credential material (empty headers). A source without an
#: entry is kernel-mediated (acquisition flows through kernel fetch commands, not
#: a direct HTTP endpoint of this package) and is therefore never probed.
#: ops.py owns the authoritative endpoint constants; this target mirrors its
#: search URL.
PROBE_TARGETS: dict[str, tuple[str, str]] = {
    "ops": ("GET", "https://ops.epo.org/3.2/published-data/search?q=patent_intel-probe"),
}

#: Fixed status vocabulary — also the deterministic key order of
#: ``DiagnosticsReport.status_counts``.
STATUSES: tuple[str, ...] = ("ready", "blocked", "skip", "planned", "unknown")


class DiagnosticsError(ValueError):
    """Diagnostics was asked to do something it refuses (e.g. probe without an
    explicit transport — an implicitly constructed network transport is exactly
    the hidden-networking failure mode this backend exists to prevent)."""


@dataclass(frozen=True)
class SourceDiagnostic:
    """One source's availability verdict (module docstring lists the vocabulary).

    ``reachable``/``probe_http_status`` are ``None`` unless the source was actually
    probed (opt-in with open gates and a probe target); a probe result never
    changes ``status`` — the gates and the wire are reported independently.
    """

    source: str
    support_level: str
    requires_credentials: bool
    #: "not_required" | "present" | "missing" | "unknown"
    credential_status: str
    credential_env_vars: tuple[str, ...]
    network_consent: bool
    in_allowed_sources: bool
    status: str  # one of STATUSES
    reachable: bool | None
    probe_http_status: int | None
    notes: tuple[str, ...]

    def describe(self) -> dict[str, Any]:
        """JSON-safe mirror (str/bool/int/None/list only) — deterministic output."""
        return {
            "source": self.source,
            "support_level": self.support_level,
            "requires_credentials": self.requires_credentials,
            "credential_status": self.credential_status,
            "credential_env_vars": list(self.credential_env_vars),
            "network_consent": self.network_consent,
            "in_allowed_sources": self.in_allowed_sources,
            "status": self.status,
            "reachable": self.reachable,
            "probe_http_status": self.probe_http_status,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class DiagnosticsReport:
    """Whole-registry verdict. No timestamps, no paths, no randomness."""

    config_provided: bool
    probe_requested: bool
    #: True only when at least one probe call was actually issued (offline default: False)
    network_touched: bool
    probed: tuple[str, ...]
    status_counts: dict[str, int]
    sources: tuple[SourceDiagnostic, ...]

    def describe(self) -> dict[str, Any]:
        """JSON-safe mirror with fixed key order (byte-stable under json.dumps)."""
        return {
            "config_provided": self.config_provided,
            "probe_requested": self.probe_requested,
            "network_touched": self.network_touched,
            "probed": list(self.probed),
            "status_counts": dict(self.status_counts),
            "sources": [entry.describe() for entry in self.sources],
        }


def diagnose_sources(
    config: Any | None = None,
    *,
    only: list[str] | None = None,
    probe: bool = False,
    transport: Transport | None = None,
    timeout_sec: int = 10,
) -> DiagnosticsReport:
    """Diagnose every registered source (or ``only`` these ids), offline by default.

    ``config`` is a loaded :class:`patent_intel.config.PatentIntelConfig` (or any
    object exposing ``network_consent`` / ``allowed_sources``); ``None`` evaluates
    both gates as closed (factory defaults deny network). ``probe=True`` is the
    explicit opt-in for reachability checks and *requires* ``transport`` — asking
    to probe without one raises :class:`DiagnosticsError` instead of building a
    network transport implicitly. Only ``ready`` sources with a probe target are
    probed; everything else stays untouched.

    The future ``doctor sources`` CLI is expected to wire this as
    ``diagnose_sources(load_config(resolve_state_dir(root, state_dir)), only=...)``.
    """
    if only is None:
        adapters = [get_source(source_id) for source_id in registry.ids()]
    else:
        unknown = [source_id for source_id in only if source_id not in registry]
        if unknown:
            raise KeyError(f"unknown source {unknown[0]!r}; available: {registry.ids()}")
        adapters = [get_source(source_id) for source_id in only]
    return _diagnose_adapters(
        adapters,
        config=config,
        probe=probe,
        transport=transport,
        timeout_sec=timeout_sec,
    )


def _diagnose_adapters(
    adapters: list[SourceAdapter],
    *,
    config: Any | None,
    probe: bool,
    transport: Transport | None,
    timeout_sec: int,
) -> DiagnosticsReport:
    """Core pass over explicit adapters — lets tests classify synthetic adapters
    (planned / unknown-credential sources) without polluting the global registry."""
    probe_transport: Transport | None = transport if probe else None
    if probe and probe_transport is None:
        raise DiagnosticsError(
            "probe=True requires an explicit transport callable; refusing to build a "
            "network transport implicitly (the default diagnostics path is offline)"
        )

    config_provided = config is not None
    consent = bool(getattr(config, "network_consent", False)) if config_provided else False
    allowed_raw = getattr(config, "allowed_sources", None) if config_provided else None
    # a malformed config object degrades to "nothing allowed" — diagnostics reports,
    # it never crashes on shapes it does not understand
    allowed = set(allowed_raw) if isinstance(allowed_raw, (list, tuple, set, frozenset)) else set()

    entries: list[SourceDiagnostic] = []
    probed: list[str] = []
    network_touched = False

    for adapter in adapters:
        cap = adapter.capabilities()
        cred_status, cred_vars = _credential_status(adapter)
        notes: list[str] = []
        if cap.notes:
            notes.append(cap.notes)

        # gate order: planned → credentials → config consent → ready
        if cap.support_level == "planned":
            status = "planned"
            notes.append("design-only adapter (support_level=planned); never executed")
        elif cred_status == "missing":
            status = "skip"
            notes.append("credentials missing → skipped without error; set " + " / ".join(cred_vars))
        elif cred_status == "unknown":
            status = "unknown"
            notes.append(
                "adapter declares credentials but no offline credential check is known "
                "for this source; refusing to guess (honest unknown)"
            )
        elif not consent or adapter.id not in allowed:
            status = "blocked"
            if not consent:
                notes.append("config.network_consent is false — live acquisition is double-gated off")
            if adapter.id not in allowed:
                notes.append("source not listed in config.allowed_sources")
        else:
            status = "ready"

        reachable: bool | None = None
        http_status: int | None = None
        if probe_transport is not None and status == "ready":
            target = PROBE_TARGETS.get(adapter.id)
            if target is None:
                notes.append("no direct HTTP probe target (kernel-mediated acquisition); not probed")
            else:
                verb, url = target
                probed.append(adapter.id)
                network_touched = True
                try:
                    resp = probe_transport(verb, url, {}, timeout_sec)
                except Exception as exc:  # noqa: BLE001 - transport layer
                    reachable = False
                    notes.append(f"probe failed: {type(exc).__name__}")
                else:
                    reachable = True
                    raw_status = getattr(resp, "status_code", None)
                    if isinstance(raw_status, int) and not isinstance(raw_status, bool):
                        http_status = raw_status
                    shown = f"HTTP {http_status}" if http_status is not None else "no HTTP status in response"
                    notes.append(
                        f"probe reached the endpoint ({shown}); reachability only, "
                        "not authorization/quota"
                    )

        entries.append(
            SourceDiagnostic(
                source=adapter.id,
                support_level=cap.support_level,
                requires_credentials=cap.requires_credentials,
                credential_status=cred_status,
                credential_env_vars=cred_vars,
                network_consent=consent,
                in_allowed_sources=adapter.id in allowed,
                status=status,
                reachable=reachable,
                probe_http_status=http_status,
                notes=tuple(notes),
            )
        )

    counts = {name: 0 for name in STATUSES}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1
    return DiagnosticsReport(
        config_provided=config_provided,
        probe_requested=probe,
        network_touched=network_touched,
        probed=tuple(probed),
        status_counts=counts,
        sources=tuple(entries),
    )


def _credential_status(adapter: SourceAdapter) -> tuple[str, tuple[str, ...]]:
    """Offline credential-existence verdict. Reads env var *names*; never values."""
    cap = adapter.capabilities()
    if not cap.requires_credentials:
        return "not_required", ()
    var_names = CREDENTIAL_ENV_VARS.get(adapter.id, ())
    if not var_names:
        return "unknown", ()
    missing = [name for name in var_names if not (os.environ.get(name) or "").strip()]
    if missing:
        return "missing", var_names
    return "present", var_names
