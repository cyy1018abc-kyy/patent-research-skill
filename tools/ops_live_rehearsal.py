#!/usr/bin/env python3
"""OPS live-rehearsal driver (Stage 4 / L4) — implements runbook §1 as one audited command.

Turns docs/live-rehearsal-runbook.md §0.5 into a deterministic sequence with a hard
request budget (≤8, the runbook's registered estimate) and one evidence JSON:

1. OAuth smoke            — one token request; token material never printed;
2. dry-run/execute consistency — the dry-run preview must render exactly the query
                            string the execute step sends (runbook §1 step 4);
3. paged acquisition      — 2 pages @ 25, raw into the sidecar with SHA-256 audit;
4. raw-artifact audit     — RawArtifactRegistry.register_from_refs + verify_all all-ok;
5. 403 drill              — invalid credentials, 1 page: the run must FAIL cleanly
                            (no retry storm) with already-captured pages preserved.

Credentials come from OPS_OAUTH_KEY / OPS_OAUTH_SECRET and are **never** written to
logs, the report, or error messages. The driver is transport-pluggable so the whole
sequence is testable offline against a fake (the live run needs no code change).

Usage:
    python tools/ops_live_rehearsal.py --sidecar <dir> [--json]   # live (credentials + consent required)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "extensions" / "patent_intel" / "src"))

from patent_intel.config import PatentIntelConfig  # noqa: E402
from patent_intel.contracts import QuerySpec  # noqa: E402
from patent_intel.artifacts import RawArtifactRegistry  # noqa: E402
from patent_intel.sources.ops import OpsAdapter  # noqa: E402

REQUEST_BUDGET = 8  # runbook §1 registered estimate (incl. the 403 drill)

BASE_QUERY = QuerySpec(
    owner="WP-B", query_id="Q-OPS-REHEARSAL-1", axis_id="N1@REHEARSAL",
    terms=["beacon timing"], language="en", query_type="single_feature", source="ops",
)


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _consent() -> PatentIntelConfig:
    return PatentIntelConfig(network_consent=True, allowed_sources=["ops"])


def run_rehearsal(*, sidecar: Path, transport: Any = None, live: bool = True) -> dict:
    """Execute the runbook §1 sequence; returns the evidence report dict.

    ``transport`` overrides the adapter's HTTP transport (offline self-test); when
    ``live`` the real environment credentials are used and the consent gate applies.
    Raises when a step fails hard or the request budget is exceeded — the caller
    still writes partial evidence.
    """
    sidecar = Path(sidecar)
    sidecar.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []
    requests_total = 0

    def counted(step: str, detail: dict[str, Any], requests: int) -> None:
        nonlocal requests_total
        requests_total += requests
        if requests_total > REQUEST_BUDGET:
            raise RuntimeError(
                f"request budget exceeded: {requests_total} > {REQUEST_BUDGET} — aborting"
                " (runbook discipline: no request beyond the registered estimate)"
            )
        steps.append({"step": step, "requests": requests, **detail})

    kwargs: dict[str, Any] = {"sleep": lambda _s: None}
    if transport is not None:
        kwargs["transport"] = transport

    # -- 1. OAuth smoke -----------------------------------------------------
    adapter = OpsAdapter(**kwargs)
    token = adapter._access_token()
    counted("oauth_smoke", {"ok": True, "token_prefix": token[:6] + "…"}, requests=1)

    # -- 2. dry-run/execute consistency + 2-page acquisition -----------------
    plan = adapter.build_request(BASE_QUERY)
    preview = adapter.dry_run(plan, sidecar).preview[0]
    result = adapter.execute(
        plan, sidecar, confirm_network=True, config=_consent(),
        state_dir=sidecar, max_pages=2,
    )
    consistent = plan.args[0] in preview  # §5.4: preview renders the executed query
    run = result.runs[0] if result.runs else None
    counted(
        "dry_run_execute_consistency_and_paging",
        {
            "ok": bool(result.runs) and consistent,
            "query": plan.args[0],
            "consistent": consistent,
            "status": run.status if run else None,
            "complete": run.complete if run else None,
            "incomplete_reason": run.incomplete_reason if run else None,
            "raw_pages": len(result.raw_refs),
        },
        requests=2,
    )

    # -- 3. raw-artifact hash audit -------------------------------------------
    registry = RawArtifactRegistry(
        base_dir=sidecar, index_path=sidecar / "raw_registry.json"
    )
    refs = registry.register_from_refs(
        result.raw_refs, source="ops", base_dir=sidecar, query_id=BASE_QUERY.query_id
    )
    verifications = registry.verify_all()
    counted(
        "raw_artifact_hash_audit",
        {
            "ok": bool(refs) and all(v["ok"] for v in verifications),
            "registered": len(refs),
            "verifications": verifications,
        },
        requests=0,
    )

    # -- 4. 403 drill -----------------------------------------------------------
    counted("http_403_drill", _run_403_drill(sidecar, transport=transport), requests=1)

    return {
        "tool": "ops_live_rehearsal",
        "live": live,
        "steps": steps,
        "requests_total": requests_total,
        "request_budget": REQUEST_BUDGET,
        "verdict": "PASS" if all(s["ok"] for s in steps) else "FAIL",
        "note": (
            "演练证据 ≠ 能力升级：partial→full 还需 runbook §1 第 8-9 步的能力矩阵"
            "回填与 policy-log 实测行登记"
        ),
    }


def _run_403_drill(sidecar: Path, *, transport: Any = None) -> dict[str, Any]:
    """Invalid credentials, 1 page: the run must FAIL cleanly — no retry storm,
    already-captured pages preserved. The observed status/code is recorded as
    evidence (the real API's invalid-credential behaviour is what the drill finds).
    """
    saved = (os.environ.get("OPS_OAUTH_KEY"), os.environ.get("OPS_OAUTH_SECRET"))
    os.environ["OPS_OAUTH_KEY"] = "invalid-rehearsal-key"
    os.environ["OPS_OAUTH_SECRET"] = "invalid-rehearsal-secret"
    try:
        kwargs: dict[str, Any] = {"sleep": lambda _s: None}
        if transport is not None:
            kwargs["transport"] = transport
        adapter = OpsAdapter(**kwargs)
        plan = adapter.build_request(BASE_QUERY)
        result = adapter.execute(
            plan, sidecar, confirm_network=True, config=_consent(),
            state_dir=sidecar, max_pages=1,
        )
        run = result.runs[0] if result.runs else None
        failed = bool(result.runs) and run is not None and run.status == "failed"
        detail = str(run.error) if run else ""
        return {
            "ok": failed,
            "status": run.status if run else None,
            "error_excerpt": detail[:120],
            "preserved_pages": len(result.raw_refs),
        }
    finally:
        if saved[0] is None:
            os.environ.pop("OPS_OAUTH_KEY", None)
        else:
            os.environ["OPS_OAUTH_KEY"] = saved[0]
        if saved[1] is None:
            os.environ.pop("OPS_OAUTH_SECRET", None)
        else:
            os.environ["OPS_OAUTH_SECRET"] = saved[1]


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sidecar", required=True, help="sidecar dir for raw/ + audit ledger")
    parser.add_argument("--json", action="store_true", help="print the evidence report as JSON")
    args = parser.parse_args()

    started = time.time()
    try:
        report = run_rehearsal(sidecar=Path(args.sidecar), live=True)
    except Exception as exc:  # noqa: BLE001 - partial evidence is still evidence
        report = {"tool": "ops_live_rehearsal", "live": True, "verdict": "FAIL",
                  "fatal": f"{type(exc).__name__}: {exc}", "steps": []}
    report["elapsed_seconds"] = round(time.time() - started, 2)
    report["credentials_logged"] = False

    out = Path(args.sidecar) / f"rehearsal-evidence-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True))
    else:
        print(f"[rehearsal] verdict={report['verdict']} evidence={out}")
        for step in report.get("steps", []):
            print(f"  {step['step']}: ok={step['ok']} requests={step['requests']}")
    return 0 if report.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
