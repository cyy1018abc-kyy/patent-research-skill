"""release-doctor —— 发布链路一键体检（本地预检 + 实际 Release 审计）。

为什么需要
----------
发布质量此前散落在多处：bump --check 锁版本配对、unittest 锁安装包、CI 步骤
锁 evals/术语/保密/链接，但「实际发布到 GitHub 的东西」直到发完才有人看——
历史教训（publish 对已存在 tag 静默 no-op、安装器 bug 只有特定平台能抓到）
说明需要一个独立的、对**实际 Release 资产**负责的体检器。

两种模式
--------
* offline（默认）：不联网。版本配对（复用 bump_version.check）、evals/术语/
  保密守卫/引用链接四个守卫脚本、构建双 zip 并深检 manifest、按平台可用的
  安装器实测（ps1 / bash / one-click）。CI 的 check job 用它做发布前总预检。
* release：审计 GitHub 上**已发布**的 Release——tag 存在性与 draft/latest 状态、
  资产名单与发布脚本一致、逐资产 sha256 对 SUMS、Release 内 zip 的 manifest
  （schema/skills/compat/source.commit）、notes 非空、并用**下载到的真实资产**
  跑各平台安装测试 + 内核 wheel 隔离导入。只走 api.github.com（本机 github.com
  直连被阻时依然可用）。CI 在 publish 之后对发布结果跑这一档。

用法
----
    python tools/release_doctor.py                 # offline 预检
    python tools/release_doctor.py --dist dist     # 复用已构建的 dist（CI 快路径）
    python tools/release_doctor.py --release --expect-commit <sha>
    python tools/release_doctor.py --offline --json

退出码：0 全部通过（SKIP 不算失败）；1 存在 FAIL；2 用法/环境错误。
新增体检项时：写一个返回 (status, detail) 的检查函数并登记进 CHECKS_*，
status 只能是 pass/fail/skip，skip 必须写明原因（平台不适用 ≠ 隐瞒）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_API = "https://api.github.com"
PASS, FAIL, SKIP = "pass", "fail", "skip"
INSTALL_TIMEOUT = 420


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _load_tool(name: str):
    """按路径加载 tools/ 下的兄弟脚本（它们不是包，无相对导入）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── 纯函数：发布脚本解析 / SUMS / manifest 校验（单元测试覆盖） ────────────


def check_extension_wheel_files(package_dir: Path) -> tuple[str, str]:
    """校验 ``<package_dir>/extension/`` 下的可选扩展 wheel 与其独立 SUMS（O-04）。

    扩展是可选组件：目录不存在 → SKIP（不算失败）；存在则 SUMS 哈希必须一致，
    wheel 元数据必须满足「最小安装零第三方依赖 + extras 齐全 + 入口点存在」。
    """
    extension_dir = package_dir / "extension"
    if not extension_dir.is_dir():
        return SKIP, "extension wheel 未构建（可选组件，不阻断 skill 发布）"
    wheels = sorted(extension_dir.glob("patent_intel-*.whl"))
    sums_files = sorted(extension_dir.glob("SHA256SUMS-patent-intel-*.txt"))
    if len(wheels) != 1 or len(sums_files) != 1:
        return FAIL, f"extension 目录应恰有一个 wheel 与一份 SUMS：{[p.name for p in wheels]} / {[p.name for p in sums_files]}"
    sums = parse_sums(sums_files[0].read_text(encoding="utf-8"))
    if set(sums) != {wheels[0].name}:
        return FAIL, f"SUMS 名单与 wheel 不一致: {sorted(sums)} vs {wheels[0].name}"
    digest = hashlib.sha256(wheels[0].read_bytes()).hexdigest()
    if sums[wheels[0].name] != digest:
        return FAIL, f"wheel sha256 与 SUMS 不一致（{wheels[0].name}）"
    problems = _inspect_extension_metadata(wheels[0])
    if problems:
        return FAIL, "; ".join(problems)
    return PASS, f"{wheels[0].name}（sha256 一致；最小安装零第三方依赖、extras 齐全）"


def _inspect_extension_metadata(wheel: Path) -> list[str]:
    """Lightweight wheel audit: METADATA + entry_points (no install, offline)."""
    import zipfile

    problems: list[str] = []
    try:
        with zipfile.ZipFile(wheel) as archive:
            metadata_name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            metadata = archive.read(metadata_name).decode("utf-8")
            entries_name = next(n for n in archive.namelist() if n.endswith(".dist-info/entry_points.txt"))
            entries = archive.read(entries_name).decode("utf-8")
    except (StopIteration, zipfile.BadZipFile, KeyError) as exc:
        return [f"wheel 元数据不可读: {exc}"]

    in_body = False
    requires_dist: list[str] = []
    extras: set[str] = set()
    for line in metadata.splitlines():
        if not line.strip():
            in_body = True
            continue
        if in_body:
            break
        if line.startswith("Requires-Dist:"):
            requires_dist.append(line.split(":", 1)[1].strip())
            if "extra ==" in line:
                extras.add(line.split("extra ==")[-1].strip().strip('"'))
    base_deps = [r for r in requires_dist if "extra ==" not in r]
    if base_deps:
        problems.append(f"基础安装声明了第三方依赖: {base_deps}（最小安装必须零依赖）")
    for required_extra in ("kernel", "pdf", "dense", "ops"):
        if required_extra not in extras:
            problems.append(f"缺少 extras: {required_extra}")
    if "patent-intel" not in entries or "cli" not in entries:
        problems.append("entry_points 缺少 patent-intel = patent_intel.cli:main")
    return problems


