# patentkit 0.9.0

Companion kernel for Patent Research Skill 3.8.0; Python 3.11+. Assessment protocol 1,
G-S-01…05 semantics and the evidence three-tier system are unchanged; no rule changes.

## What changed

- **Explicit LF at every kernel text write site**. 31 `write_text` calls had no explicit
  `newline`, so Windows text mode translated `\n` to `\r\n` and the same workspace /
  benchmark case was byte-different between Windows and Linux/CI (115 files measured in
  the 3.7.0 round; the benchmark generator had to paper over it with `_force_lf()`).
  This release fixes it at the source: init template copies, assessment/backfill/census
  JSON, review worksheets (CSV + JSON), fetch raw artifacts and logs, the five-gate
  trackers, report / map / provenance / figures outputs, delivery and revise state — all
  now pass `newline="\n"`. Kernel outputs are byte-identical across platforms, so
  sha256-bound fixtures and cross-platform goldens no longer depend on line endings.
- **Two invariant regressions lock the discipline**: `test_init_writes_lf_only` (template
  copy path) and `test_pipeline_writes_lf_only` (every byte the kernel touches in the
  golden pipeline). Kernel suite: 761 tests, 747 passed / 14 skipped / 0 failed.
  Binary write sites (mkstemp + `fdopen("wb")` atomic writes, `shutil.copy2` evidence
  originals) are intentionally untouched.
- **Behavior note**: text writes no longer translate `\n` to `\r\n` on Windows; the
  review CSV worksheet (utf-8-sig) is LF on every platform now, matching Linux/CI.
  Existing CRLF files on disk are **not** rewritten in bulk — they normalize only when
  the kernel itself rewrites them.
- **Release engineering**: the two prose kernel-version statements in
  `release/patches/README.md` ("current kernel is", "declares version") are now
  permanent `bump_version.py --check` needles — the 0.8.0 round missed them (stale
  0.7.0) and this release repairs them.

## 升级

- `pip install patentkit-0.9.0-py3-none-any.whl`；旧工作区零迁移。
