"""Tests for 41A-5: first-class batch entry (retrieval/batch.py + thin-shell runner).

Contract under test: ``run_batch`` rows are byte-identical to the preregistered
loop it replaced (replicated independently here, then compared at the byte
level); benchmark-mode auto-approval is an explicit flag whose default keeps
plans unapproved (zero rows, not a silent bypass); ``batch_mode`` is stamped
into the meta; the script shell stays compatible (same helpers, same file
format).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from patent_intel.retrieval.batch import (
    BatchConfig,
    BatchError,
    merge_rankings,
    run_batch,
    topic_query_texts,
)
from patent_intel.retrieval.lexical import BM25Index, CorpusDoc

_DOCS = [
    ("FAM-90001", "frame sync timing marker"),
    ("FAM-90002", "frame sync protocol handshake"),
    ("FAM-90003", "timing recovery loop filter"),
    ("FAM-90004", "water pump pressure valve"),
    ("FAM-90005", "chemical composition catalyst"),
    ("FAM-90006", "frame timing drift"),
]

_TOPICS = [
    {"topic_id": "TP-9001", "source_id": "q1"},
    {"topic_id": "TP-9002", "source_id": "q2"},
]

_QUERIES = {
    "q1": {"title_en": "frame sync timing", "abstract_en": "", "claims_text": ""},
    "q2": {"title_en": "catalyst", "abstract_en": "chemical composition", "claims_text": "catalyst composition"},
}


def _index() -> BM25Index:
    return BM25Index(
        [CorpusDoc(doc_id=doc_id, text=text, family_id=doc_id) for doc_id, text in _DOCS],
        k1=1.5,
        b=0.75,
    )


def _dump_rows(rows: list[dict]) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows).encode("utf-8")


class TestBaselineByteIdentity:
    def test_rows_match_independent_preregistered_loop(self):
        index = _index()
        k = 5
        result = run_batch(
            _TOPICS,
            _QUERIES,
            index,
            BatchConfig(side="baseline", k_per_request=k),
            batch_mode="test",
        )

        # Independent replication of the preregistered loop (the pre-41A-5 body).
        expected_rows: list[dict] = []
        for topic in _TOPICS:
            texts = topic_query_texts(topic, _QUERIES)
            score_maps = []
            for name in ("tac", "ta", "claims"):
                hits = index.search(texts[name], k=k)
                score_maps.append(dict(hits))
            for rank, (fam, _score) in enumerate(merge_rankings(score_maps, k), start=1):
                expected_rows.append({"topic_id": topic["topic_id"], "family_id": fam, "rank": rank})

        assert result.rows == expected_rows
        assert _dump_rows(result.rows) == _dump_rows(expected_rows)

    def test_deterministic_across_runs(self):
        kwargs = dict(
            topics=_TOPICS,
            queries_by_id=_QUERIES,
            index=_index(),
            config=BatchConfig(side="baseline", k_per_request=5),
        )
        first = _dump_rows(run_batch(batch_mode="t", **kwargs).rows)
        second = _dump_rows(run_batch(batch_mode="t", **kwargs).rows)
        assert first == second

    def test_meta_carries_honest_accounting(self):
        result = run_batch(
            _TOPICS, _QUERIES, _index(), BatchConfig(side="baseline", k_per_request=5), batch_mode="ci"
        )
        # 2 topics × 3 preregistered variants
        assert result.requests_total == 6
        assert result.meta["topics_run"] == 2
        assert result.meta["batch_mode"] == "ci"
        assert result.meta["budget"] == "3 fixed requests (tac/ta/claims)"


class TestExtensionApprovalFlag:
    def test_default_refuses_unapproved_plans(self):
        result = run_batch(
            _TOPICS,
            _QUERIES,
            _index(),
            BatchConfig(side="extension", k_per_request=5),
            batch_mode="test",
        )
        assert result.rows == []
        assert result.requests_total == 0

    def test_explicit_approval_runs_and_matches_manual_replication(self):
        index = _index()
        k = 5
        config = BatchConfig(
            side="extension", k_per_request=k, budget_requests=3, approve_queries=True
        )
        result = run_batch(_TOPICS, _QUERIES, index, config, batch_mode="test")
        assert result.requests_total > 0

        # Independent replication of the pre-41A-5 extension loop (auto-approved).
        from patent_intel.retrieval.controller import AdaptiveController, RunOutcome
        from patent_intel.retrieval.features import extract_features
        from patent_intel.retrieval.query_plan import QueryPlanBuilder

        expected_rows: list[dict] = []
        total = 0
        for topic in _TOPICS:
            q = _QUERIES[topic["source_id"]]
            statements = [q["title_en"] or "", q["abstract_en"] or ""]
            statements += [c.strip() for c in (q["claims_text"] or "").splitlines() if c.strip()]
            bundle = extract_features(
                statements, axis_id=f"N1@{topic['topic_id']}", source_tag="dapfam-benchmark", approved=True
            )
            plan = QueryPlanBuilder().build(bundle)
            for query_spec in plan.queries:
                query_spec.approved = True
            pending = plan.approved_queries()
            if not pending:
                continue
            score_maps: list[dict[str, float]] = []

            def runner(query_spec):
                hits = index.search(" ".join(query_spec.terms), k=k)
                score_maps.append(dict(hits))
                return RunOutcome(
                    query_id=query_spec.query_id,
                    hits=[h[0] for h in hits],
                    families=[h[0] for h in hits],
                    cost=1.0,
                )

            controller = AdaptiveController(runner, max_requests=3, max_cost=3.0)
            controller.run_plan(pending)
            total += len(score_maps)
            for rank, (fam, _score) in enumerate(merge_rankings(score_maps, k), start=1):
                expected_rows.append({"topic_id": topic["topic_id"], "family_id": fam, "rank": rank})

        assert result.requests_total == total
        assert _dump_rows(result.rows) == _dump_rows(expected_rows)

    def test_budget_is_honored(self):
        result = run_batch(
            _TOPICS,
            _QUERIES,
            _index(),
            BatchConfig(side="extension", k_per_request=5, budget_requests=1, approve_queries=True),
            batch_mode="test",
        )
        assert result.requests_total <= 2  # ≤ budget_requests per topic
        assert result.meta["budget"] == "AdaptiveController max 1 requests/topic"


class TestConfigContract:
    def test_bad_side_rejected(self):
        with pytest.raises(BatchError, match="side"):
            BatchConfig(side="yolo")

    def test_zero_k_rejected(self):
        with pytest.raises(BatchError, match="k_per_request"):
            BatchConfig(side="baseline", k_per_request=0)

    def test_negative_budget_rejected(self):
        with pytest.raises(BatchError, match="budget_requests"):
            BatchConfig(side="baseline", budget_requests=-1)

    def test_approval_flag_meaningless_on_baseline_rejected(self):
        with pytest.raises(BatchError, match="approve_queries"):
            BatchConfig(side="baseline", approve_queries=True)


def _load_run_benchmark_module():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "benchmarks" / "retrieval" / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("run_benchmark_batch_test", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestThinShellCompatibility:
    def test_script_helpers_delegate_to_the_library(self):
        module = _load_run_benchmark_module()
        assert module.topic_query_texts(_TOPICS[0], _QUERIES) == topic_query_texts(_TOPICS[0], _QUERIES)
        assert module.merge_rankings([{"FAM-90001": 1.0}, {"FAM-90002": 2.0}], 5) == [
            ("FAM-90002", 2.0),
            ("FAM-90001", 1.0),
        ]

    def test_write_run_format_unchanged(self, tmp_path: Path):
        module = _load_run_benchmark_module()
        module.RUNS_DIR = tmp_path
        rows = [{"topic_id": "TP-9001", "family_id": "FAM-90001", "rank": 1}]
        meta = {"requests_total": 3, "topics_run": 1, "batch_mode": "format-check"}
        module.write_run("format-side", rows, meta)

        written = (tmp_path / "format-side.jsonl").read_bytes()
        assert written == _dump_rows(rows)
        meta_written = json.loads((tmp_path / "meta-format-side.json").read_text(encoding="utf-8"))
        assert meta_written["batch_mode"] == "format-check"
        assert meta_written["side"] == "format-side"
