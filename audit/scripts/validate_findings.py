#!/usr/bin/env python3
"""Validate a patent-audit findings.json document against the three-verdict contract.

Derived from Cloudflare security-audit-skill's validate-findings.cjs (MIT License,
Copyright (c) 2025-2026 Cloudflare, Inc.), re-implemented in Python with the
field contracts rewritten for the patent-search domain. No code is vendored.

Contract: audit/references/04-findings-contract.md + audit/findings-schema.json.

Usage:
    python validate_findings.py <findings.json> [--workspace <root>] [--json]

Exit codes: 0 = pass, 1 = validation failure, 2 = usage/environment error.
Checks are structural plus (with --workspace) evidence integrity: every evidence
``ref`` must exist under the workspace root and its ``quote`` must appear
verbatim inside the paragraph addressed by ``locator``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path, PurePosixPath

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

LIMITS = {
    "input_bytes": 5 * 1024 * 1024,
    "findings": 1000,
    "nesting_depth": 64,
    "errors": 100,
}

FINGERPRINT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
VERDICTS = ("confirmed", "needs_validation", "rejected")
TRACE_KINDS = ("element", "disclosure", "effect")
DISCLOSURE_EXTENTS = ("full", "partial")
IMPACT_CATEGORIES = ("X", "Y", "A")
CONFIDENCE_SCORES = ("low", "medium", "high")
CONDITION_KINDS = (
    "claim_interpretation",
    "priority_date",
    "family_status",
    "translation",
    "document_availability",
    "search_scope",
)

COMMON_FIELDS = ("verdict", "fingerprint", "title", "description", "element", "trace", "evidence")
CONFIRMED_FIELDS = COMMON_FIELDS + (
    "mapping_rationale",
    "disclosure_extent",
    "distinctions",
    "impact",
    "independent_review",
    "confidence",
)
CONFIRMED_OPTIONAL = ("element_coverage", "conditions")
NEEDS_VALIDATION_FIELDS = COMMON_FIELDS + ("claimed_rationale", "blockers", "validation_plan")
REJECTED_FIELDS = COMMON_FIELDS + ("claimed_rationale", "refutation")

WINDOWS_RESERVED = re.compile(
    r"^(?:con|prn|aux|nul|clock\$|conin\$|conout\$|com[1-9]|lpt[1-9])(?:\.|$)", re.IGNORECASE
)
LOCATOR_PARAGRAPH_RE = re.compile(r"^\[\d{1,6}\]$")
LOCATOR_LINE_RE = re.compile(r"^L\d{1,7}$")

_INVISIBLE_CATEGORIES = {"Cc", "Cf", "Cs", "Zl", "Zp"}


def _pin_utf8_stdio() -> None:
    """Pin stdio to UTF-8 so cp1252 consoles cannot corrupt CJK diagnostics."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError, AttributeError):
            pass


def has_visible_prose(value: str) -> bool:
    """True when the string carries at least one visible, non-space code point."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return any(
        not ch.isspace() and unicodedata.category(ch) not in _INVISIBLE_CATEGORIES for ch in value
    )


def clean_scalar(value: object) -> bool:
    """Reject strings with lone surrogates or control/format characters."""
    if not isinstance(value, str):
        return True
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return not any(unicodedata.category(ch) in {"Cc", "Cf", "Cs"} for ch in value)


def is_safe_relative_source_path(value: object) -> bool:
    """Port of the original safe-source-path rule: workspace-relative, forward slashes only."""
    if not isinstance(value, str) or not value or not clean_scalar(value):
        return False
    if value.strip() != value:
        return False
    if "\\" in value or ":" in value or value.startswith("~"):
        return False
    if value.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    segments = value.rstrip("/").split("/")
    for segment in segments:
        if segment in ("", ".", ".."):
            return False
        if segment.endswith(" ") or segment.endswith("."):
            return False
        if WINDOWS_RESERVED.match(segment):
            return False
    return True


def is_ref_with_locator(value: object) -> bool:
    """trace.ref form: safe relative path plus an optional ``#fragment``."""
    if not isinstance(value, str) or not value:
        return False
    path, sep, fragment = value.partition("#")
    if sep and (not fragment or "#" in fragment):
        return False
    return is_safe_relative_source_path(path) if path else bool(sep) and bool(fragment)


