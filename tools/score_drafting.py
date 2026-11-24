"""score_drafting —— 撰写正文一致性基准评分器（4.3 / M2：`draft lint` 的检出率与误报）。

评分对象是内核 `patentkit.manuscript_lint.lint_texts`（与 `draft lint` / 交付门 E-016 同一实现，
这里不另立规则）；评分依据是每个案例 YAML 的 `expected` 清单。

案例（`benchmarks/drafting/cases/*.yaml`，全部合成）：
* 干净稿：`expected: []`——任何级别的发现都计为误报；
* 缺陷注入稿：每个注入缺陷对应一条 `{code, path}`。

比对按 `(code, path)` 集合进行（同一位置同一代码的多条消息合并为一条）：
* detected   = 期望 ∩ 实际
* missed     = 期望 − 实际（漏检）
* unexpected = 实际 − 期望（误报，含 warn 级）

指标：detection_rate = detected / 期望总数；false_positives = unexpected 总数。

用法：
    python tools/score_drafting.py --suite benchmarks/drafting/cases
    python tools/score_drafting.py --suite benchmarks/drafting/cases --gate perfect   # CI 门
    python tools/score_drafting.py --case benchmarks/drafting/cases/dm02-um-defects.yaml --json

退出码：0 通过；1 评分完成但 --gate 未达标；2 环境/案例无效（不可评）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FIELDS = (
    "id",
    "application_type",
    "title",
    "structured_claims",
    "figures",
    "claims",
    "specification",
    "abstract",
    "expected",
)


class CaseError(ValueError):
    """A benchmark case file is malformed (exit 2)."""


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def load_case(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CaseError(f"{path}: cannot read case: {exc}") from exc
    if not isinstance(data, dict):
        raise CaseError(f"{path}: case must be a mapping")
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise CaseError(f"{path}: missing fields {missing}")
    if data["expected"] is None:
        data["expected"] = []
    for item in data["expected"]:
        if not isinstance(item, dict) or not item.get("code") or not item.get("path"):
            raise CaseError(f"{path}: every expected entry needs code and path, got {item!r}")
    if Path(path).stem != str(data["id"]):
        raise CaseError(f"{path}: id {data['id']!r} does not match the file name")
    return data


def score_case(case: dict[str, Any]) -> dict[str, Any]:
    from patentkit import manuscript_lint  # kernel is the single implementation of the rules

    report = manuscript_lint.lint_texts(
        claims_text=str(case["claims"]),
        specification_text=str(case["specification"]),
        abstract_text=str(case["abstract"]),
        structured_claims=list(case["structured_claims"] or []),
        figures=list(case["figures"] or []),
        application_type=str(case["application_type"]),
        title=str(case["title"] or ""),
    )
    found = {(finding["code"], finding["path"]) for finding in report["errors"] + report["warnings"]}
    expected = {(str(item["code"]), str(item["path"])) for item in case["expected"]}
    detected = expected & found
    missed = expected - found
    unexpected = found - expected
    return {
        "id": case["id"],
        "expected": len(expected),
        "detected": len(detected),
        "missed": sorted(f"{code} @ {path}" for code, path in missed),
        "unexpected": sorted(f"{code} @ {path}" for code, path in unexpected),
        "detection_rate": (len(detected) / len(expected)) if expected else 1.0,
        "codes": sorted({code for code, _path in expected}),
    }


def score_suite(paths: list[Path]) -> dict[str, Any]:
    cases = [score_case(load_case(path)) for path in paths]
    expected = sum(case["expected"] for case in cases)
    detected = sum(case["detected"] for case in cases)
    false_positives = sum(len(case["unexpected"]) for case in cases)
    return {
        "cases": cases,
        "expected": expected,
        "detected": detected,
        "detection_rate": (detected / expected) if expected else 1.0,
        "false_positives": false_positives,
        "codes_covered": sorted({code for case in cases for code in case["codes"]}),
        "perfect": detected == expected and false_positives == 0,
    }


def render(result: dict[str, Any]) -> str:
    lines = []
    for case in result["cases"]:
        status = "✅" if not case["missed"] and not case["unexpected"] else "❌"
        lines.append(f"{status} {case['id']}: detected {case['detected']}/{case['expected']}, unexpected {len(case['unexpected'])}")
        lines.extend(f"     missed      {item}" for item in case["missed"])
        lines.extend(f"     unexpected  {item}" for item in case["unexpected"])
    lines.append("")
    lines.append(
        f"detection_rate {result['detection_rate']:.3f} ({result['detected']}/{result['expected']}), "
        f"false_positives {result['false_positives']}, codes covered {len(result['codes_covered'])}: "
        + ", ".join(result["codes_covered"])
    )
    return "\n".join(lines)


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description="Score `draft lint` against the synthetic drafting benchmark")
    parser.add_argument("--suite", type=Path, help="directory of *.yaml cases")
    parser.add_argument("--case", type=Path, help="one case file")
    parser.add_argument("--gate", choices=("perfect",), help="perfect = every seeded defect detected and zero false positives")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if bool(args.suite) == bool(args.case):
        parser.error("pass exactly one of --suite or --case")
    paths = sorted(args.suite.glob("*.yaml")) if args.suite else [args.case]
    if not paths:
        print(f"no cases under {args.suite}", file=sys.stderr)
        return 2
    try:
        result = score_suite(paths)
    except CaseError as exc:
        print(f"[INVALID] {exc}", file=sys.stderr)
        return 2
    except ImportError as exc:
        print(f"[ENV] patentkit (>= 0.11.0) is required: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    if args.gate == "perfect" and not result["perfect"]:
        if not args.json:
            print("gate perfect: NOT MET")
        return 1
    if args.gate and not args.json:
        print("gate perfect: MET")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
