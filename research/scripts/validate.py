#!/usr/bin/env python
"""Thin wrapper over consistency validation V001-V028 — calls `patentkit.api.validate`.

The rules are implemented in `patentkit/validate.py`; this script **copies no rules or thresholds**:
it only decides which findings to show, how to lay them out, and how to map exit codes.

Usage:

    python patent-research-skill/scripts/validate.py            # normal: only errors count as failure
    python patent-research-skill/scripts/validate.py --strict   # strict: warnings also count as failure
    python patent-research-skill/scripts/validate.py --json

Exit code: 0 pass / 1 blocking findings (normal: errors; strict: warnings too) / 2 workspace problem / 3 missing dependency.
"""

from __future__ import annotations

import argparse

import _env

#: Maximum number of blocking findings to list in human output; beyond that, point to --json instead of flooding the terminal
_MAX_SHOW = 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate.py",
        description="Consistency validation V001-V028 (thin wrapper over patentkit.api.validate)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="strict mode: warnings also count as failures (CI criteria)",
    )
    _env.add_common_args(parser)
    return parser


def _blocking(data: dict) -> list[dict]:
    """The findings that actually cause failure in the current mode.

    Normal mode takes only errors; strict mode also counts warnings. info never blocks — it is
    "a historical fact recorded truthfully" (e.g. partial collection), not an error to fix.
    """
    levels = {"error", "warn"} if data["strict"] else {"error"}
    return [finding for finding in data["findings"] if finding["level"] in levels]


def render(data: dict) -> str:
    summary = data["summary"]
    strict = data["strict"]
    mode = "strict" if strict else "normal"
    info = summary["total"] - summary["errors"] - summary["warnings"]
    blocking = _blocking(data)

    if data["ok"]:
        lines = [f"✅ Validation passed ({mode}): 0 error / 0 warn" + (f" / {info} info (non-blocking)" if info else "")]
        return "\n".join(lines)

    lines = [
        f"❌ Validation failed ({mode}): {summary['errors']} error / {summary['warnings']} warn"
        f" / {info} info"
    ]
    by_code: dict[str, int] = {}
    for finding in blocking:
        by_code[finding["code"]] = by_code.get(finding["code"], 0) + 1
    lines.append("By rule: " + "  ".join(f"{code}×{count}" for code, count in sorted(by_code.items())))
    lines.append("")
    for finding in blocking[:_MAX_SHOW]:
        location = finding["path"] + (f":{finding['line']}" if finding.get("line") else "")
        lines.append(
            f"  [{finding['level'].upper():5}] {finding['code']} {location} — {finding['message']}"
        )
    hidden = len(blocking) - _MAX_SHOW
    if hidden > 0:
        lines.append(f"  … {hidden} more; see --json")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    _env.configure_stdio()
    args = build_parser().parse_args(argv)
    _env.require_patentkit(as_json=args.json)
    root = _env.resolve_workspace(args.root, as_json=args.json)

    # Deferred import: when the package is missing, require_patentkit() gives install guidance instead of a traceback
    from patentkit import api
    from patentkit.registry import TerminologyError

    try:
        data = api.validate(root, strict=args.strict)
    except (api.WorkspaceError, TerminologyError) as exc:
        return _env.failure(
            f"Failed to read workspace data: {exc}",
            _env.EXIT_WORKSPACE,
            hints=("Run python -m patentkit doctor first to locate whether the glossary or a data file is the problem",),
            as_json=args.json,
        )

    if args.json:
        _env.emit_json({"command": "validate", **data})
        return _env.EXIT_OK if data["ok"] else _env.EXIT_FAIL

    print(render(data))
    return _env.EXIT_OK if data["ok"] else _env.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
