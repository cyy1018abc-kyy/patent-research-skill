#!/usr/bin/env python3
"""Read-only hard-negative diagnostics entry (roadmap 41A-4) — library shell.

Thin CLI over ``patent_intel.advisory.confidence``: takes a JSON signals file,
prints the deterministic diagnosis JSON to stdout. No network, no writes
(unless ``--output`` is given), no gold access — the caller supplies every
input; the tool never judges relevance.

Input JSON (UTF-8)::

    {
      "ranked": [["FAM-10001", 12.5], ["FAM-10002", 9.0]],
      "query_terms": ["frame", "sync"],
      "candidate_terms": {"FAM-10001": ["frame"], "FAM-10002": ["sync", "frame"]},
      "gold": ["FAM-10002"],
      "params": {"n": 10, "margin_threshold": 0.05, "dominance_ratio": 0.5}
    }

Usage::

    python benchmarks/retrieval/diagnose_negatives.py --input signals.json
    python benchmarks/retrieval/diagnose_negatives.py --input signals.json --output diag.json

Exit codes: 0 = diagnosis produced; 2 = contract violation (bad JSON, missing
coverage, duplicate ids — see ``ConfidenceError``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
sys.path.insert(0, str(REPO_ROOT / "extensions" / "patent_intel" / "src"))

from patent_intel.advisory.confidence import ConfidenceError, diagnose_candidates


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _dump_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hard-negative / overconfidence diagnostics (read-only)")
    parser.add_argument("--input", required=True, help="signals JSON file (see module docstring)")
    parser.add_argument("--output", help="optional path to also write the diagnosis JSON")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        params = payload.get("params") or {}
        diagnosis = diagnose_candidates(
            [(str(fid), float(score)) for fid, score in payload["ranked"]],
            query_terms=payload.get("query_terms") or [],
            candidate_terms=payload.get("candidate_terms") or {},
            gold=payload.get("gold") or [],
            n=int(params.get("n", 10)),
            margin_threshold=float(params.get("margin_threshold", 0.05)),
            dominance_ratio=float(params.get("dominance_ratio", 0.5)),
        )
    except (ConfidenceError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[diagnose-negatives] contract violation: {exc}", file=sys.stderr)
        return 2

    rendered = _dump_json(diagnosis.describe())
    sys.stdout.write(rendered)
    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(rendered)
    return 0


if __name__ == "__main__":
    _pin_utf8_stdio()
    raise SystemExit(main())