def parse_publish_assets(script_text: str) -> dict[str, list[str]]:
    """从 publish_release.sh 解析 tag → 上传资产名列表（不含 dist/ 前缀）。

    发布脚本的 tag 与资产名是硬编码配对点（见 bump_version 的清单）；上传行里的
    tag 通常写作 "$kernel"/"$skill" 变量，这里先解析赋值行再做变量展开。
    """
    tags: dict[str, str] = {}
    for key in ("kernel", "skill"):
        found = re.search(rf'^{key}=(\S+)', script_text, re.M)
        if not found:
            raise ValueError(f"publish script: missing '{key}=' tag assignment")
        tags[key] = found.group(1)
    uploads: dict[str, list[str]] = {tag: [] for tag in tags.values()}

    def resolve(token: str) -> str:
        variable = re.fullmatch(r'"?\$\{?(\w+)\}?"?', token)
        if variable:
            name = variable.group(1)
            if name not in tags:
                raise ValueError(f"publish script: upload 行引用了未知变量 {token}")
            return tags[name]
        return token.strip('"')

    for line in script_text.splitlines():
        found = re.match(r'\s*gh release upload\s+(.+)', line)
        if not found:
            continue
        tokens = found.group(1).split()
        if not tokens:
            continue
        tag = resolve(tokens[0])
        if tag not in uploads:
            continue
        for token in tokens[1:]:
            if token.startswith("-"):
                continue
            uploads[tag].append(Path(token).name)
    missing = [tag for tag, assets in uploads.items() if not assets]
    if missing:
        raise ValueError(f"publish script: no 'gh release upload' line for {missing}")
    return uploads


def parse_sums(text: str) -> dict[str, str]:
    """解析 SHA256SUMS 文本 → {文件名: sha256}；格式异常即报错（SUMS 是承诺，不能猜）。"""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        found = re.fullmatch(r"([0-9a-f]{64})  (.+)", line.strip())
        if not found:
            raise ValueError(f"SHA256SUMS: malformed line: {line.strip()[:80]}")
        name, digest = found.group(2), found.group(1)
        if name in sums:
            raise ValueError(f"SHA256SUMS: duplicate entry for {name}")
        sums[name] = digest
    if not sums:
        raise ValueError("SHA256SUMS: no entries")
    return sums


def verify_sums(sums: dict[str, str], expected_names: list[str]) -> list[str]:
    """SUMS 名单必须与预期资产集合完全一致（缺 = 资产没挂上；多 = 名单过期）。"""
    problems = []
    expected = set(expected_names)
    actual = set(sums)
    for name in sorted(expected - actual):
        problems.append(f"SHA256SUMS 缺少条目: {name}")
    for name in sorted(actual - expected):
        problems.append(f"SHA256SUMS 多出条目: {name}")
    return problems


def verify_zip_manifest(zip_path: Path, *, skill_version: str, kernel_version: str,
                        expected_skills: list[str] | None = None) -> list[str]:
    """发布 zip 的 manifest 深检：schema/skills/compat/逐文件哈希。返回问题清单。"""
    problems: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except KeyError:
            return ["zip 缺少 manifest.json"]
        if manifest.get("schema_version") != 2:
            problems.append(f"manifest schema_version 应为 2，实际 {manifest.get('schema_version')}")
        skills = [s.get("name") for s in manifest.get("skills", [])]
        versions = {s.get("version") for s in manifest.get("skills", [])}
        if expected_skills is not None and skills != expected_skills:
            problems.append(f"manifest skills 应为 {expected_skills}，实际 {skills}")
        if len(versions) != 1 or skill_version not in versions:
            problems.append(f"manifest skill 版本应配对为 {skill_version}，实际 {sorted(versions)}")
        compat = manifest.get("compat", {})
        if compat.get("patentkit") != f">={kernel_version}":
            problems.append(f"manifest compat.patentkit 应为 >={kernel_version}，实际 {compat.get('patentkit')}")
        if compat.get("assessment_protocol") != 1:
            problems.append(f"manifest compat.assessment_protocol 应为 1，实际 {compat.get('assessment_protocol')}")
        declared = {item.get("path"): item for item in manifest.get("files", [])}
        names = {n for n in archive.namelist() if not n.endswith("/")} - {"manifest.json"}
        if names != set(declared):
            problems.append("manifest.files 与 zip 实际文件集合不一致: "
                            f"缺 {sorted(names - set(declared))[:5]} 多 {sorted(set(declared) - names)[:5]}")
        for name in sorted(names & set(declared)):
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != declared[name].get("sha256"):
                problems.append(f"manifest 哈希不符: {name}")
            if len(data) != declared[name].get("size"):
                problems.append(f"manifest 大小不符: {name}")
    return problems


