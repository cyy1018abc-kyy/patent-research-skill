"""撰写正文一致性基准（4.3 / M2）的评分器退化检测。

评分器最危险的失败模式是只会打满分的橡皮图章。本测试：
* 金标准（全部案例）必须 perfect——检出全部注入缺陷且零误报；
* 删掉一条期望 → 必须出现误报（证明评分器真的在比对实际发现）；
* 伪造一条期望 → 必须出现漏检；
* 在干净稿里注入一个缺陷 → 内核必须检出，干净稿不再干净；
* 案例格式错误 → 拒评（CaseError）。
"""

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("score_drafting", ROOT / "tools/score_drafting.py")
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)

CASES = ROOT / "benchmarks/drafting/cases"


class DraftingBenchmark(unittest.TestCase):
    def setUp(self):
        self.paths = sorted(CASES.glob("*.yaml"))
        self.cases = {path.stem: scorer.load_case(path) for path in self.paths}

    def test_gold_suite_is_perfect(self):
        result = scorer.score_suite(self.paths)
        self.assertTrue(result["perfect"], scorer.render(result))
        self.assertGreaterEqual(len(result["cases"]), 4)
        # Both application types have a clean case (false-positive control) and a defect case.
        clean = [case for case in result["cases"] if case["expected"] == 0]
        self.assertGreaterEqual(len(clean), 2)
        # Every lint code M-002…M-015 is exercised by at least one seeded defect.
        self.assertEqual(result["codes_covered"], [f"M-{n:03d}" for n in range(2, 16)])

    def test_dropping_an_expectation_surfaces_a_false_positive(self):
        case = copy.deepcopy(self.cases["dm02-um-defects"])
        dropped = case["expected"].pop(0)
        scored = scorer.score_case(case)
        self.assertIn(f"{dropped['code']} @ {dropped['path']}", scored["unexpected"])

    def test_inventing_an_expectation_surfaces_a_miss(self):
        case = copy.deepcopy(self.cases["dm01-um-clean"])
        case["expected"] = [{"code": "M-006", "path": "abstract"}]
        scored = scorer.score_case(case)
        self.assertEqual(scored["missed"], ["M-006 @ abstract"])
        self.assertEqual(scored["detection_rate"], 0.0)

    def test_injected_defect_in_clean_case_is_detected(self):
        case = copy.deepcopy(self.cases["dm03-inv-clean"])
        case["claims"] = case["claims"].replace("根据权利要求3所述的", "根据权利要求2所述的")
        scored = scorer.score_case(case)
        self.assertIn("M-003 @ claims/4", scored["unexpected"])

    def test_malformed_case_is_rejected(self):
        broken = CASES / "dm01-um-clean.yaml"
        case = scorer.load_case(broken)
        self.assertEqual(case["id"], "dm01-um-clean")
        with self.assertRaises(scorer.CaseError):
            scorer.load_case(ROOT / "benchmarks/drafting/README.md")


if __name__ == "__main__":
    unittest.main()
