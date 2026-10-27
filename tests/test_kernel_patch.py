"""补丁路径头归一：空新增/删除文件没有 ---/+++ 行可消歧。

`git diff --no-index a b` 给新增文件的左侧、删除文件的右侧留下合成的树名一层
（`a/b/x.py b/x.py`）。非空文件还能靠 `+++ b/` 行纠正，**空文件**没有正文行，
git apply 只能读 `diff --git` 头，于是报 "header lacks filename information"。
这里锁住 `_strip_double_prefixes` 把两侧还原成同一相对路径，并真跑一次 apply。
"""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kernel_patch_builder", ROOT / "tools/build_kernel_patch.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

UPSTREAM_DIR = "kernel-build/patentkit-0.1.2"
GIT = ("git", "-c", "core.autocrlf=false")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([*GIT, *args], cwd=cwd, capture_output=True, text=True)


class PatchHeaderNormalization(unittest.TestCase):
    def test_added_deleted_and_modified_headers_are_symmetric(self):
        with tempfile.TemporaryDirectory() as name:
            work = Path(name)
            old, new = work / "a", work / "b"
            old.mkdir()
            new.mkdir()
            for path, content in ((old / "mod.py", "x = 1\n"), (new / "mod.py", "x = 2\n"),
                                  (old / "gone.py", "y = 1\n"), (new / "empty_new.py", "")):
                path.write_text(content, encoding="utf-8", newline="\n")

            raw = subprocess.run([*GIT, "diff", "--no-index", "--no-renames", "a", "b"],
                                 cwd=work, capture_output=True, text=True).stdout
            patch = builder._strip_double_prefixes(raw)

            for rel in ("mod.py", "gone.py", "empty_new.py"):
                self.assertIn(f"diff --git a/{rel} b/{rel}", patch, f"{rel} 的路径头不对称")
            self.assertNotIn("a/b/", patch)
            self.assertNotIn("b/a/", patch)

            # 真应用一次：基线树 = 上游（含 mod.py 与 gone.py），空新增文件必须能落地
            repo = work / "repo"
            base = repo / UPSTREAM_DIR
            base.mkdir(parents=True)
            for path, content in ((base / "mod.py", "x = 1\n"), (base / "gone.py", "y = 1\n")):
                path.write_text(content, encoding="utf-8", newline="\n")
            self.assertEqual(_git(repo, "init", "-q").returncode, 0)
            patch_file = work / "candidate.patch"
            patch_file.write_text(patch, encoding="utf-8", newline="\n")
            check = _git(repo, "apply", "--check", f"--directory={UPSTREAM_DIR}", str(patch_file))
            self.assertEqual(check.returncode, 0, check.stderr)
            applied = _git(repo, "apply", f"--directory={UPSTREAM_DIR}", str(patch_file))
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertTrue((base / "empty_new.py").is_file())
            self.assertFalse((base / "gone.py").exists())
            self.assertEqual((base / "mod.py").read_bytes(), b"x = 2\n")


if __name__ == "__main__":
    unittest.main()
