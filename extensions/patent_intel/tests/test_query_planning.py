"""WP-A query-planning tests (UT-Q01/Q02/Q03, blueprint A-01..A-03 acceptance)."""

from __future__ import annotations

import pytest

from patent_intel.contracts import Requiredness
from patent_intel.retrieval.features import FeatureExtractionError, extract_features
from patent_intel.retrieval.query_expand import (
    DictionaryExpander,
    LLMExpander,
    TermExpansionError,
    expand_features,
    terms_to_query_spec,
)
from patent_intel.retrieval.query_plan import CNIPA_MAX_AND, QueryPlanBuilder, RenderError, render_query
from patent_intel.retrieval.terminology import detect_language, is_broadening, normalize_term

AXIS = "N1@TGT-0001"


# ── A-01 features (UT-Q01) ───────────────────────────────────────────


def test_features_split_into_independent_clauses() -> None:
    bundle = extract_features(
        ["信标发送时刻估计；漂移估计与补偿。动态信标周期调整"],
        axis_id=AXIS,
    )
    assert len(bundle.features) == 3
    ids = [f.feature_id for f in bundle.features]
    assert len(set(ids)) == 3
    # independent features never pollute each other's statements
    statements = [f.statement for f in bundle.features]
    assert statements[0] == "信标发送时刻估计"
    assert "漂移" not in statements[0]
    assert all(f.approved is False for f in bundle.features)  # never auto-approved
    assert all(f.source_refs for f in bundle.features)


def test_negation_stays_negative() -> None:
    bundle = extract_features(["不含漂移补偿模块"], axis_id=AXIS)
    feature = bundle.features[0]
    assert feature.negation is True
    assert feature.requiredness == Requiredness.NEGATION
    # negation must not be expandable into positive query terms
    with pytest.raises(TermExpansionError, match="negation"):
        terms_to_query_spec(
            feature,
            [{"term": "drift compensation", "relation": "translation", "feature_id": feature.feature_id, "source": "seed-dictionary", "verified": True}],  # type: ignore[list-item]
            query_id="Q-x",
            axis_id=AXIS,
            source="cnipa",
            query_type="single_feature",
        )


def test_numeric_bounds_captured_not_dropped() -> None:
    bundle = extract_features(["同步精度误差 ≤ 1ms"], axis_id=AXIS)
    feature = bundle.features[0]
    assert feature.requiredness == Requiredness.NUMERIC_BOUND
    assert feature.numeric_bounds and feature.numeric_bounds[0]["op"] == "≤"
    assert feature.numeric_bounds[0]["value"] == "1"
    assert feature.numeric_bounds[0]["unit"] == "ms"
    assert feature.numeric_bounds[0]["context"]  # original context preserved for review


def test_optional_features_graded_optional() -> None:
    bundle = extract_features(["可选地包括温度传感器"], axis_id=AXIS)
    assert bundle.features[0].requiredness == Requiredness.OPTIONAL


def test_empty_input_rejected() -> None:
    with pytest.raises(FeatureExtractionError):
        extract_features(["", "；"], axis_id=AXIS)
    with pytest.raises(FeatureExtractionError):
        extract_features(["x"], axis_id="")


# ── A-02 expansion (UT-Q03) ──────────────────────────────────────────


def test_dictionary_expander_attaches_provenance() -> None:
    bundle = extract_features(["信标发送时刻估计"], axis_id=AXIS)
    feature = bundle.features[0]
    candidates = DictionaryExpander().expand(feature)
    base = candidates[0]
    assert base.relation == "base" and base.feature_id == feature.feature_id
    expanded = [c for c in candidates if c.relation != "base"]
    assert any(c.term == "beacon" and c.relation == "translation" for c in expanded)
    assert all(c.feature_id == feature.feature_id for c in expanded)
    assert all(c.source for c in expanded)  # every term has a recorded source


def test_expansion_never_changes_requiredness() -> None:
    """扩词不凭空添加必要特征: expanded terms are retrieval aids, feature stays as-is."""
    bundle = extract_features(["可选地包括温度传感器"], axis_id=AXIS)
    feature = bundle.features[0]
    _ = expand_features([feature])
    assert feature.requiredness == Requiredness.OPTIONAL  # unchanged after expansion


def test_llm_terms_without_feature_link_are_unverified() -> None:
    """UT-Q03: 扩词没有来源特征时标 unverified-proposal."""

    def fake_client(prompt: str) -> list[dict]:
        return [{"term": "timing offset", "relation": "synonym"}]

    expander = LLMExpander(model_id="test-model", client=fake_client)
    bundle = extract_features(["信标发送时刻估计"], axis_id=AXIS)
    candidates = expander.expand(bundle.features[0])
    assert candidates and candidates[0].source == "llm:test-model"
    assert candidates[0].feature_id == bundle.features[0].feature_id  # linked
    assert expander.unverified_proposals == []


