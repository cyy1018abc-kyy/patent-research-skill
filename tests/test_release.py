"""在隔离目录验收正式安装包（v3.0.0 起为双产物：全量包 + drafting 单技能包）、
安装器和旧工作区迁移。"""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_builder", ROOT / "tools/build_skill_release.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ReleaseAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="patent-release-test-")
        cls.root = Path(cls.temp.name)
        cls.result = builder.build(cls.root / "dist", "2026-10-25T00:00:00+00:00")
        cls.full_zip = ROOT / "dist/patent-research-skill-v3.4.0.zip"
        cls.drafting_zip = ROOT / "dist/patent-drafting-skill-v3.4.0.zip"
        if not cls.full_zip.is_file() or not cls.drafting_zip.is_file():
            raise AssertionError("Build both release ZIPs in dist before acceptance (full + drafting)")
        cls.package = cls.root / "package"
        with zipfile.ZipFile(cls.full_zip) as archive:
            archive.extractall(cls.package)
        cls.drafting_package = cls.root / "drafting_package"
        with zipfile.ZipFile(cls.drafting_zip) as archive:
            archive.extractall(cls.drafting_package)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_command(self, *args, expected=0):
        env = os.environ.copy()
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(args[0] if len(args) == 1 else args, cwd=self.package, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_package_hashes_layout_and_reproducibility(self):
        for package_zip in (self.full_zip, self.drafting_zip):
            with zipfile.ZipFile(package_zip) as archive:
                names = {name for name in archive.namelist() if not name.endswith("/")}
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(names - {"manifest.json"}, {item["path"] for item in manifest["files"]})
                for item in manifest["files"]:
                    data = archive.read(item["path"])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
                    self.assertEqual(len(data), item["size"])
                self.assertEqual(manifest["schema_version"], 2)
                self.assertEqual(manifest["compat"]["assessment_protocol"], 1)
        full_names = zipfile.ZipFile(self.full_zip).namelist()
        self.assertIn("patent-research/SKILL.md", full_names)
        self.assertIn("patent-drafting/SKILL.md", full_names)
        drafting_names = zipfile.ZipFile(self.drafting_zip).namelist()
        self.assertIn("patent-drafting/SKILL.md", drafting_names)
        self.assertNotIn("patent-research/SKILL.md", drafting_names)
        full_manifest = json.loads(zipfile.ZipFile(self.full_zip).read("manifest.json"))
        self.assertEqual([s["name"] for s in full_manifest["skills"]],
                         ["patent-research", "patent-drafting"])
        self.assertTrue(full_manifest["contents"]["samples_included"])
        single_manifest = json.loads(zipfile.ZipFile(self.drafting_zip).read("manifest.json"))
        self.assertEqual([s["name"] for s in single_manifest["skills"]], ["patent-drafting"])
        self.assertFalse(single_manifest["contents"]["samples_included"])
        self.assertFalse(any("__pycache__" in n or n.endswith(".pyc") for n in full_names))
        second = builder.build(self.root / "repeat", "2026-10-25T00:00:00+00:00")
        self.assertEqual(self.result["zips"]["full"]["sha256"], second["zips"]["full"]["sha256"])
        self.assertEqual(self.result["zips"]["drafting"]["sha256"], second["zips"]["drafting"]["sha256"])

    def test_reference_links_resolve_inside_each_installed_payload(self):
        """安装后的体验验收：解包后的每个正式包里，相对链接都必须在载荷内闭合。

        仓库目录里 `../` 能解析的链接在安装后（单技能目录）是死链；跨技能导航必须
        走文内的技能交接说明。工具与 CI 同款（tools/check_reference_links.py）。
        """
        checker = ROOT / "tools" / "check_reference_links.py"
        for package in (self.package, self.drafting_package):
            result = subprocess.run(
                [sys.executable, str(checker), "--root", str(package), "--quiet"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sample_and_expected_gate_failure(self):
        scripts = self.package / "patent-research/scripts"
        sample = self.package / "samples/sample_workspace"
        validation = self.run_command(sys.executable, str(scripts / "validate.py"), "--root", str(sample), "--strict", "--json")
        self.assertTrue(json.loads(validation.stdout)["ok"])
        self.run_command(sys.executable, str(scripts / "status.py"), "--root", str(sample), "--json")
        gates = self.run_command(sys.executable, str(scripts / "gates.py"), "--root", str(sample), "--json", expected=1)
        self.assertFalse(json.loads(gates.stdout)["all_pass"])

    def test_powershell_installs_both_skills(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            self.skipTest("PowerShell is covered by the Windows CI runner")
        dest = self.root / "powershell-skills"
        command = (shell, "-NoProfile", "-File", str(self.package / "install.ps1"), "-Dest", str(dest))
        self.run_command(*command, "-DryRun")
        self.assertFalse(dest.exists())
        self.run_command(*command)
        self.assertTrue((dest / "patent-research/SKILL.md").is_file())
        self.assertTrue((dest / "patent-drafting/SKILL.md").is_file())
        self.run_command(*command, expected=1)
        self.run_command(*command, "-Force")
        self.run_command(*command, "-Uninstall")
        self.assertFalse((dest / "patent-research").exists())
        self.assertFalse((dest / "patent-drafting").exists())

    @unittest.skipIf(os.name == "nt", "POSIX installation is covered by the Linux CI runner")
    def test_bash_installs_both_skills(self):
        dest = self.root / "bash-skills"
        command = ("bash", str(self.package / "install.sh"), "--dest", str(dest))
        self.run_command(*command, "--dry-run")
        self.assertFalse(dest.exists())
        self.run_command(*command)
        self.assertTrue((dest / "patent-research/SKILL.md").is_file())
        self.assertTrue((dest / "patent-drafting/SKILL.md").is_file())
        self.run_command(*command, expected=1)
        self.run_command(*command, "--force")
        self.run_command(*command, "--uninstall")
        self.assertFalse((dest / "patent-research").exists())
        self.assertFalse((dest / "patent-drafting").exists())

    def test_drafting_single_package_installs_standalone(self):
        """单技能包（无样例）也能独立安装：自检降级为 SKILL.md 就位检查。"""
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            self.skipTest("PowerShell is covered by the Windows CI runner")
        dest = self.root / "drafting-only-skills"
        command = (shell, "-NoProfile", "-File", str(self.drafting_package / "install.ps1"), "-Dest", str(dest))
        self.run_command(*command)
        self.assertTrue((dest / "patent-drafting/SKILL.md").is_file())
        self.assertFalse((dest / "patent-research").exists())

    def test_legacy_migration_then_installed_wrappers(self):
        from patentkit.assessment import schema_properties
        root = self.root / "legacy-workspace"
        shutil.copytree(self.package / "samples/sample_workspace", root)
        schema_path = root / "03_candidates/candidates_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for name in schema_properties():
            schema["properties"].pop(name, None)
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        example = json.loads((self.package / "patent-research/assets/sample_data/candidates_example.json").read_text(encoding="utf-8"))
        # 旧数据故意不携带模型身份与人工确认，迁移不得推定它们。
        for name in schema_properties():
            example.pop(name, None)
        example.update(id="P-900", target="TGT-0002", tags=["N1@TGT-0002"], evidence_level="asserted")
        candidate = root / "03_candidates/P-900.json"
        candidate.write_text(json.dumps(example), encoding="utf-8")
        before = candidate.read_bytes()
        command = (sys.executable, "-m", "patentkit", "review", "migrate-assessments", "--root", str(root))
        self.run_command(*command)
        self.assertEqual(candidate.read_bytes(), before)
        self.run_command(*command, "--apply")
        migrated = json.loads(candidate.read_text(encoding="utf-8"))
        self.assertEqual(migrated["assessment"]["actor"], "unknown")
        self.assertFalse(migrated.get("human_confirmation"))
        self.assertEqual(migrated["evidence_level"], "asserted")
        script = self.package / "patent-research/scripts/status.py"
        result = self.run_command(sys.executable, str(script), "--root", str(root), "--json")
        self.assertEqual(json.loads(result.stdout)["active_target"], "TGT-0002")

    @unittest.skipUnless(os.name == "nt", "Windows one-click installer")
    def test_oneclick_installs_the_final_zip_to_an_isolated_directory(self):
        wheel = ROOT / "dist/patentkit-0.6.0-py3-none-any.whl"
        self.assertTrue(wheel.is_file(), "Build the kernel wheel in dist before acceptance")
        bundle = self.root / "oneclick-bundle"
        bundle.mkdir()
        shutil.copy2(wheel, bundle)
        shutil.copy2(self.full_zip, bundle)
        installer = bundle / "install-oneclick.cmd"
        shutil.copy2(self.package / installer.name, installer)
        dest = self.root / "oneclick-skills"
        command = f'"{os.environ["COMSPEC"]}" /d /s /c ""{installer}" --quiet --dest "{dest}""'
        self.run_command(command)
        self.assertTrue((dest / "patent-research/SKILL.md").is_file())
        self.assertTrue((dest / "patent-drafting/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
