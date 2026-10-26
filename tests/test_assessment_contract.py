"""技能包装层只检查协议与输出契约，不复制内核的门槛计算。"""

import contextlib
import importlib.util
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("skill_env", ROOT / "research/scripts/_env.py")
env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(env)


class AssessmentContract(unittest.TestCase):
    def setUp(self):
        env._REQUIRED = False
        self.package = types.ModuleType("patentkit")
        self.package.__path__ = []

    def test_old_kernel_is_rejected_as_one_json(self):
        output = io.StringIO()
        with patch.dict(sys.modules, {"patentkit": self.package, "patentkit.assessment": None}):
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as caught:
                env.require_patentkit(as_json=True)
        self.assertEqual(caught.exception.code, 3)
        result = json.loads(output.getvalue())
        self.assertEqual(result["code"], 3)
        self.assertIn("0.7.0", result["error"])

    def test_supported_protocol_is_accepted_without_output(self):
        protocol = types.ModuleType("patentkit.assessment")
        protocol.PROTOCOL_VERSION = 1
        output = io.StringIO()
        with patch.dict(sys.modules, {"patentkit": self.package, "patentkit.assessment": protocol}):
            with contextlib.redirect_stdout(output):
                env.require_patentkit(as_json=True)
        self.assertTrue(env._REQUIRED)
        self.assertEqual(output.getvalue(), "")

    def test_unrecognized_protocol_is_rejected(self):
        protocol = types.ModuleType("patentkit.assessment")
        protocol.PROTOCOL_VERSION = 99
        with patch.dict(sys.modules, {"patentkit": self.package, "patentkit.assessment": protocol}):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
                env.require_patentkit(as_json=True)
        self.assertEqual(caught.exception.code, 3)

    def test_skill_and_sample_keep_source_and_judgment_separate(self):
        skill = (ROOT / "research/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("version: 3.5.0", skill)
        self.assertIn("07-assessment-protocol.md", skill)
        self.assertNotIn("conclusion is downgraded to `asserted`", skill)
        sample = json.loads((ROOT / "research/assets/sample_data/candidates_example.json").read_text(encoding="utf-8"))
        self.assertEqual(sample["assessment"]["actor"], "unknown")
        self.assertIsNone(sample["human_confirmation"])


if __name__ == "__main__":
    unittest.main()
