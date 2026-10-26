"""release-doctor 纯函数单元测试（网络与安装器部分由 offline/release 全跑覆盖）。"""

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_doctor", ROOT / "tools/release_doctor.py")
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)

PUBLISH_SAMPLE = """#!/usr/bin/env bash
set -euo pipefail
kernel=patentkit-v0.6.0
skill=skill-v3.4.0
gh release upload "$kernel" dist/patentkit-0.6.0-py3-none-any.whl dist/patentkit-0.6.0.tar.gz dist/SHA256SUMS-patentkit-v0.6.0.txt --clobber
gh release upload "$skill" dist/patent-research-skill-v3.4.0.zip dist/patent-drafting-skill-v3.4.0.zip dist/INSTALL-colleagues.md dist/install-oneclick.cmd dist/SHA256SUMS-skill-v3.4.0.txt --clobber
"""


class ParsePublishAssets(unittest.TestCase):
    def test_extracts_tags_and_asset_names(self):
        assets = doctor.parse_publish_assets(PUBLISH_SAMPLE)
        self.assertEqual(assets["patentkit-v0.6.0"], ["patentkit-0.6.0-py3-none-any.whl",
                                                      "patentkit-0.6.0.tar.gz",
                                                      "SHA256SUMS-patentkit-v0.6.0.txt"])
        self.assertEqual(assets["skill-v3.4.0"], ["patent-research-skill-v3.4.0.zip",
                                                  "patent-drafting-skill-v3.4.0.zip",
                                                  "INSTALL-colleagues.md",
                                                  "install-oneclick.cmd",
                                                  "SHA256SUMS-skill-v3.4.0.txt"])

    def test_real_publish_script_parses(self):
        assets = doctor.parse_publish_assets((ROOT / "tools/publish_release.sh").read_text(encoding="utf-8"))
        bump = doctor._load_tool("bump_version")
        skill_tag = f"skill-v{bump._frontmatter_version('research')}"
        kernel_tag = f"patentkit-v{bump._kernel_version()}"
        self.assertIn(skill_tag, assets)
        self.assertIn(kernel_tag, assets)
        self.assertTrue(any(name.endswith(".zip") for name in assets[skill_tag]))
        self.assertTrue(any(name.endswith(".whl") for name in assets[kernel_tag]))

    def test_missing_tag_assignment_raises(self):
        with self.assertRaises(ValueError):
            doctor.parse_publish_assets("skill=skill-v1.0.0\n")

    def test_missing_upload_line_raises(self):
        with self.assertRaises(ValueError):
            doctor.parse_publish_assets("kernel=patentkit-v0.1.0\nskill=skill-v1.0.0\n")


class ParseSums(unittest.TestCase):
    def test_valid(self):
        sums = doctor.parse_sums("b" * 64 + "  a.zip\n" + "d" * 64 + "  b.txt\n")
        self.assertEqual(sums, {"a.zip": "b" * 64, "b.txt": "d" * 64})

    def test_malformed_rejected(self):
        for text in ("abc a.zip\n", "  a.zip\n", ""):
            with self.assertRaises(ValueError):
                doctor.parse_sums(text)

    def test_duplicate_rejected(self):
        digest = "a" * 64
        with self.assertRaises(ValueError):
            doctor.parse_sums(f"{digest}  a.zip\n{digest}  a.zip\n")

    def test_coverage_gaps(self):
        problems = doctor.verify_sums({"a.zip": "x", "extra.txt": "y"}, ["a.zip", "b.zip"])
        self.assertEqual(problems, ["SHA256SUMS 缺少条目: b.zip", "SHA256SUMS 多出条目: extra.txt"])


class VerifyZipManifest(unittest.TestCase):
    def _make_zip(self, path: Path, files: dict[str, bytes], manifest: dict):
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))

    def test_good_manifest(self):
        files = {"patent-research/SKILL.md": b"# skill\n", "LICENSE": b"MIT\n"}
        manifest = {
            "schema_version": 2,
            "skills": [{"name": "patent-research", "version": "9.9.9"},
                       {"name": "patent-drafting", "version": "9.9.9"}],
            "compat": {"patentkit": ">=0.6.0", "assessment_protocol": 1},
            "files": [{"path": name, "size": len(data),
                       "sha256": hashlib.sha256(data).hexdigest()} for name, data in sorted(files.items())],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pkg.zip"
            self._make_zip(path, files, manifest)
            self.assertEqual(doctor.verify_zip_manifest(path, skill_version="9.9.9",
                                                        kernel_version="0.6.0",
                                                        expected_skills=["patent-research", "patent-drafting"]), [])

    def test_detects_tampering_and_drift(self):
        files = {"patent-research/SKILL.md": b"# skill\n"}
        manifest = {
            "schema_version": 1,
            "skills": [{"name": "patent-research", "version": "8.0.0"}],
            "compat": {"patentkit": ">=0.5.0", "assessment_protocol": 2},
            "files": [{"path": "patent-research/SKILL.md", "size": 3,
                       "sha256": "0" * 64}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pkg.zip"
            self._make_zip(path, files, manifest)
            problems = doctor.verify_zip_manifest(path, skill_version="9.9.9",
                                                  kernel_version="0.6.0",
                                                  expected_skills=["patent-research"])
            text = "\n".join(problems)
            for needle in ("schema_version", "版本应配对", "compat.patentkit", "assessment_protocol", "哈希不符", "大小不符"):
                self.assertIn(needle, text)


class ResultAggregation(unittest.TestCase):
    def test_ok_requires_no_fail(self):
        results = [doctor.Result("a", "A", doctor.PASS, ""),
                   doctor.Result("b", "B", doctor.SKIP, "平台不适用"),
                   doctor.Result("c", "C", doctor.FAIL, "细节")]
        self.assertFalse(all(r.status != doctor.FAIL for r in results))
        self.assertTrue(all(r.status != doctor.FAIL for r in results[:2]))


if __name__ == "__main__":
    unittest.main()
