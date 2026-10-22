"""技能脚本的共用环境层 —— 编码、依赖、工作区、JSON 四件事。

`scripts/` 下的命令会被 **LLM 客户端以子进程方式调用**（Codex CLI / Claude Code /
Cline …），调用方只关心「退出码 + stdout 能否解析」，不关心终端排版。这类环境有
四类问题反复出现，集中到这里处理，各命令脚本只保留业务呈现：

| 问题 | 不处理的后果 | 本文件的处理 |
|---|---|---|
| Windows 控制台按 GBK 编码 stdout | 打印 ✅/⚠️ 直接 `UnicodeEncodeError` 崩掉；子进程捕获到乱码 | `configure_stdio()` 锁定 UTF-8 |
| 没装 patentkit | 抛一屏 traceback，客户端不知道该装什么 | `require_patentkit()` 给安装命令，exit 3 |
| 不在工作区里 | 静默回退到 cwd，报「术语表不存在」误导人 | `resolve_workspace()` 固定定位顺序，exit 2 + 三条修法 |
| `--json` 里混进人类提示 | 调用方 `json.loads` 直接失败 | `emit_json()` 是 --json 模式唯一的 stdout 出口 |

退出码约定（与 `patentkit` CLI 的差异见 `scripts/README.md`）：

| 码 | 含义 |
|---|---|
| 0 | 成功，命令自身的判定通过 |
| 1 | 业务失败：校验有 error / 门未全 PASS / 报告写不出 |
| 2 | 工作区问题：定位不到、`--root` 指错、工作区数据不可解析；argparse 用法错误也是 2 |
| 3 | 依赖缺失：Python < 3.11，或 patentkit / 其依赖未安装 |

设计约束：**本文件只依赖标准库**。patentkit 的 import 全部延迟到函数内部，
否则「没装包」会在脚本启动的第一行就变成 traceback，`require_patentkit()` 的
友好提示永远执行不到。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Iterable, NoReturn

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_WORKSPACE = 2
EXIT_DEPENDENCY = 3
#: 非业务码：Ctrl+C 中断。POSIX 惯例 130 = 128 + SIGINT。
EXIT_INTERRUPTED = 130

#: 与 `patentkit/pyproject.toml` 的 requires-python 保持一致
MIN_PYTHON = (3, 11)

#: 依赖检查只做一次（同一进程内 main 可能被重复调用）
_REQUIRED = False


# ── 编码 ──────────────────────────────────────────────────────────────


def configure_stdio() -> None:
    """把 stdout/stderr 固定为 UTF-8。

    Windows 下 Python 默认按控制台代码页（cp936）编码输出。本包的输出含
    `✅/❌/⚠️` 等符号，直接 print 会 `UnicodeEncodeError`；被父进程捕获时
    还会因为编码不一致变成乱码。重设编码比要求用户先 `chcp 65001` 或
    设 `PYTHONIOENCODING` 更可靠 —— 这个坑不该让调用方来填。

    `errors="replace"`：终端实在显示不了某个符号时降级成 `?`，也不要整条命令崩掉。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # 被替换成非 TextIOWrapper 的流（如测试里的 StringIO）
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - 流已关闭等极端情况
            pass


# ── 依赖 ──────────────────────────────────────────────────────────────


def require_patentkit() -> None:
    """确认 Python 版本与 patentkit 可用；不满足时打印修法并 exit 3。

    检查顺序：先 Python 版本（低于 3.11 时连 patentkit 都不必试装），
    再 `import patentkit`。区分两种 ImportError：

    * 缺 `patentkit` 本身 —— 没装，给安装命令；
    * 缺第三方依赖（如 `yaml`）—— 装了但依赖不全，给补装命令。
      原来的写法一律提示「没装 patentkit」，用户会白重装一遍。
    """
    global _REQUIRED
    if _REQUIRED:
        return

    if sys.version_info < MIN_PYTHON:
        _die(
            f"需要 Python ≥ {MIN_PYTHON[0]}.{MIN_PYTHON[1]}，"
            f"当前是 {platform.python_version()}",
            EXIT_DEPENDENCY,
            hints=(
                "本技能脚本使用 3.11+ 语法（`X | None`、内建泛型）",
                '升级 Python 后重装：pip install -e ".[dev]"',
            ),
        )

    try:
        import patentkit  # noqa: F401  # 只做可用性探测
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing == "patentkit" or missing.startswith("patentkit."):
            _die(
                "没有找到 patentkit 包",
                EXIT_DEPENDENCY,
                hints=(
                    '在仓库根（含 pyproject.toml）安装：pip install -e ".[dev]"',
                    "或安装发布版：pip install patentkit",
                    "装完自检：python -m patentkit doctor",
                ),
            )
        _die(
            f"patentkit 已安装，但缺少依赖模块 '{missing}'",
            EXIT_DEPENDENCY,
            hints=(
                '补齐依赖：pip install -e ".[dev]"',
                "依赖清单见仓库根 pyproject.toml 的 [project] dependencies",
            ),
        )

    _REQUIRED = True


# ── 工作区 ────────────────────────────────────────────────────────────


def _workspace_hints() -> tuple[str, ...]:
    """定位失败时的三条修法。固定顺序，方便调用方 grep。"""
    return (
        "1) cd 到工作区根目录（含 workspace.yml）后再运行",
        "2) 加 --root <工作区路径> 显式指定",
        "3) 设环境变量 PATENTKIT_WORKSPACE=<工作区路径>，之后在任何目录都能用",
    )


