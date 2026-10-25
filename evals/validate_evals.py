#!/usr/bin/env python
"""evals/evals.json 的结构与覆盖校验（CI 步骤；确定性，不跑模型）。

多技能版（schema 2）：每个用例带 `skill` 字段，锚定到对应技能的 SKILL.md。
校验四层：
1. 结构：字段齐全、类别合法、id 唯一、skill 已注册；
2. 数量：>=10 组用例，四类都有，且**每个技能至少一个 trigger 用例**；
3. **触发短语真实存在**：case 的 skill_phrases 必须逐字出现在对应 SKILL.md 的
   description 里——description 是客户端匹配触发的唯一依据；
4. 输出契约：format 用例的 result_format_fields 必须以 `**字段**` 形式出现在对应
   SKILL.md 的结果格式表中；两个 SKILL.md 都必须含「⚠️ 未经验证工具校验」硬约束。

行为评测（模型是否照做）按 evals/README.md 人工执行，CI 不假装跑过。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 技能名 → 源码 SKILL.md（v3.0.0 多技能布局）
SKILLS = {
    "patent-research": ROOT / "research" / "SKILL.md",
    "patent-drafting": ROOT / "drafting" / "SKILL.md",
}

VALID_CATEGORIES = {"trigger", "boundary", "refusal", "format"}
MIN_CASES = 10


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
    cases = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))["cases"]
    skill_texts = {name: (path.read_text(encoding="utf-8") if path.is_file() else "")
                   for name, path in SKILLS.items()}
    problems: list[str] = []

    for name, path in SKILLS.items():
        if not path.is_file():
            problems.append(f"SKILL.md 缺失：{path}")
        elif "⚠️ 未经验证工具校验" not in skill_texts[name]:
            problems.append(f"{name} 的 SKILL.md 缺少「⚠️ 未经验证工具校验」硬约束")

    if len(cases) < MIN_CASES:
        problems.append(f"用例不足：{len(cases)} < {MIN_CASES}")

    seen_ids: set[str] = set()
    by_cat: dict[str, int] = {}
    trigger_per_skill: dict[str, int] = {name: 0 for name in SKILLS}

    for case in cases:
        cid = case.get("id", "?")
        if cid in seen_ids:
            problems.append(f"{cid}: id 重复")
        seen_ids.add(cid)

        skill = case.get("skill")
        if skill not in SKILLS:
            problems.append(f"{cid}: 未注册的 skill {skill!r}")
            continue
        text = skill_texts[skill]

        cat = case.get("category")
        if cat not in VALID_CATEGORIES:
            problems.append(f"{cid}: 非法类别 {cat!r}")
            continue
        by_cat[cat] = by_cat.get(cat, 0) + 1
        if cat == "trigger":
            trigger_per_skill[skill] += 1

        if not str(case.get("input") or "").strip():
            problems.append(f"{cid}: input 为空")

        expect = case.get("expect") or {}
        for phrase in expect.get("skill_phrases", []):
            if phrase not in text:
                problems.append(f"{cid}: 触发短语未出现在 {skill} 的 SKILL.md：{phrase!r}")

        if expect.get("must_refuse") and not expect.get("behavior"):
            problems.append(f"{cid}: 拒绝用例必须写明 behavior（拒绝后给什么替代）")

        if cat == "format":
            for field in expect.get("result_format_fields", []):
                if f"**{field}**" not in text:
                    problems.append(f"{cid}: {skill} 的结果格式缺少字段：{field}")

    for required in VALID_CATEGORIES:
        if by_cat.get(required, 0) == 0:
            problems.append(f"缺少 {required} 类用例")
    for name, count in trigger_per_skill.items():
        if count == 0:
            problems.append(f"技能 {name} 缺少 trigger 用例")

    if problems:
        print(f"evals 校验失败（{len(problems)} 项）：")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(f"✅ evals 校验通过：{len(cases)} 组用例覆盖 {len(SKILLS)} 个技能，四类齐备，"
          f"触发短语全部锚定各自 SKILL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
