#!/usr/bin/env python
"""生成 `04_对比分析/runs/` 的对比 run 骨架 —— 薄封装 `patentkit.api.report`。

骨架内容（D 列、N-主轴覆盖矩阵、三层判定占位、capture_mode 元数据段）由
`patentkit/report.py` 生成；本脚本只负责定位工作区、把相对路径按工作区根解析、
以及把失败收敛成退出码。

用法：

    # 写到工作区内的相对路径（相对 --out 按工作区根解析，不是按当前目录）
    python patent-research-skill/scripts/report.py --target TGT-0002 \
        --out 04_对比分析/runs/2026-01-01_TGT-0002.md

    # 不写盘，只把骨架打到 stdout 预览
    python patent-research-skill/scripts/report.py --target TGT-0002

退出码：0 生成成功 / 1 生成或写盘失败 / 2 工作区问题或用法错误 / 3 依赖缺失。

⚠️ 为什么 `--out` 不做默认值：默认写盘会在用户没想清楚时污染工作区数据。
本脚本**宁可让你多敲一个参数**，也不替你猜路径。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="report.py",
        description="生成对比 run 骨架（薄封装 patentkit.api.report）",
    )
    parser.add_argument(
        "--target",
        metavar="TGT-xxxx",
        required=True,
        help="目标 ID；必须与 00_方法论/术语表.yml 的 targets 一致，否则骨架里没有轴",
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help="输出路径；相对路径按工作区根解析。省略则只打印骨架（不写盘）",
    )
    _env.add_common_args(parser)
    return parser


def _resolve_out(root: Path, raw: str | None) -> Path | None:
    """--out 的相对路径按**工作区根**解析，而不是当前目录。

    技能脚本常被客户端从任意 cwd 调起；按 cwd 解析会让文件落到意想不到的地方。
    """
    if not raw:
        return None
    out = Path(raw).expanduser()
    if not out.is_absolute():
        out = root / out
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _env.require_patentkit()
    root = _env.resolve_workspace(args.root, as_json=args.json)
    out = _resolve_out(root, args.out)

    # 延迟 import：没装包时由 require_patentkit() 给安装指引，而不是抛 traceback
    from patentkit import api
    from patentkit.registry import TerminologyError

    extra = ["--out", str(out)] if out is not None else []
    try:
        data = api.report(root, target=args.target, argv_extra=extra)
    except (api.WorkspaceError, TerminologyError) as exc:
        return _env.failure(
            f"读取工作区数据失败：{exc}",
            _env.EXIT_WORKSPACE,
            hints=("先跑 python -m patentkit doctor 定位是术语表还是数据文件的问题",),
            as_json=args.json,
        )
    except OSError as exc:
        return _env.failure(
            f"写入对比 run 骨架失败：{exc}",
            _env.EXIT_FAIL,
            hints=("--out 必须是可写的文件路径（不能是已存在的目录）",),
            as_json=args.json,
        )

    if not data.get("ok"):
        detail = data.get("stderr") or data.get("stdout") or "（底层没有输出）"
        return _env.failure(
            f"生成对比 run 骨架失败：{detail}",
            _env.EXIT_FAIL,
            as_json=args.json,
        )

    if args.json:
        _env.emit_json(
            {
                **data,
                "command": "report",
                "workspace": str(root),
                "target": args.target,
                "out": str(out) if out is not None else None,
            }
        )
        return _env.EXIT_OK

    if out is not None:
        print(f"✅ 已生成对比 run 骨架：{out}")
        print(f"   目标：{args.target}")
        print(
            "   下一步：填 §3 覆盖矩阵与 §4 三层判定；"
            "§6 的 capture_mode 必须如实标注"
        )
        print("           （live → 可作 verified；retrospective / memory → 只能 asserted）")
    else:
        # 预览模式：底层把骨架打印到被捕获的 stdout，这里原样转出
        print(data.get("stdout") or "")
    return _env.EXIT_OK


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
