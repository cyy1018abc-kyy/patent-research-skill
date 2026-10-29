#!/usr/bin/env python
"""把工作区状态导出为可编辑的 .docx 查新报告 —— `patentkit export-docx` 的薄封装。

规则在内核（patentkit/export.py）：数字全部来自工作区（门禁/候选/日志），零手工转写；
三层级判定与结论段落在文中是显式的「人工填写」占位，文档不发明结论。
python-docx 是可选依赖（`pip install "patentkit[docx]"`），缺失时 exit 3 并给安装指引。

用法：

    python patent-research-skill/scripts/export_docx.py TGT-0002
    python patent-research-skill/scripts/export_docx.py TGT-0002 --out 报告.docx

退出码：0 成功 / 1 业务失败 / 2 工作区问题 / 3 缺依赖（内核或 python-docx）。
"""

from __future__ import annotations

import argparse
import sys

import _env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="export_docx.py",
        description="导出 .docx 查新报告（数据来自工作区；三层级判定需人工填写）",
    )
    parser.add_argument("target_id", nargs="?", default=None, help="目标 ID，如 TGT-0002（默认 active）")
    parser.add_argument("--out", default=None, help="输出 .docx 路径（默认 04_comparative_analysis/ 下按日期命名）")
    _env.add_common_args(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    _env.configure_stdio()
    args = build_parser().parse_args(argv)
    _env.require_patentkit(as_json=args.json)
    root = _env.resolve_workspace(args.root, as_json=args.json)

    # 延迟导入：缺包时 require_patentkit 给出指引而不是 traceback
    from patentkit import export as export_mod

    rest = [args.target_id] if args.target_id else []
    rest += ["--root", str(root)]
    if args.out:
        rest += ["--out", args.out]

    # export-docx 的中文输出直接透传；--json 模式下打印结构化结果
    if args.json:
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = export_mod.main(rest)
        _env.emit_json({"command": "export_docx", "ok": rc == 0, "exit": rc, "log": buffer.getvalue().strip().splitlines()})
        return rc

    return export_mod.main(rest)


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
