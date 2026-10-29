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
from patent_intel.io.safe_io import read_json_limited, write_json_atomic
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


# ── query group (WP-A) ────────────────────────────────────────────────


def _workspace_or_exit(root: str | None, *, as_json: bool) -> Path:
    from patent_intel.kernel_bridge import find_kernel_workspace, is_kernel_workspace

    if root:
        candidate = Path(root).expanduser()
        if not is_kernel_workspace(candidate):
            message = f"not a patentkit workspace (no workspace.yml): {candidate}"
            if as_json:
                _emit_json({"ok": False, "error": message})
            else:
                print(f"❌ {message}", file=sys.stderr)
            raise SystemExit(EXIT_WORKSPACE)
        return candidate.resolve()
    try:
        return find_kernel_workspace(Path.cwd())
    except FileNotFoundError as exc:
        if as_json:
            _emit_json({"ok": False, "error": str(exc)})
        else:
            print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(EXIT_WORKSPACE) from None


def _cmd_query_plan(args: argparse.Namespace) -> int:
    """Build the query family for one axis as proposals (no writes outside sidecar)."""
    from patent_intel.kernel_bridge import read_axes
    from patent_intel.retrieval.features import extract_features
    from patent_intel.retrieval.query_plan import QueryPlanBuilder

    workspace = _workspace_or_exit(args.root, as_json=args.json)
    axes = read_axes(workspace)
    axis_key = args.axis if "@" in args.axis else f"{args.axis}@{_active_target(workspace)}"
    info = axes.get(axis_key)
    if info is None:
        message = f"axis {axis_key!r} not in glossary (known: {sorted(axes)})"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_WORKSPACE
    title = str(info.get("title_zh") or info.get("title_en") or "").strip()
    if not title:
        message = f"axis {axis_key!r} has no title to plan from"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_FAIL
    bundle = extract_features([title], axis_id=axis_key, source_tag="glossary-axis")
    plan = QueryPlanBuilder().build(bundle)
    payload = plan.describe()
    payload["axis_title"] = title
    if args.json:
        _emit_json({"ok": True, "plan": payload})
    else:
        print(f"axis {axis_key} — {title}: {len(plan.queries)} proposal queries")
        for q in plan.queries:
            print(f"  {q.query_id} [{q.query_type}] terms={q.terms[:4]}{'…' if len(q.terms) > 4 else ''}")
        for a in plan.annotations:
            print(f"  (annotation) {a['kind']}: {a['statement']}")
        print("proposals only — approve via review before any kernel-side use")
    return EXIT_OK


def _active_target(workspace: Path) -> str:
    from patent_intel.kernel_bridge import read_glossary

    glossary = read_glossary(workspace)
    return str(glossary.get("active_target") or "")


