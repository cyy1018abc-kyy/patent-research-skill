#!/usr/bin/env python
"""Summary of five gates × three columns (verified/attested/asserted) — thin wrapper over `patentkit.api.gates`.

Criteria (fixed on the tool side, not recomputed here): **PASS is recognized only on the strictest verified column**;
attested/asserted are historical record and do not constitute a basis for passing. This script only presents:

Usage:

    python patent-research-skill/scripts/gates.py
    python patent-research-skill/scripts/gates.py --target TGT-0002 --json

`--target` defaults to the glossary's `active_target`; multi-target workspaces should specify it explicitly,
otherwise you see the gates of "the currently active target", not the one you meant.

Exit code: 0 all five gates PASS / 1 some gate not passed (including N/A) / 2 workspace problem / 3 missing dependency.

⚠️ Difference from the native `python -m patentkit gates`: the native command exits **2** when not all gates
pass, while this script maps it to **1** under the skill package's unified exit-code convention (2 is reserved
for workspace problems).
"""

from __future__ import annotations

import argparse
import unicodedata

import _env

_GATE_MARK = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "N/A": "⬜ N/A"}

_HEADERS = ("Gate", "Status", "Threshold", "verified (strictest)", "≥attested", "≥asserted")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gates.py",
        description="G-S-01..05 three-column acceptance-gate summary (thin wrapper over patentkit.api.gates)",
    )
    parser.add_argument(
        "--target",
        metavar="TGT-xxxx",
        default=None,
        help="target ID (defaults to the glossary's active_target; multi-target workspaces should specify it explicitly)",
    )
    _env.add_common_args(parser)
    return parser


def _display_width(text: str) -> int:
    """Terminal display width: CJK full-width characters count as 2 columns so the table stays aligned in CJK terminals."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _table(rows: list[tuple[str, ...]]) -> list[str]:
    """A simple table aligned by display width (no third-party table library)."""
    widths = [
        max(_display_width(row[column]) for row in (rows + [_HEADERS]))
        for column in range(len(_HEADERS))
    ]
    lines = [
        "  ".join(_pad(cell, widths[index]) for index, cell in enumerate(_HEADERS)).rstrip(),
        "  ".join("-" * width for width in widths),
    ]
    for row in rows:
        lines.append("  ".join(_pad(cell, widths[index]) for index, cell in enumerate(row)).rstrip())
    return lines


def render(data: dict) -> str:
    gates = data["gates"]
    rows = [
        (
            gate["gate_id"],
            _GATE_MARK.get(gate["status"], gate["status"]),
            gate["threshold"],
            gate["values"].get("verified", "-"),
            gate["values"].get("attested", "-"),
            gate["values"].get("asserted", "-"),
        )
        for gate in gates
    ]

    lines = [f"Acceptance gates · Target {data.get('target', '?')} (PASS recognized on the verified column only)", ""]
    lines += _table(rows)
    lines.append("")

    per_axis = data.get("per_axis") or {}
    if per_axis:
        lines.append(
            "G-S-02 per axis (verified document counts): "
            + "  ".join(f"{axis}={values['verified']}" for axis, values in sorted(per_axis.items()))
        )

    failed = [gate for gate in gates if gate["status"] != "PASS"]
    if failed:
        lines.append("")
        lines.append("Failed gates:")
        for gate in failed:
            reason = gate.get("note") or "inspect the values column yourself"
            lines.append(f"  · {gate['gate_id']} ({gate['status']}) {reason}")
        lines.append("")
        lines.append("Next steps: a gate FAIL is not \"think it over\" — it means the search is insufficient; prioritize supplementary searching, not loosening the criteria")
        lines.append(f"Summary: ❌ {len(failed)}/{len(gates)} gates failed")
    else:
        lines.append("")
        lines.append(f"Summary: ✅ all gates PASS ({len(gates)}/{len(gates)})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _env.require_patentkit()
    root = _env.resolve_workspace(args.root, as_json=args.json)

    # Deferred import: when the package is missing, require_patentkit() gives install guidance instead of a traceback
    from patentkit import api
    from patentkit.registry import TerminologyError

    try:
        data = api.gates(root, target=args.target)
    except (api.WorkspaceError, TerminologyError, ValueError) as exc:
        return _env.failure(
            f"Failed to read workspace data: {exc}",
            _env.EXIT_WORKSPACE,
            hints=("Run python -m patentkit doctor first to locate glossary/active_target problems",),
            as_json=args.json,
        )

    ok = bool(data.get("all_pass"))
    if args.json:
        _env.emit_json({"command": "gates", **data, "ok": ok})
    else:
        print(render(data))
    return _env.EXIT_OK if ok else _env.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
