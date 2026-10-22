# Changelog

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
