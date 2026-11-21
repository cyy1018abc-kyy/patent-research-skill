"""Unit tests for 4.3 P0-GAP passage chunking and aggregation (pure Python)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "benchmarks" / "retrieval"))

from passage import aggregate_passage_hits, chunk_words  # noqa: E402


class ChunkWordsTests(unittest.TestCase):
    def test_deterministic_and_covers_all_words(self):
        words = [f"w{i}" for i in range(250)]
        text = " ".join(words)
        a = chunk_words(text, max_words=100)
        b = chunk_words(text, max_words=100)
        self.assertEqual(a, b)
        self.assertEqual(sum(len(c.split()) for c in a), 250)
        self.assertEqual(a[0].split()[0], "w0")
        self.assertEqual(a[-1].split()[-1], "w249")

    def test_stride_overlap(self):
        text = " ".join(f"w{i}" for i in range(100))
        chunks = chunk_words(text, max_words=40, stride=20)
        # windows start at 0,20,40,60 → 4 windows, coverage preserved
        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[1].split()[0], "w20")

    def test_min_words_filter_keeps_first_chunk(self):
        text = " ".join(f"w{i}" for i in range(60))
        chunks = chunk_words(text, max_words=50, min_words=40)
        # first chunk (50 words) kept; tail (10 words) filtered
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0].split()), 50)

    def test_short_text_single_chunk_even_below_min(self):
        text = "only three words here"
        self.assertEqual(chunk_words(text, max_words=100, min_words=50), [text])

    def test_empty_text(self):
        self.assertEqual(chunk_words("   "), [])

    def test_invalid_params(self):
        with self.assertRaises(ValueError):
            chunk_words("a b c", max_words=0)
        with self.assertRaises(ValueError):
            chunk_words("a b c", max_words=10, stride=0)
        with self.assertRaises(ValueError):
            chunk_words("a b c", max_words=10, stride=11)


class AggregateTests(unittest.TestCase):
    def test_maxp_keeps_best_passage(self):
        hits = [("f1#p0000", 1.0), ("f1#p0001", 3.0), ("f2#p0000", 2.0)]
        out = aggregate_passage_hits(hits, method="maxp")
        self.assertEqual(out, [("f1", 3.0), ("f2", 2.0)])

    def test_avg_top3_uses_up_to_three(self):
        hits = [(f"f1#p{i:04d}", s) for i, s in enumerate([5.0, 4.0, 3.0, 1.0])]
        out = aggregate_passage_hits(hits, method="avg_top3")
        self.assertAlmostEqual(out[0][1], (5.0 + 4.0 + 3.0) / 3)
        # input order must not matter
        shuffled = list(reversed(hits))
        out2 = aggregate_passage_hits(shuffled, method="avg_top3")
        self.assertEqual(out, out2)

    def test_tie_break_by_family_id(self):
        hits = [("fb#p0000", 2.0), ("fa#p0000", 2.0)]
        out = aggregate_passage_hits(hits, method="maxp")
        self.assertEqual([f for f, _ in out], ["fa", "fb"])

    def test_non_passage_id_defensive(self):
        out = aggregate_passage_hits([("plainfamily", 1.5)], method="maxp")
        self.assertEqual(out, [("plainfamily", 1.5)])

    def test_unknown_method(self):
        with self.assertRaises(ValueError):
            aggregate_passage_hits([], method="sump")


if __name__ == "__main__":
    unittest.main()
