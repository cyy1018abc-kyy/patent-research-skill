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
#: alias of the kernel convention "2 = workspace/usage problem" (bad input files,
#: malformed JSON…) — defined once here so commands never reach for an undefined name
EXIT_USAGE = EXIT_WORKSPACE


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
    dates_by_family = None
    if args.dates_file:
        dates_path = Path(args.dates_file)
        if not dates_path.is_file():
            message = f"dates file not found: {dates_path}"
            if args.json:
                _emit_json({"ok": False, "error": message})
            else:
                print(f"❌ {message}", file=sys.stderr)
            return EXIT_USAGE
        try:
            dates_by_family = json.loads(dates_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            message = f"invalid JSON in {dates_path}: {exc}"
            if args.json:
                _emit_json({"ok": False, "error": message})
            else:
                print(f"❌ {message}", file=sys.stderr)
            return EXIT_USAGE
        if not isinstance(dates_by_family, dict):
            message = f"dates file must be a JSON object mapping family_id → date entry: {dates_path}"
            if args.json:
                _emit_json({"ok": False, "error": message})
            else:
                print(f"❌ {message}", file=sys.stderr)
            return EXIT_USAGE
    report = recall_report(
        workspace,
        state_dir,
        max_requests=args.max_requests,
        zero_gain_rounds=args.zero_gain_rounds,
        enable_dense=getattr(args, "dense", False),
        dates_by_family=dates_by_family,
        target_filing_date=args.target_filing_date,
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


# ── contribution group (41A-2) ────────────────────────────────────────


def _load_controller_outcomes(payload: object, source: Path) -> tuple[list[str], list[Any]]:
    """Rebuild RunOutcome records from a dumped controller report (41A-2 CLI input).

    Accepts ``{"outcomes": [...]}`` (+ optional ``queries_run``) or a wrapper
    ``{"run": {...}}`` of the same shape. Summarized reports (hits/new_families
    as *counts*, not lists) are rejected honestly — they cannot power
    per-query contribution accounting.
    """
    from patent_intel.retrieval.controller import ControllerReport, RunOutcome

    if isinstance(payload, dict) and isinstance(payload.get("run"), dict):
        payload = payload["run"]
    if not isinstance(payload, dict):
        raise ValueError(f"{source}: expected a JSON object with an 'outcomes' list")
    raw_outcomes = payload.get("outcomes")
    if not isinstance(raw_outcomes, list):
        raise ValueError(f"{source}: missing 'outcomes' list")
    queries_run = payload.get("queries_run") or []
    if not isinstance(queries_run, list):
        raise ValueError(f"{source}: 'queries_run' must be a list when present")

    outcomes: list[Any] = []
    for index, entry in enumerate(raw_outcomes):
        if not isinstance(entry, dict):
            raise ValueError(f"{source}: outcome[{index}] is not an object")
        for field in ("hits", "families"):
            value = entry.get(field, [])
            if not isinstance(value, list):
                raise ValueError(
                    f"{source}: outcome[{index}].{field} must be a list of ids — "
                    "summarized reports (counts) cannot power contribution accounting; "
                    "dump the full controller report instead"
                )
        outcomes.append(
            RunOutcome(
                query_id=str(entry.get("query_id") or f"outcome-{index}"),
                hits=[str(h) for h in entry.get("hits") or []],
                families=[str(f) for f in entry.get("families") or []],
                new_families=[str(f) for f in entry.get("new_families") or []],
                cost=float(entry.get("cost") or 0.0),
                error=entry.get("error"),
                family_basis=str(entry.get("family_basis") or "reported"),
            )
        )
    return [str(q) for q in queries_run], outcomes


def _cmd_contribution_report(args: argparse.Namespace) -> int:
    """Per-query contribution ledger from a dumped controller report (read-only)."""
    from patent_intel.retrieval.contribution import ContributionReport
    from patent_intel.retrieval.controller import ControllerReport

    path = Path(args.report)
    if not path.is_file():
        message = f"report file not found: {path}"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_USAGE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        message = f"invalid JSON in {path}: {exc}"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_USAGE
    try:
        queries_run, outcomes = _load_controller_outcomes(payload, path)
        ledger = ContributionReport.from_report(
            ControllerReport(queries_run=queries_run, outcomes=outcomes)
        )
    except Exception as exc:  # noqa: BLE001 - contract violations reported, never crash
        message = f"{type(exc).__name__}: {exc}"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_USAGE

    described = ledger.describe()
    if args.json:
        _emit_json({"ok": True, "contribution": described})
    else:
        rows = described.get("queries") or []
        duplicates = described.get("duplicates") or []
        print(f"contribution ledger over {len(rows)} query row(s) from {path.name}")
        if duplicates:
            print(f"  duplicate queries (clean run, zero new families/documents): {len(duplicates)}")
        print(f"  problems: {len(described.get('problems') or [])}")
    return EXIT_OK


# ── bench group (41A-5) ───────────────────────────────────────────────


def _cmd_bench_run(args: argparse.Namespace) -> int:
    """First-class batch retrieval over a frozen corpus snapshot (offline)."""
    # usage problems are reported before the dependency check — a wrong path
    # should never be masked by a missing optional package
    from patent_intel.retrieval.batch import BatchConfig, run_batch
    from patent_intel.retrieval.lexical import BM25Index, CorpusDoc

    corpus_dir = Path(args.corpus_dir)
    topics_path = Path(args.topics)
    if not corpus_dir.is_dir():
        message = f"corpus dir not found: {corpus_dir}"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_USAGE
    if not topics_path.is_file():
        message = f"topics manifest not found: {topics_path}"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_USAGE
    if args.limit and args.split != "test":
        message = "--limit is for test-split smoke runs only"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_USAGE

    try:
        manifest = json.loads(topics_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        message = f"invalid JSON in {topics_path}: {exc}"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_USAGE
    topics = [t for t in manifest.get("topics", []) if t.get("split") == args.split]
    if args.limit:
        topics = topics[: args.limit]

    try:
        import pyarrow.parquet as pq
    except ImportError:
        message = "pyarrow required for parquet corpus loading (pip install pyarrow)"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"[FATAL] {message}", file=sys.stderr)
        return EXIT_DEPENDENCY

    def _parquet_column(table_path: Path, columns: list[str]) -> dict:
        table = pq.read_table(table_path, columns=columns)
        data = table.to_pydict()
        del table
        return data

    docs_table = _parquet_column(
        corpus_dir / "corpus.parquet", ["relevant_id", "title_en", "abstract_en", "claims_text"]
    )
    docs = [
        CorpusDoc(
            doc_id=docs_table["relevant_id"][i],
            text=" ".join(
                x
                for x in (
                    docs_table["title_en"][i],
                    docs_table["abstract_en"][i],
                    docs_table["claims_text"][i],
                )
                if x
            ),
            family_id=docs_table["relevant_id"][i],
        )
        for i in range(len(docs_table["relevant_id"]))
    ]
    index = BM25Index(docs, k1=args.k1, b=args.b)
    queries_table = _parquet_column(
        corpus_dir / "queries.parquet", ["query_id", "title_en", "abstract_en", "claims_text"]
    )
    queries_by_id = {
        queries_table["query_id"][i]: {
            "title_en": queries_table["title_en"][i],
            "abstract_en": queries_table["abstract_en"][i],
            "claims_text": queries_table["claims_text"][i],
        }
        for i in range(len(queries_table["query_id"]))
    }
    del docs_table, queries_table, docs

    import time as _time

    started = _time.time()
    engine_params = {"k1": args.k1, "b": args.b, "k_per_request": args.k}
    result = run_batch(
        topics,
        queries_by_id,
        index,
        BatchConfig(
            side=args.side,
            k_per_request=args.k,
            budget_requests=args.budget,
            engine_params=engine_params,
            # 41A-5: benchmark-mode auto-approval is an explicit flag, never a silent offset
            approve_queries=args.side == "extension" and args.approve,
        ),
        batch_mode=args.batch_mode or f"cli:bench-run:{args.side}",
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = dict(result.meta)
    meta.update(
        {
            "snapshot_sha256": {
                p.name: _sha256_file(corpus_dir / p.name) for p in sorted(corpus_dir.glob("*.parquet"))
            },
            "manifest_sha256": _sha256_file(topics_path),
            "split": args.split,
            "elapsed_seconds": round(_time.time() - started, 1),
            "network_requests": 0,
        }
    )
    rows_path = out_dir / f"{args.side}.jsonl"
    with open(rows_path, "w", encoding="utf-8", newline="\n") as fh:
        for row in result.rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    meta_path = out_dir / f"meta-{args.side}.json"
    with open(meta_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    payload = {
        "ok": True,
        "rows": len(result.rows),
        "requests_total": result.requests_total,
        "topics_run": len(topics),
        "batch_mode": meta["batch_mode"],
        "rows_file": str(rows_path),
        "meta_file": str(meta_path),
    }
    if args.json:
        _emit_json(payload)
    else:
        print(f"bench run [{args.side}]: {len(result.rows)} rows, {result.requests_total} requests, {len(topics)} topics")
        print(f"  rows: {rows_path}")
        print(f"  meta: {meta_path}")
    return EXIT_OK


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


# ── doctor sources (41D-2) ────────────────────────────────────────────


def _cmd_doctor_sources(args: argparse.Namespace) -> int:
    """Source availability diagnostics (default offline; no implicit network)."""
    from patent_intel.sources.diagnostics import diagnose_sources

    workspace: Path | None = None
    if args.root:
        workspace = Path(args.root).expanduser()
    try:
        state_dir = resolve_state_dir(workspace, args.state_dir)
        config = load_config(state_dir)
    except Exception as exc:  # noqa: BLE001 - a missing/unreadable context is the finding
        message = f"{type(exc).__name__}: {exc}"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_USAGE

    try:
        report = diagnose_sources(
            config,
            only=list(args.only) if args.only else None,
            timeout_sec=args.timeout,
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics contract violations reported honestly
        message = f"{type(exc).__name__}: {exc}"
        if args.json:
            _emit_json({"ok": False, "error": message})
        else:
            print(f"❌ {message}", file=sys.stderr)
        return EXIT_USAGE

    described = report.describe()
    blocked = described["status_counts"].get("blocked", 0)
    if args.json:
        _emit_json({"ok": blocked == 0, "diagnostics": described})
    else:
        print(f"source diagnostics (offline; state dir: {state_dir})")
        for entry in described["sources"]:
            note = f" — {entry['reason']}" if entry.get("reason") else ""
            print(f"  [{entry['status']:>7}] {entry['source']}{note}")
        counts = described["status_counts"]
        print(
            "result: "
            + ", ".join(f"{name}={counts[name]}" for name in sorted(counts) if counts[name])
        )
    return EXIT_OK if blocked == 0 else EXIT_FAIL


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
    doctor_sub = doctor.add_subparsers(dest="doctor_command", metavar="<subcommand>")
    dsrc = doctor_sub.add_parser(
        "sources",
        help="per-source availability diagnostics (consent/credentials/planned; default offline)",
    )
    _add_root_args(dsrc)
    dsrc.add_argument(
        "--only", nargs="*", metavar="ID", help="restrict to these source ids (default: every registered source)"
    )
    dsrc.add_argument("--timeout", type=int, default=10, metavar="SEC", help="timeout reported to probes (probes stay offline unless a transport is injected)")
    dsrc.set_defaults(func=_cmd_doctor_sources)

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
    report.add_argument(
        "--dense", action="store_true",
        help="add the dense channel to per-query RRF fusion (requires the 'dense' extra; "
             "failure degrades to lexical-only with the reason recorded)",
    )
    report.add_argument(
        "--dates-file", default=None, metavar="FILE",
        help="JSON mapping family_id → publication/priority date(s); attaches the advisory "
             "41C-1 time view to the report (never changes recall or ranking)",
    )
    report.add_argument(
        "--target-filing-date", default=None, metavar="YYYY-MM-DD",
        help="target filing date for the time view's filter_publication_after_target suggestion",
    )
    report.set_defaults(func=_cmd_recall_report)

    contribution = sub.add_parser(
        "contribution",
        help="per-query contribution accounting (41A-2) — which queries earn their budget",
    )
    contribution_sub = contribution.add_subparsers(dest="contribution_command", metavar="<subcommand>", required=True)
    creport = contribution_sub.add_parser(
        "report",
        help="contribution ledger from a dumped controller report (read-only)",
    )
    _add_root_args(creport)
    creport.add_argument(
        "--report", required=True, metavar="FILE",
        help="JSON with a full outcomes list ({outcomes: [...], queries_run: [...]} — or the "
             "same under a 'run' key); summarized reports (counts, not id lists) are rejected",
    )
    creport.set_defaults(func=_cmd_contribution_report)

    bench = sub.add_parser(
        "bench",
        help="first-class batch retrieval over a frozen corpus snapshot (41A-5, offline)",
    )
    bench_sub = bench.add_subparsers(dest="bench_command", metavar="<subcommand>", required=True)
    brun = bench_sub.add_parser(
        "run",
        help="run one side (baseline|extension) over a topic manifest + parquet corpus",
    )
    _add_root_args(brun)
    brun.add_argument("--corpus-dir", required=True, metavar="DIR", help="frozen corpus snapshot dir (corpus.parquet + queries.parquet)")
    brun.add_argument("--topics", required=True, metavar="FILE", help="topics manifest JSON ({topics: [...]})")
    brun.add_argument("--split", default="test", choices=("train", "val", "test"))
    brun.add_argument("--side", required=True, choices=("baseline", "extension"))
    brun.add_argument("--k", type=int, default=200, help="k per request (default 200)")
    brun.add_argument("--budget", type=int, default=3, help="per-topic request budget for the extension side (default 3)")
    brun.add_argument("--k1", type=float, default=1.5, help="BM25 k1 (default 1.5)")
    brun.add_argument("--b", type=float, default=0.75, help="BM25 b (default 0.75)")
    brun.add_argument("--limit", type=int, default=0, help="only run the first N topics (test-split smoke, not an evaluation)")
    brun.add_argument(
        "--approve", action="store_true",
        help="benchmark-mode auto-approval for extension plans (41A-5 explicit flag; "
             "omitting it yields zero rows instead of bypassing the approval gate)",
    )
    brun.add_argument("--batch-mode", default=None, metavar="LABEL", help="label stamped into the meta (default: cli:bench-run:<side>)")
    brun.add_argument("--out-dir", required=True, metavar="DIR", help="output dir for <side>.jsonl + meta-<side>.json")
    brun.set_defaults(func=_cmd_bench_run)

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
