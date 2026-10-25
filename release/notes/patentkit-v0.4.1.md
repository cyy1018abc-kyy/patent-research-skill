# patentkit 0.4.1

Companion kernel for Patent Research Skill 3.2.1; Python 3.11+.

**No rule or CLI changes** — this release adds the end-to-end golden regression layer:

- `regression_tests/golden/fixture/` — a fixed synthetic workspace (two live Espacenet
  logs with raw artifacts, a query library with an unexecuted sub-query, assessment
  quotes, a run file, manuscript registry + claims + revision patch, a numerical-provenance
  registry, a figure spec, matching BibTeX entries);
- `regression_tests/test_golden_pipeline.py` — runs the full pipeline on that workspace
  (ingest → AI assess → human confirm with post-assessment fingerprints → validate →
  gates → ledger → queryplan → report → export-docx → map → chain → one revise round →
  status) and compares every stage's normalized output against the checked-in snapshots in
  `regression_tests/golden/expected/` (timestamps, today's date and the workspace path are
  redacted; fixture dates are asserted data). A second test runs the whole pipeline twice
  and requires byte-identical normalized output.
- Any unintended behavior change in the rules now fails CI at push time; intentional
  changes regenerate snapshots via `GOLDEN_UPDATE=1` and are reviewed line by line.

Full suite from the patched tree: 529 passed / 9 skipped (527 + 2 golden tests).
Version single source: `patentkit.__version__ = "0.4.1"`.

Assets: `patentkit-0.4.1-py3-none-any.whl`, `patentkit-0.4.1.tar.gz`, and
`SHA256SUMS-patentkit-v0.4.1.txt`. The kernel is reconstructed in CI from the
public `patentkit-0.1.2.tar.gz` plus `release/patches/patentkit-0.1.2-to-0.4.1.patch`
(see `release/patches/README.md`).
