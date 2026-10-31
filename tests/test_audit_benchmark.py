"""Audit-mode benchmark regression tests (bm01/bm02).

Locks the score_audit_findings.py contract: the gold self-check must reach the
perfect gate, and every degenerate variant (locator drift, false confirmations,
dropped disclosures, missing independent review) must score below it — the
anti-rubber-stamp property the audit benchmark adds on top of the Cloudflare
methodology.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402


def _load_scorer():
    spec = importlib.util.spec_from_file_location(
        "score_audit_findings", ROOT / "tools" / "score_audit_findings.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCORER = _load_scorer()
CASES = {
    name: ROOT / "benchmarks" / "cases" / name
    for name in ("bm01-timesync", "bm02-bms")
}


def gold_findings(case_dir: Path) -> list:
    ground_truth = yaml.safe_load(
        (case_dir / "ground_truth.yaml").read_text(encoding="utf-8")
    )
    return SCORER.gold_findings_document(ground_truth)


@unittest.skipUnless(CASES["bm01-timesync"].is_dir(), "benchmark cases not present")
class AuditBenchmarkGoldTests(unittest.TestCase):
    def test_gold_selfcheck_reaches_perfect_gate(self):
        for name, case_dir in CASES.items():
            with self.subTest(case=name):
                result = SCORER.score(case_dir, gold_findings(case_dir), SCORER.load_ground_truth(case_dir))
                self.assertEqual(result["validation_errors"], [])
                for metric, value in result["metrics"].items():
                    self.assertEqual(value, 1.0, f"{name}/{metric}: {result}")

    def test_emitted_gold_findings_pass_contract_validator(self):
        problems = []
        for name, case_dir in CASES.items():
            findings = gold_findings(case_dir)
            local = SCORER.VF.Problems()
            SCORER.VF.walk_limits(findings, local)
            SCORER.VF.validate_document(findings, local)
            problems.extend(f"{name}: {p}" for p in local.items)
        self.assertEqual(problems, [])


class AuditDegenerationTests(unittest.TestCase):
    """Degenerate variants must lose points — no rubber stamps."""

    @classmethod
    def setUpClass(cls):
        cls.case = CASES["bm01-timesync"]
        cls.ground_truth = SCORER.load_ground_truth(cls.case)
        cls.gold = gold_findings(cls.case)
        cls.absent_feature = next(
            (pid, feature)
            for pid, cand in cls.ground_truth["candidates"].items()
            for feature, disc in (cand.get("disclosure") or {}).items()
            if disc.get("status") == "absent"
        )

    def score(self, findings):
        return SCORER.score(self.case, findings, self.ground_truth)

    def test_locator_drift_loses_evidence_integrity(self):
        degraded = copy.deepcopy(self.gold)
        degraded[0]["evidence"][0]["locator"] = "[0001]"
        result = self.score(degraded)
        self.assertLess(result["metrics"]["evidence_integrity"], 1.0)

    def test_false_confirmation_of_absent_feature_loses_precision(self):
        degraded = copy.deepcopy(self.gold)
        _pid, feature = self.absent_feature
        decoy = copy.deepcopy(degraded[0])
        decoy["fingerprint"] = f"MAP:{feature}:ZZ9DECOY"
        decoy["element"] = f"claims-map.md#{feature}"
        decoy["title"] = "陷阱映射"
        result = self.score(degraded + [decoy])
        self.assertLess(result["metrics"]["mapping_precision"], 1.0)
        # the decoy maps an absent feature (its copied evidence keeps the donor doc)
        self.assertTrue(
            any(fp.startswith(f"{feature}@") for fp in result["false_positives"]),
            result["false_positives"],
        )

    def test_dropped_disclosure_loses_coverage(self):
        degraded = self.gold[1:]
        result = self.score(degraded)
        self.assertLess(result["metrics"]["mapping_coverage"], 1.0)
        self.assertTrue(result["missed_gold"])

    def test_missing_independent_review_loses_discipline(self):
        degraded = copy.deepcopy(self.gold)
        del degraded[0]["independent_review"]
        result = self.score(degraded)
        self.assertEqual(result["metrics"]["verdict_discipline"], 0.0)

    def test_gate_exit_codes(self):
        with self.subTest("gold passes the gate"):
            self.assertEqual(SCORER.main([
                "--case", str(self.case),
                "--gold-selfcheck", "--gate", "perfect", "--json",
            ]), 0)
        with self.subTest("degraded fails the gate"):
            with unittest.mock.patch.object(
                SCORER,
                "gold_findings_document",
                return_value=self.gold[1:],
            ):
                self.assertEqual(SCORER.main([
                    "--case", str(self.case),
                    "--gold-selfcheck", "--gate", "perfect", "--json",
                ]), 1)

    def test_mutually_exclusive_input_flags(self):
        self.assertEqual(SCORER.main([
            "--case", str(self.case),
            "--findings", "x.json", "--gold-selfcheck",
        ]), 2)


if __name__ == "__main__":
    unittest.main()
