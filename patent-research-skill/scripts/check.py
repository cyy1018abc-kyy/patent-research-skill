#!/usr/bin/env python
"""CI 入口：`validate --strict` + `gates` 一并跑 —— 等价于 `python -m patentkit check`。

两项都过才算过：

1. `python -m patentkit validate --strict`：数据一致性（warn 也算失败）
2. `python -m patentkit gates`：五门 G-S-01..05 全 PASS（只认 verified 列）

用法：

    python patent-research-skill/scripts/check.py
    python patent-research-skill/scripts/check.py --json

退出码：0 全过 / 1 任一项失败 / 2 工作区问题 / 3 依赖缺失。

⚠️ 与原生 `python -m patentkit check` 的区别：原生在门禁未过时返回 **2**，
本脚本按技能包统一约定归到 **1**（2 专用于工作区问题）。调用方若要区分
「数据不一致」与「门没过」，看 `--json` 里的 `validate.ok` / `gates.all_pass`。
"""

from __future__ import annotations

import argparse

import _env

#: 人类输出最多列多少条校验阻断项；再多就引导到 --json
_MAX_SHOW = 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check.py",
        description="提交前必跑：validate --strict + gates（任一失败 exit 1）",
    )
    _env.add_common_args(parser)
    return parser


def _render_validate(validate_data: dict) -> list[str]:
    summary = validate_data["summary"]
    if validate_data["ok"]:
        return ["✅ 校验（strict）：0 error / 0 warn"]

    blocking = [
        finding
        for finding in validate_data["findings"]
        if finding["level"] in {"error", "warn"}
    ]
    lines = [f"❌ 校验（strict）：{summary['errors']} error / {summary['warnings']} warn"]
    for finding in blocking[:_MAX_SHOW]:
        lines.append(
            f"   [{finding['level'].upper():5}] {finding['code']} {finding['path']}"
            f" — {finding['message']}"
        )
    hidden = len(blocking) - _MAX_SHOW
    if hidden > 0:
        lines.append(f"   … 其余 {hidden} 条见 --json")
    return lines


def _render_gates(gates_data: dict) -> list[str]:
    gates = gates_data["gates"]
    if gates_data.get("all_pass"):
        return ["✅ 验收门：五门全 PASS（只认 verified 列）"]
    detail = " · ".join(f"{gate['gate_id']} {gate['status']}" for gate in gates)
    return [f"❌ 验收门：{detail}"]


def render(validate_data: dict, gates_data: dict) -> str:
    validate_ok = bool(validate_data["ok"])
    gates_ok = bool(gates_data.get("all_pass"))
    lines = [*_render_validate(validate_data), *_render_gates(gates_data), ""]

    if validate_ok and gates_ok:
        lines.append("✅ check 通过：数据一致且五门齐 PASS，可以进入下一阶段")
        return "\n".join(lines)

    lines.append("下一步：")
    if not validate_ok:
        lines.append("  · 先修校验阻断项 —— 数据不一致时门禁数字不可信")
    if not gates_ok:
        lines.append("  · 门禁未过优先补检索，不是放宽口径")
    lines.append("❌ check 未通过")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _env.require_patentkit()
    root = _env.resolve_workspace(args.root, as_json=args.json)

    # 延迟 import：没装包时由 require_patentkit() 给安装指引，而不是抛 traceback
    from patentkit import api
    from patentkit.registry import TerminologyError

    try:
        validate_data = api.validate(root, strict=True)
        gates_data = api.gates(root)
    except (api.WorkspaceError, TerminologyError, ValueError) as exc:
        return _env.failure(
            f"读取工作区数据失败：{exc}",
            _env.EXIT_WORKSPACE,
            hints=("先跑 python -m patentkit doctor 定位是术语表还是数据文件的问题",),
            as_json=args.json,
        )

    ok = bool(validate_data["ok"]) and bool(gates_data.get("all_pass"))
    if args.json:
        _env.emit_json(
            {
                "command": "check",
                "workspace": str(root),
                "ok": ok,
                "validate": validate_data,
                "gates": gates_data,
            }
        )
    else:
        print(render(validate_data, gates_data))
    return _env.EXIT_OK if ok else _env.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
