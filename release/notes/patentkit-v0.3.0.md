# patentkit 0.3.0

Companion kernel for Patent Research Skill 2.5.0; Python 3.11+.

- Delivery-safety layer: `export-docx` (optional `[docx]` extra; workspace-verbatim
  .docx search report), `map` (offline self-contained HTML overview), `layout`
  (read-only 1+N portfolio view), `ledger` (evidence ledger), `provenance scan/check`
  (numerical-claim A/B/C registry), `figures check/draw` (mark consistency + SVG),
  `deadlines list/check/init` (statutory-deadline ledger; refuses to compute without
  a base date — the official document always prevails).
- New validation rules: V031/V032 numerical provenance (fail-closed), V033 figure
  marks (warn-only), V034 conclusions citing evidence outside the ledger (error).
- Assessment protocol unchanged (version 1); workspaces from 0.2.0 need no migration.
- Kernel test suite runs fully from the patched tree: `tests/conftest.py` reconstructed
  (the sdist shipped tests without their fixture layer), stale assertions synced to
  protocol semantics, private-layout tests skip cleanly (503 passed / 9 skipped).
- Version single source: `patentkit.__version__ = "0.3.0"`.

Assets: `patentkit-0.3.0-py3-none-any.whl`, `patentkit-0.3.0.tar.gz`, and
`SHA256SUMS-patentkit-v0.3.0.txt`. The kernel is reconstructed in CI from the
checksum-verified public 0.1.2 source and the repository's complete source patch
(`release/patches/patentkit-0.1.2-to-0.3.0.patch`).
