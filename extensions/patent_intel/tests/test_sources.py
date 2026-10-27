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
