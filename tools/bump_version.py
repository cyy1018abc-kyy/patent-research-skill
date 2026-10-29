"""全仓版本号配对点升级工具（skill ↔ kernel ↔ 发布脚本的硬编码配对点）。

背景：版本号散布在十余处硬编码点（两个 SKILL frontmatter 及其英文镜像、验收测试、
安装文档、发布脚本 tag、CI 资产名、patches README 指针），漏一处则 CI 断，
或推 main 只过 CI 却不发版（publish 对已存在 tag 直接 no-op）。本工具把配对点
固化为显式清单，并做三层防护：

1. **定向替换**：只改动清单内文件（词边界正则，kernel 0.3.0 与 skill 3.0.1 互不误伤）；
2. **一致性校验（--check，可单跑，已入 CI）**：frontmatter 配对、测试文件名、
   发布脚本 tag、notes 文件存在性、内核版本三处口径一致；
3. **残留扫描**：替换后全仓 grep 旧版本号，白名单（CHANGELOG/docs/历史 notes/
   补丁文件/镜像 README 的"since x.y.z"陈述）之外出现即失败。

用法：
    python tools/bump_version.py --check                 # 只校验（CI 用）
    python tools/bump_version.py --to 3.1.0 --notes      # skill 配对升级 + notes 骨架
    python tools/bump_version.py --to 3.2.0 --kernel-to 0.4.0 --notes
    python tools/bump_version.py --to 3.1.0 --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKILL_PAIRING_FILES = (
    ("research/SKILL.md", "research frontmatter"),
    ("drafting/SKILL.md", "drafting frontmatter"),
    ("discovery/SKILL.md", "discovery frontmatter"),
    ("research/references.en/SKILL.en.md", "research 英文镜像 frontmatter"),
    ("drafting/references.en/SKILL.en.md", "drafting 英文镜像 frontmatter"),
    ("discovery/references.en/SKILL.en.md", "discovery 英文镜像 frontmatter"),
    ("discovery/README.md", "discovery README 版本头"),
    ("tests/test_release.py", "发布验收 zip 文件名"),
    ("tests/test_assessment_contract.py", "SKILL version 断言"),
    ("evals/evals.json", "评测清单 skill_version（3.9.0 轮补入：残留扫描抓到的漏网配对点）"),
    ("release/INSTALL.md", "安装文档 tag/zip/notes 链接"),
    ("release/install-oneclick.cmd", "一键安装器 zip 名"),
    ("release/install-guide-for-colleagues.md", "同事安装指南"),
    ("README.md", "仓库 README（版本头、下载表、兼容性、版本行）"),
    ("release/patches/README.md", "补丁 README 的 notes 指针"),
    ("tools/publish_release.sh", "发布脚本 skill tag 与上传资产名"),
)

KERNEL_PAIRING_FILES = (
    ("tools/build_skill_release.py", "构建器 KERNEL_VERSION 门"),
    ("tools/publish_release.sh", "发布脚本 kernel tag 与 wheel/sdist 资产名"),
    (".github/workflows/ci.yml", "CI wheel glob 与 SHA256SUMS 名"),
    ("research/scripts/_env.py", "内核版本错误提示"),
    ("research/scripts/self_test.py", "REQUIRED_KERNEL 与文档"),
    ("release/install-oneclick.cmd", "一键安装器 wheel 名"),
    ("release/install.ps1", "PowerShell 安装器内核提示"),
    ("release/install.sh", "bash 安装器内核提示"),
    ("tests/test_release.py", "验收测试的 wheel 文件名"),
    ("tests/test_assessment_contract.py", "内核错误消息版本断言"),
    ("research/SKILL.md", "SKILL 配套版本行"),
    ("drafting/SKILL.md", "SKILL 配套版本行"),
    ("discovery/SKILL.md", "SKILL 配套版本行"),
    ("research/references.en/SKILL.en.md", "英文镜像配套版本行"),
    ("drafting/references.en/SKILL.en.md", "英文镜像配套版本行"),
    ("discovery/references.en/SKILL.en.md", "英文镜像配套版本行"),
    ("discovery/README.md", "discovery README 内核要求行"),
    ("drafting/README.md", "drafting README 前置版本行"),
    # 注意：release/patches/README.md 故意不在本清单——它含历史叙述段
    # （"Skill 2.5.0 requires patentkit 0.3.0"），整文件替换会篡改历史；
    # 当前补丁名与 notes 指针由 check() 专项校验，新版本的叙述段手工更新。
    ("release/INSTALL.md", "安装文档内核版本"),
    ("release/install-guide-for-colleagues.md", "同事安装指南内核版本"),
    ("README.md", "README 内核版本"),
)

#: 旧版本号允许残留下来的位置（历史记录，不属于当前配对点）。
RESIDUE_WHITELIST = (
    ("CHANGELOG.md", "历史条目"),
    ("docs/", "历史报告/决策备忘"),
    ("release/notes/", "历史发布说明"),
    ("release/patches/", "历史补丁文件名"),
    ("research/references.en/README.md", "镜像完成时间的 since 陈述"),
    ("drafting/references.en/README.md", "镜像完成时间的 since 陈述"),
    ("research/README.md", "历史能力表标题含当年内核版本；安装节 wheel 名由 check() 专项校验"),
    ("research/references/06-drafting-and-polishing-rules.md", "「内核 0.3.0 起」历史陈述"),
    ("research/references/07-assessment-protocol.md", "协议兼容性历史陈述"),
    ("research/references/08-figures.md", "「实现于内核 0.3.0」历史陈述"),
    ("research/references.en/08-figures.md", "「kernel 0.3.0」历史陈述"),
    ("research/references/02-query-templates.md", "「内核 0.4.0 起有工具」历史陈述"),
    ("research/references.en/02-query-templates.md", "「since kernel 0.4.0」历史陈述"),
    ("drafting/references/13-revision-loop.md", "「内核 0.4.0 起强制执行」历史陈述"),
    ("drafting/references.en/13-revision-loop.md", "「Since kernel 0.4.0」历史陈述"),
    ("research/references/05-acceptance-gates.md", "「0.6.0 起 G-S-04 普查记录」历史陈述"),
    ("research/references.en/05-acceptance-gates.md", "「Since 0.6.0」G-S-04 census history"),
    ("drafting/references/15-claims-and-support.md", "「内核 0.8.0 起，D-019 citations」历史陈述（特性发布于 0.8.0）"),
    ("drafting/references.en/15-claims-and-support.md", "「kernel 0.8.0」D-019 citations history"),
    ("tools/build_kernel_patch.py", "工具文档字符串里的历史补丁名示例"),
    ("tools/render_terminal_shot.py", "截图脚注按当次发布手工更新"),
    ("evals/check_terminology.py", "「3.1.0 起全部双语」历史陈述"),
    ("tools/bump_version.py", "本工具自身的文档字符串"),
)


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _frontmatter_version(skill_dir: str) -> str:
    text = (ROOT / skill_dir / "SKILL.md").read_text(encoding="utf-8")
    meta = __import__("yaml").safe_load(text.split("---", 2)[1])
    return str(meta["metadata"]["version"])


def _kernel_version() -> str:
    text = (ROOT / "tools/build_skill_release.py").read_text(encoding="utf-8")
    found = re.search(r'KERNEL_VERSION = "(\d+\.\d+\.\d+)"', text)
    if not found:
        raise SystemExit("无法从 tools/build_skill_release.py 解析 KERNEL_VERSION")
    return found.group(1)


def _version_pattern(old: str) -> re.Pattern[str]:
    # 词边界按"数字段"界定：前面不能是数字/点（防 13.0.1），后面不能紧跟数字或
    # ".数字"（防 3.0.12 / 3.0.1.5），但允许 .zip/.md 这类非数字后缀。
    return re.compile(rf"(?<![\d.]){re.escape(old)}(?!\d)(?!\.\d)")


def _residue_allowed(rel_path: str) -> str | None:
    for prefix, reason in RESIDUE_WHITELIST:
        if rel_path == prefix or rel_path.startswith(prefix):
            return reason
    return None


def scan_residue(old: str) -> list[str]:
    """全仓扫描旧版本号残留；白名单之外的出现即问题。"""
    import subprocess

    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    pattern = _version_pattern(old)
    problems = []
    for rel in tracked:
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if pattern.search(line) and not _residue_allowed(rel):
                problems.append(f"{rel}:{line_no}: {line.strip()[:100]}")
    return problems


def check() -> list[str]:
    """当前版本配对点一致性校验（--check；CI 每次推送都跑）。"""
    problems: list[str] = []
    skill = _frontmatter_version("research")
    kernel = _kernel_version()

    paired = {"research": skill, "drafting": _frontmatter_version("drafting")}
    if len(set(paired.values())) != 1:
        problems.append(f"两技能版本必须配对：{paired}")

    for skill_dir in ("research", "drafting"):
        mirror = ROOT / skill_dir / "references.en" / "SKILL.en.md"
        if mirror.is_file() and f"version: {skill}" not in mirror.read_text(encoding="utf-8"):
            problems.append(f"{skill_dir}/references.en/SKILL.en.md 的 version 与 {skill} 不一致")

    release_py = (ROOT / "tests/test_release.py").read_text(encoding="utf-8")
    for name in (f"patent-research-skill-v{skill}.zip", f"patent-drafting-skill-v{skill}.zip"):
        if name not in release_py:
            problems.append(f"tests/test_release.py 缺少 {name}")

    publish = (ROOT / "tools/publish_release.sh").read_text(encoding="utf-8")
    if f"skill-v{skill}" not in publish:
        problems.append(f"tools/publish_release.sh 的 skill tag 不是 skill-v{skill}")
    if f"patentkit-v{kernel}" not in publish:
        problems.append(f"tools/publish_release.sh 的 kernel tag 不是 patentkit-v{kernel}")

    for notes in (f"release/notes/skill-v{skill}.md", f"release/notes/patentkit-v{kernel}.md"):
        if not (ROOT / notes).is_file():
            problems.append(f"发布脚本依赖的 release notes 缺失（缺失则 publish 失败）：{notes}")

    env_py = (ROOT / "research/scripts/_env.py").read_text(encoding="utf-8")
    if f"patentkit >= {kernel}" not in env_py:
        problems.append(f"research/scripts/_env.py 的错误提示与内核 {kernel} 不一致")

    research_readme = (ROOT / "research/README.md").read_text(encoding="utf-8")
    if f"patentkit-{kernel}-py3-none-any.whl" not in research_readme:
        problems.append(f"research/README.md 安装节的 wheel 名与内核 {kernel} 不一致")

    # 安装器 / 自检 / 测试里的内核版本（3.2.0 升级时由残留扫描发现，这里固化为常驻校验）
    kernel_needles = {
        "release/install-oneclick.cmd": [f"patentkit-{kernel}-py3-none-any.whl"],
        "release/install.ps1": [f"patentkit {kernel}"],
        "release/install.sh": [f"patentkit {kernel}"],
        "research/scripts/self_test.py": [f'REQUIRED_KERNEL = "{kernel}"'],
        "tests/test_assessment_contract.py": [f'assertIn("{kernel}"'],
        "research/SKILL.md": [f"patentkit >= {kernel}"],
        "drafting/SKILL.md": [f"patentkit >= {kernel}"],
    }
    for rel, needles in kernel_needles.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                problems.append(f"{rel} 缺少 {needle!r}（内核 {kernel} 配对点）")

    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for needle in (f"patentkit-{kernel}-py3-none-any.whl", f"SHA256SUMS-patentkit-v{kernel}.txt"):
        if needle not in ci:
            problems.append(f".github/workflows/ci.yml 缺少 {needle}")

    patches_readme = (ROOT / "release/patches/README.md").read_text(encoding="utf-8")
    if f"../notes/skill-v{skill}.md" not in patches_readme:
        problems.append(f"release/patches/README.md 的 notes 指针不是 skill-v{skill}.md")
    if not re.search(rf"patentkit-\d+\.\d+\.\d+-to-{re.escape(kernel)}\.patch", patches_readme):
        problems.append(f"release/patches/README.md 未指向当前内核补丁 -to-{kernel}.patch")
    # 散文版本号两处（0.8.0 轮漏改「current kernel is 0.7.0 / declares version 0.7.0」的教训固化）
    if f"current kernel is **{kernel}**" not in patches_readme:
        problems.append(f"release/patches/README.md 的「current kernel is」散文版本不是 {kernel}")
    if f"version `{kernel}`" not in patches_readme:
        problems.append(f"release/patches/README.md 的「declares version」散文版本不是 {kernel}")
    for patch in ROOT.glob("release/patches/patentkit-*-to-*.patch"):
        if f"-to-{kernel}.patch" not in patch.name:
            continue
        applied_gate = f"-to-{kernel}.patch"
        if applied_gate not in (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"):
            problems.append(f"ci.yml 未引用当前内核补丁 {patch.name}")
        break

    if not problems:
        print(f"✅ 版本配对点一致：skill（research+drafting+discovery）={skill}，kernel={kernel}，"
              f"测试/发布脚本/CI/notes/补丁指针全部对齐")
    return problems


def _write_notes(kind: str, version: str, old: str) -> Path:
    """从上一版 notes 生成骨架：替换版本号，清空变更段留 TODO。"""
    source = ROOT / "release/notes" / f"{kind}-v{old}.md"
    target = ROOT / "release/notes" / f"{kind}-v{version}.md"
    if target.exists():
        print(f"  · notes 已存在，跳过生成：{target.relative_to(ROOT)}")
        return target
    if source.is_file():
        text = _version_pattern(old).sub(version, source.read_text(encoding="utf-8"))
        text = re.sub(r"(## 什么变了.*?)(?=## )", r"\1\n- [TODO: 本次变更点，逐条列出]\n\n", text, flags=re.S)
    else:
        text = (f"# {kind} {version}\n\nRequires **patentkit <kernel>, assessment protocol 1**, Python 3.11+.\n\n"
                "## 什么变了\n\n- [TODO: 本次变更点]\n\n## 升级\n\n- [TODO]\n")
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"  · 生成 notes 骨架：{target.relative_to(ROOT)}（变更段留 TODO，发布前填好）")
    return target


def bump(to: str, kernel_to: str | None, make_notes: bool, dry_run: bool, from_skill: str | None,
         from_kernel: str | None) -> int:
    old_skill = from_skill or _frontmatter_version("research")
    old_kernel = from_kernel or _kernel_version()
    if kernel_to and kernel_to == old_kernel and old_skill != to:
        raise SystemExit(
            f"构建器 KERNEL_VERSION 已是 {kernel_to}——多半是上次升级中断在半途。"
            f"恢复请显式传旧内核版本：--kernel-to {kernel_to} --kernel-from <中断前的内核版本>"
        )
    if not re.fullmatch(r"\d+\.\d+\.\d+", to):
        raise SystemExit(f"--to 不是 x.y.z 形式：{to}")
    if to == old_skill and (kernel_to or None) in (None, old_kernel):
        raise SystemExit(f"目标版本与当前相同（skill {old_skill} / kernel {old_kernel}）；没有可做的升级")

    plans: list[tuple[str, str, re.Pattern[str], str]] = []
    for rel, why in SKILL_PAIRING_FILES:
        plans.append((rel, f"skill {old_skill}→{to}（{why}）", _version_pattern(old_skill), to))
    if kernel_to:
        for rel, why in KERNEL_PAIRING_FILES:
            plans.append((rel, f"kernel {old_kernel}→{kernel_to}（{why}）", _version_pattern(old_kernel), kernel_to))

    print(f"计划：skill {old_skill} → {to}" + (f"，kernel {old_kernel} → {kernel_to}" if kernel_to else ""))
    for rel, why, pattern, new in plans:
        path = ROOT / rel
        if not path.is_file():
            print(f"  ✗ 配对点文件缺失：{rel}")
            return 1
        text = path.read_text(encoding="utf-8")
        hits = len(pattern.findall(text))
        print(f"  · {rel}: {hits} 处（{why}）")
        if not dry_run and hits:
            # 保留原文件行尾：read_text 会把 CRLF 归一成 \n，直接写回会把
            # install-oneclick.cmd 这类 CRLF 文件写坏（批处理解析错乱）。
            was_crlf = b"\r\n" in path.read_bytes()
            path.write_text(pattern.sub(new, text), encoding="utf-8",
                            newline="\r\n" if was_crlf else "\n")

    if make_notes and not dry_run:
        _write_notes("skill", to, old_skill)
        if kernel_to:
            _write_notes("patentkit", kernel_to, old_kernel)
    elif make_notes and dry_run:
        print(f"  · [dry-run] 将生成 notes：release/notes/skill-v{to}.md"
              + (f" / release/notes/patentkit-v{kernel_to}.md" if kernel_to else ""))

    if dry_run:
        print("（dry-run：未写入任何文件）")
        return 0

    print("\n一致性校验：")
    problems = check()
    problems += [f"旧版本号 {old_skill} 残留：{line}" for line in scan_residue(old_skill)]
    if kernel_to:
        problems += [f"旧内核版本号 {old_kernel} 残留：{line}" for line in scan_residue(old_kernel)]

    if problems:
        print(f"\n✗ {len(problems)} 个问题：")
        for p in problems:
            print(f"  · {p}")
        print("\n残留若属历史记录，请把它加进本工具的 RESIDUE_WHITELIST 并说明理由；"
              "不要为了过扫描而改历史文档。")
        return 1
    print("\n✅ 升级完成。别忘了（工具不代写的部分）：")
    print("  · CHANGELOG.md 顶部加新版本条目；")
    print("  · release/notes/skill-v" + to + ".md 的 TODO 填好；")
    print("  · 若镜像状态变了，同步 research|drafting 的 references.en/README.md 陈述。")
    return 0


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="只做一致性校验，不改文件（CI 用）")
    parser.add_argument("--to", help="新的 skill 版本（research 与 drafting 同时升）")
    parser.add_argument("--from", dest="from_skill", help="旧 skill 版本（默认读当前 frontmatter；"
                        "升级中断后状态混合时用它显式指定）")
    parser.add_argument("--kernel-from", dest="from_kernel", help="旧内核版本（默认读 build_skill_release.py）")
    parser.add_argument("--kernel-to", help="新的内核版本（不动内核则省略）")
    parser.add_argument("--notes", action="store_true", help="按上一版生成 release notes 骨架")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不写入")
    args = parser.parse_args()

    try:
        if args.check:
            problems = check()
            for p in problems:
                print(f"  ✗ {p}")
            return 1 if problems else 0
        if not args.to:
            parser.error("需要 --to X.Y.Z（或 --check）")
        return bump(args.to, args.kernel_to, args.notes, args.dry_run, args.from_skill, args.from_kernel)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Failed: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
