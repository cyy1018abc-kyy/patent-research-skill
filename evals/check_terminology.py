#!/usr/bin/env python
"""中英术语一致性校验（CI 步骤；多技能版）。

v3.0.0 布局：research/references（中文主版本 01–08+glossary）、
drafting/references（00,09–13+glossary）、research/references.en（英文镜像 01–07）。

校验三层：
1. **配对完整**：01–07 在 research 中文与英文镜像两侧都存在（08+ 与 drafting 目前
   中文先行，README 已声明）；
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
EN = ROOT / "research" / "references.en"

#: 中文主文件名（research 侧 01–07 有英文镜像）
PAIRED = [f"0{i}-" for i in range(1, 8)]

#: 核心锚定术语：中文须在中文文档（两技能）出现，英文 token 须在英文镜像出现。
#: 只收录两版真实共用的核心术语；2.5.0+ 新增概念（账本/地图/改稿闭环/附图标记等）
#: 目前中文先行，翻译完成后加入本表。
GLOBAL_ANCHORS = [
    ("验收门", "acceptance gate"),
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

    zh_files = sorted(ZH_RESEARCH.glob("*.md")) + sorted(ZH_DRAFTING.glob("*.md"))
    zh_all = "\n".join(p.read_text(encoding="utf-8") for p in zh_files)
    en_all = "\n".join(p.read_text(encoding="utf-8") for p in sorted(EN.glob("*.md")))

    # 1. 配对完整（按前缀 01-…07-）
    for prefix in PAIRED:
        if not any(p.name.startswith(prefix) for p in ZH_RESEARCH.glob("*.md")):
            problems.append(f"中文主版本缺失：research/references/{prefix}*.md")
        if not any(p.name.startswith(prefix) for p in EN.glob("*.md")):
            problems.append(f"英文镜像缺失：research/references.en/{prefix}*.md")

    # 2. 术语锚定
    for zh_term, en_term in GLOBAL_ANCHORS:
        if zh_term not in zh_all:
            problems.append(f"锚定术语未在中文文档出现：{zh_term}")
        if en_term.split()[0] not in en_all:
            problems.append(f"锚定术语未在英文镜像出现：{en_term}")

    # 3. glossary 双份同步（research 权威，drafting 复制）
    g_research = ZH_RESEARCH / "glossary.md"
    g_drafting = ZH_DRAFTING / "glossary.md"
    if not g_research.is_file() or not g_drafting.is_file():
        problems.append("glossary.md 必须同时存在于 research 与 drafting 的 references/")
    elif g_research.read_bytes() != g_drafting.read_bytes():
        problems.append("research 与 drafting 的 glossary.md 不一致——以 research 为准复制后重试"
                        "（单技能包自包含；CI 防两份漂移）")

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
    print("✅ 术语一致性通过：01–07 中英配对完整，锚定术语在用，glossary 双份逐字节一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
