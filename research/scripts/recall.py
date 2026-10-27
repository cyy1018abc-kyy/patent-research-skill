#!/usr/bin/env python
"""Recall-enhancement thin wrapper (blueprint A-07, WP-A).

The only Skill-side entry into the patent_intel extension. Discipline:

* **degrade honestly**: patent_intel not installed → print install guidance, exit 3;
  the plain research workflow never depends on this script;
* **route only**: business logic lives in `patent_intel` (offline recall report);
  this file resolves the workspace, forwards `--json`, and maps exit codes;
* **no kernel writes**: the recall report writes only to the extension sidecar.

Usage:
    python research/scripts/recall.py report --root <workspace> [--json]
    python research/scripts/recall.py plan  --root <workspace> --axis N1 [--json]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _env  # noqa: E402  (same layer as the other scripts; stdlib only)

#: what to tell the user when the extension is absent
_INSTALL_HINTS = (
    "pip install -e extensions/patent_intel --no-deps   # 从仓库根目录（最小安装）",
    "pip install \"patent_intel[kernel]\"                # 或从 PyPI/构建产物安装",
    "安装后自检: python -m patent_intel doctor --root <workspace>",
)


def _require_patent_intel(as_json: bool) -> None:
    try:
        import patent_intel  # noqa: F401
    except ImportError:
        _env._die(  # noqa: SLF001 - uniform script-layer failure output
            "The patent_intel extension is not installed (recall enhancement is optional)",
            _env.EXIT_DEPENDENCY,
            as_json=as_json,
            hints=_INSTALL_HINTS,
        )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="recall.py",
        description="Offline recall diagnostics via the optional patent_intel extension.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    report = sub.add_parser("report", help="offline coverage + incremental-yield report (sidecar only)")
    _env.add_common_args(report)
    report.add_argument("--state-dir", default=None, help="override the sidecar state dir")
    report.add_argument("--max-requests", type=int, default=20)

    plan = sub.add_parser("plan", help="query-family proposals for one axis (printed, nothing written)")
    _env.add_common_args(plan)
    plan.add_argument("--axis", required=True, help="axis id, bare (N1) or target-qualified (N1@TGT-9001)")

    args = parser.parse_args(argv)
    _env.configure_stdio()
    _require_patent_intel(as_json=args.json)
    _env.require_patentkit(as_json=args.json)  # plan/report also read the kernel workspace
    workspace = _env.resolve_workspace(args.root, as_json=args.json)

    # forward to the extension CLI in-process (same exit-code contract)
    from patent_intel.cli import main as intel_main

    forwarded: list[str] = []
    if args.command == "report":
        forwarded = ["recall", "report", "--root", str(workspace)]
        if args.state_dir:
            forwarded += ["--state-dir", args.state_dir]
        if args.max_requests != 20:
            forwarded += ["--max-requests", str(args.max_requests)]
    else:
        forwarded = ["query", "plan", "--root", str(workspace), "--axis", args.axis]
    if args.json:
        forwarded.append("--json")

    code = intel_main(forwarded)
    # extension exit codes: 0 ok | 1 business | 2 workspace | 3 dependency (aligned)
    return int(code)


if __name__ == "__main__":
    raise SystemExit(_env.run_script(main))
