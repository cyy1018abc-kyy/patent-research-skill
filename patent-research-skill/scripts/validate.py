#!/usr/bin/env python
"""一致性校验 V001-V028 的薄封装 —— 调 `patentkit.api.validate`。

规则实现在 `patentkit/validate.py`，本脚本**不复制任何规则或阈值**：
只决定展示哪几条、怎么排版、退出码怎么归。

用法：

    python patent-research-skill/scripts/validate.py            # 普通：只有 error 算失败
    python patent-research-skill/scripts/validate.py --strict   # 严格：warn 也算失败
    python patent-research-skill/scripts/validate.py --json

退出码：0 通过 / 1 有阻断项（普通看 error，strict 下 warn 也算）/ 2 工作区问题 / 3 依赖缺失。
"""

from __future__ import annotations

import argparse

import _env

#: 人类输出最多列多少条阻断项；再多就引导到 --json，别把终端刷爆
_MAX_SHOW = 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate.py",
        description="一致性校验 V001-V028（薄封装 patentkit.api.validate）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：warn 也算失败（CI 口径）",
    )
    _env.add_common_args(parser)
    return parser


def _blocking(data: dict) -> list[dict]:
    """当前模式下真正导致失败的 finding。

    普通模式只取 error；strict 模式把 warn 也算上。info 永远不阻断 ——
    那是「如实记录的历史事实」（如部分抓取），不是要修的错误。
    """
    levels = {"error", "warn"} if data["strict"] else {"error"}
    return [finding for finding in data["findings"] if finding["level"] in levels]


def render(data: dict) -> str:
    summary = data["summary"]
    strict = data["strict"]
    mode = "strict" if strict else "普通"
    info = summary["total"] - summary["errors"] - summary["warnings"]
    blocking = _blocking(data)

    if data["ok"]:
        lines = [f"✅ 校验通过（{mode}）：0 error / 0 warn" + (f" / {info} info（不阻断）" if info else "")]
        return "\n".join(lines)

    lines = [
        f"❌ 校验失败（{mode}）：{summary['errors']} error / {summary['warnings']} warn"
        f" / {info} info"
    ]
    by_code: dict[str, int] = {}
    for finding in blocking:
        by_code[finding["code"]] = by_code.get(finding["code"], 0) + 1
    lines.append("按规则：" + "  ".join(f"{code}×{count}" for code, count in sorted(by_code.items())))
    lines.append("")
    for finding in blocking[:_MAX_SHOW]:
        location = finding["path"] + (f":{finding['line']}" if finding.get("line") else "")
        lines.append(
            f"  [{finding['level'].upper():5}] {finding['code']} {location} — {finding['message']}"
        )
    hidden = len(blocking) - _MAX_SHOW
    if hidden > 0:
        lines.append(f"  … 其余 {hidden} 条见 --json")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _env.require_patentkit()
    root = _env.resolve_workspace(args.root, as_json=args.json)

    # 延迟 import：没装包时由 require_patentkit() 给安装指引，而不是抛 traceback
    from patentkit import api
    from patentkit.registry import TerminologyError

    try:
        data = api.validate(root, strict=args.strict)
    except (api.WorkspaceError, TerminologyError) as exc:
        return _env.failure(
            f"读取工作区数据失败：{exc}",
            _env.EXIT_WORKSPACE,
            hints=("先跑 python -m patentkit doctor 定位是术语表还是数据文件的问题",),
            as_json=args.json,
        )

    if args.json:
        _env.emit_json({"command": "validate", **data})
        return _env.EXIT_OK if data["ok"] else _env.EXIT_FAIL

    print(render(data))
    return _env.EXIT_OK if data["ok"] else _env.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
