# patentkit 0.4.0

Companion kernel for Patent Research Skill 3.2.0; Python 3.11+.

- **Planning and revision layer** on top of the 0.3.0 delivery-safety layer:
  - `queryplan` — per-axis search coverage planning: registered vs executed sub-queries,
    G-S-02 verified buffer (same criteria as reference 05), uncovered concept groups with
    deterministic supplementary-query skeletons; `--apply` appends to the query library
    (append-only: existing indices are never renumbered, comments preserved verbatim);
  - `revise apply/status/close` — the revision loop of drafting reference 13 as code:
    structured local patches (every `find` must match exactly once, otherwise the whole
    patch is refused with zero writes), patch + ledger + registry re-bind in one
    transaction, post-round integrity check ("edited without a logged round" is caught),
    3-round-per-issue escalation warning;
  - `chain` — the evidence-chain panorama (logs → candidates → D-list → runs → conclusions
    → ledger → gates → revision ledger) as one offline self-contained HTML page.
- New validation rules: V035 (revision ledger structurally invalid — error) and V036
  (file content changed after the last logged round — warn, escalated by `--strict`);
  rule range is now V001–V036.
- `status` next-step hints point at `queryplan` when G-S-02 has not passed.
- Assessment protocol unchanged (version 1); workspaces from 0.3.0 need no migration —
  the new capabilities are opt-in (the revision ledger is created by the first
  `revise apply`).
- Kernel test suite green from the patched tree (525 passed / 9 skipped, including the
  new `tests/test_04_release_features.py` and `regression_tests/test_revision_loop.py`).
- Version single source: `patentkit.__version__ = "0.4.0"`.

Assets: `patentkit-0.4.0-py3-none-any.whl`, `patentkit-0.4.0.tar.gz`, and
`SHA256SUMS-patentkit-v0.4.0.txt`. The kernel is reconstructed in CI from the
public `patentkit-0.1.2.tar.gz` plus `release/patches/patentkit-0.1.2-to-0.4.0.patch`
(see `release/patches/README.md`; the rebuild itself is scripted by
`tools/build_kernel_patch.py`).
