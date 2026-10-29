"""Machine-checkable kernel boundary: which kernel verbs/flags the extension may drive.

``tests/test_kernel_boundary.py`` asserts (a) the bridge only dispatches verbs listed
here, and (b) none of the extension's source ever targets kernel workspace paths for
writing. Adding a verb here requires a new test proving the invocation is read-only —
this file is the single place the boundary is declared.
"""

from __future__ import annotations

__all__ = ["READONLY_VERBS", "FORBIDDEN_FLAGS"]

#: Kernel subcommands patent_intel may invoke as subprocesses. Every entry is
#: read-only by default in the kernel CLI (verified against the kernel's own docs;
#: e.g. `queryplan` only writes with --apply, which the bridge refuses separately).
READONLY_VERBS = frozenset(
    {
        "queryplan",  # gap detection over the query library (read-only without --apply)
        "validate",  # V-series re-validation report
        "gates",  # G-S gate report
        "check",  # validate --strict + gates, single JSON document
        "status",  # workspace status summary
    }
)

#: Flags that enable kernel-side mutations; the bridge refuses any command carrying one.
FORBIDDEN_FLAGS = frozenset(
    {
        "--apply",
        "--run",
        "--force",
        "--fill",
        "--execute",
        "--confirm",
        "--write",
    }
)
