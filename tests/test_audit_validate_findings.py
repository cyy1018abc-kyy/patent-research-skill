"""Tests for audit/scripts/validate_findings.py (patent-audit three-verdict contract).

The validator is loaded by file path (same pattern as tests/test_reference_links.py)
because audit/scripts is a skill payload, not an installed package.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BM01_WORKSPACE = ROOT / "benchmarks" / "cases" / "bm01-timesync" / "workspace"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "audit_validate_findings", ROOT / "audit" / "scripts" / "validate_findings.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VF = _load_validator()


def confirmed_finding(**overrides):
    finding = {
        "verdict": "confirmed",
        "fingerprint": "MAP:F1:ZZ900011A1",
        "title": "F1 部分披露于 ZZ900011A1",
        "description": "对比文件在 [0004] 段披露信标携带发送时刻，但手段不同。",
        "element": "claims-map.md#F1",
        "trace": [
            {"kind": "element", "ref": "claims-map.md#F1", "description": "要素 F1"},
            {
                "kind": "disclosure",
                "ref": "02_search_logs/raw/ZZ900011A1.md#[0004]",
                "description": "披露发送时刻字段",
            },
        ],
        "evidence": [
            {
                "ref": "02_search_logs/raw/ZZ900011A1.md",
                "locator": "[0004]",
                "quote": "汇聚节点在射频开启前的最后一步将本地时刻写入该字段",
                "description": "披露发送时刻写入",
            }
        ],
        "mapping_rationale": "信标携带发送时刻与 F1 前半一致，构成部分披露。",
        "disclosure_extent": "partial",
        "distinctions": ["修正依据为直接写入而非队列深度预测"],
        "impact": {"category": "Y", "reason": "部分披露，组合影响创造性"},
        "independent_review": {"status": "verified", "reviewer": "a5-reviewer"},
        "confidence": {"score": "high", "reason": "原文逐字核对"},
    }
    finding.update(overrides)
    return finding


def needs_validation_finding(**overrides):
    finding = {
        "verdict": "needs_validation",
        "fingerprint": "MAP:F4:ZZ900014A1",
        "title": "F4 与重传请求帧疑似近义",
        "description": "重传请求帧与重同步请求帧一字之差。",
        "element": "claims-map.md#F4",
        "trace": [
            {"kind": "element", "ref": "claims-map.md#F4", "description": "要素 F4"},
            {
                "kind": "disclosure",
                "ref": "02_search_logs/raw/ZZ900014A1.md#[0006]",
                "description": "重传请求帧",
            },
        ],
        "evidence": [
            {
                "ref": "02_search_logs/raw/ZZ900014A1.md",
                "locator": "[0006]",
                "quote": "主动向网关发送重传请求帧",
                "description": "原文",
            }
        ],
        "claimed_rationale": "重传请求帧可能对应重同步请求帧",
        "blockers": ["缺少触发条件与载荷的完整段落"],
        "validation_plan": {"local": "重读全文核对触发条件"},
    }
    finding.update(overrides)
    return finding


def rejected_finding(**overrides):
    finding = {
        "verdict": "rejected",
        "fingerprint": "MAP:F2:ZZ900013A1",
        "title": "F2 与监听间隔调整无关",
        "description": "该文献调整监听间隔，不涉及漂移估计。",
        "element": "claims-map.md#F2",
        "trace": [
            {"kind": "element", "ref": "claims-map.md#F2", "description": "要素 F2"},
            {
                "kind": "disclosure",
                "ref": "02_search_logs/raw/ZZ900013A1.md#[0005]",
                "description": "监听间隔调整",
            },
        ],
        "evidence": [
            {
                "ref": "02_search_logs/raw/ZZ900013A1.md",
                "locator": "[0005]",
                "quote": "当任一邻居的流量计数超过突发门限时，节点缩短下一周期的监听间隔，以降低报文等待时延",
                "description": "仅监听间隔",
            }
        ],
        "claimed_rationale": "动态调整思想相近",
        "refutation": "对象是监听间隔而非时钟漂移，特征未披露；反证定位 [0005]",
    }
    finding.update(overrides)
    return finding


class ValidateFindingsTests(unittest.TestCase):
    def validate(self, findings, workspace=None):
        problems = VF.Problems()
        VF.walk_limits(findings, problems)
        VF.validate_document(findings, problems)
        if workspace is not None:
            VF.verify_evidence_against_workspace(findings, Path(workspace), problems)
        return problems.items

    def test_valid_three_verdict_document_passes(self):
        findings = sorted(
            [confirmed_finding(), needs_validation_finding(), rejected_finding()],
            key=lambda f: f["fingerprint"],
        )
        self.assertEqual(self.validate(findings), [])

    def test_document_must_be_sorted_and_unique(self):
        problems = VF.Problems()
        VF.validate_document(
            [confirmed_finding(), confirmed_finding(fingerprint="MAP:F1:ZZ900011A1")], problems
        )
        self.assertTrue(any("duplicate" in p for p in problems.items))
        problems = VF.Problems()
        VF.validate_document(
            [
                confirmed_finding(fingerprint="MAP:F1:B"),
                confirmed_finding(fingerprint="MAP:F1:A"),
            ],
            problems,
        )
        self.assertTrue(any("sorted lexicographically" in p for p in problems.items))

    def test_confirmed_forbids_claimed_fields(self):
        finding = confirmed_finding(claimed_rationale="x")
        problems = VF.Problems()
        VF.validate_finding(problems, 0, finding)
        self.assertTrue(any("must not contain" in p for p in problems.items))

    def test_confirmed_requires_independent_review(self):
        finding = confirmed_finding()
        del finding["independent_review"]
        problems = VF.Problems()
        VF.validate_finding(problems, 0, finding)
        self.assertTrue(any("independent_review" in p for p in problems.items))

    def test_needs_validation_cannot_carry_impact_or_confidence(self):
        finding = needs_validation_finding(
            impact={"category": "X", "reason": "r"}, confidence={"score": "high", "reason": "r"}
        )
        problems = VF.Problems()
        VF.validate_finding(problems, 0, finding)
        joined = "\n".join(problems.items)
        self.assertIn("'impact'", joined)
        self.assertIn("'confidence'", joined)

    def test_needs_validation_requires_blockers_and_plan(self):
        finding = needs_validation_finding(blockers=[], validation_plan={})
        problems = VF.Problems()
        VF.validate_finding(problems, 0, finding)
        joined = "\n".join(problems.items)
        self.assertIn("blockers", joined)
        self.assertIn("validation_plan", joined)

    def test_rejected_requires_refutation(self):
        finding = rejected_finding(refutation="")
        problems = VF.Problems()
        VF.validate_finding(problems, 0, finding)
        self.assertTrue(any("refutation" in p for p in problems.items))

    def test_partial_disclosure_forbids_category_x(self):
        finding = confirmed_finding(
            disclosure_extent="partial",
            impact={"category": "X", "reason": "r"},
            element_coverage={"elements": ["claims-map.md#F1"], "all_elements": True},
        )
        problems = VF.Problems()
        VF.validate_finding(problems, 0, finding)
        self.assertTrue(any("X cannot rest on" in p for p in problems.items))

    def test_category_x_requires_full_element_coverage(self):
        finding = confirmed_finding(
            disclosure_extent="full", impact={"category": "X", "reason": "r"}
        )
        problems = VF.Problems()
        VF.validate_finding(problems, 0, finding)
        self.assertTrue(any("all_elements" in p for p in problems.items))

    def test_trace_ordering_rules(self):
        finding = confirmed_finding()
        finding["trace"] = [
            {"kind": "disclosure", "ref": "a.md#[0001]", "description": "d"},
            {"kind": "element", "ref": "claims-map.md#F1", "description": "d"},
        ]
        problems = VF.Problems()
        VF.validate_finding(problems, 0, finding)
        joined = "\n".join(problems.items)
        self.assertIn("trace[0].kind", joined)
        self.assertIn("trace[1].kind", joined)

    def test_evidence_ref_rejects_unsafe_paths(self):
        for bad in ("..\\evil.md", "/abs/path.md", "C:\\x.md", "a/../b.md", "a/b "):
            finding = confirmed_finding()
            finding["evidence"] = [
                {"ref": bad, "locator": "[0004]", "quote": "汇聚节点", "description": "d"}
            ]
            problems = VF.Problems()
            VF.validate_finding(problems, 0, finding)
            self.assertTrue(
                any("safe workspace-relative" in p for p in problems.items), bad
            )

    @unittest.skipUnless(BM01_WORKSPACE.is_dir(), "bm01 corpus not present")
    def test_workspace_evidence_verbatim_passes(self):
        findings = [confirmed_finding()]
        self.assertEqual(self.validate(findings, BM01_WORKSPACE), [])

    @unittest.skipUnless(BM01_WORKSPACE.is_dir(), "bm01 corpus not present")
    def test_workspace_detects_locator_drift(self):
        finding = confirmed_finding()
        finding["evidence"][0]["locator"] = "[0005]"
        problems = VF.Problems()
        VF.verify_evidence_against_workspace([finding], BM01_WORKSPACE, problems)
        self.assertTrue(any("verbatim quote not found" in p for p in problems.items))

    @unittest.skipUnless(BM01_WORKSPACE.is_dir(), "bm01 corpus not present")
    def test_workspace_detects_missing_document(self):
        finding = confirmed_finding()
        finding["evidence"][0]["ref"] = "02_search_logs/raw/ZZ9FOO.md"
        problems = VF.Problems()
        VF.verify_evidence_against_workspace([finding], BM01_WORKSPACE, problems)
        self.assertTrue(any("not found under workspace" in p for p in problems.items))


class ValidateFindingsCliTests(unittest.TestCase):
    def _write(self, tmp: Path, findings) -> Path:
        path = tmp / "findings.json"
        path.write_text(
            json.dumps(findings, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return path

    def test_exit_codes_and_json_output(self):
        findings = sorted(
            [confirmed_finding(), needs_validation_finding(), rejected_finding()],
            key=lambda f: f["fingerprint"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), findings)
            self.assertEqual(VF.main([str(path), "--json"]), 0)
            broken = self._write(Path(tmp), [confirmed_finding(impact={"category": "Z"})])
            self.assertEqual(VF.main([str(broken)]), 1)
            self.assertEqual(VF.main([str(path / "missing.json")]), 2)


if __name__ == "__main__":
    unittest.main()