def resolve_workspace(explicit: str | None = None, *, as_json: bool = False) -> Path:
    """定位工作区根，**找不到就 exit 2**（不返回、不静默回退）。

    定位顺序与 `patentkit.paths.find_workspace` 一致：

    1. `--root PATH`：显式指定。指错了直接报错 —— **绝不悄悄回退**，
       否则用户会以为在改 A 工作区，实际算了 B。
    2. 环境变量 `PATENTKIT_WORKSPACE`：显式指定；指错了同样直接报错。
    3. 从当前目录向上找 `workspace.yml`（兼容旧标志组合）。

    这里没有直接调用 `find_workspace()` 就完事，是因为要先区分「--root 指错」
    与「环境变量指错」两种语境，给出对应的修法；直接透传异常消息会让
    `--root` 场景的提示指错方向。
    """
    require_patentkit()
    from patentkit import paths

    if explicit:
        root = Path(explicit).expanduser()
        if not paths.is_workspace(root):
            _die(
                f"--root 指向的目录不是 patentkit 工作区：{root}",
                EXIT_WORKSPACE,
                hints=_workspace_hints(),
                as_json=as_json,
            )
        return root.resolve()

    env_value = os.environ.get(paths.ENV_WORKSPACE) or ""
    if env_value:
        root = Path(env_value).expanduser()
        if not paths.is_workspace(root):
            _die(
                f"环境变量 {paths.ENV_WORKSPACE} 指向的目录不是工作区：{env_value}",
                EXIT_WORKSPACE,
                hints=(
                    f"改指向含 workspace.yml 的目录，或清掉 {paths.ENV_WORKSPACE} 让它退回向上查找",
                    *_workspace_hints(),
                ),
                as_json=as_json,
            )
        return root.resolve()

    try:
        return paths.find_workspace()
    except paths.WorkspaceNotFound:
        _die(
            f"从 {Path.cwd()} 向上找不到 patentkit 工作区（没有 workspace.yml）",
            EXIT_WORKSPACE,
            hints=_workspace_hints(),
            as_json=as_json,
        )


# ── 通用参数与输出 ────────────────────────────────────────────────────


def add_common_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """给子命令加统一的 `--root` / `--json` 两个参数。

    参数说明里写明定位顺序与 JSON 契约 —— 很多人只看 `--help`。
    """
    parser.add_argument(
        "--root",
        metavar="PATH",
        default=None,
        help="工作区根；默认按 --root → PATENTKIT_WORKSPACE → 向上找 workspace.yml 定位",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="只输出机器可读 JSON（stdout 仅一个 JSON 文档，人类提示只走 stderr）",
    )
    return parser


def emit_json(data: Any) -> None:
    """--json 模式**唯一**允许的 stdout 输出。

    `ensure_ascii=False`：中文原样输出，日志与人工排查都直接可读；
    `indent=2`：与 `patentkit` 其它 `--json` 输出保持同一种形态。
    """
    print(json.dumps(data, ensure_ascii=False, indent=2))


def failure(
    message: str,
    code: int = EXIT_FAIL,
    *,
    hints: Iterable[str] = (),
    as_json: bool = False,
) -> int:
    """统一的失败出口：人类提示走 stderr；--json 模式输出结构化错误到 stdout。

    返回退出码而不是抛异常，方便 `main()` 直接 `return _env.failure(...)`；
    需要立即退出的地方用 `_die()`。
    """
    hint_list = list(hints)
    if as_json:
        emit_json({"ok": False, "code": code, "error": message, "hints": hint_list})
    else:
        print(f"❌ {message}", file=sys.stderr)
        for hint in hint_list:
            print(f"   · {hint}", file=sys.stderr)
    return code


def _die(
    message: str,
    code: int = EXIT_FAIL,
    *,
    hints: Iterable[str] = (),
    as_json: bool = False,
) -> NoReturn:
    """同 `failure()`，但以 `SystemExit(code)` 立即退出。"""
    raise SystemExit(failure(message, code, hints=hints, as_json=as_json))


# ── 脚本入口 ──────────────────────────────────────────────────────────


def run_script(main: Any) -> int:
    """脚本统一入口：锁编码 → 跑 main → 把意外异常收敛成一个退出码。

    为什么要兜底异常：LLM 客户端读到 traceback 只会把整段贴回来，
    真正有用的信息（重跑哪条命令、退出码几）反而淹没。可预期的失败
    （工作区/业务）在各自 `main()` 里已处理成 1/2/3；走到这里的都是意外，
    给一行摘要 + 自检命令，退出码按「业务失败」算。

    argparse 的用法错误（exit 2）与 resolve_workspace 的退出（exit 2）
    都是 `SystemExit`，必须原样穿过去，不能重新归类。
    """
    configure_stdio()
    try:
        return int(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\n⚠️ 已中断", file=sys.stderr)
        return EXIT_INTERRUPTED
    except Exception as exc:  # noqa: BLE001 - 见函数说明：故意兜底
        print(f"❌ 未预期错误：{type(exc).__name__}: {exc}", file=sys.stderr)
        print("   · 先跑 python -m patentkit doctor 自检", file=sys.stderr)
        print("   · 需要结构化错误时加 --json", file=sys.stderr)
        return EXIT_FAIL