def _source_commit(manifest_text: str) -> str:
    return str(json.loads(manifest_text).get("source", {}).get("commit") or "")


# ── 检查脚手架 ────────────────────────────────────────────────────────────


class Result:
    def __init__(self, check_id: str, title: str, status: str, detail: str):
        self.check_id, self.title, self.status, self.detail = check_id, title, status, detail


def _run_script(args: list[str], cwd: Path | None = None, timeout: int = 300) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    proc = subprocess.run([str(a) for a in args], cwd=cwd or ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _run_guard(script: Path, *args: str) -> tuple[str, str]:
    code, output = _run_script([sys.executable, script, *args])
    if code == 0:
        return PASS, "OK"
    return FAIL, output[-1500:] or f"exit {code}"


def _skill_names() -> list[str]:
    """全部技能载荷名（从构建器 SKILL_DIRS 推导，随三技能演进自动跟上）。"""
    builder = _load_tool("build_skill_release")
    return [f"patent-{d}" for d in builder.SKILL_DIRS]


def _single_skill_names() -> list[str]:
    builder = _load_tool("build_skill_release")
    return [f"patent-{d}" for d in builder.SINGLE_SKILLS]


# ── offline 检查 ──────────────────────────────────────────────────────────


def check_pairing() -> tuple[str, str]:
    bump = _load_tool("bump_version")
    problems = bump.check()
    if problems:
        return FAIL, "\n".join(problems)
    return PASS, "bump_version.check() 全部配对点一致"


def check_guards() -> tuple[str, str]:
    """四个常驻守卫脚本：evals 清单 / 术语一致性 / 保密红线 / 引用链接。"""
    lines = []
    for script, args, label in (
        (ROOT / "evals/validate_evals.py", (), "evals 清单"),
        (ROOT / "evals/check_terminology.py", (), "中英术语一致"),
        (ROOT / "tools/check_no_workspace_data.py", (), "保密守卫"),
        (ROOT / "tools/check_reference_links.py", ("--quiet",), "引用链接"),
    ):
        status, detail = _run_guard(script, *args)
        lines.append(f"{label}: {status} {detail if status == FAIL else ''}".rstrip())
    if any(FAIL in line for line in lines):
        return FAIL, "\n".join(lines)
    return PASS, "4/4 守卫通过（evals / 术语 / 保密 / 链接）"


def _prepare_packages(dist: Path | None) -> tuple[Path, list[str], str | None]:
    """返回 (包目录, 构建出的 zip 路径列表, wheel 路径或 None)。

    --dist 给定且内容齐全时直接复用（CI 已构建）；否则现场构建双 zip 到临时目录。
    """
    wheel = None
    if dist is not None:
        zips = sorted(dist.glob("*-skill-v*.zip"))
        if len(zips) != 2:
            raise ValueError(f"--dist 缺少双 zip（full + drafting）：{[p.name for p in zips]}")
        wheels = sorted(dist.glob("patentkit-*-py3-none-any.whl"))
        wheel = wheels[0] if wheels else None
        return dist, [str(p) for p in zips], wheel
    builder = _load_tool("build_skill_release")
    out = Path(tempfile.mkdtemp(prefix="release-doctor-build-"))
    builder.build(out, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return out, sorted(str(p) for p in out.glob("*-skill-v*.zip")), None


def check_local_build(dist: Path | None) -> tuple[str, str, Path, list[Path], Path | None]:
    """构建/复用双 zip 并深检 manifest + 与发布脚本资产名单对比。

    返回 (status, detail, 包目录, zip 列表, wheel)——供安装器检查复用。
    """
    bump = _load_tool("bump_version")
    skill_version = bump._frontmatter_version("research")
    kernel_version = bump._kernel_version()
    try:
        package_dir, zips, wheel = _prepare_packages(dist)
    except Exception as exc:  # noqa: BLE001 - 构建失败本身就是要报告的结果
        return FAIL, f"构建/复用发布包失败: {exc}", ROOT, [], None

    problems: list[str] = []
    publish = parse_publish_assets((ROOT / "tools/publish_release.sh").read_text(encoding="utf-8"))
    built_names = sorted(p.name for p in package_dir.glob("*") if p.is_file())
    # 内核资产（wheel/sdist/kernel SUMS）由 CI 的内核构建步骤产出，不在 build_skill_release 范围；
    # 本检查只对 skill tag 的上传名单负责（--dist 复用时允许混有内核产物）。
    def _kernel_artifact(name: str) -> bool:
        return bool(re.fullmatch(r"(patentkit-.*\.(whl|tar\.gz)|SHA256SUMS-patentkit-.*\.txt)", name))
    skill_built = sorted(n for n in built_names if not _kernel_artifact(n))
    uploaded_skill = sorted(publish[f"skill-v{skill_version}"])
    if skill_built != uploaded_skill:
        problems.append(f"构建产物与发布脚本 skill 名单不一致:\n  构建: {skill_built}\n  发布: {uploaded_skill}")

    for zip_path in map(Path, zips):
        expected_skills = (_skill_names() if "patent-research-skill-v" in zip_path.name
                           else _single_skill_names())
        problems += [f"{zip_path.name}: {p}" for p in
                     verify_zip_manifest(zip_path, skill_version=skill_version,
                                         kernel_version=kernel_version, expected_skills=expected_skills)]
    for sums_file in package_dir.glob("SHA256SUMS-*.txt"):
        try:
            sums = parse_sums(sums_file.read_text(encoding="utf-8"))
        except ValueError as exc:
            problems.append(f"{sums_file.name}: {exc}")
            continue
        # 每份 SUMS 只对自己的 tag 名单负责（dist 混装 kernel/skill 产物时互不越界）
        sums_tag = next((t for t, assets in publish.items()
                         if sums_file.name in assets), None)
        expected = [n for n in publish.get(sums_tag, []) if n != sums_file.name] if sums_tag else None
        if expected is not None:
            problems += [f"{sums_file.name}: {p}" for p in verify_sums(sums, expected)]
        for name, digest in sums.items():
            path = package_dir / name
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                problems.append(f"{sums_file.name}: 哈希不符 {name}")
    if problems:
        return FAIL, "\n".join(problems), package_dir, [Path(p) for p in zips], wheel
    detail = f"双 zip manifest/SUMS/资产名单一致（skill {skill_version} / kernel {kernel_version}）"
    return PASS, detail, package_dir, [Path(p) for p in zips], wheel


def _installer_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _kernel_env(work: Path, wheel: Path | None) -> tuple[dict[str, str] | None, str]:
    """为 ps1/bash 安装器准备"内核可导入"的环境（安装器有内核前置检查）。

    优先复用当前环境；当前环境 import 不了且手上有 wheel 时，造一次性 venv 并把
    wheel 装进去（绝不污染当前环境）。返回 (env|None, 说明)；None = 两个前提都不
    满足，调用方应 SKIP。
    """
    probe = subprocess.run([sys.executable, "-c", "import patentkit"], capture_output=True, timeout=60)
    if probe.returncode == 0:
        return _installer_env(), "当前环境已含内核"
    if wheel is None or not wheel.is_file():
        return None, "当前环境无内核且无 wheel 可装"
    venv = work / "installer-venv"
    proc = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=180)
    if proc.returncode != 0:
        return None, f"一次性 venv 创建失败: {(proc.stdout + proc.stderr)[-300:]}"
    pip = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
    proc = subprocess.run([str(pip), "-m", "pip", "install", "--quiet", str(wheel)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=420)
    if proc.returncode != 0:
        return None, f"venv 内安装内核 wheel 失败: {(proc.stdout + proc.stderr)[-400:]}"
    env = _installer_env()
    env["PATH"] = str(venv / ("Scripts" if os.name == "nt" else "bin")) + os.pathsep + env["PATH"]
    return env, "一次性 venv + 下载的 wheel"


def _try_ps1(package: Path, dest: Path, env: dict[str, str]) -> tuple[bool, str]:
    shell = None
    for candidate in ("pwsh", "powershell"):
        found = __import__("shutil").which(candidate)
        if found:
            shell = found
            break
    if not shell:
        return False, "no PowerShell found"
    proc = subprocess.run([shell, "-NoProfile", "-File", str(package / "install.ps1"),
                           "-Dest", str(dest)], env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=INSTALL_TIMEOUT)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()[-1200:]


def _try_bash(package: Path, dest: Path, env: dict[str, str]) -> tuple[bool, str]:
    proc = subprocess.run(["bash", str(package / "install.sh"), "--dest", str(dest)],
                          env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=INSTALL_TIMEOUT)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()[-1200:]


def _try_oneclick(bundle: Path, dest: Path, work: Path) -> tuple[bool, str]:
    """one-click 实测前先造一次性 venv 并插到 PATH 最前：安装器会 `pip install`
    内核 wheel，绝不能落进当前运行环境（本地是 -e 开发安装，CI runner 同理）。"""
    venv = work / "oneclick-venv"
    proc = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=180)
    if proc.returncode != 0:
        return False, f"一次性 venv 创建失败: {proc.stdout}{proc.stderr}"[-800:]
    env = _installer_env()
    venv_scripts = venv / "Scripts" if os.name == "nt" else venv / "bin"
    env["PATH"] = str(venv_scripts) + os.pathsep + env["PATH"]
    comspec = os.environ.get("COMSPEC", "cmd.exe")
    installer = bundle / "install-oneclick.cmd"
    command = f'"{comspec}" /d /s /c ""{installer}" --quiet --dest "{dest}""'
    proc = subprocess.run(command, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=INSTALL_TIMEOUT, shell=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()[-1200:]


def _installed_ok(dest: Path, skills: list[str]) -> list[str]:
    missing = [s for s in skills if not (dest / s / "SKILL.md").is_file()]
    return [] if not missing else [f"安装后缺少 {m}/SKILL.md" for m in missing]


def check_installers(package: Path, zips: list[Path], wheel: Path | None) -> tuple[str, str]:
    """按当前平台能跑的安装器实测：ps1（跨平台）、bash（POSIX）、one-click（Windows）。"""
    lines: list[str] = []
    failed = False
    full_zip = next((z for z in zips if "patent-research-skill-v" in z.name), None)
    with tempfile.TemporaryDirectory(prefix="release-doctor-install-") as tmp:
        work = Path(tmp)
        with zipfile.ZipFile(full_zip) as archive:
            archive.extractall(work / "pkg")
        statuses = []

        def record(label: str, ok: bool, output: str, ran: bool, why: str = "") -> None:
            nonlocal failed
            if not ran:
                statuses.append(f"{label}: SKIP（{why}）")
                return
            missing = _installed_ok(dest_for[label], _skill_names())
            ok = ok and not missing
            statuses.append(f"{label}: {'PASS' if ok else 'FAIL'}{(' — ' + '；'.join(missing)) if missing else ''}")
            if not ok:
                statuses.append(f"  输出尾部: {output}")
                failed = True

        dest_for: dict[str, Path] = {}
        ran = __import__("shutil").which("pwsh") or __import__("shutil").which("powershell")
        env, env_note = _kernel_env(work, wheel)
        dest_for["install.ps1"] = work / "dest-ps1"
        record("install.ps1", *_try_ps1(work / "pkg", dest_for["install.ps1"], env) + (bool(ran) and env is not None,
               "无 PowerShell" if not ran else f"内核环境不可用（{env_note}）"))
        if os.name != "nt":
            dest_for["install.sh"] = work / "dest-sh"
            record("install.sh", *_try_bash(work / "pkg", dest_for["install.sh"], env) + (env is not None,
                   f"内核环境不可用（{env_note}）"))
        else:
            statuses.append("install.sh: SKIP（POSIX 安装器由 Linux CI 覆盖）")
        if os.name == "nt":
            if wheel is not None and wheel.is_file():
                bundle = work / "bundle"
                bundle.mkdir()
                __import__("shutil").copy2(wheel, bundle / wheel.name)
                __import__("shutil").copy2(full_zip, bundle / full_zip.name)
                __import__("shutil").copy2(work / "pkg" / "install-oneclick.cmd", bundle / "install-oneclick.cmd")
                dest_for["install-oneclick.cmd"] = work / "dest-oneclick"
                record("install-oneclick.cmd", *_try_oneclick(bundle, dest_for["install-oneclick.cmd"], work) + (True, ""))
            else:
                statuses.append("install-oneclick.cmd: SKIP（本地无内核 wheel；CI check job 带 --dist 会跑）")
        else:
            statuses.append("install-oneclick.cmd: SKIP（Windows 专用）")
        lines += statuses
    if failed:
        return FAIL, "\n".join(lines)
    return PASS, "；".join(lines)


# ── release（网络）检查 ───────────────────────────────────────────────────


class Github:
    def __init__(self, repo: str, token: str | None, timeout: int = 60):
        self.repo, self.token, self.timeout = repo, token, timeout

    def get(self, path: str, accept: str = "application/vnd.github+json") -> bytes:
        request = urllib.request.Request(f"{REPO_API}/repos/{self.repo}/{path}",
                                         headers={"Accept": accept, "User-Agent": "release-doctor"})
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def releases(self) -> list[dict]:
        out = []
        for page in (1, 2, 3):
            batch = json.loads(self.get(f"releases?per_page=100&page={page}"))
            out += batch
            if len(batch) < 100:
                break
        return out

    def latest_tag(self) -> str:
        return str(json.loads(self.get("releases/latest")).get("tag_name") or "")

    def asset(self, asset_id: int) -> bytes:
        return self.get(f"releases/assets/{asset_id}", accept="application/octet-stream")


def _owner_repo() -> str:
    url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"],
                                  cwd=ROOT, text=True).strip()
    found = re.search(r"github\.com[/:]([\w.-]+/[\w.-]+?)(?:\.git)?$", url)
    if not found:
        raise ValueError(f"无法从 remote.origin.url 解析 owner/repo: {url}")
    return found.group(1)


def _is_ancestor(maybe_ancestor: str, descendant: str) -> bool:
    """maybe_ancestor 是否为 descendant 的祖先（用于"发布后有补充提交"的判定）。

    需要 checkout 带 publish 提交的完整历史（CI 传 fetch-depth: 0）；浅克隆下
    判定不了就返回 False（按严格相等语义报错，宁可误报不可漏报）。
    """
    try:
        return subprocess.run(["git", "merge-base", "--is-ancestor", maybe_ancestor, descendant],
                              cwd=ROOT, capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def check_release_state(gh: Github, expect_commit: str | None) -> tuple[str, str]:
    bump = _load_tool("bump_version")
    skill_version, kernel_version = bump._frontmatter_version("research"), bump._kernel_version()
    tags = {"skill": f"skill-v{skill_version}", "kernel": f"patentkit-v{kernel_version}"}
    by_tag = {rel.get("tag_name"): rel for rel in gh.releases()}
    latest = gh.latest_tag()
    problems, notes = [], []
    for key, tag in tags.items():
        rel = by_tag.get(tag)
        if rel is None:
            problems.append(f"Release 不存在: {tag}")
            continue
        if rel.get("draft"):
            problems.append(f"{tag} 仍是 draft")
        if rel.get("prerelease"):
            problems.append(f"{tag} 被标记为 prerelease")
        commit = rel.get("target_commitish") or ""
        if expect_commit and commit != expect_commit:
            if key == "skill" and not _is_ancestor(commit, expect_commit):
                # 严格相等只适用于"发布就是本次推送"的场景；发布后有纯 CI/文档类
                # 补充提交时，只要求发布来源是当前提交的祖先（fetch-depth: 0 下可判）。
                problems.append(f"{tag} target_commitish={commit} ≠ 期望 {expect_commit}（且非其祖先）")
            elif key == "skill":
                notes.append(f"{tag} 来自当前历史的祖先提交 {commit[:12]}（发布后有补充提交）")
            else:
                # 内核未升版的轮次不重发 kernel tag，指向旧提交属预期（配对由 manifest.compat 把关）
                notes.append(f"{tag} 未随本轮重发（target={commit[:12]}）")
        if key == "skill" and latest != tag:
            problems.append(f"Latest release 是 {latest}，应为 {tag}")
        if key == "kernel" and latest == tag:
            problems.append("内核 Release 不应占据 Latest（skill 才是门面）")
    if problems:
        return FAIL, "\n".join(problems)
    detail = (f"{tags['skill']} = Latest、{tags['kernel']} 非草稿；"
              f"skill target_commitish{(' = ' + expect_commit) if expect_commit else ' 已核对'}"
              + ("；" + "；".join(notes) if notes else ""))
    return PASS, detail


def _release_assets(gh: Github, tag: str) -> dict[str, dict]:
    rel = next((r for r in gh.releases() if r.get("tag_name") == tag), None)
    if rel is None:
        raise ValueError(f"release {tag} not found")
    return {a["name"]: a for a in rel.get("assets", [])}


def check_release_assets(gh: Github) -> tuple[str, str]:
    bump = _load_tool("bump_version")
    skill_version, kernel_version = bump._frontmatter_version("research"), bump._kernel_version()
    publish = parse_publish_assets((ROOT / "tools/publish_release.sh").read_text(encoding="utf-8"))
    problems = []
    actual_assets = {}
    for key, tag in (("skill", f"skill-v{skill_version}"), ("kernel", f"patentkit-v{kernel_version}")):
        try:
            actual_assets[tag] = _release_assets(gh, tag)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        expected = set(publish[tag])
        actual = set(actual_assets[tag])
        if actual != expected:
            problems.append(f"{tag} 资产名单不一致:\n  应有: {sorted(expected)}\n  实际: {sorted(actual)}")
    if problems:
        return FAIL, "\n".join(problems)
    total = sum(len(v) for v in actual_assets.values())
    return PASS, f"两个 Release 的 {total} 个资产与发布脚本名单完全一致"


def check_release_hashes(gh: Github) -> tuple[str, str, dict[str, bytes]]:
    """下载全部资产，校验每个文件 sha256 对 SUMS；返回 {资产名: 字节} 供安装测试复用。"""
    bump = _load_tool("bump_version")
    skill_version, kernel_version = bump._frontmatter_version("research"), bump._kernel_version()
    publish = parse_publish_assets((ROOT / "tools/publish_release.sh").read_text(encoding="utf-8"))
    problems, blobs = [], {}
    for tag in (f"skill-v{skill_version}", f"patentkit-v{kernel_version}"):
        assets = _release_assets(gh, tag)
        sums_asset = next((a for name, a in assets.items() if name.startswith("SHA256SUMS-")), None)
        if sums_asset is None:
            problems.append(f"{tag} 缺少 SHA256SUMS 资产")
            continue
        sums = parse_sums(gh.asset(sums_asset["id"]).decode("utf-8"))
        problems += [f"{tag}: {p}" for p in verify_sums(sums, [n for n in assets if n != sums_asset["name"]])]
        for name, asset in assets.items():
            if name == sums_asset["name"]:
                continue
            data = gh.asset(asset["id"])
            blobs[name] = data
            if hashlib.sha256(data).hexdigest() != sums.get(name):
                problems.append(f"{tag}: {name} sha256 与 SUMS 不符")
    if problems:
        return FAIL, "\n".join(problems), {}
    return PASS, f"{len(blobs)} 个资产逐个重算 sha256 与 SUMS 一致", blobs


def check_release_manifest(gh: Github, blobs: dict[str, bytes]) -> tuple[str, str]:
    bump = _load_tool("bump_version")
    skill_version, kernel_version = bump._frontmatter_version("research"), bump._kernel_version()
    problems, commits = [], set()
    for name, expected_skills in ((f"patent-research-skill-v{skill_version}.zip", _skill_names()),
                                  (f"patent-drafting-skill-v{skill_version}.zip", _single_skill_names())):
        data = blobs.get(name)
        if data is None:
            problems.append(f"缺少发布资产 {name}（无法做 manifest 深检）")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_bytes(data)
            problems += [f"{name}: {p}" for p in
                         verify_zip_manifest(path, skill_version=skill_version,
                                             kernel_version=kernel_version, expected_skills=expected_skills)]
            with zipfile.ZipFile(path) as archive:
                commits.add(_source_commit(archive.read("manifest.json").decode("utf-8")))
    if len(commits) > 1:
        problems.append(f"两个 zip 的 source.commit 不一致: {sorted(commits)}")
    if problems:
        return FAIL, "\n".join(problems)
    detail = f"manifest 深检通过（source.commit={next(iter(commits), '?')[:12]}）"
    return PASS, detail


def check_release_notes(gh: Github) -> tuple[str, str]:
    bump = _load_tool("bump_version")
    skill_version, kernel_version = bump._frontmatter_version("research"), bump._kernel_version()
    problems = []
    for tag in (f"skill-v{skill_version}", f"patentkit-v{kernel_version}"):
        rel = next((r for r in gh.releases() if r.get("tag_name") == tag), None)
        body = (rel or {}).get("body") or ""
        if not body.strip():
            problems.append(f"{tag} 的 Release 说明为空")
            continue
        notes = (ROOT / "release/notes" / f"{tag}.md").read_text(encoding="utf-8")
        first_heading = next((line for line in notes.splitlines() if line.startswith("# ")), "")
        if first_heading and first_heading.strip() not in body:
            problems.append(f"{tag} 的说明首行与 release/notes/{tag}.md 不符")
    if problems:
        return FAIL, "\n".join(problems)
    return PASS, "两个 Release 的说明非空且与 notes 文件同源"


def check_release_install(gh: Github, blobs: dict[str, bytes]) -> tuple[str, str]:
    """用**下载到的真实资产**跑安装测试（区别于 offline 档的本地构建产物）。"""
    bump = _load_tool("bump_version")
    skill_version = bump._frontmatter_version("research")
    full_name = f"patent-research-skill-v{skill_version}.zip"
    statuses: list[str] = []
    failed = False
    with tempfile.TemporaryDirectory(prefix="release-doctor-relinst-") as tmp:
        work = Path(tmp)
        full_zip = work / full_name
        full_zip.write_bytes(blobs[full_name])
        with zipfile.ZipFile(full_zip) as archive:
            archive.extractall(work / "pkg")
        wheel_name = f"patentkit-{bump._kernel_version()}-py3-none-any.whl"
        wheel = work / wheel_name
        if wheel_name in blobs:
            wheel.write_bytes(blobs[wheel_name])

        def record(label: str, ok: bool, output: str, ran: bool, why: str = "") -> None:
            nonlocal failed
            if not ran:
                statuses.append(f"{label}: SKIP（{why}）")
                return
            missing = _installed_ok(dest[label], _skill_names())
            ok = ok and not missing
            statuses.append(f"{label}: {'PASS' if ok else 'FAIL'}{(' — ' + '；'.join(missing)) if missing else ''}")
            if not ok:
                statuses.append(f"  输出尾部: {output}")
                failed = True

        dest: dict[str, Path] = {}
        ran = bool(__import__("shutil").which("pwsh") or __import__("shutil").which("powershell"))
        env, env_note = _kernel_env(work, wheel if wheel.is_file() else None)
        dest["install.ps1"] = work / "dest-ps1"
        record("install.ps1", *_try_ps1(work / "pkg", dest["install.ps1"], env) + (ran and env is not None,
               "无 PowerShell" if not ran else f"内核环境不可用（{env_note}）"))
        if os.name != "nt":
            dest["install.sh"] = work / "dest-sh"
            record("install.sh", *_try_bash(work / "pkg", dest["install.sh"], env) + (env is not None,
                   f"内核环境不可用（{env_note}）"))
        else:
            statuses.append("install.sh: SKIP（POSIX 安装器由 Linux CI 覆盖）")
        if os.name == "nt" and wheel.is_file():
            bundle = work / "bundle"
            bundle.mkdir()
            __import__("shutil").copy2(wheel, bundle / wheel.name)
            __import__("shutil").copy2(full_zip, bundle / full_zip.name)
            __import__("shutil").copy2(work / "pkg" / "install-oneclick.cmd", bundle / "install-oneclick.cmd")
            dest["install-oneclick.cmd"] = work / "dest-oneclick"
            record("install-oneclick.cmd", *_try_oneclick(bundle, dest["install-oneclick.cmd"], work) + (True, ""))
        elif os.name == "nt":
            statuses.append("install-oneclick.cmd: SKIP（Release 未含内核 wheel 资产）")
        else:
            statuses.append("install-oneclick.cmd: SKIP（Windows 专用）")
    if failed:
        return FAIL, "\n".join(statuses)
    return PASS, "；".join(statuses)


def check_kernel_wheel(blobs: dict[str, bytes]) -> tuple[str, str]:
    """内核 wheel 隔离导入：--target 解包 + import 断言，不污染当前环境。"""
    bump = _load_tool("bump_version")
    kernel_version = bump._kernel_version()
    wheel_name = f"patentkit-{kernel_version}-py3-none-any.whl"
    data = blobs.get(wheel_name)
    if data is None:
        return SKIP, "Release 未含内核 wheel（或前序哈希检查未通过）"
    with tempfile.TemporaryDirectory(prefix="release-doctor-wheel-") as tmp:
        target = Path(tmp) / "site"
        with zipfile.ZipFile(__import__("io").BytesIO(data)) as archive:
            archive.extractall(target)
        code = ("import sys, patentkit; "
                "from patentkit.assessment import PROTOCOL_VERSION; "
                f"assert patentkit.__version__ == '{kernel_version}', patentkit.__version__; "
                "assert PROTOCOL_VERSION == 1, PROTOCOL_VERSION; "
                "assert patentkit.__file__ and sys.path[0] in patentkit.__file__, patentkit.__file__")
        code = code.replace("sys.path[0]", repr(str(target)))
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(target)})
        if proc.returncode != 0:
            return FAIL, f"wheel 导入断言失败:\n{proc.stdout}{proc.stderr}"[-1200:]
    sdist_name = f"patentkit-{kernel_version}.tar.gz"
    if sdist_name in blobs:
        with tarfile.open(fileobj=__import__("io").BytesIO(blobs[sdist_name]), mode="r:gz") as archive:
            if not any(m.name.endswith("patentkit/__init__.py") for m in archive.getmembers()):
                return FAIL, f"{sdist_name} 内未见 patentkit/__init__.py"
    return PASS, f"wheel {kernel_version} 导入断言通过（版本 / 协议 1 / 隔离路径）"


