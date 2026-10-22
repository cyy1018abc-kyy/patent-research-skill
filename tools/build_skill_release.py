#!/usr/bin/env python
"""构建 `patent-research-skill` 独立安装包（P2）。

为什么要单独做一个构建器
------------------------
技能包要分发给**没读过本仓库**的人，就不能让他们 `git clone` 后自己找目录。
本脚本把「技能包 payload + 安装脚本 + 脱敏示例工作区 + 校验清单」打成一个 zip：

```
dist/patent-research-skill-v<版本>.zip
├── manifest.json          # 版本、兼容性、文件 sha256 清单
├── INSTALL.md             # 完整安装说明（随包）
├── 安装说明-给同事.md       # 一页纸（随包，也单独上传 Release 方便转发）
├── install.ps1 / install.sh / install-oneclick.cmd
├── patent-research/       # ← 安装进客户端技能目录的就是它（目录名 = SKILL.md name）
└── samples/示例工作区/     # 脱敏工作区（TGT-0002，合成数据），给自检/P3 测试用
```

设计约束
--------
1. **不含任何真实项目数据**：payload 只来自 `patent-research-skill/`；示例工作区用
   `patentkit init` 的模板现场生成（目标固定 `TGT-0002`）。构建时再扫一遍真实 ID。
2. **可重复构建**：同一 `--built-at` 与同一源码，两次构建输出 zip **逐字节相同**
   （zip 内时间戳固定、文件顺序排序、manifest 稳定）。发布/复核靠这个做 diff。
3. **规则不复制**：示例工作区直接复用 `patentkit.init` 的模板与占位符渲染；
   校验用 `patentkit.api.validate(strict=True)`，不在这里另写判据。
4. **构建即验收**：payload 结构、references 数量、脚本可编译、示例工作区
   `validate --strict` 干净、manifest sha256 回读校验 —— 任一失败即构建失败（exit 1）。

用法：

    python tools/build_skill_release.py                     # 输出到 dist/
    python tools/build_skill_release.py --out dist/
    python tools/build_skill_release.py --built-at 2026-10-20T00:00:00+08:00
    python tools/build_skill_release.py --no-samples --json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402  （仓库依赖，pyproject 已声明）

SKILL_DIR = ROOT / "patent-research-skill"
RELEASE_DIR = ROOT / "release"
DEFAULT_OUT = ROOT / "dist"

#: 安装目录名必须 = SKILL.md 的 name（客户端按目录识别技能）
SKILL_NAME = "patent-research"
PACKAGE_NAME = "patent-research-skill"
INSTALL_MD = RELEASE_DIR / "INSTALL.md"
#: 给同事看的一页纸（随包分发；也单独上传到 GitHub Release 方便直接转发）
INSTALL_GUIDE = RELEASE_DIR / "安装说明-给同事.md"
INSTALLERS = (
    RELEASE_DIR / "install.ps1",
    RELEASE_DIR / "install.sh",
    RELEASE_DIR / "install-oneclick.cmd",
)

#: 示例工作区固定目标（合成数据；真实项目编号，构建时会拦（见 LEAK_PATTERNS））
SAMPLE_TARGET = "TGT-0002"
SAMPLE_TITLE = "示例目标：燃料电池与气路循环（合成数据，非真实项目）"
SAMPLE_DIR_NAME = "示例工作区"
SAMPLE_README = """# 示例工作区（脱敏合成数据）

> ⚠️ **这是合成数据，不是真实项目。** 用它只为演示/自检：
> 目录结构、术语表、检索式库、校验门都能跑通，但**没有任何真实检索证据**。
> 不要把它当证据、不要复制它的候选/结论去写专利文件。

## 用途

1. **安装自检**：`python <技能目录>/scripts/status.py --root "<本目录>"` 应 exit 0。
2. **跨客户端测试（P3）**：给 Codex / Claude Code 一个不接触真实数据的工作区。
3. **练习**：照着 `references/` 走一遍检索 → 入库 → 门禁流程。

## 里面有什么