class Problems:
    """Error collector capped at LIMITS['errors'] messages."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, message: str) -> None:
        if len(self.items) < LIMITS["errors"]:
            self.items.append(message)

    @property
    def truncated(self) -> bool:
        return len(self.items) >= LIMITS["errors"]


def walk_limits(node: object, problems: Problems, location: str = "$", depth: int = 0) -> None:
    """Enforce input size limits independent of schema interpretation."""
    if depth > LIMITS["nesting_depth"]:
        problems.add(f"{location}: exceeds {LIMITS['nesting_depth']} level nesting depth limit")
        return
    if isinstance(node, list):
        if len(node) > LIMITS["findings"] * 100:
            problems.add(f"{location}: exceeds array item limit")
            return
        for index, item in enumerate(node):
            if isinstance(item, (dict, list)):
                walk_limits(item, problems, f"{location}[{index}]", depth + 1)
    elif isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                walk_limits(value, problems, f"{location}.{key}", depth + 1)


def require_string(problems: Problems, base: str, record: dict, field: str) -> None:
    value = record.get(field)
    if not isinstance(value, str) or not value or not has_visible_prose(value):
        problems.add(f"{base}.{field}: must be a non-empty visible string")
    elif not clean_scalar(value):
        problems.add(f"{base}.{field}: must not contain control or format characters")


def validate_trace(problems: Problems, base: str, record: dict) -> None:
    trace = record.get("trace")
    if not isinstance(trace, list) or len(trace) < 2:
        problems.add(f"{base}.trace: must be an array with at least 2 items")
        return
    seen: list[object] = []
    for index, item in enumerate(trace):
        if not isinstance(item, dict):
            problems.add(f"{base}.trace[{index}]: must be an object")
            continue
        seen.append(item)
        kind = item.get("kind")
        if kind not in TRACE_KINDS:
            problems.add(f"{base}.trace[{index}].kind: must be one of {TRACE_KINDS}")
        if not is_ref_with_locator(item.get("ref")):
            problems.add(
                f"{base}.trace[{index}].ref: must be a workspace-relative path"
                " with an optional #fragment"
            )
        require_string(problems, f"{base}.trace[{index}]", item, "description")
    if len(seen) != len(trace):
        return
    kinds = [item.get("kind") for item in trace]
    if kinds[0] != "element":
        problems.add(f"{base}.trace[0].kind: must be \"element\", got {kinds[0]!r}")
    if kinds[-1] not in ("disclosure", "effect"):
        problems.add(f"{base}.trace[{len(trace) - 1}].kind: must be \"disclosure\" or \"effect\"")
    for index, kind in enumerate(kinds[1:-1], start=1):
        if kind != "disclosure":
            problems.add(f"{base}.trace[{index}].kind: must be \"disclosure\", got {kind!r}")


def validate_evidence(problems: Problems, base: str, record: dict) -> None:
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        problems.add(f"{base}.evidence: must be a non-empty array")
        return
    encoded: set[str] = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            problems.add(f"{base}.evidence[{index}]: must be an object")
            continue
        ref = item.get("ref")
        if not is_safe_relative_source_path(ref):
            problems.add(
                f"{base}.evidence[{index}].ref: must be a safe workspace-relative source path"
            )
        locator = item.get("locator")
        if (
            not isinstance(locator, str)
            or not locator.strip()
            or locator.strip() != locator
            or not has_visible_prose(locator)
        ):
            problems.add(f"{base}.evidence[{index}].locator: must be a non-empty trimmed string")
        quote = item.get("quote")
        if not isinstance(quote, str) or len(quote) < 2 or not has_visible_prose(quote):
            problems.add(f"{base}.evidence[{index}].quote: must be a verbatim quote (>= 2 chars)")
        require_string(problems, f"{base}.evidence[{index}]", item, "description")
        encoded.add(json.dumps(item, sort_keys=True, ensure_ascii=False))
    if len(encoded) != len(evidence):
        problems.add(f"{base}.evidence: items must be unique")


def validate_impact(problems: Problems, base: str, record: dict) -> None:
    impact = record.get("impact")
    if not isinstance(impact, dict):
        problems.add(f"{base}.impact: must be an object")
        return
    category = impact.get("category")
    if category not in IMPACT_CATEGORIES:
        problems.add(f"{base}.impact.category: must be one of {IMPACT_CATEGORIES}")
    require_string(problems, f"{base}.impact", impact, "reason")
    extent = record.get("disclosure_extent")
    if category == "X":
        if extent == "partial":
            problems.add(
                f"{base}.impact.category: X cannot rest on disclosure_extent \"partial\""
                " (overall cannot exceed demonstrated disclosure)"
            )
        coverage = record.get("element_coverage")
        if not isinstance(coverage, dict) or coverage.get("all_elements") is not True:
            problems.add(
                f"{base}.element_coverage: category X requires element_coverage"
                " with all_elements == true"
            )


def validate_confirmed(problems: Problems, base: str, record: dict) -> None:
    for field in ("mapping_rationale",):
        require_string(problems, base, record, field)
    extent = record.get("disclosure_extent")
    if extent not in DISCLOSURE_EXTENTS:
        problems.add(f"{base}.disclosure_extent: must be one of {DISCLOSURE_EXTENTS}")
    distinctions = record.get("distinctions")
    if not isinstance(distinctions, list) or any(
        not isinstance(item, str) or not item for item in distinctions
    ):
        problems.add(f"{base}.distinctions: must be an array of strings (may be empty)")
    validate_impact(problems, base, record)
    review = record.get("independent_review")
    if not isinstance(review, dict):
        problems.add(f"{base}.independent_review: must be an object (phase A5 mark)")
    else:
        if review.get("status") != "verified":
            problems.add(f"{base}.independent_review.status: must be \"verified\"")
        require_string(problems, f"{base}.independent_review", review, "reviewer")
    confidence = record.get("confidence")
    if not isinstance(confidence, dict):
        problems.add(f"{base}.confidence: must be an object")
    else:
        if confidence.get("score") not in CONFIDENCE_SCORES:
            problems.add(f"{base}.confidence.score: must be one of {CONFIDENCE_SCORES}")
        require_string(problems, f"{base}.confidence", confidence, "reason")
    conditions = record.get("conditions")
    if conditions is not None:
        if not isinstance(conditions, list):
            problems.add(f"{base}.conditions: must be an array when present")
        else:
            for index, item in enumerate(conditions):
                if not isinstance(item, dict) or item.get("kind") not in CONDITION_KINDS:
                    problems.add(
                        f"{base}.conditions[{index}]: kind must be one of {CONDITION_KINDS}"
                    )
                    continue
                require_string(problems, f"{base}.conditions[{index}]", item, "description")


def validate_needs_validation(problems: Problems, base: str, record: dict) -> None:
    require_string(problems, base, record, "claimed_rationale")
    blockers = record.get("blockers")
    if not isinstance(blockers, list) or not blockers:
        problems.add(f"{base}.blockers: must be a non-empty array of missing decisive facts")
    else:
        for index, item in enumerate(blockers):
            if not isinstance(item, str) or not has_visible_prose(item):
                problems.add(f"{base}.blockers[{index}]: must be a non-empty visible string")
        if len({json.dumps(b, ensure_ascii=False) for b in blockers}) != len(blockers):
            problems.add(f"{base}.blockers: items must be unique")
    plan = record.get("validation_plan")
    if not isinstance(plan, dict):
        problems.add(f"{base}.validation_plan: must be an object with local and/or external")
        return
    has_plan = False
    for field in ("local", "external"):
        value = plan.get(field)
        if value is None:
            continue
        if isinstance(value, str) and value and has_visible_prose(value):
            has_plan = True
        else:
            problems.add(f"{base}.validation_plan.{field}: must be a non-empty visible string")
    if not has_plan:
        problems.add(
            f"{base}.validation_plan: requires at least one visible local or external plan"
        )


def validate_rejected(problems: Problems, base: str, record: dict) -> None:
    require_string(problems, base, record, "claimed_rationale")
    require_string(problems, base, record, "refutation")


FORBIDDEN = {
    "confirmed": ("claimed_rationale", "blockers", "validation_plan", "refutation"),
    "needs_validation": (
        "impact",
        "disclosure_extent",
        "confidence",
        "distinctions",
        "independent_review",
        "mapping_rationale",
        "refutation",
        "element_coverage",
        "conditions",
        "root_cause",
    ),
    "rejected": (
        "impact",
        "confidence",
        "independent_review",
        "blockers",
        "validation_plan",
        "mapping_rationale",
        "disclosure_extent",
        "element_coverage",
        "conditions",
        "root_cause",
    ),
}
ALLOWED = {
    "confirmed": set(CONFIRMED_FIELDS) | set(CONFIRMED_OPTIONAL),
    "needs_validation": set(NEEDS_VALIDATION_FIELDS),
    "rejected": set(REJECTED_FIELDS),
}
REQUIRED = {
    "confirmed": CONFIRMED_FIELDS,
    "needs_validation": NEEDS_VALIDATION_FIELDS,
    "rejected": REJECTED_FIELDS,
}


def validate_finding(problems: Problems, index: int, finding: object) -> None:
    if not isinstance(finding, dict):
        problems.add(f"$[{index}]: must be an object")
        return
    base = f"$[{index}]"
    verdict = finding.get("verdict")
    if verdict not in VERDICTS:
        problems.add(f"{base}.verdict: must be one of {VERDICTS}")
        return
    for field in FORBIDDEN[verdict]:
        if field in finding:
            problems.add(f"{base}: {verdict} finding must not contain {field!r}")
    for field in REQUIRED[verdict]:
        if field not in finding:
            problems.add(f"{base}: missing required field {field!r}")
    for key in finding:
        if key not in ALLOWED[verdict]:
            problems.add(f"{base}: unexpected field {key!r}")
    fingerprint = finding.get("fingerprint")
    if not isinstance(fingerprint, str) or not FINGERPRINT_RE.match(fingerprint):
        problems.add(
            f"{base}.fingerprint: must match {FINGERPRINT_RE.pattern} (stable, source-derived)"
        )
    for field in ("title", "description", "element"):
        require_string(problems, base, finding, field)
    if "trace" in finding:
        validate_trace(problems, base, finding)
    if "evidence" in finding:
        validate_evidence(problems, base, finding)
    if verdict == "confirmed":
        validate_confirmed(problems, base, finding)
    elif verdict == "needs_validation":
        validate_needs_validation(problems, base, finding)
    else:
        validate_rejected(problems, base, finding)


def validate_document(findings: object, problems: Problems) -> None:
    if not isinstance(findings, list):
        problems.add("$: top-level document must be an array")
        return
    if len(findings) > LIMITS["findings"]:
        problems.add(f"$: exceeds {LIMITS['findings']} findings limit")
        return
    seen: dict[str, int] = {}
    previous: str | None = None
    for index, finding in enumerate(findings):
        if problems.truncated:
            break
        validate_finding(problems, index, finding)
        if not isinstance(finding, dict):
            continue
        fingerprint = finding.get("fingerprint")
        if isinstance(fingerprint, str) and FINGERPRINT_RE.match(fingerprint):
            if fingerprint in seen:
                problems.add(f"$[{index}].fingerprint: duplicate of $[{seen[fingerprint]}]")
            else:
                seen[fingerprint] = index
            if previous is not None and previous > fingerprint:
                problems.add(f"$[{index}].fingerprint: findings must be sorted lexicographically")
            previous = fingerprint


def locate_paragraph(text: str, locator: str) -> str | None:
    """Return the paragraph block addressed by a locator, or None when absent.

    Structured locators (``[00NN]`` paragraph tags, ``L<n>`` line pointers) must be
    found exactly; the repo corpus convention is one ``[00xx]`` paragraph per line,
    so line matches take precedence over blank-line blocks. Free-form locators fall
    back to whole-document scope.
    """
    if LOCATOR_PARAGRAPH_RE.match(locator):
        lines = [line for line in text.splitlines() if line.strip().startswith(locator)]
        if lines:
            return "\n".join(lines)
        for paragraph in re.split(r"\n\s*\n", text):
            if locator in paragraph:
                return paragraph
        return None
    if LOCATOR_LINE_RE.match(locator):
        number = int(locator[1:])
        lines = text.splitlines()
        if 1 <= number <= len(lines):
            return lines[number - 1]
        return None
    return text


def verify_evidence_against_workspace(
    findings: list, workspace: Path, problems: Problems
) -> None:
    """Check every evidence quote against the referenced workspace document."""
    cache: dict[str, str] = {}

    def read(ref: str) -> str | None:
        if ref not in cache:
            path = workspace / PurePosixPath(ref)
            try:
                cache[ref] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError, ValueError):
                cache[ref] = ""
        return cache[ref] or None

    for index, finding in enumerate(findings):
        if not isinstance(finding, dict) or problems.truncated:
            continue
        base = f"$[{index}]"
        evidence = finding.get("evidence")
        if not isinstance(evidence, list):
            continue
        for entry_index, item in enumerate(evidence):
            if not isinstance(item, dict):
                continue
            ref = item.get("ref")
            locator = item.get("locator")
            quote = item.get("quote")
            if not (isinstance(ref, str) and isinstance(locator, str) and isinstance(quote, str)):
                continue
            text = read(ref)
            if text is None:
                problems.add(
                    f"{base}.evidence[{entry_index}].ref: document not found under workspace: {ref}"
                )
                continue
            scope = locate_paragraph(text, locator)
            if scope is None:
                problems.add(
                    f"{base}.evidence[{entry_index}].locator: {locator} not found in {ref}"
                )
                continue
            if quote not in scope:
                problems.add(
                    f"{base}.evidence[{entry_index}].quote: verbatim quote not found at"
                    f" {ref}#{locator}"
                )


def load_input(path: Path, problems: Problems) -> object | None:
    try:
        raw = path.read_bytes()
    except OSError as error:
        print(f"Failed to read findings JSON: {error}", file=sys.stderr)
        return None
    if len(raw) > LIMITS["input_bytes"]:
        problems.add(f"input exceeds {LIMITS['input_bytes']} byte limit")
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"Failed to parse findings JSON: {error}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Validate a patent-audit findings.json document."
    )
    parser.add_argument("findings", type=Path, help="path to findings.json")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="workspace root for evidence integrity checks (ref/locator/quote)",
    )
    parser.add_argument("--json", action="store_true", help="emit a single JSON document")
    args = parser.parse_args(argv)
    if not args.findings.is_file():
        print(f"findings file not found: {args.findings}", file=sys.stderr)
        return EXIT_USAGE

    problems = Problems()
    findings = load_input(args.findings, problems)
    if findings is not None:
        walk_limits(findings, problems)
        if isinstance(findings, list) and len(findings) <= LIMITS["findings"]:
            validate_document(findings, problems)
        if args.workspace is not None and isinstance(findings, list):
            verify_evidence_against_workspace(findings, args.workspace, problems)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not problems.items,
                    "errors": problems.items,
                    "checked": len(findings) if isinstance(findings, list) else 0,
                    "truncated": problems.truncated,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif problems.items:
        for message in problems.items:
            print(f"ERROR: {message}", file=sys.stderr)
        cap = "; output capped at 100" if problems.truncated else ""
        print(f"FAIL: {len(problems.items)} validation error(s){cap}", file=sys.stderr)
    else:
        count = len(findings) if isinstance(findings, list) else 0
        print(f"PASS: {count} findings valid")
    return EXIT_FAIL if problems.items else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
