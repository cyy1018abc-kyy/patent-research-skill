#!/usr/bin/env python
"""CI entry point: run `validate --strict` + `gates` together — equivalent to `python -m patentkit check`.

Both must pass to pass:

1. `python -m patentkit validate --strict`: data consistency (warnings also count as failures)
2. `python -m patentkit gates`: all five gates G-S-01..05 PASS (verified column only)

Usage:

    python patent-research-skill/scripts/check.py
    python patent-research-skill/scripts/check.py --json

Exit code: 0 all pass / 1 any failure / 2 workspace problem / 3 missing dependency.

⚠️ Difference from the native `python -m patentkit check`: the native command returns **2** when the gates
do not pass, while this script maps it to **1** under the skill package's unified exit-code convention (2 is
reserved for workspace problems). If the caller needs to distinguish "inconsistent data" from "gates not
passed", look at `validate.ok` / `gates.all_pass` in the `--json` output.
"""

from __future__ import annotations

import argparse

import _env

#: Maximum number of blocking validation findings to list in human output; beyond that, point to --json
_MAX_SHOW = 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check.py",
        description="Required before commit: validate --strict + gates (any failure → exit 1)",
    )
    _env.add_common_args(parser)
    return parser


def _render_validate(validate_data: dict) -> list[str]:
    summary = validate_data["summary"]
    if validate_data["ok"]:
        return ["✅ Validation (strict): 0 error / 0 warn"]

    blocking = [
        finding
        for finding in validate_data["findings"]
        if finding["level"] in {"error", "warn"}
    ]
    lines = [f"❌ Validation (strict): {summary['errors']} error / {summary['warnings']} warn"]
    for finding in blocking[:_MAX_SHOW]:
        lines.append(
            f"   [{finding['level'].upper():5}] {finding['code']} {finding['path']}"
            f" — {finding['message']}"
        )
    hidden = len(blocking) - _MAX_SHOW
    if hidden > 0:
        lines.append(f"   … {hidden} more; see --json")
    return lines


def _render_gates(gates_data: dict) -> list[str]:
    gates = gates_data["gates"]
    if gates_data.get("all_pass"):
        return ["✅ Acceptance gates: all gates PASS (verified column only)"]
    detail = " · ".join(f"{gate['gate_id']} {gate['status']}" for gate in gates)
    return [f"❌ Acceptance gates: {detail}"]


def render(validate_data: dict, gates_data: dict) -> str:
    validate_ok = bool(validate_data["ok"])
    gates_ok = bool(gates_data.get("all_pass"))
    lines = [*_render_validate(validate_data), *_render_gates(gates_data), ""]

    if validate_ok and gates_ok:
        lines.append("✅ check passed: data is consistent and all gates PASS; you can move to the next stage")
        return "\n".join(lines)

    lines.append("Next steps:")
    if not validate_ok:
        lines.append("  · Fix the blocking validation findings first — gate numbers are not trustworthy while the data is inconsistent")
    if not gates_ok:
        lines.append("  · When gates do not pass, add searches first; do not loosen the criteria")
    lines.append("❌ check did not pass")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _env.require_patentkit(as_json=args.json)
    root = _env.resolve_workspace(args.root, as_json=args.json)

    # Deferred import: when the package is missing, require_patentkit() gives install guidance instead of a traceback
    from patentkit import api
    from patentkit.registry import TerminologyError

    try:
        validate_data = api.validate(root, strict=True)
        gates_data = api.gates(root)
    except (api.WorkspaceError, TerminologyError, ValueError) as exc:
        return _env.failure(
            f"Failed to read workspace data: {exc}",
            _env.EXIT_WORKSPACE,
            hints=("Run python -m patentkit doctor first to locate whether the glossary or a data file is the problem",),
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
