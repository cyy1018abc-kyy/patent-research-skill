"""Cross-domain expansion via corpus co-occurrence mining (roadmap 41A-3, P1-A3).

Acceptance gates covered here:

* **split isolation** — test-split topics entering the miner are rejected at the
  signature layer (explicit keyword-only ``splits``, per-topic label cross-check);
* **determinism** — identical topics + corpus + params ⇒ identical table bytes;
* **leakage hard gate** — a mining artifact whose recorded input contains a test
  topic is rejected by check_leakage.py (function level and CLI ``--inject``);
* **dictionary fallback equivalence** — a mining-less CrossDomainExpander is
  exactly today's DictionaryExpander behavior (candidates and full plans).

No gold data of any split is read by these tests; fixtures are synthetic.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from patent_intel.retrieval.cooccurrence import (
    MINING_SPLITS,
    CooccurrenceMiner,
    MiningInputError,
    MiningParams,
    MiningTable,
    MiningTableError,
    TopicSeed,
)
from patent_intel.retrieval.features import extract_features
from patent_intel.retrieval.lexical import CorpusDoc
from patent_intel.retrieval.query_expand import CrossDomainExpander, DictionaryExpander
from patent_intel.retrieval.query_plan import QueryPlanBuilder

AXIS = "N1@TGT-0001"
REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK_LEAKAGE = REPO_ROOT / "benchmarks" / "retrieval" / "check_leakage.py"
MINE_SCRIPT = REPO_ROOT / "benchmarks" / "retrieval" / "mine_cooccurrence.py"

SMALL_CORPUS_PARAMS = MiningParams(
    min_cooccurrence=2, min_lift=1.2, min_df=1, max_df_ratio=0.9, max_terms_per_seed=5
)


def _topics():
    return [
        TopicSeed("TP-0001", "train", "beacon timing estimation for wireless sensor networks"),
        TopicSeed("TP-0002", "train", "beacon drift compensation in quantum sensor arrays"),
        TopicSeed("TP-0003", "val", "clock sync of quantum sensing devices"),
    ]


def _corpus():
    return [
        CorpusDoc("ZZ1000001A1", "beacon timing quantum sensor calibration method"),
        CorpusDoc("ZZ1000002A1", "beacon timing quantum entanglement sensor array"),
        CorpusDoc("ZZ1000003A1", "beacon drift quantum sensor compensation circuit"),
        CorpusDoc("ZZ1000004A1", "patent unrelated meteorological balloon patent telemetry patent"),
    ]


def _mine(topics=None, corpus=None, splits=("train", "val"), params=None):
    return CooccurrenceMiner(params or SMALL_CORPUS_PARAMS).mine(
        topics if topics is not None else _topics(),
        corpus if corpus is not None else _corpus(),
        splits=splits,
    )


def _load_check_leakage():
    spec = importlib.util.spec_from_file_location("check_leakage_under_test", CHECK_LEAKAGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── split isolation (signature-level) ─────────────────────────────────


def test_miner_rejects_test_split_declaration() -> None:
    """splits='test' is structurally impossible — mining never sees test data."""
    with pytest.raises(MiningInputError, match="test"):
        _mine(splits="test")


def test_miner_rejects_unknown_split_declaration() -> None:
    with pytest.raises(MiningInputError, match="holdout"):
        _mine(splits=("train", "holdout"))


def test_miner_rejects_test_topic_smuggled_into_input() -> None:
    """A test topic mixed into the topic list is a hard error, never a silent filter."""
    leaked = _topics() + [TopicSeed("TP-0009", "test", "beacon timing leak probe")]
    with pytest.raises(MiningInputError, match="TP-0009"):
        _mine(topics=leaked, splits=("train", "val"))


def test_miner_rejects_split_label_mismatch() -> None:
    mismatched = [TopicSeed("TP-0001", "val", "beacon timing estimation")]
    with pytest.raises(MiningInputError, match="TP-0001"):
        _mine(topics=mismatched, splits="train")


def test_miner_rejects_unlabeled_topic_mapping() -> None:
    with pytest.raises(MiningInputError, match="split"):
        _mine(topics=[{"topic_id": "TP-0001", "text": "beacon timing"}], splits="train")


def test_splits_argument_is_explicit_and_keyword_only() -> None:
    """No default: silence is how test data leaks — the caller must state the split."""
    with pytest.raises(TypeError):
        CooccurrenceMiner().mine(_topics(), _corpus())


def test_miner_rejects_empty_and_duplicate_inputs() -> None:
    with pytest.raises(MiningInputError, match="no topics"):
        _mine(topics=[])
    with pytest.raises(MiningInputError, match="more than once"):
        _mine(topics=_topics() + [_topics()[0]])
    with pytest.raises(MiningInputError, match="empty seed text"):
        _mine(topics=[TopicSeed("TP-0001", "train", "   ")])
    with pytest.raises(MiningInputError, match="empty corpus"):
        _mine(corpus=[])
    with pytest.raises(MiningInputError, match="duplicate doc_id"):
        _mine(corpus=_corpus() + [CorpusDoc("ZZ1000001A1", "duplicate id")])


def test_miner_fails_closed_on_impossible_df_band() -> None:
    """min_df above the df-band ceiling would mine an empty table — refuse loudly."""
    with pytest.raises(MiningInputError, match="max_df_ratio"):
        _mine(params=MiningParams(min_df=2, max_df_ratio=0.05))


def test_mining_splits_constant_excludes_test() -> None:
    assert MINING_SPLITS == ("train", "val")
    assert "test" not in MINING_SPLITS


# ── determinism (same input ⇒ same bytes) ─────────────────────────────


def test_mining_is_byte_deterministic() -> None:
    first = _mine().to_json()
    second = _mine().to_json()
    assert first == second
    assert first.endswith("\n")


def test_mining_is_independent_of_topic_and_corpus_order() -> None:
    """Integer counts only: order of topics/corpus must not move a byte."""
    table_a = _mine()
    topics_rev = list(reversed(_topics()))
    corpus_rev = list(reversed(_corpus()))
    table_b = _mine(topics=topics_rev, corpus=corpus_rev)
    assert table_a.to_json() == table_b.to_json()


_CROSS_PROCESS_SNIPPET = """
from patent_intel.retrieval.cooccurrence import CooccurrenceMiner, MiningParams, TopicSeed, CorpusDoc
topics = [
    TopicSeed("TP-0001", "train", "beacon timing estimation for wireless sensor networks"),
    TopicSeed("TP-0002", "train", "beacon drift compensation in quantum sensor arrays"),
    TopicSeed("TP-0003", "val", "clock sync of quantum sensing devices"),
]
corpus = [
    CorpusDoc("ZZ1000001A1", "beacon timing quantum sensor calibration method"),
    CorpusDoc("ZZ1000002A1", "beacon timing quantum entanglement sensor array"),
    CorpusDoc("ZZ1000003A1", "beacon drift quantum sensor compensation circuit"),
    CorpusDoc("ZZ1000004A1", "patent unrelated meteorological balloon patent telemetry patent"),
]
params = MiningParams(min_cooccurrence=2, min_lift=1.2, min_df=1, max_df_ratio=0.9, max_terms_per_seed=5)
import sys as _sys
_sys.stdout.write(CooccurrenceMiner(params).mine(topics, corpus, splits=("train", "val")).to_json())
"""


def test_mining_bytes_stable_across_processes() -> None:
    """The acceptance gate is byte-level: two fresh interpreters (different hash
    seeds) must serialize the identical table, matching the in-process result."""
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT / "extensions" / "patent_intel" / "src"))
    outputs = []
    for _ in range(2):
        proc = subprocess.run(
            [sys.executable, "-c", _CROSS_PROCESS_SNIPPET],
            capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(REPO_ROOT))
        assert proc.returncode == 0, proc.stderr
        outputs.append(proc.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0] == _mine().to_json()


def test_table_round_trip_and_digest_tamper_detection() -> None:
    table = _mine()
    restored = MiningTable.from_dict(json.loads(table.to_json()))
    assert restored.to_json() == table.to_json()
    assert restored.terms_for("beacon") == table.terms_for("beacon")

    tampered = json.loads(table.to_json())
    tampered["entries"]["beacon"][0]["co"] += 1
    with pytest.raises(MiningTableError, match="digest mismatch"):
        MiningTable.from_dict(tampered)


# ── mining content ────────────────────────────────────────────────────


def test_mined_terms_scored_filtered_and_capped() -> None:
    table = _mine()
    # 'beacon' co-occurs with quantum/sensor/timing; 'patent' (df=4 > 0.9*4) is banded out
    entries = table.terms_for("beacon")
    assert entries, "expected mined terms for the beacon seed"
    terms = [entry.term for entry in entries]
    assert "quantum" in terms and "sensor" in terms
    assert "patent" not in terms
    lifts = [entry.lift for entry in entries]
    assert lifts == sorted(lifts, reverse=True)
    assert all(entry.co_occurrence >= SMALL_CORPUS_PARAMS.min_cooccurrence for entry in entries)
    # cap per seed
    assert len(entries) <= SMALL_CORPUS_PARAMS.max_terms_per_seed


def test_table_provenance_records_splits_params_and_digest() -> None:
    table = _mine()
    prov = table.mining_provenance()
    assert prov["splits"] == ["train", "val"]
    assert prov["params"] == SMALL_CORPUS_PARAMS.to_dict()
    assert prov["corpus_docs"] == 4
    assert prov["topics"] == 3
    assert len(prov["digest"]) == 64


# ── CrossDomainExpander: mining path ──────────────────────────────────


def test_expander_mined_terms_carry_mining_provenance() -> None:
    table = _mine()
    bundle = extract_features(["beacon timing estimation"], axis_id=AXIS)
    candidates = CrossDomainExpander(mining=table).expand(bundle.features[0])
    mined = [c for c in candidates if c.relation == "cross_domain"]
    assert mined, "mining table should feed cross_domain candidates"
    for cand in mined:
        assert cand.source.startswith("cooccurrence:")
        assert cand.source.endswith(table.digest[:12])
        assert cand.feature_id == bundle.features[0].feature_id
        block = cand.extra["mining"]
        assert block["splits"] == ["train", "val"]
        assert block["params"] == SMALL_CORPUS_PARAMS.to_dict()
        assert block["digest"] == table.digest


def test_expander_does_not_remine_statement_tokens() -> None:
    """Tokens of the feature statement itself are not cross-domain candidates."""
    table = _mine()
    bundle = extract_features(["beacon timing estimation"], axis_id=AXIS)
    mined_terms = [
        c.term for c in CrossDomainExpander(mining=table).expand(bundle.features[0])
        if c.relation == "cross_domain"
    ]
    assert "beacon" not in mined_terms
    assert "timing" not in mined_terms
    assert "quantum" in mined_terms


def test_expander_caps_mined_terms_per_feature() -> None:
    table = _mine()
    bundle = extract_features(["beacon timing estimation"], axis_id=AXIS)
    expander = CrossDomainExpander(mining=table, max_mined_terms=1)
    mined = [c for c in expander.expand(bundle.features[0]) if c.relation == "cross_domain"]
    assert len(mined) == 1
    with pytest.raises(Exception, match="max_mined_terms"):
        CrossDomainExpander(mining=table, max_mined_terms=-1)


def test_expander_dedups_mined_against_dictionary_terms(tmp_path: Path) -> None:
    table = _mine()
    # a dictionary entry whose term collides with a mined term wins (dictionary first)
    dict_path = tmp_path / "collide.json"
    dict_path.write_text(
        json.dumps({"beacon timing estimation": [{"term": "quantum", "relation": "cross_domain"}]},
                   ensure_ascii=False),
        encoding="utf-8")
    bundle = extract_features(["beacon timing estimation"], axis_id=AXIS)
    with_mining = CrossDomainExpander(mining=table, extra_dictionaries=[dict_path]).expand(bundle.features[0])
    mined = [c for c in with_mining if c.relation == "cross_domain"]
    assert [c.term for c in mined].count("quantum") == 1
    assert mined[0].source == "user-dictionary"  # the dictionary instance is kept


# ── dictionary fallback equivalence (acceptance gate) ─────────────────


def _user_dictionary(tmp_path: Path) -> Path:
    user_dict = {
        "信标发送时刻估计": [
            {"term": "NTP clock discipline", "relation": "cross_domain"},
        ],
        "漂移补偿": [
            {"term": "feedforward control", "relation": "cross_domain"},
        ],
    }
    path = tmp_path / "user_crossdomain.json"
    path.write_text(json.dumps(user_dict, ensure_ascii=False), encoding="utf-8")
    return path


def test_fallback_candidates_equal_dictionary_expander(tmp_path: Path) -> None:
    dict_path = _user_dictionary(tmp_path)
    bundle = extract_features(["信标发送时刻估计；漂移估计与补偿"], axis_id=AXIS)
    plain = DictionaryExpander(extra_dictionaries=[dict_path])
    fallback = CrossDomainExpander(mining=None, extra_dictionaries=[dict_path])
    for feature in bundle.features:
        assert fallback.expand(feature) == plain.expand(feature)


def test_fallback_plan_equal_to_current_dictionary_plan(tmp_path: Path) -> None:
    """Full plan equivalence: same queries, same provenance, same bytes."""
    dict_path = _user_dictionary(tmp_path)
    bundle = extract_features(["信标发送时刻估计；漂移估计与补偿"], axis_id=AXIS)
    plan_a = QueryPlanBuilder(expanders=[DictionaryExpander(extra_dictionaries=[dict_path])]).build(bundle)
    plan_b = QueryPlanBuilder(expanders=[CrossDomainExpander(mining=None, extra_dictionaries=[dict_path])]).build(bundle)
    assert [q.to_dict() for q in plan_a.queries] == [q.to_dict() for q in plan_b.queries]
    assert plan_a.describe() == plan_b.describe()
    xd = [q for q in plan_a.queries if q.query_type == "cross_domain"]
    assert xd and all(p["relation"] == "cross_domain" for q in xd for p in q.provenance)
    assert all("mining" not in p for q in xd for p in q.provenance)  # no fabricated mining block


def test_builder_mining_table_convenience_generates_xd_queries() -> None:
    table = _mine()
    bundle = extract_features(["beacon timing estimation"], axis_id=AXIS)
    plan = QueryPlanBuilder(mining_table=table).build(bundle)
    xd = [q for q in plan.queries if q.query_type == "cross_domain"]
    assert xd
    assert all(q.query_id.startswith("Q-N1-XD-") for q in xd)
    assert all(q.approved is False for q in xd)
    for query in xd:
        mining_blocks = [p.get("mining") for p in (query.provenance or []) if p.get("mining")]
        assert mining_blocks, "mined XD query must carry the mining provenance block"
        assert mining_blocks[0]["splits"] == ["train", "val"]
        assert mining_blocks[0]["digest"] == table.digest
    # feature attribution stays honest: mined terms link to their origin feature
    assert all(q.feature_ids == ["FEAT-N1-001"] for q in xd)


# ── leakage hard gate in check_leakage.py ─────────────────────────────


def _manifest_dict() -> dict:
    return {
        "suite": "synthetic-crossdomain",
        "topics": [
            {"topic_id": "TP-0001", "split": "train", "source_id": "QF-100",
             "gold_families": ["FAM-1"], "time_split_key": "2001-01-01T00:00:00"},
            {"topic_id": "TP-0002", "split": "val", "source_id": "QF-200",
             "gold_families": ["FAM-2"], "time_split_key": "2002-01-01T00:00:00"},
            {"topic_id": "TP-0003", "split": "test", "source_id": "QF-300",
             "gold_families": ["FAM-3"], "time_split_key": "2003-01-01T00:00:00"},
        ],
    }


def _artifact_dict(topic_ids: list[str]) -> dict:
    return {
        "schema_version": 1,
        "record_type": "cooccurrence_table",
        "mining_input": {"splits": ["train", "val"], "topic_ids": topic_ids,
                         "topics_total": len(topic_ids)},
        "entries": {"beacon": [{"term": "quantum", "co": 3, "df": 3, "lift": 2.5}]},
    }


def test_leakage_gate_accepts_clean_mining_input() -> None:
    cl = _load_check_leakage()
    manifest = _manifest_dict()
    artifact = _artifact_dict(["TP-0001", "TP-0002"])
    assert cl.cooccurrence_violations(manifest, artifact) == []


def test_leakage_gate_rejects_test_topic_in_mining_input() -> None:
    cl = _load_check_leakage()
    manifest = _manifest_dict()
    leaked = _artifact_dict(["TP-0001", "TP-0003"])  # TP-0003 is a test topic
    problems = cl.cooccurrence_violations(manifest, leaked)
    assert any("TP-0003" in p and "test" in p for p in problems)


def test_leakage_gate_rejects_test_split_declaration_and_unrecorded_input() -> None:
    cl = _load_check_leakage()
    manifest = _manifest_dict()
    declared_test = _artifact_dict(["TP-0001"])
    declared_test["mining_input"]["splits"] = ["test"]
    problems = cl.cooccurrence_violations(manifest, declared_test)
    assert any("test" in p for p in problems)
    # fail closed: no mining_input record → cannot be proven clean
    assert cl.cooccurrence_violations(manifest, {"entries": {}})


def test_leakage_gate_rejects_unknown_and_duplicate_topic_ids() -> None:
    cl = _load_check_leakage()
    manifest = _manifest_dict()
    artifact = _artifact_dict(["TP-0001", "TP-9999", "TP-0001"])
    problems = cl.cooccurrence_violations(manifest, artifact)
    assert any("TP-9999" in p for p in problems)
    assert any("重复" in p for p in problems)


def test_leakage_cli_clean_and_injected_cooccurrence(tmp_path: Path) -> None:
    """CLI end-to-end: clean artifact passes; the injected test-topic sample is rejected."""
    manifest_path = tmp_path / "manifest.json"
    artifact_path = tmp_path / "cooccurrence.json"
    manifest_path.write_text(json.dumps(_manifest_dict(), ensure_ascii=False), encoding="utf-8")
    artifact_path.write_text(json.dumps(_artifact_dict(["TP-0001", "TP-0002"]), ensure_ascii=False), encoding="utf-8")
    base = [
        sys.executable, str(CHECK_LEAKAGE),
        "--manifest", str(manifest_path),
        "--cooccurrence", str(artifact_path),
    ]
    clean = subprocess.run(base, capture_output=True, text=True, encoding="utf-8", cwd=str(tmp_path))
    assert clean.returncode == 0, clean.stderr
    assert "挖掘输入纯度" in clean.stdout

    injected = subprocess.run(base + ["--inject", "cooccurrence"],
                              capture_output=True, text=True, encoding="utf-8", cwd=str(tmp_path))
    assert injected.returncode == 0, injected.stderr
    assert "注入 cooccurrence 被正确检出" in injected.stdout

    # a genuinely leaked artifact (test topic recorded as consumed) fails the gate
    leaked_path = tmp_path / "cooccurrence_leaked.json"
    leaked_path.write_text(
        json.dumps(_artifact_dict(["TP-0001", "TP-0003"]), ensure_ascii=False), encoding="utf-8")
    leaked = subprocess.run(
        [sys.executable, str(CHECK_LEAKAGE), "--manifest", str(manifest_path),
         "--cooccurrence", str(leaked_path)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(tmp_path))
    assert leaked.returncode == 1
    assert "TP-0003" in leaked.stderr


def test_mine_script_refuses_test_split_before_any_io(tmp_path: Path) -> None:
    """The mining entry point rejects a test request before reading anything."""
    result = subprocess.run(
        [sys.executable, str(MINE_SCRIPT), "--splits", "test",
         "--manifest", str(tmp_path / "nonexistent.json")],
        capture_output=True, text=True, encoding="utf-8", cwd=str(tmp_path))
    assert result.returncode == 2
    assert "FATAL" in result.stderr
    mixed = subprocess.run(
        [sys.executable, str(MINE_SCRIPT), "--splits", "train,test",
         "--manifest", str(tmp_path / "nonexistent.json")],
        capture_output=True, text=True, encoding="utf-8", cwd=str(tmp_path))
    assert mixed.returncode == 2
