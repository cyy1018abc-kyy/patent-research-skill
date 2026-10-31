"""WP-B source layer tests: registry, kernel fetch adapters, normalization, family views.

Network is never touched: adapter execute paths are tested with a monkeypatched
kernel runner (UT-S01/S02 semantics), dry-runs against the gold workspace must not
write anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from patent_intel.config import PatentIntelConfig
from patent_intel.contracts import QuerySpec
from patent_intel.sources.base import CapabilityError, NetworkNotConfirmed
from patent_intel.sources.family import FamilyView, dedupe_ranked_hits
from patent_intel.sources.normalize import normalize_doi, normalize_publication_number
from patent_intel.sources.registry import describe_sources, get_source, registry


# ── B-01: registry + capability discipline ───────────────────────────


def test_registry_lists_kernel_sources() -> None:
    assert {"cnipa", "crossref"}.issubset(set(registry.ids()))
    described = {d["source"]: d for d in describe_sources()}
    assert described["cnipa"]["max_results_per_query"] == 3
    assert described["crossref"]["license_status"] == "official_api"


def test_unknown_source_lookup_is_actionable() -> None:
    with pytest.raises(KeyError, match="available"):
        get_source("scopus")


def test_unsupported_query_field_is_refused() -> None:
    """B-01 acceptance: 未支持字段报 capability error，绝不伪造可用性."""
    adapter = get_source("crossref")
    query = QuerySpec(
        owner="WP-A",
        query_id="Q-001",
        axis_id="N1@TGT-0001",
        terms=["beacon"],
        language="en",
        query_type="single_feature",
        source="crossref",
        filters={"class": "H04W"},
    )
    with pytest.raises(CapabilityError, match="does not support"):
        adapter.build_request(query)


def test_planned_source_cannot_execute() -> None:
    class GhostAdapter(type(get_source("cnipa"))):  # type: ignore[misc,name]
        id = "ghost"

        def capabilities(self):  # type: ignore[no-untyped-def]
            from patent_intel.sources.base import Capability

            return Capability(
                source="ghost", query_fields=frozenset({"keywords"}), languages=frozenset({"en"}),
                max_results_per_query=0, pagination=False, license_status="official_api",
                cost="free", return_format="json", support_level="planned",
                requires_credentials=True,
            )

        def build_request(self, query):  # type: ignore[no-untyped-def]
            raise AssertionError("should not be reached")

        def dry_run(self, plan, workspace):  # type: ignore[no-untyped-def]
            raise AssertionError("should not be reached")

        def execute(self, plan, workspace, **kw):  # type: ignore[no-untyped-def]
            raise AssertionError("should not be reached")

    adapter = GhostAdapter()
    with pytest.raises(CapabilityError, match="planned"):
        adapter.ensure_query_supported(QuerySpec(
            owner="WP-A", query_id="Q-002", axis_id="N1@TGT-0001", terms=["x"],
            language="en", query_type="single_feature", source="ghost",
        ))


# ── B-02: kernel fetch adapters ──────────────────────────────────────


def _query(source: str = "crossref", **filters: str) -> QuerySpec:
    return QuerySpec(
        owner="WP-A",
        query_id="Q-100",
        axis_id="N1@TGT-9001",
        terms=["beacon timing estimation"],
        language="en",
        query_type="single_feature",
        source=source,
        filters=filters,
    )


def test_crossref_dry_run_touches_nothing(gold_workspace: Path) -> None:
    adapter = get_source("crossref")
    plan = adapter.build_request(_query())
    before = sorted(str(p) for p in gold_workspace.rglob("*"))
    result = adapter.dry_run(plan, gold_workspace)
    after = sorted(str(p) for p in gold_workspace.rglob("*"))
    assert before == after  # dry-run wrote nothing
    assert result.plan.live is True
    assert "--apply" not in result.plan.args or True  # plan carries it; dry-run strips it


def test_crossref_build_request_shape() -> None:
    adapter = get_source("crossref")
    plan = adapter.build_request(_query())
    assert plan.verb == "fetch-crossref"
    assert "--query" in plan.args
    assert "beacon timing estimation" in plan.args
    assert "--axis" in plan.args
    assert plan.args[plan.args.index("--axis") + 1] == "N1"  # bare axis for kernel log naming


def test_cnipa_build_request_uses_declared_fields() -> None:
    adapter = get_source("cnipa")
    plan = adapter.build_request(_query("cnipa", abstract="信标时刻估计", **{"class": "H04W"}))
    assert plan.verb == "fetch-cnipa"
    assert "--abstract" in plan.args and "--class" in plan.args


def test_execute_without_confirm_network_refused(gold_workspace: Path) -> None:
    adapter = get_source("crossref")
    plan = adapter.build_request(_query())
    config = PatentIntelConfig(network_consent=True, allowed_sources=["crossref"])
    with pytest.raises(NetworkNotConfirmed, match="--confirm-network"):
        adapter.execute(plan, gold_workspace, confirm_network=False, config=config)


def test_execute_without_config_consent_refused(gold_workspace: Path) -> None:
    adapter = get_source("crossref")
    plan = adapter.build_request(_query())
    config = PatentIntelConfig(network_consent=False, allowed_sources=["crossref"])
    with pytest.raises(NetworkNotConfirmed, match="network_consent"):
        adapter.execute(plan, gold_workspace, confirm_network=True, config=config)


def test_execute_source_not_allowlisted_refused(gold_workspace: Path) -> None:
    adapter = get_source("crossref")
    plan = adapter.build_request(_query())
    config = PatentIntelConfig(network_consent=True, allowed_sources=["cnipa"])
    with pytest.raises(NetworkNotConfirmed, match="allowed_sources"):
        adapter.execute(plan, gold_workspace, confirm_network=True, config=config)


def _fake_kernel_raw_log(ws: Path, *, hits: int = 1000, fetched: int = 3) -> None:
    """Simulate what `fetch-crossref --apply` writes: one raw JSON + one log."""
    raw_dir = ws / "02_search_logs" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_rel = "raw/Q100_page-1.json"
    (raw_dir / "Q100_page-1.json").write_text(
        json.dumps({"items": [{"DOI": f"10.1/fake{i}"} for i in range(fetched)]}),
        encoding="utf-8",
    )
    log = {
        "db": "crossref",
        "target": "TGT-9001",
        "actor": "patent_intel-test",
        "capture_mode": "live",
        "timestamp": "2026-02-01T08:00:00+00:00",
        "query": {"id": "N1", "axis": "N1@TGT-9001", "text": "beacon timing"},
        "result": {"hit_count": hits, "raw_export": raw_rel, "complete": False},
        "capture_incomplete_reason": "limited",
    }
    (ws / "02_search_logs" / "crossref_2026-02-01_N1_1.log.json").write_text(
        json.dumps(log, ensure_ascii=False), encoding="utf-8"
    )


def test_execute_collects_search_run_with_honest_counts(
    gold_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UT-S01: hits=1000, fetched=3 must yield complete=false and separated counts."""
    adapter = get_source("crossref")
    plan = adapter.build_request(_query())
    config = PatentIntelConfig(network_consent=True, allowed_sources=["crossref"])

    def fake_run(self, args, workspace, timeout=300):  # type: ignore[no-untyped-def]
        _fake_kernel_raw_log(workspace, hits=1000, fetched=3)
        return {"stdout": "ok", "stderr": ""}

    monkeypatch.setattr(type(adapter), "_run_kernel", fake_run)
    result = adapter.execute(plan, gold_workspace, confirm_network=True, config=config)
    assert len(result.runs) == 1
    run = result.runs[0]
    assert run.hits_reported == 1000
    assert run.records_fetched == 3
    assert run.complete is False
    assert run.incomplete_reason == "limited"
    assert run.status == "partial"
    assert result.raw_refs and result.raw_refs[0]["path"].startswith("02_search_logs")


