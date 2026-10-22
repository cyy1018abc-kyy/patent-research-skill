#!/usr/bin/env python
"""五门 × 三列（verified/attested/asserted）摘要 —— 薄封装 `patentkit.api.gates`。

口径（工具侧固定，不在这里重算）：**PASS 只认最严的 verified 列**；
attested/asserted 是历史成绩，不构成通过依据。本脚本只做呈现：

用法：

    python patent-research-skill/scripts/gates.py
    python patent-research-skill/scripts/gates.py --target TGT-0002 --json

`--target` 默认取术语表 `active_target`；多目标工作区建议显式指定，
否则看到的是「当前激活目标」的门，不是你以为的那个。

退出码：0 五门全 PASS / 1 有门未过（含 N/A）/ 2 工作区问题 / 3 依赖缺失。

⚠️ 与原生 `python -m patentkit gates` 的区别：原生命令门未过时 exit **2**，
本脚本按技能包统一退出码约定归到 **1**（2 专用于工作区问题）。
"""

from __future__ import annotations

import argparse
import unicodedata

import _env

_GATE_MARK = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "N/A": "⬜ N/A"}

_HEADERS = ("门", "判定", "阈值", "verified（最严）", "≥attested", "≥asserted")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gates.py",
        description="G-S-01..05 三列验收门摘要（薄封装 patentkit.api.gates）",
    )
    parser.add_argument(
        "--target",
        metavar="TGT-xxxx",
        default=None,
        help="目标 ID（默认取术语表 active_target；多目标工作区建议显式指定）",
    )
    _env.add_common_args(parser)
    return parser


def _display_width(text: str) -> int:
    """终端显示宽度：CJK 全角字符算 2 列，保证表格在中文终端里也对齐。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _table(rows: list[tuple[str, ...]]) -> list[str]:
    """按显示宽度对齐的简单表格（不依赖第三方表格库）。"""
    widths = [
        max(_display_width(row[column]) for row in (rows + [_HEADERS]))
        for column in range(len(_HEADERS))
    ]
    lines = [
        "  ".join(_pad(cell, widths[index]) for index, cell in enumerate(_HEADERS)).rstrip(),
        "  ".join("-" * width for width in widths),
    ]
    for row in rows:
        lines.append("  ".join(_pad(cell, widths[index]) for index, cell in enumerate(row)).rstrip())
    return lines


def render(data: dict) -> str:
    gates = data["gates"]
    rows = [
        (
            gate["gate_id"],
            _GATE_MARK.get(gate["status"], gate["status"]),
            gate["threshold"],
            gate["values"].get("verified", "-"),
            gate["values"].get("attested", "-"),
            gate["values"].get("asserted", "-"),
        )
        for gate in gates
    ]

    lines = [f"验收门 · 目标 {data.get('target', '?')}（PASS 只认 verified 列）", ""]
    lines += _table(rows)
    lines.append("")

    per_axis = data.get("per_axis") or {}
    if per_axis:
        lines.append(
            "G-S-02 分轴（verified 篇数）："
            + "  ".join(f"{axis}={values['verified']}" for axis, values in sorted(per_axis.items()))
        )

    failed = [gate for gate in gates if gate["status"] != "PASS"]
    if failed:
        lines.append("")
        lines.append("未过的门：")
        for gate in failed:
            reason = gate.get("note") or "查看 values 列自查"
            lines.append(f"  · {gate['gate_id']}（{gate['status']}）{reason}")
        lines.append("")
        lines.append("下一步：门禁 FAIL 不是「再想想」，是检索不够 —— 优先补检索，不是放宽口径")
        lines.append(f"汇总：❌ {len(failed)}/{len(gates)} 门未过")
    else:
        lines.append("")
        lines.append(f"汇总：✅ 五门全 PASS（{len(gates)}/{len(gates)}）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _env.require_patentkit()
    root = _env.resolve_workspace(args.root, as_json=args.json)

    # 延迟 import：没装包时由 require_patentkit() 给安装指引，而不是抛 traceback
    from patentkit import api
    from patentkit.registry import TerminologyError

    try:
        data = api.gates(root, target=args.target)
    except (api.WorkspaceError, TerminologyError, ValueError) as exc:
        return _env.failure(
            f"读取工作区数据失败：{exc}",
            _env.EXIT_WORKSPACE,
            hints=("先跑 python -m patentkit doctor 定位术语表/active_target 的问题",),
            as_json=args.json,
        )

    ok = bool(data.get("all_pass"))
    if args.json:
        _env.emit_json({"command": "gates", **data, "ok": ok})
    else:
        print(render(data))
    return _env.EXIT_OK if ok else _env.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