def _cmd_query_validate(args: argparse.Namespace) -> int:
    """Validate a plan JSON file against the record contracts (schema discipline)."""
    import json

    from patent_intel.contracts import QuerySpec

    path = Path(args.plan)
    if not path.is_file():
        _emit_json({"ok": False, "error": f"plan file not found: {path}"}) if args.json else print(
            f"❌ plan file not found: {path}", file=sys.stderr
        )
        return EXIT_USAGE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"❌ invalid JSON: {exc}", file=sys.stderr)
        return EXIT_USAGE
    entries = data.get("queries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        print("❌ plan must be a query list or {queries: [...]}", file=sys.stderr)
        return EXIT_USAGE
    errors: list[str] = []
    valid = 0
    for i, entry in enumerate(entries):
        try:
            QuerySpec.from_dict(entry)
            valid += 1
        except Exception as exc:  # noqa: BLE001 - collect all contract violations
            errors.append(f"query[{i}]: {exc}")
    if args.json:
        _emit_json({"ok": not errors, "valid": valid, "errors": errors})
    else:
        if errors:
            print(f"❌ {len(errors)} invalid query spec(s):")
            for err in errors:
                print(f"  · {err}")
        else:
            print(f"✅ {valid} query spec(s) valid")
    return EXIT_OK if not errors else EXIT_FAIL


# ── recall group (WP-A) ───────────────────────────────────────────────


def _cmd_recall_report(args: argparse.Namespace) -> int:
    """Offline recall diagnostic over the workspace's own corpus (writes sidecar only)."""
    from patent_intel.retrieval.reporting import recall_report
    from patent_intel.workspace import SidecarLayout

    workspace = _workspace_or_exit(args.root, as_json=args.json)
    state_dir = resolve_state_dir(workspace, args.state_dir)
    layout = SidecarLayout(state_dir)
    layout.ensure(workspace=workspace)
    report = recall_report(
        workspace,
        state_dir,
        max_requests=args.max_requests,
        zero_gain_rounds=args.zero_gain_rounds,
    )
    if args.json:
        _emit_json({"ok": True, "report": report})
    else:
        run = report["run"]
        print(f"recall report (offline, corpus={report['corpus_size']} docs)")
        print(f"  queries planned: {report['queries_planned']}, run: {len(run['queries_run'])} ({run['stop_reason']})")
        print(f"  new families discovered: {run['total_new_families']}")
        coverage = run["coverage"]
        if coverage.get("uncovered_axes"):
            print(f"  axes without any hit: {coverage['uncovered_axes']}")
        print(f"  report saved under: {state_dir / 'reports'}")
        print(f"  caveat: {report['caveat'][:100]}…")
    return EXIT_OK


# ── evidence group (WP-D) ─────────────────────────────────────────────


def _features_from_workspace(workspace: Path) -> list[dict[str, object]]:
    """Feature view from glossary axes (deterministic; no LLM involvement)."""
    from patent_intel.kernel_bridge import read_axes
    from patent_intel.retrieval.features import extract_features

    features: list[dict[str, object]] = []
    for axis_id, info in sorted(read_axes(workspace).items()):
        title = str((info or {}).get("title_zh") or (info or {}).get("title_en") or "").strip()
        if not title:
            continue
        bundle = extract_features([title], axis_id=axis_id, source_tag="glossary-axis", approved=True)
        features.extend(f.to_dict() for f in bundle.features)
    return features


def _cmd_evidence_build(args: argparse.Namespace) -> int:
    """Rebuild the evidence projection view from the kernel workspace (sidecar only)."""
    from patent_intel.evidence.coverage_matrix import build_coverage_matrix
    from patent_intel.evidence.graph import EvidenceGraphBuilder, export_projections
    from patent_intel.kernel_bridge import read_candidates
    from patent_intel.workspace import SidecarLayout

    workspace = _workspace_or_exit(args.root, as_json=args.json)
    state_dir = resolve_state_dir(workspace, args.state_dir)
    layout = SidecarLayout(state_dir)
    layout.ensure(workspace=workspace)
    features = _features_from_workspace(workspace)
    projections = EvidenceGraphBuilder(features=features).build_from_workspace(workspace)
    candidates = read_candidates(workspace)
    matrix = build_coverage_matrix(features, candidates, projections)
    export_projections(projections, layout.evidence)
    write_json_atomic(layout.evidence / "coverage_matrix.json", matrix.describe())
    summary = {
        "ok": True,
        "projections": len(projections),
        "features": len(features),
        "coverage_ratio": matrix.coverage_ratio,
        "gaps": matrix.evidence_gaps(),
        "written": [str(layout.evidence / "projections.json"), str(layout.evidence / "coverage_matrix.json")],
    }
    if args.json:
        _emit_json(summary)
    else:
        print(f"evidence view rebuilt: {len(projections)} projections over {len(features)} features")
        print(f"  coverage ratio (supported cells): {matrix.coverage_ratio:.3f}")
        if summary["gaps"]:
            print(f"  features without anchored evidence: {summary['gaps']}")
        print(f"  written to {layout.evidence}")
    return EXIT_OK


# ── advisory group (WP-D) ─────────────────────────────────────────────


def _cmd_advisory_review(args: argparse.Namespace) -> int:
    """List advisory proposals awaiting human review (read-only; sidecar only)."""
    from patent_intel.contracts import AdvisoryProposal, ReviewState
    from patent_intel.workspace import SidecarLayout

    workspace = _workspace_or_exit(args.root, as_json=args.json)
    state_dir = resolve_state_dir(workspace, args.state_dir)
    layout = SidecarLayout(state_dir)
    proposals: list[dict[str, object]] = []
    if layout.advisory.is_dir():
        for path in sorted(layout.advisory.glob("*.json")):
            try:
                proposal = AdvisoryProposal.from_dict(read_json_limited(path))
            except Exception as exc:  # noqa: BLE001 - report unreadable proposals honestly
                proposals.append({"path": path.name, "error": str(exc)})
                continue
            if args.claim and args.claim not in str((proposal.change or {}).get("claim_numbers", "")):
                continue
            proposals.append(
                {
                    "proposal_id": proposal.proposal_id,
                    "change_kind": (proposal.change or {}).get("kind"),
                    "requires_human_review": proposal.requires_human_review,
                    "kernel_gate_ref": proposal.kernel_gate_ref,
                    "evidence_refs": len(proposal.evidence_refs or []),
                    "path": path.name,
                }
            )
    payload = {
        "ok": True,
        "count": len(proposals),
        "proposals": proposals,
        "note": (
            "proposals are advisory only; adoption requires human review and the kernel "
            "draft/revise gates (V038). No proposal is ever applied automatically."
        ),
    }
    if args.json:
        _emit_json(payload)
    else:
        print(f"{len(proposals)} proposal(s) on file (state: {state_dir})")
        for p in proposals:
            if "error" in p:
                print(f"  [unreadable] {p['path']}: {p['error']}")
            else:
                print(f"  {p['proposal_id']} [{p['change_kind']}] gate: {p['kernel_gate_ref']}")
        print("  " + payload["note"][:100] + "…")
    _ = ReviewState  # imported for API symmetry with sidecar review states
    return EXIT_OK


# ── landscape group (WP-E, optional) ──────────────────────────────────


def _cmd_landscape_report(args: argparse.Namespace) -> int:
    """Descriptive landscape statistics over the searched sample (sidecar only)."""
    from patent_intel.kernel_bridge import read_candidates
    from patent_intel.landscape.report import build_landscape_report
    from patent_intel.workspace import SidecarLayout

    workspace = _workspace_or_exit(args.root, as_json=args.json)
    state_dir = resolve_state_dir(workspace, args.state_dir)
    SidecarLayout(state_dir).ensure(workspace=workspace)
    paths = build_landscape_report(read_candidates(workspace), state_dir)
    if args.json:
        _emit_json({"ok": True, **paths})
    else:
        print("landscape report written (descriptive statistics over the searched sample):")
        print(f"  csv:      {paths['csv']}")
        print(f"  markdown: {paths['markdown']}")
        print("  边界: 聚类稀疏/零命中≠技术空白已证实")
    return EXIT_OK


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

    query = sub.add_parser(
        "query",
        help="query planning proposals (WP-A) — plans are sidecar proposals, never kernel writes",
    )
    query_sub = query.add_subparsers(dest="query_command", metavar="<subcommand>", required=True)
    plan = query_sub.add_parser(
        "plan",
        help="build the query family for one glossary axis (single_feature/broad_recall/cross/xd)",
    )
    _add_root_args(plan)
    plan.add_argument("--axis", required=True, metavar="ID", help="axis id, bare (N1) or target-qualified (N1@TGT-0001)")
    plan.set_defaults(func=_cmd_query_plan)
    validate = query_sub.add_parser(
        "validate",
        help="validate a plan JSON file against the record contracts",
    )
    _add_root_args(validate)
    validate.add_argument("--plan", required=True, metavar="FILE", help="plan JSON (list or {queries: [...]})")
    validate.set_defaults(func=_cmd_query_validate)

    recall = sub.add_parser(
        "recall",
        help="offline recall diagnostics (WP-A) — BM25 over the workspace's own corpus",
    )
    recall_sub = recall.add_subparsers(dest="recall_command", metavar="<subcommand>", required=True)
    report = recall_sub.add_parser(
        "report",
        help="coverage + incremental-yield report; writes only to the sidecar reports/ dir",
    )
    _add_root_args(report)
    report.add_argument("--max-requests", type=int, default=20, help="query budget for the diagnostic run")
    report.add_argument("--zero-gain-rounds", type=int, default=3, help="stop after N consecutive zero-yield queries")
    report.set_defaults(func=_cmd_recall_report)

    evidence = sub.add_parser(
        "evidence",
        help="evidence projection views (WP-D) — rebuildable, sidecar-only, read-only on the workspace",
    )
    evidence_sub = evidence.add_subparsers(dest="evidence_command", metavar="<subcommand>", required=True)
    ebuild = evidence_sub.add_parser(
        "build",
        help="rebuild projections + coverage matrix from the kernel workspace into the sidecar",
    )
    _add_root_args(ebuild)
    ebuild.set_defaults(func=_cmd_evidence_build)

    advisory = sub.add_parser(
        "advisory",
        help="claim-amendment proposals (WP-D) — always proposals, never applied automatically",
    )
    advisory_sub = advisory.add_subparsers(dest="advisory_command", metavar="<subcommand>", required=True)
    areview = advisory_sub.add_parser(
        "review",
        help="list advisory proposals awaiting human review (read-only)",
    )
    _add_root_args(areview)
    areview.add_argument("--claim", default=None, help="filter proposals mentioning a claim number")
    areview.set_defaults(func=_cmd_advisory_review)

    landscape = sub.add_parser(
        "landscape",
        help="optional descriptive landscape statistics (WP-E) — searched sample only",
    )
    landscape_sub = landscape.add_subparsers(dest="landscape_command", metavar="<subcommand>", required=True)
    lreport = landscape_sub.add_parser(
        "report",
        help="family-deduplicated applicant/class/region/year statistics (CSV + Markdown)",
    )
    _add_root_args(lreport)
    lreport.set_defaults(func=_cmd_landscape_report)

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
