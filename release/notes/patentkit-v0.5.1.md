# patentkit 0.5.1

Companion kernel for Patent Research Skill 3.3.1; Python 3.11+.

Patch-level release: three rehearsal/golden-driven CLI fixes (each with a regression
test). No rule (V001–V036), gate, or assessment-protocol changes.

- `check --json` used to pass `--json` through to both validate and gates, printing two
  concatenated JSON documents (`json.load` fails with "Extra data"). It now prints a
  single `{"check": …, "gates": …}` document; the composite exit-code semantics are
  unchanged (validate `--strict` blocking code first — errors **or warnings** — otherwise
  gates: all-PASS→0, else→2).
- `fetch-bigquery --fill` now reports a malformed census artifact as `[FATAL]` + exit 2
  instead of a bare traceback (the `ValueError` contract of `load_census_raw` is
  unchanged and still pinned by its unit test).
- `deadlines --root` now works in both argument positions (`deadlines list --root X` used
  to be an argparse error). Subparser flags use `SUPPRESS` defaults, so the
  pre-subcommand form keeps working.

New in the regression suite: `regression_tests/test_golden_pipeline_drafting.py` — the
drafting line (provenance scan/check, figures check/draw SVG, deadlines list/check,
revise apply/status/close, `check --json`) pinned stage by stage on the shared golden
fixture: 10 snapshots plus a run-twice byte-identical determinism test. The fixture gains
the `09_deadlines/` ledger (one deliberately incomplete entry) and a grade-B provenance
entry (NUM-003 → P-002); the research golden's DOCX snapshot gains the matching row.
`tests/test_new_features.py` grows the composite-check single-document test and the
deadlines flag-position test.

Suite: 539 passed / 2 skipped (dev tree, Windows; the two POSIX-only tests run in CI),
including both golden pipelines. Workspaces need no migration.

Version single source: `patentkit.__version__ = "0.5.1"`.

Assets: `patentkit-0.5.1-py3-none-any.whl`, `patentkit-0.5.1.tar.gz`, and
`SHA256SUMS-patentkit-v0.5.1.txt`. The kernel is reconstructed in CI from the
public `patentkit-0.1.2.tar.gz` plus `release/patches/patentkit-0.1.2-to-0.5.1.patch`
(see `release/patches/README.md`).
