"""patent_intel command-line interface (blueprint §3.3).

WP-0 ships the framework and `doctor`; each work package registers its own subcommand
group as it lands, so `--help` only ever shows commands that actually work — a
placeholder that prints "not implemented" would be worse than absence.

Exit codes (aligned with the kernel's script conventions):
| 0 | success / diagnostics all green |
| 1 | business failure (doctor found blocking issues) |
| 2 | workspace/usage problem |
| 3 | missing dependency |
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from patent_intel import __version__
from patent_intel.config import ENV_STATE_DIR, STATE_DIR_NAME, load_config, resolve_state_dir
from patent_intel.workspace import SidecarLayout

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_WORKSPACE = 2
EXIT_DEPENDENCY = 3


def _emit_json(data: object) -> None:
    """The only stdout writer in --json mode (single document, CJK verbatim)."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _add_root_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--root", metavar="PATH", default=None, help="kernel workspace root")
    parser.add_argument(
        "--state-dir",
        metavar="PATH",
        default=None,
        help=f"sidecar state dir (default: <root>/{STATE_DIR_NAME} or ${ENV_STATE_DIR})",
    )
    parser.add_argument("--json", action="store_true", help="emit exactly one JSON document on stdout")
    return parser


# ── doctor ────────────────────────────────────────────────────────────


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Read-only environment/workspace/sidecar self-check. Never touches the network."""
    report: dict[str, object] = {
        "tool": "patent_intel",
        "version": __version__,
        "python": platform.python_version(),
        "platform": sys.platform,
        "checks": {},
    }
    checks: dict[str, object] = {}
    blocking = 0
    workspace_blocking = 0

    # 1) kernel availability
    from patent_intel.kernel_bridge import kernel_info

    info = kernel_info()
    checks["kernel"] = {
        "importable": info.importable,
        "version": info.version,
        "protocol_version": info.protocol_version,
        "compatible": info.compatible(),
        "note": info.error,
        "min_version": "0.8.0",
    }
    if info.importable and not info.compatible():
        blocking += 1

    # 2) workspace discovery (optional: doctor works outside a workspace too)
    workspace: Path | None = None
    if args.root:
        from patent_intel.kernel_bridge import is_kernel_workspace

        candidate = Path(args.root).expanduser()
        if not candidate.is_dir():
            checks["workspace"] = {"found": False, "error": f"directory does not exist: {candidate}"}
            workspace_blocking += 1
        elif not is_kernel_workspace(candidate):
            checks["workspace"] = {
                "found": False,
                "error": f"not a patentkit workspace (no workspace.yml): {candidate}",
            }
            workspace_blocking += 1
        else:
            workspace = candidate.resolve()
            checks["workspace"] = {"found": True, "path": str(workspace)}
    else:
        from patent_intel.kernel_bridge import find_kernel_workspace

        try:
            workspace = find_kernel_workspace(Path.cwd())
            checks["workspace"] = {"found": True, "path": str(workspace)}
        except FileNotFoundError as exc:
            checks["workspace"] = {"found": False, "note": str(exc)}

    # 3) sidecar state dir + config (only meaningful with a workspace or explicit --state-dir)
    if workspace is None and not args.state_dir:
        checks["state_dir"] = {
            "skipped": True,
            "note": "no workspace/context; state dir resolves once --root or --state-dir is given",
        }
    else:
        try:
            state_dir = resolve_state_dir(workspace, args.state_dir)
            layout = SidecarLayout(state_dir)
            entry: dict[str, object] = {"path": str(state_dir), "exists": layout.exists()}
            if workspace is not None:
                layout.check_binding(workspace)
            if layout.exists():
                entry["summary"] = layout.summary()
                config = load_config(state_dir)
                entry["config"] = {
                    "network_consent": config.network_consent,
                    "allowed_sources": config.allowed_sources,
                    "budgets": vars(config.budgets)
                    if isinstance(config.budgets, dict)
                    else config.budgets.__dict__,
                }
            else:
                entry["note"] = "sidecar not initialized yet (created on first write-capable command)"
            checks["state_dir"] = entry
        except Exception as exc:  # noqa: BLE001 - doctor reports, never crashes
            checks["state_dir"] = {"error": f"{type(exc).__name__}: {exc}"}
            blocking += 1

    checks["network"] = {
        "default": "offline",
        "note": "no network access is performed by doctor or any offline command",
    }

    report["checks"] = checks
    report["ok"] = (blocking + workspace_blocking) == 0
    report["blocking_issues"] = blocking + workspace_blocking
    report["workspace_errors"] = workspace_blocking

    if args.json:
        _emit_json(report)
    else:
        _render_doctor(report)
    # Workspace problems exit 2 (kernel convention), other blocking issues exit 1.
    if workspace_blocking:
        return EXIT_WORKSPACE
    return EXIT_OK if blocking == 0 else EXIT_FAIL


def _render_doctor(report: dict[str, object]) -> None:
    checks = report["checks"]
    assert isinstance(checks, dict)
    print(f"patent_intel {report['version']} — doctor (Python {report['python']}, {report['platform']})")
    kernel = checks.get("kernel", {})
    assert isinstance(kernel, dict)
    if kernel.get("importable"):
        mark = "OK  " if kernel.get("compatible") else "WARN"
        print(
            f"  [{mark}] kernel: patentkit {kernel.get('version')}"
            f" (protocol {kernel.get('protocol_version')}, compatible={kernel.get('compatible')})"
        )
    else:
        print(f"  [WARN] kernel: not installed — {kernel.get('note')}")
    ws = checks.get("workspace", {})
    assert isinstance(ws, dict)
    if ws.get("found"):
        print(f"  [OK  ] workspace: {ws.get('path')}")
    elif "error" in ws:
        print(f"  [FAIL] workspace: {ws.get('error')}")
    else:
        print("  [----] workspace: not found (pass --root to check a specific one)")
    sd = checks.get("state_dir", {})
    assert isinstance(sd, dict)
    if "error" in sd:
        print(f"  [FAIL] state dir: {sd.get('error')}")
    elif sd.get("skipped"):
        print(f"  [----] state dir: skipped — {sd.get('note')}")
    else:
        print(f"  [{'OK  ' if sd.get('exists') else '----'}] state dir: {sd.get('path')}")
    net = checks.get("network", {})
    assert isinstance(net, dict)
    print(f"  [OK  ] network: {net.get('default')} — {net.get('note')}")
    blocking = report.get("blocking_issues", 0)
    print(f"result: {'OK' if report['ok'] else f'{blocking} blocking issue(s)'}")


# ── parser assembly ───────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patent_intel",
        description=(
            "Optional retrieval/document/evidence extension for the patent-research skills. "
            "The patentkit kernel stays the sole authority for evidence levels, gates and sign-off."
        ),
    )
    parser.add_argument("--version", action="version", version=f"patent_intel {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    doctor = sub.add_parser(
        "doctor",
        help="read-only self-check: kernel, workspace, sidecar, network policy (no network access)",
    )
    _add_root_args(doctor)
    doctor.set_defaults(func=_cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # pragma: no cover - closed/odd streams
                pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_OK
    try:
        return int(args.func(args))
    except KeyboardInterrupt:  # pragma: no cover
        print("\n⚠️ Interrupted", file=sys.stderr)
        return 130