# ── 汇总 ─────────────────────────────────────────────────────────────────


def run_offline(dist: Path | None) -> list[Result]:
    results = [Result("pairing", "版本配对点（bump --check）", *check_pairing())]
    results.append(Result("guards", "evals/术语/保密/链接四守卫", *check_guards()))
    status, detail, package, zips, wheel = check_local_build(dist)
    results.append(Result("local-build", "双 zip 构建 + manifest + SUMS + 资产名单", status, detail))
    if status == PASS:
        results.append(Result("installers", "本机平台安装器实测", *check_installers(package, zips, wheel)))
    else:
        results.append(Result("installers", "本机平台安装器实测", SKIP, "构建检查未通过"))
    results.append(Result("extension-wheel", "可选扩展 wheel 独立校验（O-04）", *check_extension_wheel_files(package)))
    if dist is None and package != ROOT:
        __import__("shutil").rmtree(package, ignore_errors=True)  # 现场构建的临时产物
    return results


def run_release(expect_commit: str | None) -> list[Result]:
    gh = Github(_owner_repo(), os.environ.get("GITHUB_TOKEN") or None)
    results = [Result("pairing", "版本配对点（bump --check）", *check_pairing())]
    state = check_release_state(gh, expect_commit)
    results.append(Result("release-state", "Release 存在性 / draft / latest / commit", *state))
    if state[0] == FAIL:
        results.append(Result("release-assets", "Release 资产名单", SKIP, "Release 状态检查未通过"))
        results.append(Result("release-hashes", "资产 sha256 对 SUMS", SKIP, "Release 状态检查未通过"))
        return results
    results.append(Result("release-assets", "Release 资产名单", *check_release_assets(gh)))
    hashes = check_release_hashes(gh)
    results.append(Result("release-hashes", "资产 sha256 对 SUMS", hashes[0], hashes[1]))
    if hashes[0] == PASS:
        results.append(Result("release-manifest", "发布 zip manifest 深检", *check_release_manifest(gh, hashes[2])))
        results.append(Result("release-notes", "Release 说明非空且同源", *check_release_notes(gh)))
        results.append(Result("release-install", "真实资产安装测试", *check_release_install(gh, hashes[2])))
        results.append(Result("kernel-wheel", "内核 wheel 隔离导入", *check_kernel_wheel(hashes[2])))
    else:
        for check_id, title in (("release-manifest", "发布 zip manifest 深检"),
                                ("release-notes", "Release 说明非空且同源"),
                                ("release-install", "真实资产安装测试"),
                                ("kernel-wheel", "内核 wheel 隔离导入")):
            results.append(Result(check_id, title, SKIP, "哈希检查未通过，跳过依赖下载资产的检查"))
    return results


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="本地预检（默认）")
    mode.add_argument("--release", action="store_true", help="审计 GitHub 实际 Release（走 api.github.com）")
    parser.add_argument("--dist", type=Path, help="offline 模式复用已构建的 dist（含内核 wheel 时 one-click 才可测）")
    parser.add_argument("--expect-commit", help="release 模式核对 target_commitish（CI 传 github.sha）")
    parser.add_argument("--json", action="store_true", help="输出机器可读报告")
    args = parser.parse_args()

    try:
        results = run_release(args.expect_commit) if args.release else run_offline(args.dist)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"release-doctor 环境错误: {exc}\n")

    report = {"mode": "release" if args.release else "offline",
              "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "ok": all(r.status != FAIL for r in results),
              "checks": [{"id": r.check_id, "title": r.title, "status": r.status,
                          "detail": r.detail} for r in results]}
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"release-doctor（{report['mode']}）")
        for r in results:
            mark = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}[r.status]
            print(f"  [{mark}] {r.check_id} — {r.title}")
            for line in r.detail.splitlines():
                print(f"         {line}")
        failed = sum(1 for r in results if r.status == FAIL)
        skipped = sum(1 for r in results if r.status == SKIP)
        print(f"  结论: {'✅ 通过' if report['ok'] else '✗ 存在失败'}"
              f"（{len(results)} 项：失败 {failed}，跳过 {skipped}）")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
