#!/usr/bin/env python3
"""Validate a patent-audit coverage ledger (audit-ledger.json).

Derived from Cloudflare security-audit-skill's validate-coverage-ledger.cjs (MIT
License, Copyright (c) 2025-2026 Cloudflare, Inc.), re-implemented in Python with
coverage units rewritten to the patent domain (element × data source ×
classification symbol). No code is vendored.

Contract: audit/references/01-recon-claims-map.md + audit/references/00-audit-protocol.md §6.

Usage:
    python validate_ledger.py <audit-ledger.json> [--json]

Exit codes: 0 = pass, 1 = validation failure, 2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

LIMITS = {
    "input_bytes": 5 * 1024 * 1024,
    "units": 10000,
    "nesting_depth": 64,
    "errors": 100,
}

SCHEMA_VERSION = "patent-audit-ledger/1"
STATUSES = ("planned", "in_progress", "blocked", "covered", "candidate",
            "not_applicable", "out_of_scope", "deferred")
PRIOR_STATUSES = (
    "none",
    "new",
    "prior_confirmed_same_source",
    "prior_confirmed_changed_source",
    "prior_needs_validation",
    "prior_deferred",
    "prior_blocked",
    "prior_out_of_scope",
    "prior_covered_same_source",
    "prior_covered_changed_source",
    "prior_rejected_claim_changed",
)
CHECK_METHODS = ("search", "source", "local")
CANONICAL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
WINDOWS_DEVICE_NAMES = {
    "con", "prn", "aux", "nul", "clock$", "conin$", "conout$",
} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}

# State table: status -> (agent_id required, evidence required, fingerprints, unresolved)
STATE_TABLE = {
    "planned": (False, False, False, False),
    "not_applicable": (False, False, False, True),
    "out_of_scope": (False, False, False, True),
    "deferred": (False, False, False, True),
    "in_progress": (True, False, False, False),
    "blocked": (True, True, False, True),
    "covered": (True, True, False, False),
    "candidate": (True, True, True, False),
}

_INVISIBLE_CATEGORIES = {"Cc", "Cf", "Cs", "Zl", "Zp"}
_UNRESERVED = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


def _pin_utf8_stdio() -> None:
    """Pin stdio to UTF-8 so cp1252 consoles cannot corrupt CJK diagnostics."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError, AttributeError):
            pass


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


def is_canonical_agent_id(value: object) -> bool:
    if not isinstance(value, str) or not CANONICAL_ID_RE.match(value):
        return False
    return value not in WINDOWS_DEVICE_NAMES


def is_safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if value.strip() != value or "\\" in value or ":" in value or value.startswith("~"):
        return False
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    for segment in value.rstrip("/").split("/"):
        if segment in ("", ".", ".."):
            return False
        if segment.endswith(" ") or segment.endswith("."):
            return False
    return True


def percent_encode_reference(value: str) -> str:
    """RFC 3986 percent-encoding of UTF-8 bytes; only unreserved characters survive."""
    raw = value.encode("utf-8")
    return "".join(
        chr(byte) if byte in _UNRESERVED else f"%{byte:02X}" for byte in raw
    )


def derived_coverage_id(canonical_refs: dict) -> str | None:
    parts = []
    for dimension in ("element", "source", "klass"):
        value = canonical_refs.get(dimension)
        if not isinstance(value, str) or not value:
            return None
        parts.append(percent_encode_reference(value))
    return "::".join(parts)


def require_visible_string(
    problems: Problems, base: str, container: dict, field: str
) -> str | None:
    value = container.get(field)
    if not isinstance(value, str) or not value:
        problems.add(f"{base}.{field}: must be a non-empty string")
        return None
    if value.strip() != value:
        problems.add(f"{base}.{field}: must not have surrounding whitespace")
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        problems.add(f"{base}.{field}: must contain only valid Unicode scalar values")
        return None
    if any(unicodedata.category(ch) in _INVISIBLE_CATEGORIES for ch in value):
        problems.add(f"{base}.{field}: must not contain control/format characters")
        return None
    return value


