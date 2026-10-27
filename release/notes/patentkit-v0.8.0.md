# patentkit 0.8.0

Companion kernel for Patent Research Skill 3.7.0; Python 3.11+. Assessment protocol 1,
G-S-01…05 semantics and the evidence three-tier system are unchanged; the changes are
additive rules and one new audit rule.

## 什么变了

- **Revision loop <-> conclusions linkage (V038)**: `revise apply` marks every existing
  `05_novelty_conclusions/*.md` stale (kernel-generated trackers exempt); `revise status`
  lists them and exits 1; `revise close` refuses until each stale conclusion is human
  re-confirmed (`revise reconfirm --by <name>`, binds the file sha256) or explicitly waived
  with a reason (`--waive --reason`, recorded in the ledger round as `conclusion_waivers`).
  validate reports unprocessed stale conclusions, conclusions edited after their
  re-confirmation, and waivers missing from the ledger as **V038 errors**. State lives in
  `05_novelty_conclusions/conclusions_state.yml`; workspaces without it need zero migration.
- **Structured support citations (D-019)**: `support_mapping` rows accept an optional
  `citations` list (`source` = workspace-relative path resolved via the confined-path
  helper; `locator` = `L<n>[-L<m>]` line range or `[NNNN]` paragraph tag). The drafting
  audit fails citations that do not resolve. Old documents without citations stay valid.
- **Patch builder fix**: empty new files produced a `diff --git` header without
  `---/+++` disambiguation plus git's synthetic `a/b/` path, which `git apply` rejects;
  the builder now normalizes synthetic paths for added/deleted files.

## 升级

- `pip install patentkit-0.8.0-py3-none-any.whl`；旧工作区零迁移；改稿闭环中的工作区
  从下一次 `revise apply` 起按 V038 流程处理结论。