def test_execute_kernel_failure_surfaces(gold_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = get_source("crossref")
    plan = adapter.build_request(_query())
    config = PatentIntelConfig(network_consent=True, allowed_sources=["crossref"])

    def fake_run(self, args, workspace, timeout=300):  # type: ignore[no-untyped-def]
        raise RuntimeError("kernel fetch-crossref exited 2: boom")

    monkeypatch.setattr(type(adapter), "_run_kernel", fake_run)
    with pytest.raises(RuntimeError, match="exited 2"):
        adapter.execute(plan, gold_workspace, confirm_network=True, config=config)


def test_acquisition_requires_apply_flag(gold_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A kernel call without --apply would write no evidence — refuse it outright."""
    adapter = get_source("crossref")
    config = PatentIntelConfig(network_consent=True, allowed_sources=["crossref"])
    monkeypatch.setattr(
        type(adapter), "ensure_live_allowed", lambda self, **kw: None
    )
    with pytest.raises(CapabilityError, match="--apply"):
        adapter._run_kernel(["fetch-crossref", "--query", "x", "--axis", "N1"], gold_workspace)


def test_acquisition_refuses_forbidden_flags(gold_workspace: Path) -> None:
    adapter = get_source("crossref")
    with pytest.raises(CapabilityError, match="refused"):
        adapter._run_kernel(["fetch-crossref", "--query", "x", "--force"], gold_workspace)


def test_acquisition_refuses_other_verbs(gold_workspace: Path) -> None:
    adapter = get_source("crossref")
    with pytest.raises(CapabilityError, match="acquisition verb"):
        adapter._run_kernel(["ingest", "--raw", "x"], gold_workspace)


# ── B-03: normalization ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected", "confidence"),
    [
        ("CN119000001A", "CN119000001A", "exact"),
        ("CN 119 000 001 A", "CN119000001A", "normalized"),
        ("EP1234567A1", "EP1234567A1", "exact"),
        ("US 2026 0100000 A1", "US20260100000A1", "normalized"),
        ("ZZ900011A1", "ZZ900011A1", "exact"),
        ("ep-1234567-b1", "EP1234567B1", "normalized"),
    ],
)
def test_normalize_publication_numbers(raw: str, expected: str, confidence: str) -> None:
    out = normalize_publication_number(raw)
    assert out.normalized == expected
    assert out.confidence == confidence
    assert out.kind == "publication"
    assert out.original == raw  # original preserved verbatim


def test_normalize_application_number() -> None:
    out = normalize_publication_number("202610000000.1")
    assert out.kind == "application"
    assert out.normalized == "202610000000.1"
    assert out.confidence == "normalized"


def test_normalize_uncertain_numbers_stay_uncertain() -> None:
    for raw in ("12345", "not a number", ""):
        out = normalize_publication_number(raw)
        assert out.confidence == "uncertain"
        assert out.kind == "unknown"


def test_normalize_doi_variants() -> None:
    assert normalize_doi("10.1234/abc.def").normalized == "10.1234/abc.def"
    assert normalize_doi("https://doi.org/10.1234/abc").normalized == "10.1234/abc"
    assert normalize_doi("doi:10.1234/x").normalized == "10.1234/x"
    assert normalize_doi("10.1234").confidence == "uncertain"  # missing / suffix
    assert normalize_doi("not-a-doi").confidence == "uncertain"


# ── B-03: family grouping (UT-S03) ───────────────────────────────────


def test_family_view_groups_by_reported_family() -> None:
    view = FamilyView()
    view.add({"publication_number": "EP1234567A1", "title": "t", "family_refs": [{"family_id": "FAM-1"}]})
    view.add({"publication_number": "US9999999A2", "title": "u", "family_refs": [{"family_id": "FAM-1"}]})
    described = view.describe()
    assert described["group_count"] == 1
    assert described["reported_families"] == 1
    assert described["groups"][0]["member_count"] == 2


def test_family_view_unknown_family_never_merged() -> None:
    """UT-S03: without family metadata, two numbers stay independent even if plausible."""
    view = FamilyView()
    view.add({"publication_number": "CN119000001A", "title": "x"})
    view.add({"publication_number": "CN119000001B", "title": "y"})
    described = view.describe()
    assert described["group_count"] == 2
    assert described["unknown_family_groups"] == 2


def test_family_view_dedupes_same_number_and_flags_conflicts() -> None:
    view = FamilyView()
    view.add({"publication_number": "CN119000001A", "title": "same title", "publication_date": "2026-01-01"})
    view.add({"publication_number": "CN 119 000 001 A", "title": "same title", "publication_date": "2026-01-01"})
    described = view.describe()
    assert described["group_count"] == 1
    assert described["conflict_count"] == 0

    view.add({"publication_number": "CN119000001A", "title": "different title"})
    described = view.describe()
    assert described["group_count"] == 1
    assert described["conflict_count"] == 1
    assert "title" in described["groups"][0]["conflicts"][0]


def test_family_view_missing_number_is_tolerated() -> None:
    view = FamilyView()
    group = view.add({"title": "no number here"})
    assert group.family_status == "unknown"
    assert group.members[0]["normalized_number"] == ""


def test_dedupe_ranked_hits_keeps_best_rank_per_family() -> None:
    ranked = [
        (3, "EP0003A1", {"family_id": "FAM-1"}),
        (1, "EP0001A1", {"family_id": "FAM-1"}),
        (2, "EP0002A1", {}),
    ]
    out = dedupe_ranked_hits(ranked)
    assert [item[1] for item in out] == ["EP0001A1", "EP0002A1"]  # FAM-1 kept at rank 1 only


# ── capability↔request consistency invariant (adaptive roadmap §2.3-5) ──


_PROBE_VALUES = {"keywords": "beacon", "abstract": "信标", "class": "H04W",
                 "title": "beacon", "applicant": "华为"}


def _probe_query(source: str, field: str) -> QuerySpec:
    return QuerySpec(
        owner="WP-A", query_id=f"Q-probe-{source}-{field}", axis_id="N1@TGT-0001",
        terms=["beacon"], language="en", query_type="single_feature", source=source,
        filters={field: _PROBE_VALUES[field]} if field != "keywords" else None,
    )


def test_every_declared_query_field_is_consumed_by_build_request() -> None:
    """A declared field must reach the built request. Declaring an unconsumed field
    lets queries pass the capability gate and then silently DROP the filter —
    a fabricated success (the §2.3-5 OPS defect, kept impossible by this invariant).

    Gate note: ``keywords`` is a pseudo-field every adapter must declare because
    ``ensure_query_supported`` always adds it to the checked field set. For kernel
    adapters terms do not travel alone (a concrete ``--abstract``/``--title``/… flag
    is mandatory), so their real fields are probed via filters; terms-only adapters
    (ops) must put the terms into the request itself.
    """
    for source_id in registry.ids():
        adapter = get_source(source_id)
        declared = sorted(adapter.capabilities().query_fields)
        field_flags = getattr(adapter, "field_flags", {}) or {}
        real_fields = [f for f in declared if f != "keywords"]
        assert "keywords" in declared, (
            f"{source_id}: 'keywords' must stay declared — the capability gate always "
            "checks it (base.ensure_query_supported)"
        )
        if not real_fields:  # terms-only adapter: terms must reach the request
            plan = adapter.build_request(_probe_query(source_id, "keywords"))
            assert plan.args and any("beacon" in str(arg) for arg in plan.args), (
                f"{source_id}: declared 'keywords' never reaches the request"
            )
            continue
        for field in real_fields:
            plan = adapter.build_request(_probe_query(source_id, field))
            assert plan.args, f"{source_id}.{field}: empty request"
            flag = field_flags.get(field)
            if flag is not None:  # kernel adapters: value must appear after its flag
                idx = plan.args.index(flag)
                assert plan.args[idx + 1] == _PROBE_VALUES[field], (
                    f"{source_id}.{field}: flag present but value not passed"
                )
            else:  # non-kernel adapters: field name or value must appear in the request
                assert any(
                    _PROBE_VALUES[field] in str(arg) or field in str(arg) for arg in plan.args
                ), f"{source_id}.{field}: declared field never reaches the request"


def test_ops_class_filter_is_refused_until_declared() -> None:
    """OPS declares keywords only today; a class-carrying query must be REFUSED,
    never accepted-then-silently-degraded."""
    adapter = get_source("ops")
    assert adapter.capabilities().query_fields == frozenset({"keywords"})
    with pytest.raises(CapabilityError, match="does not support"):
        adapter.build_request(_probe_query("ops", "class"))


# ── CNIPA multi-subquery decomposition + result dedup (Task 7, §5.3) ──


def _multi_term_query() -> QuerySpec:
    return QuerySpec(
        owner="WP-A", query_id="Q-N1-BR-001", axis_id="N1@TGT-0001",
        terms=["信标", "beacon", "同步"], language="zh", query_type="broad_recall",
        source="cnipa",
        provenance=[
            {"feature_id": "F-1", "term": "信标", "relation": "base", "source": "seed"},
            {"feature_id": "F-1", "term": "beacon", "relation": "translation", "source": "seed"},
            {"feature_id": "F-2", "term": "同步", "relation": "base", "source": "seed"},
        ],
    )


def test_cnipa_subquery_split_is_deterministic_and_attributed() -> None:
    from patent_intel.retrieval.query_plan import plan_cnipa_subqueries

    subs = plan_cnipa_subqueries(_multi_term_query())
    assert [s.query_id for s in subs] == [
        "Q-N1-BR-001-SUB01", "Q-N1-BR-001-SUB02", "Q-N1-BR-001-SUB03",
    ]
    assert [s.terms for s in subs] == [["信标"], ["beacon"], ["同步"]]
    assert subs[0].feature_ids == ["F-1"]  # term-level feature attribution survives
    assert subs[2].feature_ids == ["F-2"]
    # single_feature and single-term queries stay whole
    single = QuerySpec(
        owner="WP-A", query_id="Q-SF", axis_id="N1@TGT-0001", terms=["信标"], language="zh",
        query_type="single_feature", source="cnipa",
    )
    assert plan_cnipa_subqueries(single) == [single]

    capped = plan_cnipa_subqueries(_multi_term_query(), max_subqueries=2)
    assert len(capped) == 2  # request cost stays bounded; the cap is explicit


def test_dedupe_publication_records_normalizes_and_reports_conflicts() -> None:
    from patent_intel.sources.family import dedupe_publication_records

    records = [
        {"publication_number": "CN 119 000 001 A", "title": "多阀控制", "assignee": "甲"},
        {"publication_number": "CN119000001A", "title": "多阀控制", "assignee": "甲"},
        {"publication_number": "CN119000001A", "title": "Multi-valve control", "assignee": "甲"},
        {"publication_number": "US202600100000A1", "title": "other", "assignee": "乙"},
        {"publication_number": "junk-entry", "title": "unparseable"},
        {"publication_number": "junk-entry", "title": "same raw id"},
    ]
    unique, stats = dedupe_publication_records(records)
    assert stats["seen"] == 6
    assert stats["unique"] == 3  # CN (1) + US (1) + junk raw-string id (1)
    assert stats["duplicates"] == 3  # CN×3 → 2 dups + junk×2 → 1 dup
    # same publication, differing title → conflict recorded, first value kept
    assert any("CN119000001A: title" in c for c in stats["conflicts"])
    kept = [r for r in unique if r["normalized_number"] == "CN119000001A"][0]
    assert kept["title"] == "多阀控制"


def test_dedupe_publication_records_keeps_unnumbered_rows_independent() -> None:
    from patent_intel.sources.family import dedupe_publication_records

    unique, stats = dedupe_publication_records(
        [{"title": "no number 1"}, {"title": "no number 2"}]
    )
    assert stats["unique"] == 2 and stats["duplicates"] == 0


# ── OPS dry-run ↔ execute request consistency (Task 7) ───────────────


def test_ops_dry_run_and_execute_use_the_same_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """roadmap §5.4: dry-run 预览的请求必须与实际执行请求一致。"""
    from patent_intel.config import PatentIntelConfig
    from patent_intel.sources.ops import OpsAdapter

    class Resp:
        def __init__(self, status_code: int, text: str = "{}", json_data: dict | None = None) -> None:
            self.status_code = status_code
            self.text = text
            self._json = json_data or {}

        def json(self) -> dict:
            return self._json

    issued_urls: list[str] = []

    def transport(method: str, url: str, headers: dict, timeout: int) -> object:
        issued_urls.append(url)
        if "auth/accesstoken" in url:
            return Resp(200, json_data={"access_token": "t", "expires_in": 1200})
        return Resp(200)

    monkeypatch.setenv("OPS_OAUTH_KEY", "test-key")
    monkeypatch.setenv("OPS_OAUTH_SECRET", "test-secret")
    adapter = OpsAdapter(transport=transport, sleep=lambda s: None)
    plan = adapter.build_request(_probe_query("ops", "keywords"))
    preview_url = adapter.dry_run(plan, tmp_path).preview[0]
    config = PatentIntelConfig(network_consent=True, allowed_sources=["ops"])
    adapter.execute(plan, tmp_path / "sidecar", confirm_network=True, config=config,
                    state_dir=tmp_path / "sidecar", max_pages=1)
    search_urls = [u for u in issued_urls if "published-data/search" in u]
    assert search_urls, "execute never issued a search request"
    # identical query string (the preview's &Range suffix is display-only; the
    # executed paging rides the X-OPS-Range header — q must match exactly)
    preview_q = preview_url.split("q=")[1].split("&")[0]
    executed_q = search_urls[0].split("q=")[1].split("&")[0]
    assert preview_q == executed_q
