# patentkit 0.6.0

Companion kernel for Patent Research Skill 3.4.0; Python 3.11+.

Feature release: the G-S-04 census-evidence rework, the data-source chain fixes, and the
review-status guard for backfills. One new rule (V037), one new workspace field
(`census`), one new module (`patentkit/census.py`); the assessment protocol and the
three-tier evidence model are unchanged.

## G-S-04 now verifies census evidence, not array shapes

The old `gate_gs04()` accepted any candidate whose `family`/`cited_by` were lists — two
empty arrays passed, and "not queried" was indistinguishable from "queried, zero hits".
Each subject (`role ∈ {near_prior_art, family}`) now needs a valid **census record** per
dimension (`patentkit/census.py`): queried doc number, source, query id, time, status
(`complete` / `zero_hits` / `partial` / `failed`), and the raw artifact with its sha256.
`zero_hits` counts as complete; not-queried, `partial`, `failed`, and missing-or-modified
artifacts do not. G-S-04 failures now carry a per-object detail list (which candidate,
which dimension, why). The gate FAILs honestly on 0.5.x workspaces until the census is
filled — that is the point, not a regression.

- validate gains **V037**: a census record that *exists* but is broken (missing fields,
  artifact deleted or modified, doc-number mismatch, status contradicting the artifact
  content) is an error. An honest `partial`/`failed` record is not corruption — validate
  stays quiet, the gate refuses to count it.
- `candidates_schema.json` (template + `migrate` plan) gains the managed `census`
  property; older workspaces refresh it with `python -m patentkit migrate`.

## fetch-bigquery chain fixes (all verifiable without credentials)

1. Dry-run pre-check and execution now share the same SQL **and the same
   `query_parameters`** (the pre-check previously did not bind parameters — for
   parameterized SQL that is a different request).
2. The cited-by subquery returns the **citing** document's number (the old projection
   returned the queried number itself and measured nothing).
3. Archives are named `bigquery_<date>_<target>_<HHMMSS>_GS04_<rows>.jsonl` (+ paired
   log, run-time as the numeric query sequence per V006/V007) and **refuse to overwrite**
   an existing artifact — the file's hash is bound by census records, silent replacement
   would be evidence tampering. Every queried doc lands as one row (zero hits included,
   with a `found` flag).
4. `--fill` writes the census records (field-level artifact binding), requires the
   artifact to live under workspace `02_search_logs/`, cross-checks the bound search
   log's target (cross-target backfill is refused), only touches the passed target, and
   **skips candidates with human review traces unless `--force`** — every forced write is
   appended to `02_search_logs/backfill_audit.jsonl`. Fill is idempotent; empty-array
   candidates get `zero_hits` records so a legitimate zero-hit lookup is provable.
5. Cost estimates use the official dry-run `total_bytes_processed` (not
   `total_bytes_billed`), and `--max-cost-usd` (default 5) refuses execution when the
   estimate exceeds the budget.

## backfill (abstracts) gains the same review guard

`backfill abstracts` skips candidates with human review traces by default (`--force`
overrides, audited to the same `backfill_audit.jsonl`). Abstract fields are not part of
the assessment fingerprint, so a forced write does not invalidate an existing
confirmation — but it leaves a trace.

## Tests

New: census gate matrix (not-queried / zero-hits / complete / modified-artifact /
per-dimension / partial), V037 positive and negative cases, run-census parameter-sharing
and budget-refusal tests (stubbed BigQuery client), archive overwrite refusal,
fill target-binding / review-guard / force-audit / conflict-keeps-human-values /
zero-hits tests, the backfill review-guard test, and the packaged reference-link checks.
Golden pipeline: the shared fixture gains a census artifact + log and a fill stage before
human confirmation, plus three appended stages (reviewed-skip report → `--force` with
audit → the audit file itself).

Suite: 511 passed / 9 skipped (dev tree, Windows; POSIX-only tests run in CI) plus 44
regression tests including both golden pipelines. Workspaces need `patentkit migrate`
(schema) before the first `--fill`.

Version single source: `patentkit.__version__ = "0.6.0"`.

Assets: `patentkit-0.6.0-py3-none-any.whl`, `patentkit-0.6.0.tar.gz`, and
`SHA256SUMS-patentkit-v0.6.0.txt`. The kernel is reconstructed in CI from the
public `patentkit-0.1.2.tar.gz` plus `release/patches/patentkit-0.1.2-to-0.6.0.patch`
(see `release/patches/README.md`).
