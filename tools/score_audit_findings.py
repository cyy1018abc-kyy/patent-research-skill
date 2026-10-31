#!/usr/bin/env python3
"""Score patent-audit findings.json against a benchmark case's ground truth.

This is the audit-mode counterpart of score_benchmark.py: it maps the three-verdict
findings of a patent-audit run (or the deterministic gold findings converted from
ground_truth.yaml) onto the case's gold "element <-> prior art" disclosures and
reports four metrics:

- mapping_coverage   — gold disclosures covered by a confirmed/needs_validation lead
- mapping_precision  — confirmed findings that match a gold disclosure
- evidence_integrity — confirmed findings whose every quote is verbatim at its locator
- verdict_discipline — findings.json passes the three-verdict contract validator

The gold self-check converts ground_truth.yaml into findings.json deterministically
and scores it; with --gate perfect it must reach 1.0 on every metric (the CI gate).
Degenerate variants (locator drift, false confirmations, dropped disclosures) must
score below the gate — tests/test_audit_benchmark.py locks that.

Usage:
    python tools/score_audit_findings.py --case benchmarks/cases/bm01-timesync \
        --findings run/findings.json [--json]
    python tools/score_audit_findings.py --case benchmarks/cases/bm01-timesync \
        --gold-selfcheck [--emit-gold out.json] [--gate perfect] [--json]

Exit codes: 0 = pass (or gate met), 1 = gate unmet / scoring failure, 2 = usage error.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402  (repo-standard dependency, already required by score_benchmark)

WEIGHTS = {
    "mapping_coverage": 0.35,
    "mapping_precision": 0.35,
    "evidence_integrity": 0.20,
    "verdict_discipline": 0.10,
}
FULL_STATUSES = {"full", "disclosed"}


def _pin_utf8_stdio() -> None:
    """Pin stdio to UTF-8 so cp1252 consoles cannot corrupt CJK diagnostics."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError, AttributeError):
            pass


