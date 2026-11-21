"""Unit tests for CrossEncoderReranker (4.3 CE1) — stub backend, zero downloads."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from patent_intel.retrieval.reranker import CrossEncoderReranker  # noqa: E402

TEXTS = {"d1": "alpha cell", "d2": "beta electrode", "d3": "gamma membrane"}


class _StubModel:
    """Deterministic stub: score = hash-free rule on (query, text) pair count."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs, batch_size=8, show_progress_bar=False):
        self.calls.append(list(pairs))
        if self.fail:
            raise RuntimeError("stub inference failure")
        return [float(len(text.split()) % 3) for _q, text in pairs]


def _make(*, fail: bool = False, **kw) -> tuple[CrossEncoderReranker, _StubModel]:
    r = CrossEncoderReranker(TEXTS, model_path="stub-path", **kw)
    stub = _StubModel(fail=fail)
    r._model = stub  # bypass _require_model (no real weights in unit tests)
    return r, stub


class CrossEncoderRerankerTests(unittest.TestCase):
    def test_same_ids_same_length(self):
        r, _ = _make()
        candidates = [("d2", 1.0), ("d1", 0.9), ("d3", 0.8)]
        out = r.rerank("cell", candidates)
        self.assertEqual([d for d, _ in out], ["d1", "d2", "d3"])  # all 1-word → 1.0, tie by id
        self.assertEqual(sorted(d for d, _ in out), ["d1", "d2", "d3"])

    def test_deterministic_and_tie_by_doc_id(self):
        r, _ = _make()
        candidates = [("d3", 0.1), ("d1", 0.2), ("d2", 0.3)]
        a = r.rerank("q", candidates)
        b = r.rerank("q", candidates)
        self.assertEqual(a, b)
        scores = dict(a)
        self.assertEqual(scores["d1"], scores["d2"])  # tie → doc_id ascending
        self.assertLess(a.index(("d1", scores["d1"])), a.index(("d2", scores["d2"])))

    def test_scores_descending(self):
        texts = {"long": "a b c d e f", "short": "x"}
        r = CrossEncoderReranker(texts, model_path="stub-path")
        r._model = _StubModel()
        out = r.rerank("q", [("short", 9.0), ("long", 1.0)])
        # stub scores: long → 6 words % 3 = 0.0, short → 1 word % 3 = 1.0 → short first
        self.assertEqual(out, [("short", 1.0), ("long", 0.0)])

    def test_missing_text_raises_loud(self):
        r, _ = _make()
        with self.assertRaises(ValueError) as ctx:
            r.rerank("q", [("d1", 1.0), ("ghost-999", 0.5)])
        self.assertIn("ghost-999", str(ctx.exception))
        self.assertIn("refusing to reorder", str(ctx.exception))

    def test_empty_candidates(self):
        r, _ = _make()
        self.assertEqual(r.rerank("q", []), [])

    def test_predict_failure_propagates(self):
        r, _ = _make(fail=True)
        with self.assertRaises(RuntimeError):
            r.rerank("q", [("d1", 1.0)])  # caller (pipeline) owns degradation

    def test_name_carries_model_dir(self):
        r, _ = _make()
        self.assertTrue(r.name.startswith("cross-encoder:"))
        self.assertIn("stub-path", r.name)

    def test_missing_weights_error_mentions_path(self):
        r = CrossEncoderReranker(TEXTS, model_path="F:/definitely/not/there")
        with self.assertRaises(RuntimeError) as ctx:
            r.rerank("q", [("d1", 1.0)])
        self.assertIn("materialize offline", str(ctx.exception))
        self.assertIn("no implicit download", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
