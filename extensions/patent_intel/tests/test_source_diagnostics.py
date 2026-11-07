"""Source diagnostics tests (blueprint 41D-2).

Acceptance gates exercised here:

* missing credentials → ``skip`` verdict, never an exception;
* the injected transport is *asserted* not called on the default path — and not
  called even with ``probe=True`` whenever no source has open gates;
* the default path makes zero network calls — enforced twice: the module-wide
  socket guard (shared ``no_network`` fixture) and the recording-transport
  assertion;
* same inputs → byte-identical ``describe()`` output (determinism: no timestamps,
  no paths).

Probing is exercised exclusively against fake transports; no test in this module
(or the backend's default path) ever touches the network.
"""

from __future__ import annotations

import json

import pytest

from patent_intel.config import PatentIntelConfig
from patent_intel.contracts import QuerySpec
from patent_intel.sources.base import Capability, RequestPlan, SourceAdapter
from patent_intel.sources.diagnostics import (
    CREDENTIAL_ENV_VARS,
    STATUSES,
    DiagnosticsError,
    _diagnose_adapters,
    diagnose_sources,
)
from patent_intel.sources.ops import OpsAdapter
from patent_intel.sources.registry import get_source, registry


@pytest.fixture(autouse=True)
def _offline_enforced(no_network: None) -> None:
    """Every test in this module runs with socket creation refused (41D-2)."""


# ── doubles & helpers ─────────────────────────────────────────────────


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def recording_transport(status_code: int = 401):
    """Transport double: records every call, returns a canned status. Never network."""
    calls: list[dict[str, object]] = []

    def transport(method: str, url: str, headers: dict, timeout: int) -> _Resp:
        calls.append({"method": method, "url": url, "headers": dict(headers), "timeout": timeout})
        return _Resp(status_code)

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def _consenting_config(*source_ids: str) -> PatentIntelConfig:
    return PatentIntelConfig(network_consent=True, allowed_sources=list(source_ids))


def _without_ops_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPS_OAUTH_KEY", raising=False)
    monkeypatch.delenv("OPS_OAUTH_SECRET", raising=False)


def _with_ops_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_OAUTH_KEY", "test-key")
    monkeypatch.setenv("OPS_OAUTH_SECRET", "test-secret")


def _entry(report, source_id: str):
    return {entry.source: entry for entry in report.sources}[source_id]


class _StaticAdapter(SourceAdapter):
    """Capability-only adapter shell; execution paths never run in diagnostics."""

    def __init__(self, source_id: str, cap: Capability) -> None:
        self.id = source_id
        self._cap = cap

    def capabilities(self) -> Capability:
        return self._cap

    def build_request(self, query: QuerySpec) -> RequestPlan:  # pragma: no cover
        raise NotImplementedError

    def dry_run(self, plan: RequestPlan, workspace: object) -> object:  # pragma: no cover
        raise NotImplementedError

    def execute(  # pragma: no cover - never executed
        self, plan: RequestPlan, workspace: object, *, confirm_network: bool, config: object
    ) -> object:
        raise NotImplementedError


def _capability(source_id: str, support_level: str, requires_credentials: bool) -> Capability:
    return Capability(
        source=source_id,
        query_fields=frozenset({"keywords"}),
        languages=frozenset({"en"}),
        max_results_per_query=0,
        pagination=False,
        license_status="official_api",
        cost="free",
        return_format="json",
        support_level=support_level,
        requires_credentials=requires_credentials,
        notes="synthetic adapter for diagnostics classification tests",
    )


# ── default path: fully offline, transport untouched ─────────────────


def test_default_path_zero_network_and_transport_never_called(monkeypatch) -> None:
    _without_ops_credentials(monkeypatch)
    transport = recording_transport()
    config = _consenting_config("cnipa", "crossref", "ops")

    report = diagnose_sources(config, transport=transport)

    assert transport.calls == []  # transport injected but never invoked
    assert report.probe_requested is False
    assert report.network_touched is False
    assert report.probed == ()
    assert report.config_provided is True
    entries = {entry.source: entry for entry in report.sources}
    # gate order visible in one default pass: consent given → cnipa/crossref ready,
    # ops still skips on missing credentials (skip, not blocked, not an error)
    assert entries["cnipa"].status == "ready"
    assert entries["crossref"].status == "ready"
    assert entries["ops"].status == "skip"
    assert all(entry.reachable is None for entry in report.sources)


