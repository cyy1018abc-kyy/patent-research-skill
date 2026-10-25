# Changelog

## 2026-10-25 · Skill 3.0.0 / kernel 0.3.0（未变）

Multi-skill matrix split, per the accepted decisions in `docs/skill-matrix-plan.md`
(plan C / proceed now / OA merged into drafting → two skills to start).

- **Two skills from one repo**: `research/` (patent-research: 检索/查新/证据链/门禁/交付物,
  references 01–08 + glossary) and `drafting/` (patent-drafting: 交底书/权利要求/OA 答复/
  改稿闭环, references 00,09–13 + glossary). Versions are paired (both 3.0.0).
- **Dual products**: the full zip installs both skills; a standalone
  `patent-drafting-skill-v3.0.0.zip` installs drafting alone (no sample workspace;
  installer self-check degrades to a SKILL.md presence check).
- **Installers are multi-skill**: driven by `manifest.json` schema 2 (`skills` list);
  install/upgrade/uninstall enumerate every payload directory.
- **drafting is script-free by design**: it calls `python -m patentkit <cmd>` directly —
  rules stay in the kernel, no second entry point. Its `references/00-prerequisites.md`
  carries a self-contained summary of the research-side discipline.
- **Shared assets stay in sync by CI**: the glossary copies in research/ and drafting/
  must be byte-identical (`evals/check_terminology.py`); evals grew to 20 cases with a
  `skill` field per case and per-skill trigger anchoring.
- research/SKILL.md now hands drafting/OA requests to the sibling skill; hard constraints
  9/10 (ledger-only citations, A/B/C provenance) apply to both skills.
- Kernel unchanged at 0.3.0 (patch untouched); workspaces need no migration.


## 2026-10-25 · Skill 2.5.0 / kernel 0.3.0

Consolidated release of the upgrade checklist (P0+P1+P2 of
`docs/../升级迭代清单-2026-10-25.md`; the planned 2.5/2.6/2.7/2.8 pacing was merged into one
paired release for a single verification pass).

**Skill package (Chinese-primary runtime)**
- SKILL.md / references / assets are now the authoritative Chinese edition; English mirrors
  live in `references.en/` (01–07 maintained on both sides; 08–13 Chinese-first).
- New references: 08 figures, 09 disclosure & application drafts, 10 claim drafting,
  11 OA response skeleton, 12 policy radar, 13 revision loop; bilingual `glossary.md`.
- Hard constraints extended: #9 conclusions may cite only ledger IDs (V034); #10 numerical
  claims must carry A/B/C provenance (V031/V032).
- `scripts/self_test.py` (six post-install checks incl. negative gate case) and
  `scripts/export_docx.py` wrapper; bilingual `agents/openai.yaml`.

**Kernel 0.3.0 (delivery-safety layer; patch `release/patches/patentkit-0.1.2-to-0.3.0.patch`)**
- New commands: `export-docx` (optional `[docx]` extra), `map`, `layout`, `ledger`,
  `provenance scan/check`, `figures check/draw`, `deadlines list/check/init`.
- New validation rules: V031/V032 (numerical provenance, fail-closed), V033 (figure marks,
  warn-only), V034 (conclusions citing evidence outside the ledger, error).
- `tests/conftest.py` reconstructed so the full suite runs from the distributed tree;
  stale tests synced to assessment-protocol semantics; layout-dependent private-repo tests
  skip cleanly (503 passed / 9 skipped).
- Version single source bumped to 0.3.0; `pyproject` gains `[docx]` extra.

**Quality engineering (CI)**
- `evals/`: 14 trigger/refusal/boundary/format cases; `validate_evals.py` anchors every
  trigger phrase to the SKILL.md description and the result-format five fields.
- `evals/check_terminology.py`: zh↔en pairing + glossary anchors.
- `tools/check_no_workspace_data.py` secrecy guard + `.gitignore` red lines
  (workspace dirs, 专利申请/, 交付文本/, *.docx).
- CI: kernel full suite runs from the patched tree; wheel/ZIP names and version asserts
  moved to 0.3.0; python-docx installed for export tests.

**Docs**: data-source expansion memo (BigQuery/OPS/pqai; MCP stays frozen),
skill-matrix split design (v3.0, decision points listed), scope decisions (no copyright/
infringement modules by default), distribution checklist, policy log, synthetic-data
example walkthrough.


## 2026-10-23 · Skill 2.4.0 / kernel 0.2.0

- Separate source evidence_level from assessment actor, support and human confirmation.
- Allow supported AI scoring for G-S-02; require explicit current human confirmation for G-S-03.
- Preserve human decisions; conflicting AI outputs become proposals.
- Bind confirmation to substantive judgment content and located original passages; preserve history and ignore unrelated metadata changes.
- Add conservative schema migration and reject old kernels lacking assessment protocol 1.
- Restore reproducible installation ZIP builds, manifests and checksums; verify actual wheel installation, skill installation/upgrade/uninstall and legacy migration on Windows/Linux with Python 3.11/3.12.
- Publish the matched kernel and skill assets only after all CI checks pass; align download and migration instructions with this version pair.

## 2026-10-22 · Skill 2.3.3 + kernel 0.1.2

- Compatibility release for the English workspace layout: the skill now requires
  `patentkit >= 0.1.2` (0.1.1 still expects the old paths).
- Kernel 0.1.2: English paths/messages; quoted `title` placeholders in workspace
  templates so titles containing `": "` render valid YAML.
- Skill runtime, installers, documentation and release notes remain fully English.

## 2026-10-22 · Skill 2.3.2

- Full English edition: skill runtime (`SKILL.md`, `references/`, script messages, assets),
  installers, documentation, and release notes are now entirely in English.
- Repository paths renamed to English; install guide source file is
  `install-guide-for-colleagues.md` (the Release asset is `INSTALL-colleagues.md`).
- Kernel `patentkit` remains 0.1.1.

## 2026-10-22 · Skill 2.3.1

- Repository documentation, release notes, and installer messages translated to English.
- The one-page install guide is now shipped as `INSTALL-colleagues.md` (ASCII filename).
- Skill runtime content (`SKILL.md`, `references/`, script output, sample data) remains
  in Chinese because the skill targets Chinese patent practice.
- Kernel `patentkit` remains 0.1.1.

## 2026-10-22 · Skill 2.3.0

- Added `install-oneclick.cmd` for Windows: checks Python, installs the kernel wheel,
  extracts the skill package, and runs `install.ps1 -Client both` (supports `--quiet`).
- Added the one-page install guide (now `INSTALL-colleagues.md`).
- Build-time validation requires these files in every release package.

## 2026-10-22 · Skill 2.2.0

- Added `agents/openai.yaml`: the desktop app shows a localized name and description,
  and `@` inserts a default prompt.
- Build-time validation and regression tests for the metadata.

## 2026-10-22 · Skill 2.1.0 / kernel 0.1.1

- Extracted the `scripts/` execution layer (status/validate/gates/report/check).
- Added the standalone installer (installers + manifest + synthetic sample workspace).
- Added cross-client test assets (Claude Code / Codex CLI).
- Kernel: fixed a hint that could echo a historical target ID; unified versioning.