def _load_findings_validator():
    spec = importlib.util.spec_from_file_location(
        "audit_validate_findings", ROOT / "audit" / "scripts" / "validate_findings.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VF = _load_findings_validator()


def load_ground_truth(case_dir: Path) -> dict:
    path = case_dir / "ground_truth.yaml"
    if not path.is_file():
        raise SystemExit(f"ground truth not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def gold_disclosures(ground_truth: dict) -> list[dict]:
    """Flatten per-candidate feature disclosures into gold mapping entries."""
    entries = []
    for _pid, candidate in (ground_truth.get("candidates") or {}).items():
        role = candidate.get("role")
        if role == "excluded" or role is None:
            continue
        novelty = candidate.get("novelty_check")
        for feature, disclosure in (candidate.get("disclosure") or {}).items():
            status = disclosure.get("status")
            if status in (None, "absent"):
                continue
            entries.append(
                {
                    "feature": feature,
                    "doc_number": candidate.get("doc_number"),
                    "status": status,
                    "ref": disclosure.get("ref"),
                    "locator": disclosure.get("locator"),
                    "quote": disclosure.get("quote", ""),
                    "note": disclosure.get("note", ""),
                    "novelty_full": novelty == "full",
                }
            )
    return entries


def gold_findings_document(ground_truth: dict) -> list[dict]:
    """Deterministically convert gold disclosures into a valid findings.json document."""
    records = []
    for entry in gold_disclosures(ground_truth):
        feature = entry["feature"]
        doc = entry["doc_number"]
        extent = "full" if entry["status"] in FULL_STATUSES else "partial"
        category = "X" if entry["novelty_full"] else "Y"
        feature_text = (ground_truth.get("features") or {}).get(feature, {}).get("statement", "")
        trace = [
            {
                "kind": "element",
                "ref": f"claims-map.md#{feature}",
                "description": feature_text or f"要素 {feature}",
            }
        ]
        if entry["ref"] and entry["locator"]:
            trace.append(
                {
                    "kind": "disclosure",
                    "ref": f"{entry['ref']}#{entry['locator']}",
                    "description": entry["note"] or "对比文件披露段落",
                }
            )
        record = {
            "verdict": "confirmed",
            "fingerprint": f"MAP:{feature}:{doc}",
            "title": f"{feature} 披露于 {doc} {entry.get('locator', '')}".strip(),
            "description": entry["note"] or f"{feature} 与 {doc} 的披露映射（gold 真值）。",
            "element": f"claims-map.md#{feature}",
            "trace": trace,
            "evidence": [
                {
                    "ref": entry["ref"],
                    "locator": entry["locator"],
                    "quote": entry["quote"],
                    "description": entry["note"] or "gold 真值引文",
                }
            ],
            "mapping_rationale": entry["note"] or f"{feature} 与 {doc} 的披露对应。",
            "disclosure_extent": extent,
            "distinctions": [],
            "impact": {
                "category": category,
                "reason": (
                    "单篇完整披露全部要素，毁新颖"
                    if entry["novelty_full"]
                    else "部分披露关键手段，需组合影响创造性"
                ),
            },
            "independent_review": {"status": "verified", "reviewer": "gold-selfcheck"},
            "confidence": {"score": "high", "reason": "gold 真值引文与定位"},
        }
        if entry["novelty_full"]:
            record["element_coverage"] = {
                "elements": sorted((ground_truth.get("features") or {}).keys()),
                "all_elements": True,
            }
        records.append(record)
    records.sort(key=lambda r: r["fingerprint"])
    return records


def _element_token(finding: dict) -> str:
    element = finding.get("element", "")
    return element.rsplit("#", 1)[-1] if isinstance(element, str) else ""


def _doc_and_locator(finding: dict) -> tuple[str, str]:
    evidence = finding.get("evidence") or []
    for item in evidence:
        if isinstance(item, dict) and isinstance(item.get("ref"), str):
            doc = PurePosixPath(item["ref"].partition("#")[0]).stem
            return doc, item.get("locator", "")
    return "", ""


def score(case_dir: Path, findings: list, ground_truth: dict) -> dict:
    """Compute the four audit metrics for a findings document."""
    gold = gold_disclosures(ground_truth)
    gold_keys = {(e["feature"], e["doc_number"], e["locator"]) for e in gold}

    confirmed = [f for f in findings if isinstance(f, dict) and f.get("verdict") == "confirmed"]
    leads = [
        f
        for f in findings
        if isinstance(f, dict) and f.get("verdict") in ("confirmed", "needs_validation")
    ]

    confirmed_keys = set()
    for finding in confirmed:
        key = (_element_token(finding), *_doc_and_locator(finding))
        confirmed_keys.add(key)
    covered_keys = set()
    for finding in leads:
        covered_keys.add((_element_token(finding), *_doc_and_locator(finding)))

    coverage = (len(covered_keys & gold_keys) / len(gold_keys)) if gold_keys else 1.0
    precision = (len(confirmed_keys & gold_keys) / len(confirmed)) if confirmed else 1.0

    problems = VF.Problems()
    VF.walk_limits(findings, problems)
    VF.validate_document(findings, problems)
    workspace = case_dir / "workspace"
    evidence_problems: dict[str, list[str]] = {}
    if workspace.is_dir():
        per_finding = []
        for index, finding in enumerate(confirmed):
            local = VF.Problems()
            VF.verify_evidence_against_workspace([finding], workspace, local)
            per_finding.extend(local.items)
            fingerprint = finding.get("fingerprint", f"$[{index}]")
            evidence_problems[fingerprint] = local.items
        problems.items.extend(item for item in per_finding if not problems.items)
    discipline = 1.0 if not problems.items else 0.0
    integrity = (
        (len(confirmed) - len([fp for fp, items in evidence_problems.items() if items]))
        / len(confirmed)
        if confirmed
        else 1.0
    )

    metrics = {
        "mapping_coverage": round(coverage, 6),
        "mapping_precision": round(precision, 6),
        "evidence_integrity": round(max(0.0, integrity), 6),
        "verdict_discipline": discipline,
    }
    overall = sum(WEIGHTS[k] * v for k, v in metrics.items())
    missed = sorted(f"{k[0]}@{k[1]}#{k[2]}" for k in gold_keys - covered_keys)
    false_positives = sorted(f"{k[0]}@{k[1]}#{k[2]}" for k in confirmed_keys - gold_keys)
    return {
        "metrics": metrics,
        "overall": round(overall, 6),
        "gold_disclosures": len(gold_keys),
        "confirmed": len(confirmed),
        "missed_gold": missed,
        "false_positives": false_positives,
        "validation_errors": problems.items[:20],
    }


def main(argv: list[str] | None = None) -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Score patent-audit findings.json against a benchmark case's ground truth."
    )
    parser.add_argument("--case", type=Path, required=True, help="benchmark case directory")
    parser.add_argument("--findings", type=Path, help="findings.json to score")
    parser.add_argument(
        "--gold-selfcheck",
        action="store_true",
        help="convert ground_truth.yaml to gold findings and score them",
    )
    parser.add_argument("--emit-gold", type=Path, help="write the converted gold findings here")
    parser.add_argument(
        "--gate", choices=("perfect",), help="require every metric to reach 1.0"
    )
    parser.add_argument("--json", action="store_true", help="emit a single JSON document")
    args = parser.parse_args(argv)

    if not args.case.is_dir():
        print(f"case directory not found: {args.case}", file=sys.stderr)
        return 2
    if bool(args.findings) == bool(args.gold_selfcheck):
        print("choose exactly one of --findings / --gold-selfcheck", file=sys.stderr)
        return 2

    ground_truth = load_ground_truth(args.case)
    if args.gold_selfcheck:
        document = gold_findings_document(ground_truth)
        if args.emit_gold:
            args.emit_gold.parent.mkdir(parents=True, exist_ok=True)
            args.emit_gold.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        findings = document
        source = "gold-selfcheck"
    else:
        if not args.findings.is_file():
            print(f"findings file not found: {args.findings}", file=sys.stderr)
            return 2
        try:
            findings = json.loads(args.findings.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"failed to read findings: {error}", file=sys.stderr)
            return 2
        if not isinstance(findings, list):
            print("findings document must be a top-level array", file=sys.stderr)
            return 2
        source = str(args.findings)

    result = score(args.case, findings, ground_truth)
    result["case"] = args.case.name
    result["source"] = source
    gate_met = all(v == 1.0 for v in result["metrics"].values())
    result["gate_perfect_met"] = gate_met

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"case: {result['case']}  source: {source}")
        for name, value in result["metrics"].items():
            print(f"  {name}: {value:.3f}")
        print(f"  overall: {result['overall']:.3f}")
        if result["missed_gold"]:
            print(f"  missed gold: {', '.join(result['missed_gold'])}")
        if result["false_positives"]:
            print(f"  false positives: {', '.join(result['false_positives'])}")
        if result["validation_errors"]:
            print(f"  validation errors: {len(result['validation_errors'])}+ (use --json)")
        if args.gate:
            print(f"gate perfect: {'MET' if gate_met else 'UNMET'}")
    if args.gate and not gate_met:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