def test_missing_credentials_skip_not_error(monkeypatch) -> None:
    _without_ops_credentials(monkeypatch)

    report = diagnose_sources()  # no config, no credentials — must not raise

    entry = _entry(report, "ops")
    assert entry.status == "skip"
    assert entry.credential_status == "missing"
    assert entry.credential_env_vars == ("OPS_OAUTH_KEY", "OPS_OAUTH_SECRET")
    assert report.status_counts["skip"] == 1
    # no config provided → consent gate closed for the credential-free sources
    cnipa = _entry(report, "cnipa")
    assert cnipa.credential_status == "not_required"
    assert cnipa.status == "blocked"
    assert cnipa.network_consent is False
    assert report.config_provided is False


# ── opt-in probe: explicit transport required, gates respected ────────


def test_probe_opt_in_without_explicit_transport_refused(monkeypatch) -> None:
    _without_ops_credentials(monkeypatch)

    with pytest.raises(DiagnosticsError, match="explicit transport"):
        diagnose_sources(probe=True)


def test_probe_skip_and_kernel_mediated_never_calls_transport(monkeypatch) -> None:
    _without_ops_credentials(monkeypatch)
    transport = recording_transport()
    config = _consenting_config("cnipa", "crossref", "ops")

    report = diagnose_sources(config, probe=True, transport=transport)

    # ops skips (credentials), cnipa/crossref are ready but kernel-mediated
    assert transport.calls == []
    assert report.network_touched is False
    assert report.probed == ()
    assert _entry(report, "ops").status == "skip"
    for source_id in ("cnipa", "crossref"):
        entry = _entry(report, source_id)
        assert entry.status == "ready"
        assert entry.reachable is None
        assert any("kernel-mediated" in note for note in entry.notes)


def test_probe_blocked_consent_never_calls_transport(monkeypatch) -> None:
    _with_ops_credentials(monkeypatch)
    transport = recording_transport()

    report = diagnose_sources(None, probe=True, transport=transport)

    # consent gate closed everywhere → probing is refused work even on opt-in
    assert transport.calls == []
    assert report.network_touched is False
    assert report.probed == ()
    assert all(entry.status == "blocked" for entry in report.sources)


def test_probe_happy_path_only_ready_source_and_no_credential_material(monkeypatch) -> None:
    _with_ops_credentials(monkeypatch)
    transport = recording_transport(status_code=401)
    config = _consenting_config("cnipa", "crossref", "ops")

    report = diagnose_sources(config, probe=True, transport=transport, timeout_sec=7)

    assert report.network_touched is True
    assert report.probed == ("ops",)
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"].startswith("https://ops.epo.org/")
    assert call["headers"] == {}  # probe requests never carry credential material
    assert call["timeout"] == 7
    assert "test-key" not in call["url"]
    assert "test-secret" not in json.dumps(call, default=str)

    ops_entry = _entry(report, "ops")
    assert ops_entry.status == "ready"  # probe does not change the gate verdict
    assert ops_entry.reachable is True  # any HTTP answer counts — 401 included
    assert ops_entry.probe_http_status == 401
    # credential values never surface anywhere in the report
    blob = json.dumps(report.describe(), ensure_ascii=False)
    assert "test-key" not in blob
    assert "test-secret" not in blob


def test_probe_transport_failure_is_a_result_not_an_error(monkeypatch) -> None:
    _with_ops_credentials(monkeypatch)
    calls: list[str] = []

    def broken_transport(method: str, url: str, headers: dict, timeout: int) -> object:
        calls.append(url)
        raise TimeoutError("network unreachable")

    config = _consenting_config("ops")

    report = diagnose_sources(config, probe=True, transport=broken_transport)

    assert calls == ["https://ops.epo.org/3.2/published-data/search?q=patent_intel-probe"]
    entry = _entry(report, "ops")
    assert entry.reachable is False
    assert entry.status == "ready"
    assert any("TimeoutError" in note for note in entry.notes)
    assert report.network_touched is True


# ── classification honesty: planned / unknown credential sources ──────


