# Changelog

## 2026-10-25 · Skill 3.4.0 / kernel 0.6.0

Census-evidence gate rework + data-source chain fixes + installed-reference closure
(from the review's P0 trio, "普查证据与安装引用一致性"):

- **G-S-04 verifies census evidence, not array shapes** — new kernel module
  `patentkit/census.py`: each subject (`near_prior_art`/`family`) needs a valid census
  record per dimension (doc number, source, query id, time, status, raw artifact +
  sha256). Zero hits count as complete; not-queried / `partial` / `failed` /
  missing-or-modified artifact do not. Records are written by `fetch-bigquery --fill`
  from the archived artifact (one row per queried doc, zero hits included) or by hand
  per reference 05. The gate report gains a per-object failure detail list.
- **validate V037** — a census record that exists but is broken (missing fields /
  artifact deleted or modified / doc mismatch / status contradicting the artifact) is an
  error; honest `partial`/`failed` stays a gate matter. Candidate schema gains the
  managed `census` property (template + `migrate`).
- **fetch-bigquery chain fixes**: dry-run pre-check and execution share the same SQL and
  `query_parameters`; the cited-by subquery returns the *citing* document number; archive
  names carry date/target/run-time and refuse silent overwrite; `--fill` requires the
  artifact inside workspace `02_search_logs/`, cross-checks the bound log's target,
  touches only the passed target, skips human-reviewed candidates unless `--force`
  (audited to `02_search_logs/backfill_audit.jsonl`), stays idempotent, and keeps human
  values on conflict; cost estimates use dry-run `total_bytes_processed` with a
  `--max-cost-usd` budget cap (default 5).
- **backfill (abstracts) review guard**: candidates with human review traces are skipped
  by default (`--force` overrides, audited to the same file).
- **Installed-reference closure**: 66 broken relative links fixed across both skill
  payloads (cross-skill links replaced with the documented skill handoff; both English
  mirrors re-pointed at their sibling files); new `tools/check_reference_links.py` runs
  in CI on the repo tree and on both unpacked release zips, with unittest coverage.
- Golden pipeline gains a census artifact + fill stages (fill → reviewed-skip → force +
  audit). Kernel docs: reference 05 rewritten for both languages; `docs/data-sources.md`
  contract updated. Deferred: revise↔conclusions linkage (its reserved V037 number is
  now used by the census rule; the linkage rule will take V038).

Suite: 511 passed / 9 skipped (dev tree, Windows) + 44 regression tests (both golden
pipelines); skill repo 14 unittests; pairing/evals/terminology/guards/link closure all
green.

## 2026-10-25 · Skill 3.3.1 / kernel 0.5.1

Data-source contract rehearsal + drafting golden regression (patch level; no rule changes):

- **Contract rehearsal recorded in `docs/data-sources.md`** — every offline contract path
  exercised on the released kernel + real CLI (dry-run zero-write, `--run` dual guards,
  `--fill` idempotent backfill, OPS XML end-to-end ingest, V-series firing as designed);
  credential-day runbook added. Real network run still pending credentials: no GCP/OPS
  credentials on this machine, `bigquery.googleapis.com` blocked (timeout),
  `ops.epo.org` reachable (403 without key, as expected).
- **Drafting golden regression** — `test_golden_pipeline_drafting.py`: 10 snapshots over
  provenance scan/check, figures check/draw (SVG), deadlines list/check,
  revise apply/status/close and the merged `check --json`, on the shared golden fixture
  (+ `09_deadlines/` ledger with a deliberately incomplete entry, + grade-B provenance
  entry NUM-003), with a run-twice determinism test.
- **MCP re-assessment** — stays frozen with evidence: 12 MCP tools vs 23 passthrough + 5
  dedicated CLI commands, no MCP-only capability exists, three re-trigger conditions
  documented in `docs/data-sources.md`.
- Three kernel CLI fixes, each with a regression test: `check --json` now emits a single
  merged `{"check", "gates"}` JSON document (was two concatenated documents; composite
  exit-code semantics unchanged); `fetch-bigquery --fill` reports malformed artifacts as
  `[FATAL]`/exit 2 (was a bare traceback); `deadlines --root` accepted in both argument
  positions (`list --root X` used to be an argparse error).
- Suite: 539 passed / 2 skipped (dev tree, Windows), both golden pipelines green.

## 2026-10-25 · Skill 3.3.0 / kernel 0.5.0

Data-source presets + formalized access contract (no rule changes; nothing connected):

- **`patentkit fetch-bigquery`** — G-S-04 census skeleton: dry-run by default (targets,
  skeleton SQL with a re-validate-against-current-schema marker, cost template);
  `--run` requires google-cloud-bigquery + GCP credentials (dry-run query first for
  bytes-billed → cost estimate → confirmation → archive raw+log per contract);
  `--fill <raw> [--apply]` backfills family/cited_by from the archived artifact
  (empty arrays only, offline-testable).
- **OPS XML ingest** — `read_raw` accepts `.xml` (OPS exchange-document exports,
  localname-based namespace-agnostic parsing, zh-first titles/abstracts).
- **Access contract** formalized in `docs/data-sources.md` (raw-first, honest logs,
  ingestable formats, dry-run default / explicit credentials, registration + evals)
  plus the OPS registration & rate-limit strategy (quota figures deferred to the
  official portal, never hard-coded).
- CI sentinel adds `fetch_bigquery.py`; the unsupported-format error now lists the
  OPS-capable `.xml`. Suite: 540 passed / 9 skipped (dev tree).


## 2026-10-25 · Skill 3.2.1 / kernel 0.4.1

Golden end-to-end regression release (no rule or CLI changes):

- **`regression_tests/golden/`** — fixed synthetic workspace + per-stage expected snapshots:
  the pipeline (ingest → AI assess → human confirm with post-assessment fingerprints →
  validate → gates → ledger → queryplan → report → export-docx → map → chain → one revise
  round) is asserted stage by stage; a determinism test runs it twice and requires identical
  normalized output. Volatile values (generated timestamps, today's date, workspace path)
  are redacted before comparison; fixture dates are asserted data. Snapshots regenerate via
  `GOLDEN_UPDATE=1` and must be reviewed line by line.
- Building the golden fixture surfaced and locked real semantics: the confirmation protocol
  rejects pre-assessment fingerprints (stale by design), V033's heuristic warn, the
  G-S-02 min-over-all-axes N/A semantics, and ingest's `<id>-<bibtex-key>.json` file naming.
- Skill side: paired version bump only. Kernel patch `patentkit-0.1.2-to-0.4.1.patch`
  rebuilt via the scripted tool (golden assets enter the auditable patch).


## 2026-10-25 · Skill 3.2.0 / kernel 0.4.0

Planning-and-revision kernel release (paired skill bump; assessment protocol unchanged):

- **`patentkit queryplan`** — per-axis search coverage planning: registered vs executed
  sub-queries, G-S-02 verified buffer (reference-05 criteria), uncovered concept groups with
  deterministic supplementary-query skeletons; `--apply` appends to the query library
  append-only (existing indices never renumbered, comments preserved verbatim). `status`
  hints point here when G-S-02 has not passed.
- **`patentkit revise`** — the revision loop (drafting reference 13) as code: structured
  local patches (every find must match exactly once → otherwise refuse with zero writes),
  patch + ledger + registry re-bind in one transaction, post-round integrity check; an
  unlogged edit is `revise status` exit 1 and validate V036; 3-round-per-issue escalation.
- **`patentkit chain`** — evidence-chain panorama (logs → candidates → D-list → runs →
  conclusions → ledger → gates → revision ledger) as one offline HTML page.
- Validation rules V035 (ledger structure — error) / V036 (unlogged edit — warn, strict
  escalates); range now V001–V036.
- References 02/05 (research) and 13 (drafting) updated in both languages; kernel patch
  `patentkit-0.1.2-to-0.4.0.patch` rebuilt and verified by `tools/build_kernel_patch.py`.
- The 3.1.0 release itself was produced with `tools/bump_version.py` + a CI `--check` step;
  this release dogfooded `--kernel-to` end to end (the residue scan caught nine kernel
  pairing points the manual checklist never listed — two installers, self_test's
  REQUIRED_KERNEL, SKILL companion lines, test wheel names).


## 2026-10-25 · Skill 3.1.0 / kernel 0.3.0（未变）

Release-engineering and distribution-closeout patch release (no kernel, no rule changes):

- **`tools/bump_version.py`** — the hardcoded skill↔kernel↔release pairing points are now
  an explicit list: targeted replacement → consistency check → repo-wide residue scan for
  the old version (with an argued whitelist for historical records). `--check` mode runs in
  CI on every push, so pairing drift is caught at push time instead of at release time.
- **`tools/build_kernel_patch.py`** — the manual kernel-patch rebuild (mirror dev tree →
  scratch diff → fix double prefixes → verify apply-ability) as one command, with two
  machine gates: the CI-equivalent `git apply --directory` under pinned
  `core.autocrlf=false`, and a byte-identical applied-tree comparison against the released
  patch. Used to rebuild and verify the 0.1.2→0.3.0 patch (the released patch is unchanged).
- **research reference 08 English mirror** (`references.en/08-figures.md`); terminology
  pairing extended to research 01–08 — both skills' references are now fully bilingual.
- **Distribution closeout**: desensitized self-test screenshot
  (`docs/assets/self-test-terminal.png`, rendered by `tools/render_terminal_shot.py` from a
  real self_test run on the synthetic sample) and marketplace listing copy
  (`docs/marketplace-listing.md`); two open items on the distribution checklist cleared.
- `evals/check_terminology.py` pairs research 01–08; CI gains a version-pairing step.


## 2026-10-25 · Skill 3.0.1 / kernel 0.3.0（未变）

Drafting-skill English mirrors (translation-only patch release):

- `drafting/references.en/`: SKILL.en.md + 00-prerequisites + 09–13 — the complete English
  mirror of the patent-drafting skill; terminology consistent with the shared glossary.
- `research/references.en/`: SKILL.en.md refreshed to the 3.x split layout; README notes
  where each mirror lives (research 08 stays Chinese-first for now).
- `evals/check_terminology.py`: drafting zh↔en pairing (00, 09–13) enforced; shared anchor
  list extended to the drafting vocabulary (evidence ledger / revision loop / policy radar /
  office action / response draft / disclosure / illustrative example / figure-mark …).
- Kernel unchanged at 0.3.0; no workspace migration; skill versions paired at 3.0.1.


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
