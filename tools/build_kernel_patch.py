"""从内核开发树重建 CI 可应用的补丁（patentkit-<upstream>-to-<kernel>.patch）。

内核源码不走 git 仓库：公开发布物是「上游 0.1.2 sdist + 本仓库的补丁」，CI 下载
上游并 `git apply --directory=kernel-build/patentkit-0.1.2` 重构 0.3.0。此前补丁靠
手工流程重建（镜像开发树 → scratch 目录 git diff --no-index → 修双重前缀 →
验证可应用），本工具把四步固化并加两层机器验证：

1. **可应用性**：补丁必须能对 SHA 校验过的上游 sdist 用 CI 同款命令 `git apply
   --check --directory=...` 通过，且补丁后树里存在 CI 的哨兵文件；
2. **等价性（--verify-against）**：新旧补丁分别应用到两份干净上游解包，产物树
   （剔除 pytest 缓存等垃圾）必须逐字节一致——证明新补丁是旧补丁的等价重建，
   而不是"恰好能 apply 的另一个东西"。

用法：
    python tools/build_kernel_patch.py --verify-against release/patches/patentkit-0.1.2-to-0.3.0.patch
    python tools/build_kernel_patch.py --kernel-version 0.4.0 --out release/patches/patentkit-0.1.2-to-0.4.0.patch

默认布局：开发树 = 仓库同级 `../patentkit`，上游 sdist = `../_upstream/`（都没有
则报错并给出 --dev-tree / --upstream-tarball 覆盖入口；下载不在本工具职责内——
上游资产以 GitHub Release 为准，SHA 由调用方保证）。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_VERSION = "0.1.2"
UPSTREAM_SHA256 = {
    "0.1.2": "5ab1ff6e6387c1b6f30e8e084b0da88d93bf71426e9cb901158562d9b52aae14",
}
#: 开发树里进入补丁的子集（其余上游文件原样保留，不产生 diff）
MIRROR_DIRS = ("patentkit", "tests", "regression_tests")
MIRROR_FILES = ("pyproject.toml", "MANIFEST.in", "README.md")
EXCLUDE_DIR_NAMES = {"__pycache__", ".pytest_cache"}
#: 应用补丁后 CI 断言存在的哨兵文件（.github/workflows/ci.yml）
SENTINEL_FILES = ("patentkit/assessment.py", "patentkit/provenance.py")
#: 补丁与产物树对比时必须剔除的垃圾（pytest 缓存 / 字节码 / egg-info）
JUNK_DIRS = {"__pycache__", ".pytest_cache"}


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _kernel_version() -> str:
    text = (ROOT / "tools/build_skill_release.py").read_text(encoding="utf-8")
    found = re.search(r'KERNEL_VERSION = "(\d+\.\d+\.\d+)"', text)
    if not found:
        raise SystemExit("无法从 tools/build_skill_release.py 解析 KERNEL_VERSION")
    return found.group(1)


def _normalize_lf(data: bytes) -> bytes:
    try:
        return data.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    except UnicodeDecodeError:
        return data


def _copy_mirror(src: Path, dest: Path) -> int:
    """把 src（文件或目录）镜像到 dest，LF 归一，剔除缓存/egg-info。返回文件数。"""
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_normalize_lf(src.read_bytes()))
        return 1
    count = 0
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if path.is_symlink():
            raise SystemExit(f"开发树不允许符号链接：{path}")
        if any(part in EXCLUDE_DIR_NAMES or part.endswith(".egg-info") for part in rel.parts):
            continue
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.suffix not in {".pyc", ".pyo"}:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(_normalize_lf(path.read_bytes()))
            count += 1
    return count


def _extract_upstream(tarball: Path, destination: Path) -> Path:
    data = tarball.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    expected = UPSTREAM_SHA256.get(UPSTREAM_VERSION)
    if expected and digest != expected:
        raise SystemExit(f"上游 sdist SHA256 不符：{digest}")
    unpacked = destination / "kernel-build"
    unpacked.mkdir(parents=True)
    with tarfile.open(fileobj=__import__("io").BytesIO(data), mode="r:gz") as archive:
        archive.extractall(unpacked, filter="data")
    tree = unpacked / f"patentkit-{UPSTREAM_VERSION}"
    if not (tree / "pyproject.toml").is_file():
        raise SystemExit(f"上游解包缺少 patentkit-{UPSTREAM_VERSION}/pyproject.toml")
    return tree


def _strip_double_prefixes(patch_text: str) -> str:
    """git diff --no-index a b 的头是 a/a/… b/b/…；剥掉重复的树名层级。

    只处理 diff --git / --- / +++ 行；正文里的 `a/a/` 字面量不属于路径头，不动。
    """
    lines = []
    for line in patch_text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            line = line.replace(" a/a/", " a/", 1).replace(" b/b/", " b/", 1)
        elif line.startswith("--- "):
            line = line.replace("a/a/", "a/", 1)
        elif line.startswith("+++ "):
            line = line.replace("b/b/", "b/", 1)
        lines.append(line)
    return "".join(lines)


def _git_apply(cwd: Path, patch: Path, directory: str, check_only: bool = False,
               autocrlf: str | None = "false") -> None:
    """CI 同款 git apply --directory；失败时把 stderr 带出来。

    autocrlf 钉成 false（CI ubuntu 的口径，最严格）；历史补丁若只兼容
    autocrlf=true，由调用方以 autocrlf=None 重试。

    注意：``git apply --directory`` 只在 **git 仓库内**按预期工作；git 2.53 在
    非仓库目录会静默退出 0 且不落盘（正是本工具旧版 --verify-against 的假通过根因）。
    调用方必须先 ``_init_git_repo`` 再应用，才能在本地复刻 CI 的行为。
    """
    cmd = ["git", "apply"] + (["--check"] if check_only else []) + [f"--directory={directory}", str(patch)]
    if autocrlf is not None:
        cmd = [cmd[0], "-c", f"core.autocrlf={autocrlf}"] + cmd[1:]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"git apply {'--check ' if check_only else ''}失败（rc={proc.returncode}）：\n{proc.stderr}")


def _init_git_repo(path: Path) -> None:
    """把解包目录变成真实 git 仓库（CI 的 $GITHUB_WORKSPACE 就是仓库根）。

    没有这一步时 ``git apply --directory`` 在裸目录里可能静默 no-op；同时用固定
    user/autocrlf 配置保证本地与 CI 的可重复性。
    """
    path.mkdir(parents=True, exist_ok=True)

    def run(*args: str) -> None:
        proc = subprocess.run(["git", *args], cwd=path, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"git {' '.join(args)} 失败（rc={proc.returncode}）：\n{proc.stderr}")

    run("init", "-q")
    run("config", "user.name", "patentkit-patch-builder")
    run("config", "user.email", "patch-builder@localhost")
    run("config", "core.autocrlf", "false")
    # 用一次基线提交把上游树固定下来，git apply 只改工作树，不影响这一步的校验语义。
    run("add", "-A")
    run("-c", "commit.gpgsign=false", "commit", "-q", "-m", "upstream baseline")


def _compare_dev_tree(applied: Path, dev_tree: Path) -> list[str]:
    """补丁应用结果（镜像子集）与内核开发树逐字节比对（LF 归一后）。

    这是重建补丁的第三层验证：不仅"能 apply"，还要证明补丁忠实重建了开发树的
    P0–P4 代码，避免镜像遗漏/旧文件覆盖新文件。
    """
    expected: dict[str, Path] = {}
    for name in MIRROR_DIRS:
        base = dev_tree / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            rel = path.relative_to(dev_tree)
            if path.is_symlink():
                continue
            if any(part in EXCLUDE_DIR_NAMES or part.endswith(".egg-info") for part in rel.parts):
                continue
            if path.is_file() and path.suffix not in {".pyc", ".pyo"}:
                expected[rel.as_posix()] = path
    for name in MIRROR_FILES:
        expected[Path(name).as_posix()] = dev_tree / name

    diffs: list[str] = []
    for rel, source in sorted(expected.items()):
        target = applied / rel
        if not target.is_file():
            diffs.append(f"补丁产物缺少：{rel}")
            continue
        if _normalize_lf(source.read_bytes()) != _normalize_lf(target.read_bytes()):
            diffs.append(f"内容不同：{rel}")
    return diffs


def build_patch(dev_tree: Path, upstream_tarball: Path, out: Path, verify_against: Path | None,
                keep_temp: Path | None, force: bool) -> int:
    if not (dev_tree / "pyproject.toml").is_file():
        raise SystemExit(f"开发树不像内核树（缺 pyproject.toml）：{dev_tree}")
    version = _kernel_version()

    with tempfile.TemporaryDirectory(prefix="pk-patch-") as temp_name:
        temp = Path(temp_name)
        pristine = _extract_upstream(upstream_tarball, temp / "unpack")
        overlaid = temp / "overlaid" / f"patentkit-{UPSTREAM_VERSION}"
        shutil.copytree(pristine, overlaid)
        mirrored = 0
        for name in MIRROR_DIRS:
            if not (dev_tree / name).is_dir():
                raise SystemExit(f"开发树缺少 {name}/：{dev_tree}")
            mirrored += _copy_mirror(dev_tree / name, overlaid / name)
        for name in MIRROR_FILES:
            if not (dev_tree / name).is_file():
                raise SystemExit(f"开发树缺少 {name}：{dev_tree}")
            mirrored += _copy_mirror(dev_tree / name, overlaid / name)

        # 行尾噪声消除：镜像做了 LF 归一，而上游 sdist 是 CRLF——内容未变仅行尾
        # 不同的文件恢复上游原字节，避免"未改动的文件"以整文件重写混进补丁。
        # （真正改动的文件仍会以整文件重写出现：补丁必须对 CRLF 上游做字节级
        # 匹配，上下文行携带上游行尾；这换来了跨 git 配置的可应用确定性。）
        for rel_root in MIRROR_DIRS + MIRROR_FILES:
            base = pristine / rel_root
            candidates = [base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []
            for src in candidates:
                rel = src.relative_to(pristine)
                dst = overlaid / rel
                if not dst.is_file():
                    continue
                if _normalize_lf(src.read_bytes()) == dst.read_bytes():
                    dst.write_bytes(src.read_bytes())

        scratch = temp / "scratch"
        scratch.mkdir()
        shutil.move(str(pristine), str(scratch / "a"))
        shutil.move(str(overlaid), str(scratch / "b"))
        proc = subprocess.run(
            ["git", "-c", "core.autocrlf=false", "diff", "--no-index", "--no-renames", "a", "b"],
            cwd=scratch, capture_output=True)
        if proc.returncode not in (0, 1):
            raise SystemExit(f"git diff --no-index 失败（rc={proc.returncode}）：{proc.stderr.decode('utf-8', 'replace')}")
        patch = _strip_double_prefixes(proc.stdout.decode("utf-8"))
        if not patch.strip():
            raise SystemExit("diff 为空：开发树与上游 0.1.2 相同？内核版本门不会允许这种状态")
        # 只查路径头行——补丁正文（测试内容等）合法地会出现这些字面量
        header_lines = [l for l in patch.splitlines()
                        if l.startswith(("diff --git ", "--- ", "+++ ", "rename ", "copy "))]
        for junk in (".pytest_cache", "egg-info", "__pycache__", ".pyc"):
            if any(junk in line for line in header_lines):
                raise SystemExit(f"补丁的路径头混入了垃圾（{junk}）——镜像排除规则失效，拒绝写出")

        patch_path = temp / "candidate.patch"
        patch_path.write_text(patch, encoding="utf-8", newline="\n")

        # 验证 1：CI 同款命令可应用（钉死 autocrlf=false，CI ubuntu 口径），且哨兵文件出现
        check_root = temp / "verify"
        _extract_upstream(upstream_tarball, check_root)
        _init_git_repo(check_root)
        target = f"kernel-build/patentkit-{UPSTREAM_VERSION}"
        _git_apply(check_root, patch_path, target, check_only=True)
        _git_apply(check_root, patch_path, target)
        for sentinel in SENTINEL_FILES:
            if not (check_root / target / sentinel).is_file():
                raise SystemExit(f"补丁应用后缺少 CI 哨兵文件：{sentinel}")

        # 验证 1b：应用结果必须逐字节重建开发树的镜像子集（防止镜像遗漏/旧文件覆盖新代码）
        dev_diffs = _compare_dev_tree(check_root / target, dev_tree)
        if dev_diffs:
            print(f"✗ 补丁应用结果与开发树不一致（{len(dev_diffs)} 处）：", file=sys.stderr)
            for line in dev_diffs[:20]:
                print(f"  · {line}", file=sys.stderr)
            return 1
        print("✅ 开发树等价性验证：补丁应用结果与开发树镜像文件逐字节一致")

        # 验证 2：与现有补丁的产物树逐字节等价（历史补丁可能只兼容 autocrlf=true，
        # 先按钉死口径试，失败再放宽重试并说明）
        if verify_against:
            cmp_new = temp / "cmp-new"
            tree_new = _extract_upstream(upstream_tarball, cmp_new) / f"kernel-build/patentkit-{UPSTREAM_VERSION}"
            _init_git_repo(cmp_new)
            _git_apply(cmp_new, patch_path, f"kernel-build/patentkit-{UPSTREAM_VERSION}")
            cmp_old = temp / "cmp-old"
            tree_old = _extract_upstream(upstream_tarball, cmp_old) / f"kernel-build/patentkit-{UPSTREAM_VERSION}"
            _init_git_repo(cmp_old)
            legacy_dir = f"kernel-build/patentkit-{UPSTREAM_VERSION}"
            try:
                _git_apply(cmp_old, verify_against.resolve(), legacy_dir)
            except SystemExit:
                print("   （历史补丁在 autocrlf=false 下应用失败，改用环境 git 配置重试做等价对比）")
                _git_apply(cmp_old, verify_against.resolve(), legacy_dir, autocrlf=None)
            diffs = _compare_trees(tree_new, tree_old)
            if diffs:
                print(f"✗ 新补丁与 {verify_against.name} 的应用结果不一致（{len(diffs)} 处）：", file=sys.stderr)
                for line in diffs[:20]:
                    print(f"  · {line}", file=sys.stderr)
                return 1
            print(f"✅ 等价性验证：与 {verify_against.name} 的应用结果逐字节一致")

        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and not force:
            raise SystemExit(f"目标补丁已存在：{out}\n"
                             "确认要覆盖已发布的补丁时加 --force；只是验证请用 --out 指到临时路径")
        if keep_temp:
            kept = out.parent / (out.stem + ".candidate.patch")
            shutil.copy2(patch_path, kept)
            print(f"（候选补丁副本：{kept}）")
        out.write_text(patch, encoding="utf-8", newline="\n")

    try:
        shown = out.relative_to(ROOT).as_posix()
    except ValueError:
        shown = str(out)
    print(f"✅ 补丁已重建：{shown}（镜像 {mirrored} 个文件，"
          f"{patch.count('diff --git')} 个 diff 条目，可被 CI 的 git apply --directory 应用）")
    print("   收尾：更新 release/patches/README.md 的补丁名与 SHA、notes 指针；"
          "kernel 版本号走 tools/bump_version.py --kernel-to。")
    return 0


def _compare_trees(left: Path, right: Path) -> list[str]:
    def entries(root: Path) -> dict[str, bytes]:
        result = {}
        for path in root.rglob("*"):
            rel = path.relative_to(root)
            parts = rel.parts
            if any(part in JUNK_DIRS or part.endswith(".egg-info") for part in parts):
                continue
            if path.is_file() and path.suffix not in {".pyc", ".pyo"}:
                result[rel.as_posix()] = path.read_bytes()
        return result

    left_files, right_files = entries(left), entries(right)
    diffs = []
    for missing in sorted(set(left_files) - set(right_files)):
        diffs.append(f"仅新补丁产物有：{missing}")
    for missing in sorted(set(right_files) - set(left_files)):
        diffs.append(f"仅旧补丁产物有：{missing}")
    for common in sorted(set(left_files) & set(right_files)):
        if left_files[common] != right_files[common]:
            diffs.append(f"内容不同：{common}")
    return diffs


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-tree", type=Path, default=ROOT.parent / "patentkit",
                        help="内核开发树（默认 ../patentkit）")
    parser.add_argument("--upstream-tarball", type=Path,
                        default=ROOT.parent / "_upstream" / f"patentkit-{UPSTREAM_VERSION}.tar.gz",
                        help="上游 sdist（默认 ../_upstream/patentkit-0.1.2.tar.gz）")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "release/patches" / f"patentkit-{UPSTREAM_VERSION}-to-{_kernel_version()}.patch")
    parser.add_argument("--verify-against", type=Path, help="现有补丁：验证新补丁应用结果与之逐字节等价")
    parser.add_argument("--keep-temp", type=Path, metavar="DIR",
                        help="把候选补丁写到 DIR 旁（调试用；正常流程不需要）")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的补丁文件")
    args = parser.parse_args()

    try:
        return build_patch(args.dev_tree, args.upstream_tarball, args.out,
                           args.verify_against, args.keep_temp, args.force)
    except (OSError, ValueError, shutil.Error, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Failed: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
