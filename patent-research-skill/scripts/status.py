#!/usr/bin/env python
"""一眼看全工作区状态 —— 薄封装 `patentkit.api.status`。

看什么：当前目标、五门 PASS/FAIL 一行汇总、校验 error/warn、候选与日志分布、
下一步 hints。**门禁怎么算、校验查什么，全部由 patentkit 决定**，本脚本只负责
选择要展示的字段与排版 —— 规则实现只有一处，不在这里复制。

用法：

    python patent-research-skill/scripts/status.py
    python patent-research-skill/scripts/status.py --root <工作区路径>
    python patent-research-skill/scripts/status.py --json

退出码：0 数据可读（**门是否 PASS 不影响本命令退出码**）。
要拿「能不能过门」当退出码，用 `gates.py` 或 `check.py`。
依赖缺失 3 / 工作区问题 2；数据不可解析（术语表坏了等）也算工作区问题 2。
"""

from __future__ import annotations

import argparse

import _env

#: gate.status → 展示符号。状态值是 patentkit 算出来的，这里只做视觉映射。
_GATE_MARK = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "N/A": "⬜ N/A"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="status.py",
        description="一眼看全：目标、五门汇总、校验、候选分布、下一步 hints",
    )
    _env.add_common_args(parser)
    return parser


def _fmt_counts(counts: dict) -> str:
    """把 {key: count} 排成一行 `key count · key count`；空字典显示「无」。"""
    if not counts:
        return "无"
    return " · ".join(f"{key} {value}" for key, value in counts.items())


def render(data: dict) -> str:
    """人类可读渲染。短、带状态符号，和 `patentkit status` 的风格保持一致。"""
    gates = data["gates"]["gates"]
    gate_line = " · ".join(
        f"{gate['gate_id']} {_GATE_MARK.get(gate['status'], gate['status'])}"
        for gate in gates
    )
    all_pass = all(gate["status"] == "PASS" for gate in gates)

    validation = data["validation"]
    info = validation["total"] - validation["errors"] - validation["warnings"]
    strict_ok = validation["errors"] == 0 and validation["warnings"] == 0

    candidates = data["candidates"]
    logs = data["logs"]
    title = f" · {data['target_title']}" if data.get("target_title") else ""

    lines = [
        f"✅ 工作区：{data['workspace']}",
        f"目标：{data['active_target']}{title}",
        f"验收门：{gate_line}  →  "
        + ("✅ 五门全 PASS（只认 verified 列）" if all_pass else "❌ 有门未过，详见 gates.py"),
        f"校验：error {validation['errors']} / warn {validation['warnings']} / info {info}"
        + ("  →  ✅ 严格模式也能过" if strict_ok else "  →  ❌ 严格模式会失败"),
        f"候选：{candidates['total']} 条 · 证据等级 {_fmt_counts(candidates['by_evidence_level'])}"
        f" · relevance≥4 共 {candidates['with_relevance_ge4']} 条",
        f"      角色 {_fmt_counts(candidates['by_role'])}"
        f" · relevance {_fmt_counts(candidates['by_relevance'])}",
        f"检索日志：{logs['total']} 份（live {logs['live']} / retrospective {logs['retrospective']}）",
        "",
    ]

    hints = data.get("hints") or []
    if hints:
        lines.append("下一步：")
        lines.extend(f"  · {hint}" for hint in hints)
    else:
        lines.append("下一步：无阻塞项（数据一致、五门齐 PASS）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _env.require_patentkit()
    root = _env.resolve_workspace(args.root, as_json=args.json)

    # 延迟 import：没装包时由 require_patentkit() 给安装指引，而不是抛 traceback
    from patentkit import api
    from patentkit.registry import TerminologyError

    try:
        data = api.status(root)
    except (api.WorkspaceError, TerminologyError, ValueError) as exc:
        return _env.failure(
            f"读取工作区数据失败：{exc}",
            _env.EXIT_WORKSPACE,
            hints=("先跑 python -m patentkit doctor 定位是术语表还是数据文件的问题",),
            as_json=args.json,
        )

    if args.json:
        _env.emit_json({"command": "status", **data, "ok": True})
        return _env.EXIT_OK

    print(render(data))
    return _env.EXIT_OK


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