def test_llm_expander_absent_client_is_noop() -> None:
    expander = LLMExpander(model_id="m", client=None)
    bundle = extract_features(["信标"], axis_id=AXIS)
    assert expander.expand(bundle.features[0]) == []


def test_query_spec_terms_all_have_provenance() -> None:
    bundle = extract_features(["电池管理"], axis_id=AXIS)
    query = terms_to_query_spec(
        bundle.features[0],
        DictionaryExpander().expand(bundle.features[0]),
        query_id="Q-N1-SF-001",
        axis_id=AXIS,
        source="cnipa",
        query_type="single_feature",
    )
    assert query.provenance and len(query.provenance) == len(query.terms)
    assert all("feature_id" in p for p in query.provenance)
    assert query.approved is False


def test_term_normalization_and_language_detection() -> None:
    assert normalize_term("  Beacon   Timing ") == "beacon timing"
    assert detect_language("信标 beacon") == "zh+en"
    assert detect_language("时间同步") == "zh"
    assert is_broadening("hypernym") is True
    assert is_broadening("synonym") is False


# ── A-03 plan builder (UT-Q02) ───────────────────────────────────────


def _bundle_for_plan() -> object:
    return extract_features(
        ["信标发送时刻估计；漂移估计与补偿；重同步请求处理"],
        axis_id=AXIS,
    )


def test_plan_builds_query_family() -> None:
    plan = QueryPlanBuilder().build(_bundle_for_plan())  # type: ignore[arg-type]
    kinds = [q.query_type for q in plan.queries]
    assert kinds.count("single_feature") == 3
    assert "broad_recall" in kinds
    assert "feature_cross" in kinds
    # own id scheme; kernel N-numbering untouched
    assert all(q.query_id.startswith("Q-N1-") for q in plan.queries)
    assert all(q.approved is False for q in plan.queries)


def test_cnipa_render_respects_max_and() -> None:
    """UT-Q02: CNIPA 最多 3 个 AND；其他库不受该限制。"""
    plan = QueryPlanBuilder().build(_bundle_for_plan())  # type: ignore[arg-type]
    cross = next(q for q in plan.queries if q.query_type == "feature_cross")
    rendered = render_query(cross, "cnipa")
    assert rendered.count(" and ") <= CNIPA_MAX_AND - 1  # 3 groups => 2 'and' joins
    assert rendered.startswith("(")
    # crossref renders as free text, NOT bound by CNIPA limits
    crossref_render = render_query(cross, "crossref")
    assert " and " not in crossref_render


def test_cnipa_render_refuses_overwide_cross() -> None:
    from patent_intel.contracts import QuerySpec

    query = QuerySpec(
        owner="WP-A",
        query_id="Q-N1-FC-999",
        axis_id=AXIS,
        terms=["a", "b", "c", "d"],
        language="zh",
        query_type="feature_cross",
        source="multi",
        filters={"and_groups": [["a"], ["b"], ["c"], ["d"]], "max_and": 3},
    )
    with pytest.raises(RenderError, match="AND groups"):
        render_query(query, "cnipa")


def test_render_unknown_source_refused() -> None:
    plan = QueryPlanBuilder().build(_bundle_for_plan())  # type: ignore[arg-type]
    with pytest.raises(RenderError, match="no renderer"):
        render_query(plan.queries[0], "scifinder")


def test_negation_becomes_annotation_not_query() -> None:
    bundle = extract_features(["信标发送时刻估计；不含漂移补偿"], axis_id=AXIS)
    plan = QueryPlanBuilder().build(bundle)  # type: ignore[arg-type]
    assert not any("漂移补偿" in q.terms for q in plan.queries if q.query_type == "single_feature")
    assert any(a["kind"] == "negation" for a in plan.annotations)


def test_cross_domain_queries_generated_from_dictionary() -> None:
    import json
    import tempfile
    from pathlib import Path

    user_dict = {
        "信标发送时刻估计": [
            {"term": "NTP clock discipline", "relation": "cross_domain"},
        ]
    }
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "user.json"
        path.write_text(json.dumps(user_dict, ensure_ascii=False), encoding="utf-8")
        builder = QueryPlanBuilder(expanders=[DictionaryExpander(extra_dictionaries=[path])])
    bundle = extract_features(["信标发送时刻估计"], axis_id=AXIS)
    plan = builder.build(bundle)  # type: ignore[arg-type]
    xd = [q for q in plan.queries if q.query_type == "cross_domain"]
    assert len(xd) == 1
    assert xd[0].terms == ["NTP clock discipline"]
    assert xd[0].provenance and xd[0].provenance[0]["relation"] == "cross_domain"