def validate_check(problems: Problems, base: str, index: int, check: object) -> list[str]:
    if not isinstance(check, dict):
        problems.add(f"{base}.checks[{index}]: must be an object")
        return []
    entry = f"{base}.checks[{index}]"
    agent_id = check.get("agent_id")
    if not is_canonical_agent_id(agent_id):
        problems.add(f"{entry}.agent_id: must be a canonical lowercase agent id")
    method = check.get("method")
    if method not in CHECK_METHODS:
        problems.add(f"{entry}.method: must be one of {CHECK_METHODS}")
    require_visible_string(problems, entry, check, "description")
    paths = check.get("reviewed_paths")
    if not isinstance(paths, list) or not paths or not all(
        is_safe_relative_path(p) for p in paths
    ):
        problems.add(
            f"{entry}.reviewed_paths: must be a non-empty list of safe relative paths"
        )
        paths = []
    artifact = check.get("artifact")
    if method == "source":
        if artifact is not None:
            problems.add(f"{entry}.artifact: must be null for method \"source\"")
    else:
        prefix = f"agents/{agent_id}/artifacts/" if isinstance(agent_id, str) else None
        if not isinstance(artifact, str) or not artifact:
            problems.add(f"{entry}.artifact: required for method {method!r}")
        elif not is_safe_relative_path(artifact) or prefix is None or not artifact.startswith(
            prefix
        ):
            problems.add(
                f"{entry}.artifact: must stay under agents/<agent_id>/artifacts/"
            )
    return [p for p in paths if isinstance(p, str)]


def validate_attempt(problems: Problems, base: str, index: int, attempt: object, wave: int) -> None:
    if not isinstance(attempt, dict):
        problems.add(f"{base}.attempts[{index}]: must be an object")
        return
    entry = f"{base}.attempts[{index}]"
    if attempt.get("status") not in ("blocked", "covered", "candidate"):
        problems.add(
            f"{entry}.status: only blocked/covered/candidate states can be archived"
        )
    attempt_wave = attempt.get("wave")
    if not isinstance(attempt_wave, int) or not (0 < attempt_wave < wave):
        problems.add(f"{entry}.wave: must be a positive integer below the live wave {wave}")
    if not is_canonical_agent_id(attempt.get("agent_id")):
        problems.add(f"{entry}.agent_id: must be a canonical lowercase agent id")
    reason = attempt.get("reassignment_reason")
    if not isinstance(reason, str) or not reason.strip():
        problems.add(f"{entry}.reassignment_reason: must cite the critic's source-backed reason")
    for field in ("reviewed_paths", "checks", "result_fingerprints"):
        if not isinstance(attempt.get(field), list):
            problems.add(f"{entry}.{field}: archived evidence must be preserved")


def validate_unit(problems: Problems, index: int, unit: object) -> None:
    if not isinstance(unit, dict):
        problems.add(f"$[{index}]: unit must be an object")
        return
    base = f"$[{index}]"
    coverage_id = unit.get("coverage_id")
    if not isinstance(coverage_id, str) or not coverage_id:
        problems.add(f"{base}.coverage_id: must be a non-empty string")
    refs = unit.get("canonical_refs")
    if not isinstance(refs, dict):
        problems.add(f"{base}.canonical_refs: must be an object with element/source/klass")
    else:
        for dimension in ("element", "source", "klass"):
            value = require_visible_string(problems, f"{base}.canonical_refs", refs, dimension)
            if value is not None and not value.isprintable():
                problems.add(f"{base}.canonical_refs.{dimension}: must be printable NFC text")
        if coverage_id and isinstance(refs, dict):
            expected = derived_coverage_id(refs)
            if expected is not None and coverage_id != expected:
                problems.add(
                    f"{base}.coverage_id: does not match canonical_refs derivation"
                    f" (expected {expected!r})"
                )
    for dimension in ("element", "source", "klass"):
        if dimension not in unit:
            problems.add(f"{base}: missing dimension field {dimension!r}")
        elif not isinstance(unit[dimension], str) or not unit[dimension].strip():
            problems.add(f"{base}.{dimension}: must be a non-empty label")
    status = unit.get("status")
    if status not in STATUSES:
        problems.add(f"{base}.status: must be one of {STATUSES}")
        return
    needs_agent, needs_evidence, needs_fingerprints, needs_unresolved = STATE_TABLE[status]
    agent_id = unit.get("agent_id")
    if needs_agent and not is_canonical_agent_id(agent_id):
        problems.add(f"{base}.agent_id: status {status!r} requires a canonical owner")
    if not needs_agent and agent_id is not None:
        problems.add(f"{base}.agent_id: status {status!r} requires null")
    paths = unit.get("reviewed_paths")
    checks = unit.get("checks")
    if not isinstance(paths, list):
        problems.add(f"{base}.reviewed_paths: must be an array")
        paths = []
    if not isinstance(checks, list):
        problems.add(f"{base}.checks: must be an array")
        checks = []
    if needs_evidence:
        if not paths or not checks:
            problems.add(
                f"{base}: status {status!r} requires non-empty reviewed_paths and checks"
            )
    else:
        if paths or checks:
            problems.add(
                f"{base}: status {status!r} requires empty reviewed_paths and checks"
            )
    union: list[str] = []
    for check_index, check in enumerate(checks):
        union.extend(validate_check(problems, base, check_index, check))
    if sorted(set(union)) != sorted(paths):
        problems.add(
            f"{base}.reviewed_paths: must equal the union of checks' reviewed_paths"
        )
    fingerprints = unit.get("result_fingerprints")
    if not isinstance(fingerprints, list):
        problems.add(f"{base}.result_fingerprints: must be an array")
        fingerprints = []
    if needs_fingerprints and not fingerprints:
        problems.add(f"{base}: status {status!r} requires result_fingerprints")
    if not needs_fingerprints and fingerprints:
        problems.add(f"{base}: status {status!r} requires empty result_fingerprints")
    unresolved = unit.get("unresolved")
    if not isinstance(unresolved, list):
        problems.add(f"{base}.unresolved: must be an array")
        unresolved = []
    if needs_unresolved and not unresolved:
        problems.add(f"{base}: status {status!r} requires a non-empty unresolved reason")
    if not needs_unresolved and unresolved:
        problems.add(f"{base}: status {status!r} requires empty unresolved")
    if status == "blocked":
        if any(not isinstance(item, str) or not item.strip() for item in unresolved):
            problems.add(f"{base}.unresolved: blocked units need a string blocker")
    wave = unit.get("wave")
    if not isinstance(wave, int) or wave < 1:
        problems.add(f"{base}.wave: must be a positive integer")
        wave = 1
    attempts = unit.get("attempts")
    if not isinstance(attempts, list):
        problems.add(f"{base}.attempts: must be an array")
        attempts = []
    for attempt_index, attempt in enumerate(attempts):
        validate_attempt(problems, base, attempt_index, attempt, wave)
    if unit.get("prior_status") not in PRIOR_STATUSES:
        problems.add(f"{base}.prior_status: must be one of {PRIOR_STATUSES}")
    starting_paths = unit.get("starting_paths")
    if not isinstance(starting_paths, list) or not starting_paths or not all(
        is_safe_relative_path(p) for p in starting_paths
    ):
        problems.add(
            f"{base}.starting_paths: must be a non-empty list of safe relative paths"
        )


