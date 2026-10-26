"""基准评分器的退化检测：对 gold 的受控变体断言"指标必须退化"（或被内核当场拦下）。

评分器最危险的失败模式是变成只会打满分的橡皮图章。本测试对参考解做定向破坏：
* 内核可见的破坏（伪造 basis 引文 / 丢决策字段 / 改语料）→ validate 或语料完整性
  必须拒评（exit 2 语义）——这是内核先行的分层防御；
* 内核不可见、评分器可见的破坏（feature_mapping 引文 / 矩阵格 / 结论引用 /
  整条评估缺席）→ 对应指标必须按口径退化。
每个测试用例拿全新的 gold 副本，互不污染；gold 本身必须满分（与 CI 的
--gate perfect 互为冗余）。
"""

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("score_benchmark", ROOT / "tools/score_benchmark.py")
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)

CASE = ROOT / "benchmarks/cases/bm01-timesync"


class ScorerDegradation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="benchmark-scorer-test-")
        self.work = Path(self.temp.name) / "gold"
        shutil.copytree(CASE / "gold", self.work)

    def tearDown(self):
        self.temp.cleanup()

    def score(self):
        report, fatal = scorer.score_case(CASE, self.work)
        self.assertEqual(fatal, [], f"变体应当可评，但被拒：{fatal}")
        return report

    def score_rejected(self) -> list[str]:
        report, fatal = scorer.score_case(CASE, self.work)
        self.assertEqual(report, {})
        return fatal

    def _candidate_path(self, cid: str) -> Path:
        hits = sorted((self.work / "03_candidates").glob(f"{cid}-*.json"))
        self.assertEqual(len(hits), 1, hits)
        return hits[0]

    def _reset_to_unassessed(self, cid: str) -> None:
        """把候选整体退回"从未评估"的合法形态（等价脚手架状态）。"""
        path = self._candidate_path(cid)
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("assessment", "human_confirmation", "feature_mapping",
                    "review_history", "assessment_proposals", "reviewed_at"):
            data.pop(key, None)
        data.update({"novelty_check": "untouched", "role": "pool",
                     "relevance_problem": 3, "relevance_means": 3})
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    def test_gold_is_perfect(self):
        report = self.score()
        self.assertTrue(scorer.perfect(report))

    def test_kernel_rejects_fabricated_basis_quote(self):
        path = self._candidate_path("P-002")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["assessment"]["basis"]["N2@TGT-9001"]["means"]["quote"] = "本发明利用量子纠缠实现瞬时补偿"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        fatal = self.score_rejected()
        self.assertTrue(any("V029" in line or "error" in line for line in fatal), fatal)

    def test_unseen_feature_mapping_quote_degrades_precision(self):
        """feature_mapping 的引文内核不校验——这正是评分器 precision 要抓的面。

        变异后重算 assessment.fingerprint，模拟"评估时就这么写"的合法工作区
        （V030 确认过期只是 warn，不阻断评分）。"""
        from patentkit import assessment as assessment_mod
        from patentkit.model import load_candidates

        path = self._candidate_path("P-003")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["feature_mapping"]["F3"]["quote"] = "监听间隔按邻居数量的平方根动态伸缩"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        cand = next(c for c in load_candidates(self.work) if c.id == "P-003")
        data["assessment"]["fingerprint"] = assessment_mod.fingerprint(cand, self.work)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        report = self.score()
        # coverage 不变是正确行为：该段同被 P-003 的 basis 引文覆盖（coverage 按段落对去重）
        self.assertLess(report["citation"]["precision"], 1.0)

    def test_unassessed_candidate_becomes_omission_and_misjudgment(self):
        self._reset_to_unassessed("P-003")
        report = self.score()
        self.assertIn("F3", report["features"]["omissions"])
        self.assertGreater(report["features"]["omission_rate"], 0.0)
        mismatches = " ".join(report["judgment"]["mismatches"])
        # 矩阵是独立产物，仍自洽（列还在、格没变）——不产生矩阵误判点
        for needle in ("P-003.role", "P-003.novelty_check", "P-003.F3.status"):
            self.assertIn(needle, mismatches, mismatches)

    def test_flipped_matrix_cell_is_a_misjudgment(self):
        matrix = self.work / "04_comparative_analysis" / "comparison_matrix.md"
        text = matrix.read_text(encoding="utf-8")
        old = "| **N1：信标发送时刻估计** | ○ | — | — |"
        new = "| **N1：信标发送时刻估计** | — | — | — |"
        self.assertIn(old, text)
        matrix.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        report = self.score()
        self.assertTrue(any("matrix[N1][P-001]" in m for m in report["judgment"]["mismatches"]),
                        report["judgment"]["mismatches"])
        self.assertGreater(report["judgment"]["misjudgment_rate"], 0.0)

    def test_missing_conclusion_citation_is_a_misjudgment(self):
        concl = self.work / "05_novelty_conclusions" / "conclusions.md"
        text = concl.read_text(encoding="utf-8")
        concl.write_text(text.replace("P-001", "P-00X"), encoding="utf-8", newline="\n")
        report = self.score()
        self.assertTrue(any("conclusions.cite[P-001]" in m for m in report["judgment"]["mismatches"]))

    def test_modified_corpus_is_rejected(self):
        raw = self.work / "02_search_logs/raw/ZZ900011A1.md"
        text = raw.read_text(encoding="utf-8")
        raw.write_text(text.replace("汇聚节点", "中心节点"), encoding="utf-8", newline="\n")
        fatal = self.score_rejected()
        self.assertTrue(any("语料被改动" in line for line in fatal))

    def test_invalid_workspace_is_rejected(self):
        path = self._candidate_path("P-003")
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("novelty_check")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        fatal = self.score_rejected()
        self.assertTrue(any("error" in line for line in fatal), fatal)


if __name__ == "__main__":
    unittest.main()
