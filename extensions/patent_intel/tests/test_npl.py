"""P1-B1 tests (roadmap 41B-1): NPL evidence chain — license-first gating, versioned
full text with SHA-256 binding, 401/403/429 stub handling.

Zero network: every adapter/fetcher is constructed with an injectable *fake*
transport and the tests count transport calls; the stub URL uses the reserved
``.invalid`` TLD so a real DNS attempt would fail loudly anyway.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from patent_intel.config import PatentIntelConfig
from patent_intel.contracts import QuerySpec, RunStatus
from patent_intel.io.audit import AuditLedger
from patent_intel.sources.base import CapabilityError, NetworkNotConfirmed, RequestPlan
from patent_intel.sources.npl import (
    DOC_LICENSE_TABLE,
    FulltextAvailability,
    FulltextVersion,
    LicenseGrant,
    LicenseNotGranted,
    NplFulltext,
    NplRecord,
    NplSourceAdapter,
    anchor_from_capture,
    fulltext_availability,
    require_licensed,
    version_relation,
)
from patent_intel.sources.registry import describe_sources, get_source

_STUB_URL = "https://stub.invalid/fulltext/paper.txt"  # RFC 2606: .invalid never resolves
_STUB_BODY = "Line one of the captured full text.\nLine two teaches the technical feature.\n"
_STUB_DOI = "10.1234/stub"

#: The only way a fetch runs in these tests: an explicitly injected grant whose
#: support_level is NOT planned. The gate checks the level, not mere presence.
_STUB_GRANTS = {
    "stub-upstream": LicenseGrant(
        source_id="stub-upstream",
        license_status="test fixture (fake transport; not a real upstream)",
        support_level="partial",
        evidence="extensions/patent_intel/tests/test_npl.py (stub transport)",
    )
}


class FakeResp:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def _recording_transport(status_code: int, body: str = _STUB_BODY):
    """Fake transport that counts calls (no-network assertion) and returns one status."""
    calls: list[str] = []

    def transport(method: str, url: str, headers: dict, timeout: int) -> FakeResp:
        calls.append(f"{method} {url}")
        return FakeResp(status_code, body)

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def _forbidden_transport():
    """A transport that must NEVER be called — any call fails the test."""
    calls: list[str] = []

    def transport(method: str, url: str, headers: dict, timeout: int) -> FakeResp:
        calls.append(f"{method} {url}")
        raise AssertionError(f"network call attempted through gate: {method} {url}")

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def _stub_adapter(transport) -> NplSourceAdapter:
    return NplSourceAdapter(upstream="stub-upstream", transport=transport, grants=_STUB_GRANTS)


def _consenting_env(tmp_path: Path) -> tuple[PatentIntelConfig, Path]:
    config = PatentIntelConfig(network_consent=True, allowed_sources=["npl"])
    state = tmp_path / "sidecar"
    state.mkdir(parents=True, exist_ok=True)
    return config, state


def _plan(args: list[str] | None = None) -> RequestPlan:
    return RequestPlan(
        source="npl",
        query_id="Q-NPL-1",
        verb="npl-fulltext",
        args=args if args is not None else [_STUB_URL, FulltextVersion.PUBLISHED, _STUB_DOI],
        summary="stub fulltext fetch",
        live=True,
    )


def _npl_query(**filters: str) -> QuerySpec:
    return QuerySpec(
        owner="WP-B",
        query_id="Q-NPL-1",
        axis_id="N1@TGT-0001",
        terms=["prior art"],
        language="en",
        query_type="single_feature",
        source="npl",
        filters=dict(filters) or None,
    )


# ── license-first gate: unlicensed sources refuse execution ───────────


def test_registry_has_npl_and_existing_sources_untouched() -> None:
    caps = {c["source"]: c for c in describe_sources()}
    assert set(caps) == {"cnipa", "crossref", "ops", "npl"}  # append-only registration
    # the acquisition contract is stub-tested (partial); the *upstream* license
    # table is what makes it non-executable against every real source
    assert caps["npl"]["support_level"] == "partial"
    assert caps["npl"]["license_status"] == "manual_export_only"
    assert caps["npl"]["query_fields"] == ["keywords"]
    # existing registrations unchanged by this package
    assert caps["cnipa"]["support_level"] == "partial"
    assert caps["crossref"]["support_level"] == "partial"
    assert caps["ops"]["support_level"] == "partial"


def test_doc_license_table_all_planned_and_mirrors_the_document() -> None:
    doc = Path(__file__).resolve().parents[3] / "docs" / "source-licensing.md"
    text = doc.read_text(encoding="utf-8")
    expected = {
        "arxiv",
        "europepmc",
        "openalex",
        "unpaywall",
        "publisher-direct",
        "standards-text",
    }
    assert set(DOC_LICENSE_TABLE) == expected
    for source_id, grant in DOC_LICENSE_TABLE.items():
        assert grant.support_level == "planned", source_id
        assert grant.evidence.startswith("docs/source-licensing.md")
        assert f"`{source_id}`" in text  # §4 table lists every id — doc↔code mirror


def test_require_licensed_refuses_unknown_and_planned() -> None:
    with pytest.raises(LicenseNotGranted, match="no license entry"):
        require_licensed("totally-unknown-source")
    with pytest.raises(LicenseNotGranted, match="planned"):
        require_licensed("arxiv")
    # an injected table cannot promote a source by listing it — level is checked
    planned_but_listed = {
        "arxiv": LicenseGrant("arxiv", "unverified", "planned", "docs/source-licensing.md")
    }
    with pytest.raises(LicenseNotGranted, match="planned"):
        require_licensed("arxiv", grants=planned_but_listed)
    grant = require_licensed("stub-upstream", grants=_STUB_GRANTS)
    assert grant.source_id == "stub-upstream"


def test_execute_refuses_unlicensed_upstream_before_any_transport_call(tmp_path: Path) -> None:
    """P1-B1 acceptance gate: the license refusal happens BEFORE the transport — an
    unlicensed source must never emit a single network request."""
    config, state = _consenting_env(tmp_path)
    transport = _forbidden_transport()
    adapter = NplSourceAdapter(upstream="arxiv", transport=transport)  # default doc table
    with pytest.raises(LicenseNotGranted, match="planned"):
        adapter.execute(
            _plan(), tmp_path, confirm_network=True, config=config, state_dir=state
        )
    assert transport.calls == []  # zero transport calls — the gate fired first
    # an upstream with no entry at all refuses the same way
    adapter2 = NplSourceAdapter(upstream="no-such-upstream", transport=transport)
    with pytest.raises(LicenseNotGranted, match="no license entry"):
        adapter2.execute(
            _plan(), tmp_path, confirm_network=True, config=config, state_dir=state
        )
    assert transport.calls == []


def test_build_request_makes_search_plan_and_refuses_undeclared_fields() -> None:
    adapter = NplSourceAdapter(transport=_forbidden_transport())
    plan = adapter.build_request(
        QuerySpec(
            owner="WP-B",
            query_id="Q-NPL-2",
            axis_id="N1@TGT-0001",
            terms=["beacon timing"],
            language="en",
            query_type="single_feature",
            source="npl",
        )
    )
    assert plan.verb == "npl-search"
    assert plan.args == ["beacon timing"]
    assert plan.live is True
    # identifier filters are NOT declared capabilities — refused, never silently dropped
    with pytest.raises(CapabilityError, match="does not support"):
        adapter.build_request(_npl_query(doi=_STUB_DOI))


def test_execute_refuses_search_plans_even_when_granted(tmp_path: Path) -> None:
    """A search plan is a reviewable preview: even with an injected grant it is not
    executable — no upstream endpoint is verified and URLs are never constructed."""
    config, state = _consenting_env(tmp_path)
    transport = _forbidden_transport()
    adapter = _stub_adapter(transport)
    search_plan = adapter.build_request(
        QuerySpec(
            owner="WP-B",
            query_id="Q-NPL-3",
            axis_id="N1@TGT-0001",
            terms=["beacon timing"],
            language="en",
            query_type="single_feature",
            source="npl",
        )
    )
    with pytest.raises(CapabilityError, match="not executable"):
        adapter.execute(
            search_plan, tmp_path, confirm_network=True, config=config, state_dir=state
        )
    assert transport.calls == []  # refusal before any transport call


def test_execute_still_requires_double_consent(tmp_path: Path) -> None:
    adapter = NplSourceAdapter(transport=_forbidden_transport(), grants=_STUB_GRANTS)
    with pytest.raises(NetworkNotConfirmed):
        adapter.execute(
            _plan(),
            tmp_path,
            confirm_network=False,
            config=PatentIntelConfig(network_consent=True, allowed_sources=["npl"]),
            state_dir=tmp_path,
        )
    with pytest.raises(NetworkNotConfirmed):
        adapter.execute(
            _plan(),
            tmp_path,
            confirm_network=True,
            config=PatentIntelConfig(network_consent=False, allowed_sources=[]),
            state_dir=tmp_path,
        )


def test_dry_run_previews_without_transport_or_writes(tmp_path: Path) -> None:
    adapter = NplSourceAdapter(transport=_forbidden_transport(), grants=_STUB_GRANTS)
    result = adapter.dry_run(_plan(), tmp_path)
    assert result.plan.live is True
    assert result.preview[0] == f"GET {_STUB_URL}"
    assert any("source-licensing.md" in note for note in result.notes)
    assert not (tmp_path / "raw").exists()  # dry-run writes nothing
    assert not (tmp_path / "audit").exists()


# ── 401/403/429 stub handling (fake transport, stop without retry) ────


@pytest.mark.parametrize("status", [401, 403, 429])
def test_stop_statuses_terminate_without_retry_storm(tmp_path: Path, status: int) -> None:
    config, state = _consenting_env(tmp_path)
    transport = _recording_transport(status)
    adapter = _stub_adapter(transport)
    result = adapter.execute(
        _plan(), tmp_path, confirm_network=True, config=config, state_dir=state
    )
    assert transport.calls == [f"GET {_STUB_URL}"]  # exactly one attempt — no retries
    run = result.runs[0]
    assert run.status == RunStatus.FAILED
    assert str(status) in (run.error or "")
    assert run.complete is not True
    failures = AuditLedger(state / "audit").failure_entries()
    assert len(failures) == 1
    assert failures[0]["stop_reason"] == f"http_{status}"
    assert failures[0]["preserved_pages"] == 0
    assert not (state / "raw").exists()  # stop statuses never write artifacts


def test_generic_error_status_is_transport_error_not_stop(tmp_path: Path) -> None:
    config, state = _consenting_env(tmp_path)
    transport = _recording_transport(500)
    adapter = _stub_adapter(transport)
    result = adapter.execute(
        _plan(), tmp_path, confirm_network=True, config=config, state_dir=state
    )
    assert transport.calls == [f"GET {_STUB_URL}"]  # single-shot: no retry loop here either
    assert result.runs[0].status == RunStatus.FAILED
    assert "500" in (result.runs[0].error or "")
    failures = AuditLedger(state / "audit").failure_entries()
    assert failures[0]["stop_reason"] == "transport_error"


def test_transport_exception_is_recorded_honestly(tmp_path: Path) -> None:
    config, state = _consenting_env(tmp_path)

    def transport(method: str, url: str, headers: dict, timeout: int) -> FakeResp:
        raise TimeoutError("network unreachable")

    adapter = _stub_adapter(transport)
    result = adapter.execute(
        _plan(), tmp_path, confirm_network=True, config=config, state_dir=state
    )
    assert result.runs[0].status == RunStatus.FAILED
    assert "TimeoutError" in (result.runs[0].error or "")


# ── happy path: raw artifact + SHA-256 audit (hash binding, end to end) ──


def test_execute_happy_path_writes_hash_bound_raw_artifact(tmp_path: Path) -> None:
    config, state = _consenting_env(tmp_path)
    transport = _recording_transport(200)
    adapter = _stub_adapter(transport)
    result = adapter.execute(
        _plan(), tmp_path, confirm_network=True, config=config, state_dir=state
    )
    run = result.runs[0]
    assert run.status == RunStatus.COMPLETE
    assert run.complete is True
    assert run.records_fetched == 1
    assert run.hits_reported is None  # a full-text fetch has no hit count — never invented

    # raw artifact exists and the audit ledger's hash matches it
    audit = AuditLedger(state / "audit")
    report = audit.verify_raw_files(state)
    assert report == {"checked": 1, "missing": 0, "mismatched": []}
    entry = audit.raw_entries()[0]
    assert entry["source"] == "npl"
    assert entry["upstream"] == "stub-upstream"  # extra dict is flattened into the entry

    # SHA-256 binding chain: raw bytes == audit entry == a reloadable capture
    raw_text = (state / entry["path"]).read_text(encoding="utf-8")
    digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    assert entry["sha256"] == digest
    assert result.raw_refs[0]["sha256"] == digest
    capture = NplFulltext.from_dict(
        {
            "version": FulltextVersion.PUBLISHED,
            "source_id": "stub-upstream",
            "url": _STUB_URL,
            "captured_at": run.executed_at,
            "sha256": entry["sha256"],
            "link_doi": _STUB_DOI,
        },
        content=raw_text,
    )
    assert capture.verify() is True


# ── NplFulltext: SHA-256 binding is validated, not declared ───────────


def test_fulltext_binding_is_validated_not_declared() -> None:
    capture = NplFulltext.capture(
        version=FulltextVersion.PREPRINT,
        content=_STUB_BODY,
        source_id="stub-upstream",
        url=_STUB_URL,
        captured_at="2026-11-07T00:00:00Z",
    )
    assert capture.sha256 == hashlib.sha256(_STUB_BODY.encode("utf-8")).hexdigest()
    assert capture.verify() is True
    # a hand-declared hash that does not bind the content is refused at construction
    with pytest.raises(ValueError, match="does not bind"):
        NplFulltext(
            version=FulltextVersion.PUBLISHED,
            content=_STUB_BODY,
            source_id="stub-upstream",
            url=_STUB_URL,
            captured_at="2026-11-07T00:00:00Z",
            sha256="f" * 64,
        )
    # a tampered serialized capture cannot be reloaded
    record = capture.to_dict()
    tampered = dict(record)
    with pytest.raises(ValueError, match="does not bind"):
        NplFulltext.from_dict(tampered, content=_STUB_BODY.replace("Line one", "TAMPERED"))


def test_fulltext_version_field_is_strict() -> None:
    with pytest.raises(ValueError, match="version"):
        NplFulltext.capture(
            version="cambridge-typeset",  # not a declared version kind
            content=_STUB_BODY,
            source_id="stub-upstream",
            url=_STUB_URL,
            captured_at="2026-11-07T00:00:00Z",
        )


# ── NplRecord.attach_fulltext: preprint↔published version discipline ──


def _capture(version: str, link_doi: str | None = None) -> NplFulltext:
    return NplFulltext.capture(
        version=version,
        content=_STUB_BODY,
        source_id="stub-upstream",
        url=_STUB_URL,
        captured_at="2026-11-07T00:00:00Z",
        link_doi=link_doi,
    )


def test_attach_fulltext_matches_identity_directly() -> None:
    preprint = NplRecord(record_id="R1", doi="10.9999/pre.1", work_type="posted-content")
    preprint.attach_fulltext(_capture(FulltextVersion.PREPRINT))
    assert preprint.captured_fulltext(FulltextVersion.PREPRINT) is not None
    assert fulltext_availability(preprint) == FulltextAvailability.FULLTEXT

    published = NplRecord(record_id="R2", doi="10.1234/final", work_type="journal-article")
    published.attach_fulltext(_capture(FulltextVersion.PUBLISHED, link_doi="10.1234/final"))
    assert published.captured_fulltext(FulltextVersion.PUBLISHED) is not None


def test_attach_fulltext_refuses_silent_version_conflation() -> None:
    preprint = NplRecord(record_id="R3", doi="10.9999/pre.1", work_type="posted-content")
    # published text on a preprint record with NO declared relation — refused
    with pytest.raises(ValueError, match="is-preprint-of"):
        preprint.attach_fulltext(_capture(FulltextVersion.PUBLISHED, link_doi="10.1234/final"))
    # declared relation + matching link_doi — allowed (only the published capture exists)
    preprint.relations["is-preprint-of"] = "10.1234/final"
    preprint.attach_fulltext(_capture(FulltextVersion.PUBLISHED, link_doi="10.1234/final"))
    assert [c.version for c in preprint.fulltext_captures] == [FulltextVersion.PUBLISHED]

    published = NplRecord(record_id="R4", doi="10.1234/final", work_type="journal-article")
    with pytest.raises(ValueError, match="has-preprint"):
        published.attach_fulltext(_capture(FulltextVersion.PREPRINT, link_doi="10.9999/pre.1"))
    # link_doi must equal the declared relation, not just any DOI
    published.relations["has-preprint"] = "10.9999/pre.1"
    with pytest.raises(ValueError, match="has-preprint"):
        published.attach_fulltext(_capture(FulltextVersion.PREPRINT, link_doi="10.9999/other"))
    published.attach_fulltext(_capture(FulltextVersion.PREPRINT, link_doi="10.9999/pre.1"))


def test_attach_fulltext_refuses_duplicate_version() -> None:
    record = NplRecord(record_id="R5", doi="10.1234/final", work_type="journal-article")
    record.attach_fulltext(_capture(FulltextVersion.PUBLISHED, link_doi="10.1234/final"))
    with pytest.raises(ValueError, match="already carries"):
        record.attach_fulltext(_capture(FulltextVersion.PUBLISHED, link_doi="10.1234/final"))


def test_attach_fulltext_unknown_identity_requires_doi_proof() -> None:
    record = NplRecord(record_id="R6", doi="10.1234/mystery", work_type=None)
    with pytest.raises(ValueError, match="work_type"):
        record.attach_fulltext(_capture(FulltextVersion.PUBLISHED, link_doi="10.1234/elsewhere"))
    record.attach_fulltext(_capture(FulltextVersion.PUBLISHED, link_doi="10.1234/mystery"))
    assert record.captured_fulltext(FulltextVersion.PUBLISHED) is not None


def test_version_relation_reports_captured_versions() -> None:
    preprint = NplRecord(
        record_id="R7",
        doi="10.9999/pre.1",
        work_type="posted-content",
        relations={"is-preprint-of": "10.1234/final"},
    )
    preprint.attach_fulltext(_capture(FulltextVersion.PREPRINT))
    summary = version_relation(preprint)
    assert summary["is_preprint"] is True
    assert summary["preprint_doi"] == "10.9999/pre.1"
    assert summary["published_doi"] == "10.1234/final"
    assert summary["captured_versions"] == [FulltextVersion.PREPRINT]
    assert "separate records" in summary["note"]


def test_fulltext_availability_backward_compatible() -> None:
    # records without captures keep the original honest semantics
    metadata = NplRecord.from_crossref(
        {"DOI": "10.1234/paper", "title": ["A study"], "type": "journal-article"},
        record_id="R8",
    )
    assert fulltext_availability(metadata) == FulltextAvailability.METADATA_ONLY
    claimed = NplRecord(record_id="R9", fulltext_url="https://example.org/pdf")
    assert fulltext_availability(claimed) == FulltextAvailability.UNKNOWN
    # a record WITH a capture is honestly fulltext
    captured = NplRecord(record_id="R10", doi="10.1234/mystery", work_type=None)
    captured.attach_fulltext(_capture(FulltextVersion.PUBLISHED, link_doi="10.1234/mystery"))
    assert fulltext_availability(captured) == FulltextAvailability.FULLTEXT


# ── quotes anchor only against captured text, never metadata ──────────


def test_anchor_from_capture_binds_capture_hash() -> None:
    record = NplRecord(record_id="R11", doi="10.1234/final", work_type="journal-article")
    capture = _capture(FulltextVersion.PUBLISHED, link_doi="10.1234/final")
    quote = "Line two teaches the technical feature."
    anchor = anchor_from_capture(record, capture, quote, source_document="raw/npl_page.txt")
    assert anchor.raw_sha256 == capture.sha256
    assert anchor.text_hash == hashlib.sha256(quote.encode("utf-8")).hexdigest()
    assert anchor.verification_status == "unverified"
    assert anchor.extra["fulltext_version"] == FulltextVersion.PUBLISHED


def test_anchor_from_capture_refuses_metadata_fabrication() -> None:
    record = NplRecord(record_id="R12", doi="10.1234/final", work_type="journal-article")
    capture = _capture(FulltextVersion.PUBLISHED, link_doi="10.1234/final")
    with pytest.raises(ValueError, match="not found in the captured"):
        anchor_from_capture(record, capture, "This sentence is nowhere in the text.",
                            source_document="raw/npl_page.txt")
    with pytest.raises(ValueError, match="empty quote"):
        anchor_from_capture(record, capture, "   ", source_document="raw/npl_page.txt")
    # a capture that fails its own re-check is never anchored against
    with pytest.raises(ValueError, match="tampered"):
        anchor_from_capture(record, _tampered_capture(), "Line one", source_document="x")


def _tampered_capture() -> NplFulltext:
    """A capture whose declared hash no longer matches its content (simulated tamper)."""
    capture = _capture(FulltextVersion.PUBLISHED, link_doi="10.1234/final")
    object.__setattr__(capture, "sha256", "0" * 64)  # simulate post-construction tamper
    return capture