def test_planned_adapter_is_never_ready_and_never_probed(monkeypatch) -> None:
    _without_ops_credentials(monkeypatch)
    transport = recording_transport()
    planned = _StaticAdapter("future-source", _capability("future-source", "planned", True))
    config = _consenting_config("future-source")

    report = _diagnose_adapters(
        [planned], config=config, probe=True, transport=transport, timeout_sec=5
    )

    entry = report.sources[0]
    assert entry.status == "planned"
    assert entry.credential_status == "unknown"  # declared, but moot: planned wins
    assert transport.calls == []
    assert report.probed == ()
    assert report.status_counts["planned"] == 1


def test_declared_credentials_without_known_check_is_honest_unknown(monkeypatch) -> None:
    _without_ops_credentials(monkeypatch)
    transport = recording_transport()
    ghost = _StaticAdapter("ghost-source", _capability("ghost-source", "partial", True))
    config = _consenting_config("ghost-source")

    report = _diagnose_adapters(
        [ghost], config=config, probe=True, transport=transport, timeout_sec=5
    )

    entry = report.sources[0]
    assert entry.status == "unknown"
    assert entry.credential_status == "unknown"
    assert entry.credential_env_vars == ()
    assert transport.calls == []  # gate closed → not probed
    assert report.status_counts["unknown"] == 1


# ── determinism (41D-2 acceptance: same input → same bytes) ───────────


def test_report_is_deterministic_same_input_same_bytes(monkeypatch, tmp_path) -> None:
    _without_ops_credentials(monkeypatch)
    config = _consenting_config("cnipa", "crossref", "ops")

    first = diagnose_sources(config, only=["ops", "cnipa"]).describe()
    second = diagnose_sources(config, only=["ops", "cnipa"]).describe()

    # no sort_keys: also locks the deterministic key *order* of describe()
    blob_a = json.dumps(first, ensure_ascii=False).encode("utf-8")
    blob_b = json.dumps(second, ensure_ascii=False).encode("utf-8")
    assert blob_a == blob_b
    # nothing that could vary between runs: no timestamps, no environment paths
    assert b"timestamp" not in blob_a
    assert str(tmp_path) not in blob_a.decode("utf-8")


def test_status_counts_cover_full_vocabulary(monkeypatch) -> None:
    _without_ops_credentials(monkeypatch)

    # INT (4.2 wave gate): pin the closed-vocabulary accounting to an explicit
    # source set — the registry legitimately grows (41B-1 registered `npl`), so
    # a no-`only` run must keep passing whatever the population is.
    report = diagnose_sources(_consenting_config("cnipa", "crossref", "ops"), only=["cnipa", "crossref", "ops"])

    assert set(report.status_counts) == set(STATUSES)
    assert report.status_counts["ready"] == 2
    assert report.status_counts["skip"] == 1
    assert report.status_counts["blocked"] == 0


# ── public surface: registry coverage, only filter, table drift ───────


def test_public_wrapper_covers_registry_and_mirrors_support_level(monkeypatch) -> None:
    _without_ops_credentials(monkeypatch)

    report = diagnose_sources()

    assert [entry.source for entry in report.sources] == registry.ids()
    entries = {entry.source: entry for entry in report.sources}
    for source_id in registry.ids():
        assert entries[source_id].support_level == get_source(source_id).capabilities().support_level


def test_only_filter_selects_and_unknown_id_refused(monkeypatch) -> None:
    _without_ops_credentials(monkeypatch)

    report = diagnose_sources(only=["ops"])
    assert [entry.source for entry in report.sources] == ["ops"]

    with pytest.raises(KeyError, match="unknown source"):
        diagnose_sources(only=["does-not-exist"])


def test_credential_table_matches_ops_adapter(monkeypatch) -> None:
    """Diagnostics' env-var table must not drift from what OpsAdapter actually reads."""
    assert CREDENTIAL_ENV_VARS["ops"] == ("OPS_OAUTH_KEY", "OPS_OAUTH_SECRET")
    adapter = OpsAdapter(transport=lambda *a, **k: None)
    monkeypatch.setenv("OPS_OAUTH_KEY", "k")
    monkeypatch.setenv("OPS_OAUTH_SECRET", "s")
    assert adapter._credentials() == ("k", "s")
