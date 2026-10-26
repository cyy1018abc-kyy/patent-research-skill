#!/usr/bin/env python
"""中英术语一致性校验（CI 步骤；多技能版）。

当前布局：research/references（中文主版本 01–08+glossary）、
drafting/references（00,09–13+glossary）、research/references.en（英文镜像 01–08）、
drafting/references.en（英文镜像 00,09–13）。

校验三层：
1. **配对完整**：research 01–08 与 drafting 00/09–13 在中文与英文镜像两侧都存在；
2. **术语锚定**：核心术语中文在中文文档（两技能合计）出现、英文在英文镜像出现；
3. **glossary 同步**：research 与 drafting 各自携带的 glossary.md 必须**逐字节一致**
   （单技能包自包含的代价是复制一份，CI 防漂移）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH_RESEARCH = ROOT / "research" / "references"
ZH_DRAFTING = ROOT / "drafting" / "references"
ZH_DISCOVERY = ROOT / "discovery" / "references"
EN_RESEARCH = ROOT / "research" / "references.en"
EN_DRAFTING = ROOT / "drafting" / "references.en"
EN_DISCOVERY = ROOT / "discovery" / "references.en"

#: 中文主文件名前缀（两侧镜像齐备的部分）
PAIRED_RESEARCH = [f"0{i}-" for i in range(1, 9)]   # 01–08
PAIRED_DRAFTING = ["00-", "09-", "10-", "11-", "12-", "13-"]
PAIRED_DISCOVERY = ["00-", "01-", "02-", "03-"]

#: 核心锚定术语：中文须在中文文档（两技能）出现，英文 token 须在英文镜像出现。
#: 只收录两版真实共用的核心术语；3.1.0 起两技能 references 已全部双语，新增概念
#: 落文档时同时补进本表。
GLOBAL_ANCHORS = [
    ("验收门", "acceptance gate"),
    ("证据账本", "evidence ledger"),
    ("改稿闭环", "revision loop"),
    ("政策雷达", "Policy radar"),
    ("审查意见", "office action"),
    ("答复底稿", "response draft"),
    ("交底书", "disclosure"),
    ("实施例示例", "illustrative example"),
    ("零披露原子", "zero-disclosure atom"),
    ("证据等级", "evidence level"),
    ("人工确认", "human confirmation"),
    ("指纹", "fingerprint"),
    ("三层判定", "three-tier"),
    ("零披露原子", "zero-disclosure atom"),
    ("数值声明溯源", "provenance"),
    ("缓冲", "buffer"),
    ("评估协议", "assessment protocol"),
    ("现有技术", "prior art"),
    ("实施例", "embodiment"),
    ("有益效果", "beneficial effect"),
    ("工作区", "workspace"),
    ("期限台账", "deadline"),
    ("附图标记", "figure-mark"),
    ("数值声明溯源", "A/B/C"),
    ("来源材料", "source material"),
    ("技术事实", "technical fact"),
    ("必要技术特征", "essential feature"),
    ("内容指纹", "content fingerprint"),
    ("专利点挖掘", "patent point mining"),
    ("交接草案", "handoff draft"),
]


def _pin_utf8_stdio() -> None:
    import sys
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main() -> int:
    _pin_utf8_stdio()
    problems: list[str] = []

    zh_files = (
        sorted(ZH_RESEARCH.glob("*.md"))
        + sorted(ZH_DRAFTING.glob("*.md"))
        + sorted(ZH_DISCOVERY.glob("*.md"))
    )
    zh_all = "\n".join(p.read_text(encoding="utf-8") for p in zh_files)
    en_all = "\n".join(p.read_text(encoding="utf-8")
                        for p in sorted(EN_RESEARCH.glob("*.md"))
                        + sorted(EN_DRAFTING.glob("*.md"))
                        + sorted(EN_DISCOVERY.glob("*.md")))

    # 1. 配对完整（research 01–07；drafting 00/09–13）
    for prefix in PAIRED_RESEARCH:
        if not any(p.name.startswith(prefix) for p in ZH_RESEARCH.glob("*.md")):
            problems.append(f"中文主版本缺失：research/references/{prefix}*.md")
        if not any(p.name.startswith(prefix) for p in EN_RESEARCH.glob("*.md")):
            problems.append(f"英文镜像缺失：research/references.en/{prefix}*.md")
    for prefix in PAIRED_DRAFTING:
        if not any(p.name.startswith(prefix) for p in ZH_DRAFTING.glob("*.md")):
            problems.append(f"中文主版本缺失：drafting/references/{prefix}*.md")
        if not any(p.name.startswith(prefix) for p in EN_DRAFTING.glob("*.md")):
            problems.append(f"英文镜像缺失：drafting/references.en/{prefix}*.md")
    for prefix in PAIRED_DISCOVERY:
        if not any(p.name.startswith(prefix) for p in ZH_DISCOVERY.glob("*.md")):
            problems.append(f"中文主版本缺失：discovery/references/{prefix}*.md")
        if not any(p.name.startswith(prefix) for p in EN_DISCOVERY.glob("*.md")):
            problems.append(f"英文镜像缺失：discovery/references.en/{prefix}*.md")

    # 2. 术语锚定
    for zh_term, en_term in GLOBAL_ANCHORS:
        if zh_term not in zh_all:
            problems.append(f"锚定术语未在中文文档出现：{zh_term}")
        if en_term.split()[0] not in en_all:
            problems.append(f"锚定术语未在英文镜像出现：{en_term}")

    # 3. glossary 双份同步（research 权威，drafting 复制）
    g_research = ZH_RESEARCH / "glossary.md"
    g_drafting = ZH_DRAFTING / "glossary.md"
    g_discovery = ZH_DISCOVERY / "glossary.md"
    if not g_research.is_file() or not g_drafting.is_file() or not g_discovery.is_file():
        problems.append("glossary.md 必须同时存在于 research / drafting / discovery 的 references/")
    elif not (g_research.read_bytes() == g_drafting.read_bytes() == g_discovery.read_bytes()):
        problems.append("research / drafting / discovery 的 glossary.md 不一致——以 research 为准复制后重试"
                        "（单技能包自包含；CI 防多份漂移）")

    # 4. glossary 自身健全性：行内中文术语必须在中文文档真实使用
    glossary = g_research.read_text(encoding="utf-8") if g_research.is_file() else ""
    for line in glossary.splitlines():
        m = re.match(r"^\|\s*([^|]+?)\s*\|", line)
        if not m:
            continue
        zh_term = m.group(1).strip()
        if not zh_term or zh_term in {"中文", "流程与角色", "工具与交付"}:
            continue
        if zh_term not in zh_all:
            problems.append(f"glossary 行的中文术语未在中文文档使用：{zh_term}")

    if problems:
        print(f"术语一致性校验失败（{len(problems)} 项）：")
        for p in problems[:30]:
            print(f"  · {p}")
        return 1
    print("✅ 术语一致性通过：research 01–08 / drafting 00,09–13 / discovery 00–03 中英配对完整，"
          "锚定术语在用，glossary 三份逐字节一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
