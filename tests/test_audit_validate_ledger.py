"""Tests for audit/scripts/validate_ledger.py (patent-audit coverage ledger contract).

The validator is loaded by file path (same pattern as tests/test_reference_links.py)
because audit/scripts is a skill payload, not an installed package.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "audit_validate_ledger", ROOT / "audit" / "scripts" / "validate_ledger.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VL = _load_validator()


def encode_ref(value: str) -> str:
    raw = value.encode("utf-8")
    return "".join(
        chr(byte) if byte in VL._UNRESERVED else f"%{byte:02X}" for byte in raw
    )


def make_unit(**overrides):
    refs = {
        "element": "claims-map.md#F1",
        "source": "02_search_logs/queries.jsonl#cnipa-fulltext",
        "klass": "claims-map.md#klass/G06F",
    }
    unit = {
        "coverage_id": "::".join(encode_ref(refs[k]) for k in ("element", "source", "klass")),
        "canonical_refs": refs,
        "element": "信标发送时刻估计",
        "source": "cnipa-fulltext",
        "klass": "G06F",
        "starting_paths": ["02_search_logs/raw/"],
        "query_plan_block": None,
        "prior_status": "none",
        "attempts": [],
        "wave": 1,
        "status": "planned",
        "agent_id": None,
        "reviewed_paths": [],
        "checks": [],
        "result_fingerprints": [],
        "unresolved": [],
    }
    unit.update(overrides)
    return unit


def make_ledger(units=None, **overrides):
    ledger = {
        "schema_version": "patent-audit-ledger/1",
        "run_id": "audit-bm01-run-1",
        "target": "TGT-9001",
        "profile": "standard",
        "mode": "single",
        "units": units if units is not None else [make_unit()],
    }
    ledger.update(overrides)
    return ledger


def hunter_unit(**overrides):
    """A candidate-state unit with owned evidence."""
    unit = make_unit(
        status="candidate",
        agent_id="a2-hunter",
        wave=2,
        canonical_refs={
            "element": "claims-map.md#F2",
            "source": "02_search_logs/queries.jsonl#cnipa-fulltext",
            "klass": "claims-map.md#klass/G06F",
        },
        reviewed_paths=["02_search_logs/raw/ZZ900012A1.md"],
        checks=[
            {
                "agent_id": "a2-hunter",
                "method": "source",
                "artifact": None,
                "description": "复核 ZZ900012A1 [0006]",
                "reviewed_paths": ["02_search_logs/raw/ZZ900012A1.md"],
            }
        ],
        result_fingerprints=["MAP:F2:ZZ900012A1"],
    )
    unit["coverage_id"] = "::".join(
        encode_ref(unit["canonical_refs"][k]) for k in ("element", "source", "klass")
    )
    unit.update(overrides)
    return unit


class ValidateLedgerTests(unittest.TestCase):
    def validate(self, ledger):
        problems = VL.Problems()
        VL.validate_ledger(ledger, problems)
        return problems.items

    def test_valid_ledger_passes(self):
        self.assertEqual(self.validate(make_ledger()), [])
        self.assertEqual(self.validate(make_ledger(units=[make_unit(), hunter_unit()])), [])

    def test_state_table_rejects_evidence_on_planned(self):
        unit = make_unit(reviewed_paths=["a.md"], checks=[{"agent_id": "a", "x": 1}])
        problems = VL.Problems()
        VL.validate_unit(problems, 0, unit)
        self.assertTrue(any("requires empty" in p for p in problems.items))

    def test_covered_requires_evidence(self):
        # covered with owned evidence and no fingerprints is the canonical covered state
        self.assertEqual(
            self.validate(make_ledger(units=[hunter_unit(status="covered", result_fingerprints=[])])),
            [],
        )
        # covered without evidence is a bare claim, not coverage
        problems = VL.Problems()
        VL.validate_unit(
            problems,
            0,
            hunter_unit(status="covered", result_fingerprints=[], checks=[], reviewed_paths=[]),
        )
        self.assertTrue(
            any("requires non-empty reviewed_paths and checks" in p for p in problems.items)
        )

    def test_blocked_requires_unresolved_reason(self):
        unit = hunter_unit(status="blocked", result_fingerprints=[], unresolved=[])
        problems = VL.Problems()
        VL.validate_unit(problems, 0, unit)
        self.assertTrue(any("non-empty unresolved" in p for p in problems.items))

    def test_duplicate_coverage_id_is_collision(self):
        problems = VL.Problems()
        VL.validate_ledger(make_ledger(units=[make_unit(), make_unit()]), problems)
        self.assertTrue(any("duplicate" in p for p in problems.items))

    def test_units_must_be_sorted(self):
        problems = VL.Problems()
        VL.validate_ledger(make_ledger(units=[hunter_unit(), make_unit()]), problems)
        self.assertTrue(any("sorted lexicographically" in p for p in problems.items))

    def test_coverage_id_must_match_derivation(self):
        unit = make_unit(coverage_id="bogus::id")
        problems = VL.Problems()
        VL.validate_unit(problems, 0, unit)
        self.assertTrue(any("canonical_refs derivation" in p for p in problems.items))

    def test_agent_id_must_be_canonical(self):
        for bad in ("A2-Hunter", "CON", "-leading", "a" * 65):
            unit = hunter_unit(agent_id=bad)
            problems = VL.Problems()
            VL.validate_unit(problems, 0, unit)
            self.assertTrue(any("canonical" in p for p in problems.items), bad)

    def test_source_check_must_not_carry_artifact(self):
        unit = hunter_unit()
        unit["checks"][0]["artifact"] = "agents/a2-hunter/artifacts/x.json"
        problems = VL.Problems()
        VL.validate_unit(problems, 0, unit)
        self.assertTrue(any('must be null for method "source"' in p for p in problems.items))

    def test_search_check_artifact_must_stay_in_agents_tree(self):
        unit = hunter_unit()
        unit["checks"][0]["method"] = "search"
        unit["checks"][0]["artifact"] = "elsewhere/result.jsonl"
        problems = VL.Problems()
        VL.validate_unit(problems, 0, unit)
        self.assertTrue(any("agents/<agent_id>/artifacts/" in p for p in problems.items))

    def test_unit_reviewed_paths_must_equal_union(self):
        unit = hunter_unit(reviewed_paths=["02_search_logs/raw/other.md"])
        problems = VL.Problems()
        VL.validate_unit(problems, 0, unit)
        self.assertTrue(any("union" in p for p in problems.items))

    def test_attempt_archive_rules(self):
        unit = hunter_unit(
            attempts=[
                {
                    "wave": 2,
                    "status": "covered",
                    "agent_id": "a2-hunter",
                    "reviewed_paths": ["a.md"],
                    "checks": [],
                    "result_fingerprints": [],
                    "unresolved": [],
                    "reassignment_reason": "critic found generic checks",
                }
            ]
        )
        problems = VL.Problems()
        VL.validate_unit(problems, 0, unit)
        self.assertTrue(any("below the live wave" in p for p in problems.items))

        unit["attempts"][0]["wave"] = 1
        unit["attempts"][0]["status"] = "planned"
        problems = VL.Problems()
        VL.validate_unit(problems, 0, unit)
        self.assertTrue(any("blocked/covered/candidate" in p for p in problems.items))

    def test_prior_status_enum(self):
        unit = make_unit(prior_status="prior_confirmed")
        problems = VL.Problems()
        VL.validate_unit(problems, 0, unit)
        self.assertTrue(any("prior_status" in p for p in problems.items))

    def test_percent_encoding_is_uppercase_rfc3986(self):
        self.assertEqual(VL.percent_encode_reference("a b"), "a%20b")
        self.assertEqual(VL.percent_encode_reference("要素"), "%E8%A6%81%E7%B4%A0")
        self.assertEqual(VL.percent_encode_reference("a-b._~"), "a-b._~")


class ValidateLedgerCliTests(unittest.TestCase):
    def test_module_entry_rejects_bad_schema_version(self):
        problems = VL.Problems()
        VL.validate_ledger(make_ledger(schema_version="patent-audit-ledger/9"), problems)
        self.assertTrue(any("schema_version" in p for p in problems.items))


if __name__ == "__main__":
    unittest.main()
