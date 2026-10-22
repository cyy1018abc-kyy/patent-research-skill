#!/usr/bin/env python
"""See the whole workspace status at a glance — thin wrapper over `patentkit.api.status`.

What it shows: the current target, a one-line summary of the five gates' PASS/FAIL, validation
error/warn counts, candidate and log distribution, and next-step hints. **How gates are computed and
what validation checks are entirely decided by patentkit**; this script only chooses which fields to
display and how to lay them out — the rules are implemented in exactly one place and are not copied here.

Usage:

    python patent-research-skill/scripts/status.py
    python patent-research-skill/scripts/status.py --root <workspace-path>
    python patent-research-skill/scripts/status.py --json

Exit code: 0 data readable (**whether the gates PASS does not affect this command's exit code**).
To use "can the gates be passed" as the exit code, use `gates.py` or `check.py`.
Missing dependency 3 / workspace problem 2; unparseable data (e.g. a broken glossary) is also workspace problem 2.
"""

from __future__ import annotations

import argparse

import _env

#: gate.status → display symbol. Status values come from patentkit; this is only a visual mapping.
_GATE_MARK = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "N/A": "⬜ N/A"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="status.py",
        description="Everything at a glance: target, five-gate summary, validation, candidate distribution, next-step hints",
    )
    _env.add_common_args(parser)
    return parser


def _fmt_counts(counts: dict) -> str:
    """Lay out {key: count} as one line `key count · key count`; an empty dict displays "none"."""
    if not counts:
        return "none"
    return " · ".join(f"{key} {value}" for key, value in counts.items())


def render(data: dict) -> str:
    """Human-readable rendering. Short, with status symbols, matching the style of `patentkit status`."""
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
        f"✅ Workspace: {data['workspace']}",
        f"Target: {data['active_target']}{title}",
        f"Acceptance gates: {gate_line}  →  "
        + ("✅ all five PASS (verified column only)" if all_pass else "❌ some gate failed; see gates.py for details"),
        f"Validation: error {validation['errors']} / warn {validation['warnings']} / info {info}"
        + ("  →  ✅ strict mode would also pass" if strict_ok else "  →  ❌ strict mode would fail"),
        f"Candidates: {candidates['total']} total · evidence level {_fmt_counts(candidates['by_evidence_level'])}"
        f" · relevance≥4: {candidates['with_relevance_ge4']}",
        f"      role {_fmt_counts(candidates['by_role'])}"
        f" · relevance {_fmt_counts(candidates['by_relevance'])}",
        f"Search logs: {logs['total']} total (live {logs['live']} / retrospective {logs['retrospective']})",
        "",
    ]

    hints = data.get("hints") or []
    if hints:
        lines.append("Next steps:")
        lines.extend(f"  · {hint}" for hint in hints)
    else:
        lines.append("Next steps: no blockers (data consistent, all five gates PASS)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _env.require_patentkit()
    root = _env.resolve_workspace(args.root, as_json=args.json)

    # Deferred import: when the package is missing, require_patentkit() gives install guidance instead of a traceback
    from patentkit import api
    from patentkit.registry import TerminologyError

    try:
        data = api.status(root)
    except (api.WorkspaceError, TerminologyError, ValueError) as exc:
        return _env.failure(
            f"Failed to read workspace data: {exc}",
            _env.EXIT_WORKSPACE,
            hints=("Run python -m patentkit doctor first to locate whether the glossary or a data file is the problem",),
            as_json=args.json,
        )

    if args.json:
        _env.emit_json({"command": "status", **data, "ok": True})
        return _env.EXIT_OK

    print(render(data))
    return _env.EXIT_OK


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
