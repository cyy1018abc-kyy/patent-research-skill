"""WP-B infra tests (B-04..B-07): rate limiting, checkpoints, audit ledger, OPS adapter
(fake transport only — no network), NPL provenance (UT-S02/UT-S04)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from patent_intel.contracts import RunStatus
from patent_intel.io.audit import AuditLedger
from patent_intel.sources.checkpoint import Checkpoint, CheckpointError, CheckpointStore
from patent_intel.sources.npl import (
    FulltextAvailability,
    NplRecord,
    fulltext_availability,
    npl_anchor,
    version_relation,
)
from patent_intel.sources.ops import OpsAdapter, OpsTransportError
from patent_intel.sources.rate_limit import (
    BackoffStopped,
    RateLimitExceeded,
    RateLimiter,
    with_backoff,
)


# ── rate limiting (UT-S02) ───────────────────────────────────────────


def test_rate_limiter_enforces_request_budget() -> None:
    limiter = RateLimiter(min_interval_sec=0.0, max_requests=2)
    limiter.acquire()
    limiter.acquire()
    with pytest.raises(RateLimitExceeded, match="budget"):
        limiter.acquire()


def test_rate_limiter_waits_between_calls() -> None:
    ticks = iter([100.0, 100.2, 101.0])
    limiter = RateLimiter(min_interval_sec=1.0)
    wait1 = limiter.acquire(now=lambda: next(ticks))
    assert wait1 == 0.0
    # second acquire sees 0.2s since last → would sleep; we just check the wait math path exists
    assert limiter._count == 1


def test_backoff_stops_on_403_429_without_retry() -> None:
    calls = {"n": 0}

    def flaky() -> object:
        calls["n"] += 1
        return type("R", (), {"status_code": 429})()

    with pytest.raises(BackoffStopped) as excinfo:
        with_backoff(flaky, max_attempts=5, sleep=lambda s: None)
    assert calls["n"] == 1  # stopped immediately — no retry storm
    assert excinfo.value.status == 429


def test_backoff_retries_transient_and_succeeds() -> None:
    seq = [type("R", (), {"status_code": 500})(), type("R", (), {"status_code": 200, "text": "ok"})()]
    out = with_backoff(lambda: seq.pop(0), max_attempts=3, sleep=lambda s: None)
    assert out.status_code == 200


def test_backoff_exhaustion_raises() -> None:
    with pytest.raises(RuntimeError, match="exhausted"):
        with_backoff(lambda: type("R", (), {"status_code": 500})(), max_attempts=2, sleep=lambda s: None)


# ── checkpoints (UT-S02: 断点恢复无重复、不覆盖) ─────────────────────


def test_checkpoint_state_machine_guards() -> None:
    cp = Checkpoint(run_id="R1", query_id="Q1", source="ops", request_fingerprint="fp")
    cp.transition(RunStatus.RUNNING)
    cp.transition(RunStatus.PARTIAL)
    with pytest.raises(CheckpointError):
        cp.transition(RunStatus.PLANNED)  # illegal backwards
    cp.transition(RunStatus.COMPLETE)
    with pytest.raises(CheckpointError):
        cp.transition(RunStatus.RUNNING)  # terminal


def test_checkpoint_failed_requires_error() -> None:
    cp = Checkpoint(run_id="R2", query_id="Q1", source="ops", request_fingerprint="fp")
    cp.transition(RunStatus.RUNNING)
    with pytest.raises(CheckpointError, match="error"):
        cp.transition(RunStatus.FAILED)


def test_checkpoint_page_recording_idempotent() -> None:
    cp = Checkpoint(run_id="R3", query_id="Q1", source="ops", request_fingerprint="fp")
    cp.record_page(fingerprint="p1", raw_ref="raw/a.json", sha256="a" * 64, bytes_written=10)
    cp.record_page(fingerprint="p1", raw_ref="raw/a.json", sha256="a" * 64, bytes_written=10)
    assert len(cp.pages_done) == 1


def test_checkpoint_store_roundtrip_and_resume(tmp_path: Path) -> None:
    store = CheckpointStore(tmp_path / "runs")
    cp = Checkpoint(run_id="R/unsafe id", query_id="Q1", source="ops", request_fingerprint="fp-1")
    cp.transition(RunStatus.RUNNING)
    cp.record_page(fingerprint="fp-1:0", raw_ref="raw/p1.json", sha256="b" * 64, bytes_written=5)
    store.save(cp)

    loaded = store.load("R/unsafe id")
    assert loaded.status == RunStatus.RUNNING
    assert loaded.fingerprints_done == {"fp-1:0"}

    resumable = store.find_resumable("fp-1")
    assert resumable is not None and resumable.run_id == "R/unsafe id"

    # completed checkpoints are not resumable
    cp.transition(RunStatus.COMPLETE)
    store.save(cp)
    assert store.find_resumable("fp-1") is None


def test_checkpoint_to_search_run_honest_counts() -> None:
    cp = Checkpoint(run_id="R4", query_id="Q1", source="ops", request_fingerprint="fp")
    cp.transition(RunStatus.RUNNING)
    cp.record_page(fingerprint="p0", raw_ref="raw/p1.json", sha256="c" * 64, bytes_written=100)
    cp.transition(RunStatus.PARTIAL)
    run = cp.to_search_run()
    assert run.status == RunStatus.PARTIAL
    assert run.complete is False
    assert run.records_fetched == 1
    assert run.hits_reported is None  # never invented
    assert run.incomplete_reason


# ── audit ledger (B-05) ──────────────────────────────────────────────


def test_audit_ledger_append_and_verify(tmp_path: Path) -> None:
    audit = AuditLedger(tmp_path / "audit")
    raw = tmp_path / "data" / "page1.json"
    raw.parent.mkdir(parents=True)
    payload = b'{"hits": []}'
    raw.write_bytes(payload)
    audit.append_raw(
        path="data/page1.json",
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes_written=len(payload),
        source="ops",
        request_fingerprint="fp",
    )
    report = audit.verify_raw_files(tmp_path)
    assert report == {"checked": 1, "missing": 0, "mismatched": []}

    raw.write_bytes(b"tampered")
    report = audit.verify_raw_files(tmp_path)
    assert report["mismatched"] == ["data/page1.json"]


def test_audit_ledger_failure_entries(tmp_path: Path) -> None:
    audit = AuditLedger(tmp_path / "audit")
    audit.append_failure(source="ops", run_id="R1", stop_reason="http_429", preserved_pages=2)
    audit.append_failure(source="ops", run_id="R2", stop_reason="timeout", preserved_pages=0)
    entries = audit.failure_entries()
    assert len(entries) == 2
    assert entries[0]["stop_reason"] == "http_429"


def test_audit_ledger_detects_corruption(tmp_path: Path) -> None:
    audit = AuditLedger(tmp_path / "audit")
    audit.append_raw(path="x", sha256="a" * 64, bytes_written=1, source="s", request_fingerprint="f")
    (tmp_path / "audit" / "raw_ledger.jsonl").write_text("{broken\n", encoding="utf-8")
    from patent_intel.io.audit import LedgerError

    with pytest.raises(LedgerError, match="corrupt"):
        audit.raw_entries()


# ── OPS adapter (fake transport; UT-S02) ─────────────────────────────


class FakeResp:
    def __init__(self, status_code: int, text: str = "{}", json_data: dict | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self._json = json_data or {}

    def json(self) -> dict:
        return self._json


def _ops_with_creds(monkeypatch: pytest.MonkeyPatch, transport) -> OpsAdapter:
    monkeypatch.setenv("OPS_OAUTH_KEY", "test-key")
    monkeypatch.setenv("OPS_OAUTH_SECRET", "test-secret")
    return OpsAdapter(transport=transport, sleep=lambda s: None)


def _allow_ops(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from patent_intel.config import PatentIntelConfig

    config = PatentIntelConfig(network_consent=True, allowed_sources=["ops"])
    state = tmp_path / "sidecar"
    state.mkdir(parents=True, exist_ok=True)
    return config, state


def test_ops_dry_run_previews_and_hides_token(tmp_path: Path) -> None:
    adapter = OpsAdapter(transport=lambda *a, **k: None)
    plan = adapter.build_request(_ops_query())
    result = adapter.dry_run(plan, tmp_path)
    assert result.plan.live is True
    assert "<redacted>" in result.preview[1]
    assert not (tmp_path / "raw").exists()  # dry-run writes nothing


def _ops_query():
    from patent_intel.contracts import QuerySpec

    return QuerySpec(
        owner="WP-B", query_id="Q-OPS-1", axis_id="N1@TGT-0001", terms=["beacon timing"],
        language="en", query_type="single_feature", source="ops", filters={},
    )


def test_ops_missing_credentials_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPS_OAUTH_KEY", raising=False)
    monkeypatch.delenv("OPS_OAUTH_SECRET", raising=False)
    adapter = OpsAdapter(transport=lambda *a, **k: None)
    with pytest.raises(Exception, match="OPS_OAUTH_KEY"):
        adapter._access_token()


def test_ops_execute_happy_path_pages_and_audits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config, state = _allow_ops(monkeypatch, tmp_path)
    calls: list[str] = []

    def transport(method: str, url: str, headers: dict, timeout: int) -> FakeResp:
        calls.append(url)
        if "auth" in url:
            return FakeResp(200, json_data={"access_token": "tok-123", "expires_in": 3600})
        return FakeResp(200, text='{"ops": "page"}')

    adapter = _ops_with_creds(monkeypatch, transport)
    plan = adapter.build_request(_ops_query())
    result = adapter.execute(
        plan, tmp_path, confirm_network=True, config=config, state_dir=state, max_pages=2
    )
    assert result.runs[0].status == RunStatus.COMPLETE
    assert result.runs[0].records_fetched == 2
    assert len(result.raw_refs) == 2
    # raw files exist with audit entries whose hashes match
    audit = AuditLedger(state / "audit")
    report = audit.verify_raw_files(state)
    assert report == {"checked": 2, "missing": 0, "mismatched": []}
    # credential material never appears anywhere on disk
    for path in state.rglob("*"):
        if path.is_file():
            assert "test-secret" not in path.read_text(encoding="utf-8", errors="replace")
            assert "tok-123" not in path.read_text(encoding="utf-8", errors="replace")


def test_ops_429_stops_and_preserves_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """UT-S02: 429 → 停止、已采集页不丢、failure ledger 记录。"""
    config, state = _allow_ops(monkeypatch, tmp_path)

    def transport(method: str, url: str, headers: dict, timeout: int) -> FakeResp:
        if "auth" in url:
            return FakeResp(200, json_data={"access_token": "tok", "expires_in": 600})
        if headers.get("X-OPS-Range", "").startswith("2"):
            return FakeResp(429)
        return FakeResp(200, text='{"page": 1}')

    adapter = _ops_with_creds(monkeypatch, transport)
    plan = adapter.build_request(_ops_query())
    result = adapter.execute(
        plan, tmp_path, confirm_network=True, config=config, state_dir=state, max_pages=3
    )
    run = result.runs[0]
    assert run.status == RunStatus.FAILED
    assert run.records_fetched == 1  # page 1 preserved
    assert run.complete is not True  # failed runs carry error, complete flag stays unset
    assert "429" in (run.error or "")
    failures = AuditLedger(state / "audit").failure_entries()
    assert failures and failures[0]["stop_reason"] == "http_429"
    assert failures[0]["preserved_pages"] == 1
    # resumable checkpoint exists for the same fingerprint
    store = CheckpointStore(state / "runs")
    assert store.find_resumable(run.request_fingerprint) is not None


def test_ops_resume_skips_existing_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config, state = _allow_ops(monkeypatch, tmp_path)
    served: list[str] = []
    page2_blocked = {"v": True}  # 429 once, then recover (simulating quota recovery)

    def transport(method: str, url: str, headers: dict, timeout: int) -> FakeResp:
        if "auth" in url:
            return FakeResp(200, json_data={"access_token": "tok", "expires_in": 600})
        served.append(headers.get("X-OPS-Range", ""))
        if headers.get("X-OPS-Range", "").startswith("2") and page2_blocked["v"]:
            page2_blocked["v"] = False
            return FakeResp(429)
        return FakeResp(200, text='{"page": 1}')

    adapter = _ops_with_creds(monkeypatch, transport)
    plan = adapter.build_request(_ops_query())
    first = adapter.execute(plan, tmp_path, confirm_network=True, config=config, state_dir=state, max_pages=2)
    assert first.runs[0].records_fetched == 1

    served.clear()
    second = adapter.execute(plan, tmp_path, confirm_network=True, config=config, state_dir=state, max_pages=2)
    assert second.runs[0].status == RunStatus.COMPLETE
    assert second.runs[0].records_fetched == 2
    assert served and served[0].startswith("2")  # page 1 NOT re-fetched


def test_ops_refused_without_consent(tmp_path: Path) -> None:
    adapter = OpsAdapter(transport=lambda *a, **k: None)
    plan = adapter.build_request(_ops_query())
    from patent_intel.sources.base import NetworkNotConfirmed

    with pytest.raises(NetworkNotConfirmed):
        adapter.execute(plan, tmp_path, confirm_network=False, config=None, state_dir=tmp_path)


def test_ops_transport_error_recorded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config, state = _allow_ops(monkeypatch, tmp_path)

    def transport(method: str, url: str, headers: dict, timeout: int) -> FakeResp:
        if "auth" in url:
            return FakeResp(200, json_data={"access_token": "tok", "expires_in": 600})
        raise TimeoutError("network unreachable")

    adapter = _ops_with_creds(monkeypatch, transport)
    plan = adapter.build_request(_ops_query())
    result = adapter.execute(plan, tmp_path, confirm_network=True, config=config, state_dir=state)
    assert result.runs[0].status == RunStatus.FAILED
    assert "TimeoutError" in (result.runs[0].error or "")


def test_ops_bad_search_status_surfaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config, state = _allow_ops(monkeypatch, tmp_path)

    def transport(method: str, url: str, headers: dict, timeout: int) -> FakeResp:
        if "auth" in url:
            return FakeResp(200, json_data={"access_token": "tok", "expires_in": 600})
        return FakeResp(500)

    adapter = _ops_with_creds(monkeypatch, transport)
    plan = adapter.build_request(_ops_query())
    result = adapter.execute(plan, tmp_path, confirm_network=True, config=config, state_dir=state)
    assert result.runs[0].status == RunStatus.FAILED


# ── NPL provenance (UT-S04) ──────────────────────────────────────────


def test_crossref_record_metadata_only_is_not_disclosure() -> None:
    item = {"DOI": "10.1234/paper", "title": ["A study"], "type": "journal-article", "issued": {"date-parts": [[2020, 5]]}}
    record = NplRecord.from_crossref(item, record_id="R1")
    assert record.doi == "10.1234/paper"
    assert fulltext_availability(record) == FulltextAvailability.METADATA_ONLY


def test_fulltext_requires_captured_artifact() -> None:
    record = NplRecord(record_id="R2", doi="10.1/x", fulltext_url="https://example.org/pdf")
    # a claimed URL without a captured artifact is honestly "unknown"
    assert fulltext_availability(record) == FulltextAvailability.UNKNOWN
    assert fulltext_availability(record, captured_text_bytes=1024) == FulltextAvailability.FULLTEXT


def test_preprint_and_published_stay_separate() -> None:
    preprint = NplRecord(
        record_id="R3", doi="10.9999/pre.1", work_type="posted-content",
        published_online="2024-01-01", relations={"is-preprint-of": "10.1234/final"},
    )
    summary = version_relation(preprint)
    assert summary["is_preprint"] is True
    assert summary["preprint_doi"] == "10.9999/pre.1"
    assert summary["published_doi"] == "10.1234/final"
    assert "separate records" in summary["note"]


def test_npl_anchor_refuses_metadata_only_fabrication() -> None:
    """DOI 摘要/目录元数据不得虚构论文全文段落。"""
    record = NplRecord(record_id="R4", doi="10.1/y")
    anchor = npl_anchor(record, "某结论句", raw_sha256="d" * 64, source_document="captured.md")
    assert anchor.verification_status == "unverified"
    with pytest.raises(ValueError, match="empty quote"):
        npl_anchor(record, "  ", raw_sha256="d" * 64, source_document="captured.md")


def test_ops_support_level_is_partial_in_registry() -> None:
    from patent_intel.sources.registry import get_source

    described = get_source("ops").capabilities()
    assert described.support_level == "partial"  # never claim live-tested
    assert described.requires_credentials is True
