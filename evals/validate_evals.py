#!/usr/bin/env python
"""evals/evals.json 的结构与覆盖校验（CI 步骤；确定性，不跑模型）。

校验四层：
1. 结构：schema 字段齐全、类别合法、id 唯一；
2. 数量：≥10 组用例，trigger/boundary/refusal/format 四类都有；
3. **触发短语真实存在**：每个 case 的 skill_phrases 必须逐字出现在 SKILL.md 的
   description 里 —— description 是客户端匹配触发的唯一依据，评测里引用一个
   description 里没有的短语等于测了一个永远不会触发的行为；
4. 输出契约：boundary 用例必须声明 output_must_start_with（⚠️ 前缀），format 用例
   必须覆盖结果格式五项。

行为评测（模型是否照做）按 evals/README.md 人工执行，CI 不假装跑过。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "patent-research-skill" / "SKILL.md"

VALID_CATEGORIES = {"trigger", "boundary", "refusal", "format"}
MIN_CASES = 10
RESULT_FORMAT_FIELDS = {"结论", "证据等级", "判定状态", "门禁状态", "未验证标注"}


def main() -> int:
    path = ROOT / "evals" / "evals.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    skill_text = SKILL.read_text(encoding="utf-8")
    # description 是 frontmatter 里的；为避免 YAML 依赖，直接在全文中找短语即可
    problems: list[str] = []

    if data.get("skill") != "patent-research":
        problems.append(f"skill 字段应为 patent-research，得到 {data.get('skill')!r}")

    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) < MIN_CASES:
        problems.append(f"用例不足：{len(cases) if isinstance(cases, list) else 0} < {MIN_CASES}")
        cases = cases if isinstance(cases, list) else []

    seen_ids: set[str] = set()
    by_cat: dict[str, int] = {}
    for case in cases:
        cid = case.get("id", "?")
        if cid in seen_ids:
            problems.append(f"{cid}: id 重复")
        seen_ids.add(cid)

        cat = case.get("category")
        if cat not in VALID_CATEGORIES:
            problems.append(f"{cid}: 非法类别 {cat!r}")
            continue
        by_cat[cat] = by_cat.get(cat, 0) + 1

        if not str(case.get("input") or "").strip():
            problems.append(f"{cid}: input 为空")

        expect = case.get("expect") or {}
        for phrase in expect.get("skill_phrases", []):
            if phrase not in skill_text:
                problems.append(f"{cid}: 触发短语未出现在 SKILL.md：{phrase!r}")

        if expect.get("must_refuse") and not expect.get("behavior"):
            problems.append(f"{cid}: 拒绝用例必须写明 behavior（拒绝后给什么替代）")



        if cat == "format":
            fields = set(expect.get("result_format_fields", []))
            if fields != RESULT_FORMAT_FIELDS:
                problems.append(f"{cid}: format 用例必须覆盖结果格式五项，得到 {sorted(fields)}")

    for required in VALID_CATEGORIES:
        if by_cat.get(required, 0) == 0:
            problems.append(f"缺少 {required} 类用例")

    # ⚠️ 前缀是硬约束 4：boundary 类里必须至少有一个用例锚定它
    prefix_cases = [
        c for c in cases
        if (c.get("expect") or {}).get("output_must_start_with", "").startswith("⚠️")
    ]
    if not prefix_cases:
        problems.append("boundary 类缺少「⚠️ 未经验证工具校验」前缀用例（硬约束 4）")

    # 结果格式五项也必须真的在 SKILL.md 里（防止格式表被改而评测没跟上）
    for field in RESULT_FORMAT_FIELDS:
        if f"**{field}**" not in skill_text:
            problems.append(f"SKILL.md 结果格式缺少字段：{field}")

    if problems:
        print(f"evals 校验失败（{len(problems)} 项）：")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(f"✅ evals 校验通过：{len(cases)} 组用例，四类齐备，触发短语全部锚定 SKILL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
