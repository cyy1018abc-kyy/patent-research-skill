#!/usr/bin/env python
"""中英术语一致性校验（CI 步骤）。

references/（中文主版本）与 references.en/（英文镜像）必须逐文件配对；
本脚本校验两层：

1. **配对完整**：01–07 每篇在两侧都存在（08+ 目前中文先行，README 已声明）；
2. **术语锚定**：glossary.md 表里的每个「中文术语」，其对应英文术语必须出现在
   英文镜像的对应文件里出现至少一次——不是逐句翻译检查（那会成为
   「测试即文档」反模式），只锚定**术语不漂移**这一件最有价值的事。

用法：python evals/check_terminology.py   （退出 0 一致 / 1 有漂移）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH = ROOT / "patent-research-skill" / "references"
EN = ROOT / "patent-research-skill" / "references.en"

#: 中文主文件名 → 英文镜像文件名（01–07 当前双侧维护）
PAIRED = {
    "01-search-framework.md": "01-search-framework.md",
    "02-query-templates.md": "02-query-templates.md",
    "03-three-tier-determination.md": "03-three-tier-determination.md",
    "04-evidence-level-system.md": "04-evidence-level-system.md",
    "05-acceptance-gates.md": "05-acceptance-gates.md",
    "06-drafting-and-polishing-rules.md": "06-drafting-and-polishing-rules.md",
    "07-assessment-protocol.md": "07-assessment-protocol.md",
}

#: 全局锚定术语：中文名必须在中文版出现，英文 token 必须在英文版出现。
#: 只收录两版当前真实共用的核心术语；2.5.0 新增概念（账本/地图/改稿闭环/附图标记等）
#: 目前中文先行（见 references.en/README.md），翻译完成后加入本表。
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
    """cp1252 控制台打印 ✅/⚠️ 会 UnicodeEncodeError（CI Windows runner 实测）；与内核
    paths.configure_stdio 同理，入口处钉 UTF-8。"""
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

    zh_all = "\n".join(p.read_text(encoding="utf-8") for p in sorted(ZH.glob("*.md")))
    en_all = "\n".join(p.read_text(encoding="utf-8") for p in sorted(EN.glob("*.md")))

    for zh_name, en_name in PAIRED.items():
        if not (ZH / zh_name).is_file():
            problems.append(f"中文主版本缺失：references/{zh_name}")
        if not (EN / en_name).is_file():
            problems.append(f"英文镜像缺失：references.en/{en_name}")

    for zh_term, en_term in GLOBAL_ANCHORS:
        if zh_term not in zh_all:
            problems.append(f"术语表锚定的中文术语未在中文版出现：{zh_term}")
        if en_term.split()[0] not in en_all:
            problems.append(f"术语表锚定的英文术语未在英文版出现：{en_term}")

    # glossary.md 自身健全性：锚定的中文术语必须在中文版真实使用（防「表里有、文里无」）
    glossary = (ZH / "glossary.md").read_text(encoding="utf-8")
    for line in glossary.splitlines():
        m = re.match(r"^\|\s*([^|]+?)\s*\|", line)
        if not m:
            continue
        zh_term = m.group(1).strip()
        if not zh_term or zh_term in {"中文", "流程与角色", "工具与交付"}:
            continue
        if zh_term not in zh_all:
            problems.append(f"glossary 行的中文术语未在中文版使用：{zh_term}")

    if problems:
        print(f"术语一致性校验失败（{len(problems)} 项）：")
        for p in problems[:30]:
            print(f"  · {p}")
        return 1
    print("✅ 术语一致性通过：中英配对完整，glossary 锚定术语两侧均在用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