def validate_ledger(ledger: object, problems: Problems) -> None:
    if not isinstance(ledger, dict):
        problems.add("$: top-level document must be an object")
        return
    if ledger.get("schema_version") != SCHEMA_VERSION:
        problems.add(f"$.schema_version: must be {SCHEMA_VERSION!r}")
    for field in ("run_id", "target"):
        value = ledger.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.add(f"$.{field}: must be a non-empty string")
    if ledger.get("profile") not in ("quick", "standard", "deep"):
        problems.add("$.profile: must be one of ('quick', 'standard', 'deep')")
    if ledger.get("mode") not in ("single", "multi"):
        problems.add("$.mode: must be one of ('single', 'multi')")
    units = ledger.get("units")
    if not isinstance(units, list):
        problems.add("$.units: must be an array")
        return
    if len(units) > LIMITS["units"]:
        problems.add(f"$.units: exceeds {LIMITS['units']} unit limit")
        return
    seen: dict[str, int] = {}
    previous: str | None = None
    for index, unit in enumerate(units):
        if problems.truncated:
            break
        validate_unit(problems, index, unit)
        if not isinstance(unit, dict):
            continue
        coverage_id = unit.get("coverage_id")
        if isinstance(coverage_id, str) and coverage_id:
            if coverage_id in seen:
                problems.add(
                    f"$[{index}].coverage_id: duplicate of $[{seen[coverage_id]}]"
                    " (canonical identity collision)"
                )
            else:
                seen[coverage_id] = index
            if previous is not None and previous > coverage_id:
                problems.add(
                    f"$[{index}].coverage_id: units must be sorted lexicographically"
                )
            previous = coverage_id


def load_input(path: Path, problems: Problems) -> object | None:
    try:
        raw = path.read_bytes()
    except OSError as error:
        print(f"Failed to read ledger JSON: {error}", file=sys.stderr)
        return None
    if len(raw) > LIMITS["input_bytes"]:
        problems.add(f"input exceeds {LIMITS['input_bytes']} byte limit")
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"Failed to parse ledger JSON: {error}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Validate a patent-audit coverage ledger (audit-ledger.json)."
    )
    parser.add_argument("ledger", type=Path, help="path to audit-ledger.json")
    parser.add_argument("--json", action="store_true", help="emit a single JSON document")
    args = parser.parse_args(argv)
    if not args.ledger.is_file():
        print(f"ledger file not found: {args.ledger}", file=sys.stderr)
        return EXIT_USAGE

    problems = Problems()
    ledger = load_input(args.ledger, problems)
    if ledger is not None:
        validate_ledger(ledger, problems)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not problems.items,
                    "errors": problems.items,
                    "checked": len(ledger.get("units", []))
                    if isinstance(ledger, dict)
                    else 0,
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
        count = len(ledger.get("units", [])) if isinstance(ledger, dict) else 0
        print(f"PASS: {count} ledger units valid")
    return EXIT_FAIL if problems.items else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
