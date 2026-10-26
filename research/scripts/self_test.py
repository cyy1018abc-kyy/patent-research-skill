#!/usr/bin/env python
"""安装后自检（self-test）：一条命令验证「内核 + 技能封装 + 工作区流」真的能跑。

对标 cnipa-patent-kit 的 self_test.py。六项检查（对标发布验收的正反用例）：

1. Python ≥ 3.11；
2. patentkit 可导入，版本 ≥ 0.7.0 且评估协议 = 1；
3. 技能封装依赖（本目录 _env）可用；
4. 用内核模板生成一个**合成样例工作区**（TGT-0002，无真实数据）；
5. 正用例：`validate --strict` 在干净样例上必须 0 error / 0 warn；
6. 反用例：`gates` 在只有模板数据的样例上必须**不全 PASS**（门禁没有被硬编码成永远通过）。

可选第 7 项：装了 python-docx 时导出一份 docx 冒烟（未装则跳过，不算失败）。

用法：

    python patent-research-skill/scripts/self_test.py
    python patent-research-skill/scripts/self_test.py --json

退出码：0 全部通过 / 1 任一检查失败 / 3 缺内核依赖。
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import _env

REQUIRED_KERNEL = "0.7.0"


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(part) for part in v.split(".")[:3])


def run_checks() -> tuple[list[dict], bool]:
    """返回 (每项检查结果, 是否全部通过)。"""
    results: list[dict] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append({"name": name, "ok": ok, "detail": detail})

    # 1. Python 版本
    record(
        "python",
        _env.MIN_PYTHON <= __import__("sys").version_info[:2],
        f"{'.'.join(map(str, __import__('sys').version_info[:3]))}",
    )

    # 2. 内核可用性 + 版本 + 协议
    try:
        import patentkit
        from patentkit.assessment import PROTOCOL_VERSION

        ok = (
            _version_tuple(patentkit.__version__) >= _version_tuple(REQUIRED_KERNEL)
            and PROTOCOL_VERSION == 1
        )
        record(
            "patentkit",
            ok,
            f"patentkit {patentkit.__version__} (assessment protocol {PROTOCOL_VERSION}; 需要 ≥{REQUIRED_KERNEL}/1)",
        )
    except Exception as exc:  # noqa: BLE001 - 任何导入问题都收敛成一条检查结果
        record("patentkit", False, f"import 失败：{exc}")
        return results, False

    from patentkit import api
    from patentkit import export as export_mod
    from patentkit.init import init_workspace

    # 3/4. 合成样例工作区
    with tempfile.TemporaryDirectory(prefix="patent-selftest-") as tmp:
        sample = Path(tmp) / "sample_workspace"
        try:
            init_workspace(sample, "TGT-0002", "自检合成样例")
            record("sample_workspace", True, f"{len(list(sample.rglob('*')))} 个条目")
        except Exception as exc:  # noqa: BLE001
            record("sample_workspace", False, f"init_workspace 失败：{exc}")
            return results, False

        # 5. 正用例：干净样例必须 strict 通过
        try:
            validation = api.validate(sample, strict=True)
            record(
                "validate_clean_sample",
                bool(validation["ok"]),
                f"error {validation['summary']['errors']} / warn {validation['summary']['warnings']}"
                + ("" if validation["ok"] else " —— 模板生成的干净工作区不应有错误"),
            )
        except Exception as exc:  # noqa: BLE001
            record("validate_clean_sample", False, f"validate 失败：{exc}")

        # 6. 反用例：门禁不得在空数据上全 PASS
        try:
            gates = api.gates(sample)
            all_pass = bool(gates.get("all_pass"))
            record(
                "gates_empty_sample_not_pass",
                not all_pass,
                "all_pass=True —— 门禁被硬编码通过，这是严重缺陷" if all_pass else "空样例正确地未通过门禁",
            )
        except Exception as exc:  # noqa: BLE001
            record("gates_empty_sample_not_pass", False, f"gates 失败：{exc}")

        # 7. 可选：docx 冒烟（内核输出重定向，保持 --json 模式下 stdout 唯一出口）
        try:
            import docx  # noqa: F401

            import contextlib
            import io

            out = Path(tmp) / "smoke.docx"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = export_mod.main(["TGT-0002", "--root", str(sample), "--out", str(out)])
            record("export_docx_smoke", rc == 0 and out.is_file(), str(out.name))
        except ImportError:
            record("export_docx_smoke", True, "跳过（未安装 python-docx；导出是可选功能）")
        except Exception as exc:  # noqa: BLE001
            record("export_docx_smoke", False, f"export-docx 失败：{exc}")

    return results, all(item["ok"] for item in results)


def render(results: list[dict]) -> str:
    lines = ["技能自检（self-test）", ""]
    for item in results:
        mark = "OK  " if item["ok"] else "FAIL"
        lines.append(f"  [{mark}] {item['name']}: {item['detail']}")
    passed = sum(1 for item in results if item["ok"])
    lines.append("")
    lines.append(f"结果：{passed}/{len(results)} 通过")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="self_test.py", description="安装后自检：内核+封装+工作区流")
    _env.add_common_args(parser)
    parser.add_argument("--skip-export", action="store_true", help="跳过 docx 冒烟检查")
    args = parser.parse_args(argv)
    _env.configure_stdio()

    # 内核缺失时给出与其它脚本一致的安装指引（exit 3）
    _env.require_patentkit(as_json=args.json)

    results, ok = run_checks()
    if args.json:
        _env.emit_json({"command": "self_test", "ok": ok, "checks": results})
    else:
        print(render(results))
    return _env.EXIT_OK if ok else _env.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