| 文件 | 说明 |
|---|---|
| `workspace.yml` | 工作区标记；`active_target: TGT-0002` |
| `00_方法论/术语表.yml` | 术语与轴定义（**权威定义源**） |
| `01_检索方案/检索式库.yml` | 检索式骨架（未执行） |
| `03_候选清单/候选清单_schema.json` | 候选清单字段约束 |
| `02_检索日志/raw/` 等目录 | 空目录，工具会往这里写 |

## 复位

删掉整个目录，重新解压发布包（或从 `patentkit/templates/workspace` 重新生成）即可。
这里**没有任何值得保留的真实数据**。
"""

#: 构建时禁止出现的真实数据（示例工作区按合成数据生成；这里再做一次兜底扫描）
LEAK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:P|L)-\d{3,}\b"), "真实候选/文献编号"),
    (re.compile(r"\bCN\d{6,}[A-Z]?\b"), "真实公开号"),
)

#: 参与泄漏扫描的 payload 面（assets/示例数据 里是明示的合成占位，不在此列）
LEAK_SCAN_GLOBS = ("SKILL.md", "README.md", "scripts/*.py", "scripts/README.md")
TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".txt", ".ps1", ".sh", ".toml"}
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


class BuildError(RuntimeError):
    """构建前置检查或自检失败。"""


# ── 基础工具 ──────────────────────────────────────────────────────────


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_files(root: Path) -> list[Path]:
    """列出目录下所有文件（排序、排除缓存），返回绝对路径。"""
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        rel_parts = path.relative_to(root).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        if path.is_dir():
            continue
        if path.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        out.append(path)
    return out


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fail(message: str) -> None:
    raise BuildError(message)


# ── 技能包与示例工作区 ────────────────────────────────────────────────


def skill_frontmatter(skill_md: Path) -> dict:
    text = read_text(skill_md)
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        fail(f"{skill_md} 没有 YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        fail(f"{skill_md} 的 frontmatter 不是字典")
    return fm


def check_payload() -> dict:
    """payload 结构与纪律检查。失败抛 BuildError。"""
    if not SKILL_DIR.is_dir():
        fail(f"找不到技能包目录：{SKILL_DIR}")

    skill_md = SKILL_DIR / "SKILL.md"
    if not skill_md.is_file():
        fail("技能包缺 SKILL.md")

    fm = skill_frontmatter(skill_md)
    if fm.get("name") != SKILL_NAME:
        fail(f"SKILL.md 的 name 应为 {SKILL_NAME!r}，实际 {fm.get('name')!r}")
    version = str((fm.get("metadata") or {}).get("version") or "").strip()
    if not version or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        fail(f"SKILL.md 缺少合法 metadata.version（当前 {version!r}）")

    refs = sorted((SKILL_DIR / "references").glob("*.md"))
    if len(refs) != 6:
        fail(f"references 应为 6 份（P0 决议），实际 {len(refs)}")
    if not (SKILL_DIR / "scripts" / "_env.py").is_file():
        fail("scripts/_env.py 缺失（脚本共用层，会让所有脚本 import 失败）")
    if not (SKILL_DIR / "README.md").is_file():
        fail("技能包缺 README.md（P2 分发必需）")

    # 桌面端（Codex/ChatGPT App）元数据：缺了不会崩，但桌面端 Skills 列表会退化成裸 name
    agents_yaml = SKILL_DIR / "agents" / "openai.yaml"
    if not agents_yaml.is_file():
        fail("缺桌面端元数据 agents/openai.yaml（桌面端 Skills 显示名/@ 默认提问）")
    try:
        agents_meta = yaml.safe_load(read_text(agents_yaml)) or {}
    except yaml.YAMLError as exc:
        fail(f"agents/openai.yaml 不是合法 YAML：{exc}")
    if not isinstance(agents_meta, dict):
        fail("agents/openai.yaml 顶层必须是映射")
    interface = agents_meta.get("interface") or {}
    if not isinstance(interface, dict):
        fail("agents/openai.yaml 的 interface 必须是映射")
    for key in ("display_name", "short_description", "default_prompt"):
        if not str(interface.get(key) or "").strip():
            fail(f"agents/openai.yaml 缺 interface.{key}（桌面端展示/默认提问依赖它）")
    if "patent-research" not in str(interface.get("default_prompt")):
        fail("agents/openai.yaml 的 interface.default_prompt 应含技能名 patent-research")

    for installer in INSTALLERS:
        if not installer.is_file():
            fail(f"安装脚本缺失：{installer}")
    if not INSTALL_MD.is_file():
        fail(f"随包安装说明缺失：{INSTALL_MD}")
    if not INSTALL_GUIDE.is_file():
        fail(f"给同事的一页纸安装说明缺失：{INSTALL_GUIDE}")

    # 分发面不得夹带真实项目数据
    for pattern in LEAK_SCAN_GLOBS:
        for path in sorted(SKILL_DIR.glob(pattern)):
            if not path.is_file():
                continue
            for regex, label in LEAK_PATTERNS:
                for match in regex.finditer(read_text(path)):
                    fail(f"{path.relative_to(ROOT)} 含{label} {match.group(0)!r}，不能打进发布包")

    # 脚本至少能被解析（不执行、不联网）
    for py in sorted((SKILL_DIR / "scripts").glob("*.py")):
        try:
            compile(read_text(py), str(py), "exec")
        except SyntaxError as exc:  # pragma: no cover - 构建期兜底
            fail(f"{py.relative_to(ROOT)} 语法错误：{exc}")

    return {"name": SKILL_NAME, "version": version, "references": len(refs)}


def build_sample_workspace(dest: Path, date: str) -> None:
    """生成脱敏示例工作区：复用 `patentkit.init` 的模板与渲染，不另写一套。"""
    from patentkit import api
    from patentkit.init import DIRS, render, template_dir

    tpl = template_dir()
    dest.mkdir(parents=True, exist_ok=True)
    for rel_dir in DIRS:
        (dest / rel_dir).mkdir(parents=True, exist_ok=True)

    for src in sorted(tpl.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(tpl)
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(
            render(read_text(src), SAMPLE_TARGET, SAMPLE_TITLE, date),
            encoding="utf-8",
        )

    (dest / "README.md").write_text(SAMPLE_README, encoding="utf-8")

    # 示例工作区必须自身可用：validate --strict 干净（与 `patentkit init` 的验收口径一致）
    result = api.validate(str(dest.resolve()), strict=True)
    if not result.get("ok"):
        summary = result.get("summary", {})
        fail(
            "示例工作区 validate --strict 不干净："
            f"error={summary.get('errors')} warn={summary.get('warnings')}"
        )

    # 示例工作区里也不能出现真实目标/编号
    for path in iter_files(dest):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_text(path)
        for regex, label in LEAK_PATTERNS:
            for match in regex.finditer(text):
                fail(f"示例工作区含{label} {match.group(0)!r}（{path.name}）")


# ── 打包 ──────────────────────────────────────────────────────────────


def source_info() -> dict:
    def git(*args: str) -> str | None:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
        except (OSError, subprocess.SubprocessError):  # pragma: no cover - 无 git 环境
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout.strip()

    return {
        "repo": git("config", "--get", "remote.origin.url") or "",
        "commit": git("rev-parse", "--short", "HEAD") or "",
        # 只看**已跟踪文件的改动**：构建产物在 dist/（gitignored），不应让 dirty 抖动
        "dirty": bool(git("status", "--porcelain", "--untracked-files=no") or ""),
    }


def patentkit_dist_version() -> str:
    """manifest.compat.patentkit 的版本来源。

    以包内 `patentkit.__version__` 为权威（与 `pyproject.toml` 的动态版本同源），
    而不是先读已安装元数据：editable 安装的元数据可能停在旧版本，会让 manifest
    里的兼容下限与源码实际版本不一致。未安装/读不到时再退回元数据；
    独立分发仓库（只有技能包、没有内核源码）可用环境变量显式指定。
    """
    env_version = os.environ.get("PATENTKIT_COMPAT_VERSION", "").strip()
    if env_version:
        return env_version
    try:
        from patentkit import __version__

        if __version__:
            return __version__
    except Exception:  # noqa: BLE001 - 源码树缺失时退回元数据
        pass
    try:
        return importlib.metadata.version("patentkit")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover - 未安装场景
        return ""


def zip_datetime(built_at: datetime) -> tuple[int, int, int, int, int, int]:
    return (built_at.year, built_at.month, built_at.day, built_at.hour, built_at.minute, built_at.second)


def _zipinfo(name: str, date_time: tuple[int, int, int, int, int, int], is_dir: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=date_time)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = ((0o755 if is_dir else 0o644) & 0xFFFF) << 16
    if is_dir:
        info.external_attr |= 0x10  # MS-DOS 目录位
    return info


def plan_entries(*, include_samples: bool, built_at: datetime, sample_root: Path | None) -> tuple[dict[str, bytes], set[str]]:
    """收集 zip 内的文件内容与目录（路径 → bytes；目录名以 / 结尾）。"""
    files: dict[str, bytes] = {}
    dirs: set[str] = set()

    def add_tree(src: Path, prefix: str) -> None:
        for path in iter_files(src):
            rel = path.relative_to(src).as_posix()
            files[f"{prefix}/{rel}"] = path.read_bytes()
        for path in sorted(src.rglob("*")):
            if not path.is_dir():
                continue
            rel_parts = path.relative_to(src).parts
            if any(part in EXCLUDE_DIRS for part in rel_parts):
                continue
            rel = path.relative_to(src).as_posix()
            dirs.add(f"{prefix}/{rel}/")

    add_tree(SKILL_DIR, SKILL_NAME)
    for extra in (INSTALL_MD, INSTALL_GUIDE, *INSTALLERS):
        files[extra.name] = extra.read_bytes()

    if include_samples:
        if sample_root is None:
            fail("include_samples=True 但没有示例工作区目录")
        add_tree(sample_root, f"samples/{SAMPLE_DIR_NAME}")

    dirs.add(f"{SKILL_NAME}/")
    if include_samples:
        dirs.add("samples/")
        dirs.add(f"samples/{SAMPLE_DIR_NAME}/")

    return files, dirs


def make_manifest(
    *,
    payload: dict,
    files: dict[str, bytes],
    built_at: datetime,
    include_samples: bool,
) -> dict:
    entries = [
        {"path": name, "sha256": sha256_bytes(data), "size": len(data)}
        for name, data in sorted(files.items())
    ]
    pk_version = patentkit_dist_version()
    return {
        "schema_version": 1,
        "package": PACKAGE_NAME,
        "skill": {
            "name": payload["name"],
            "version": payload["version"],
            "install_dir": SKILL_NAME,
        },
        "built_at": built_at.isoformat(),
        "source": source_info(),
        "compat": {
            "python": ">=3.11",
            "patentkit": f">={pk_version}" if pk_version else "unknown",
        },
        "contents": {
            "files": len(entries),
            "bytes": sum(e["size"] for e in entries),
            "references": payload["references"],
            "samples_included": include_samples,
        },
        "files": entries,
    }


def write_zip(zip_path: Path, manifest: dict, files: dict[str, bytes], dirs: set[str], built_at: datetime) -> None:
    date_time = zip_datetime(built_at)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    all_files = {"manifest.json": manifest_bytes, **files}
    # 目录项全部保留：示例工作区里的空目录（如 02_检索日志/raw/）必须随包存在，
    # 否则解压后第一次 ingest 就会因为路径不存在失败。
    final_dirs = set(dirs)

    tmp = zip_path.with_suffix(zip_path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(final_dirs):
                zf.writestr(_zipinfo(name, date_time, is_dir=True), b"")
            for name in sorted(all_files):
                zf.writestr(_zipinfo(name, date_time, is_dir=False), all_files[name])
        tmp.replace(zip_path)
    finally:
        tmp.unlink(missing_ok=True)


def verify_zip(zip_path: Path) -> dict:
    """回读 zip：manifest 与文件 sha256 必须对得上，且没有缓存/真实数据。"""
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        if "manifest.json" not in names:
            fail("zip 里没有 manifest.json")
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        listed = {entry["path"] for entry in manifest["files"]}
        on_disk = {name for name in names if not name.endswith("/")} - {"manifest.json"}
        if listed != on_disk:
            fail(f"manifest 与 zip 文件清单不一致：缺 {sorted(on_disk - listed)[:5]} / 多 {sorted(listed - on_disk)[:5]}")

        for entry in manifest["files"]:
            data = zf.read(entry["path"])
            if sha256_bytes(data) != entry["sha256"]:
                fail(f"sha256 不匹配：{entry['path']}")
            if len(data) != entry["size"]:
                fail(f"size 不匹配：{entry['path']}")

        for name in names:
            if any(part in name.split("/") for part in EXCLUDE_DIRS):
                fail(f"zip 里混入缓存目录：{name}")
            if name.endswith((".pyc", ".pyo")):
                fail(f"zip 里混入字节码：{name}")

        forbidden = ("patent-research/workspace.yml", "patent-research/03_候选清单/", "patent-research/02_检索日志/")
        for prefix in forbidden:
            if any(name == prefix or name.startswith(prefix) for name in names):
                fail(f"zip 的 payload 里混入工作区数据：{prefix}")

    return manifest


def build(out_dir: Path, *, built_at: datetime, include_samples: bool = True) -> dict:
    payload = check_payload()

    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{PACKAGE_NAME}-v{payload['version']}.zip"
    zip_path = out_dir / zip_name

    sample_dir = out_dir / f".sample-build-{os.getpid()}"
    shutil.rmtree(sample_dir, ignore_errors=True)
    try:
        sample_root: Path | None = None
        if include_samples:
            sample_root = sample_dir / SAMPLE_DIR_NAME
            build_sample_workspace(sample_root, built_at.date().isoformat())

        files, dirs = plan_entries(include_samples=include_samples, built_at=built_at, sample_root=sample_root)
        manifest = make_manifest(
            payload=payload, files=files, built_at=built_at, include_samples=include_samples
        )
        write_zip(zip_path, manifest, files, dirs, built_at)
        verify_zip(zip_path)
    finally:
        # 为什么不用 tempfile.TemporaryDirectory：它在 Windows 上用 0o700 建目录，
        # 在某些受限环境（如 DSH 沙箱）下连创建者都无法列目录/删除，收尾时直接抛
        # PermissionError。这里用普通 mkdir + 唯一名，够用且不踩那个坑。
        shutil.rmtree(sample_dir, ignore_errors=True)

    return {
        "zip": str(zip_path),
        "version": payload["version"],
        "built_at": built_at.isoformat(),
        "files": manifest["contents"]["files"],
        "bytes": manifest["contents"]["bytes"],
        "sha256": sha256_bytes(zip_path.read_bytes()),
    }


# ── CLI ───────────────────────────────────────────────────────────────


def parse_built_at(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--built-at 需要 ISO 时间（如 2026-10-20T00:00:00+08:00）：{exc}") from None


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python tools/build_skill_release.py",
        description="构建 patent-research-skill 独立安装包（zip + manifest + 安装脚本 + 示例工作区）",
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出目录（默认 dist/，已在 .gitignore）")
    ap.add_argument(
        "--built-at",
        type=parse_built_at,
        default=None,
        help="构建时间（ISO 8601）；用于可重复构建与测试，默认当前时间",
    )
    ap.add_argument("--no-samples", action="store_true", help="不打包示例工作区")
    ap.add_argument("--json", action="store_true", help="输出 JSON 构建结果")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    built_at = args.built_at or datetime.now().astimezone().replace(microsecond=0)
    if built_at.tzinfo is None:
        built_at = built_at.astimezone()

    try:
        result = build(args.out, built_at=built_at, include_samples=not args.no_samples)
    except BuildError as exc:
        print(f"[BUILD FAILED] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"[构建完成] {result['zip']}")
    print(f"  版本     : {result['version']}")
    print(f"  构建时间 : {result['built_at']}")
    print(f"  文件数   : {result['files']}")
    print(f"  总字节   : {result['bytes']}")
    print(f"  zip sha256: {result['sha256']}")
    print()
    print("下一步：")
    print(f"  1) 自检 manifest : python tools/build_skill_release.py --out {args.out} --json")
    print("  2) 本机安装      : pwsh -File dist/patent-research-skill-v<版本>/install.ps1 -DryRun")
    print("  3) 跨客户端测试  : 见 跨客户端测试/README.md（用包内 samples/示例工作区）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
