# Changelog

## 2026-10-28 · Unreleased — Patent Research Skill 4.0 WP-0..WP-F：可选扩展 patent_intel（对应蓝图 F/T/B/A/C/D/E/O 各工作包）

**新增 `extensions/patent_intel`（独立可选 wheel，最小安装零第三方依赖）**

- WP-0 边界层：版本化记录契约（schema_version/owner/created_at/extra 保留）、
  sidecar 状态目录（`.patent-intel/`，绑定工作区、删除即卸载且内核校验不变）、
  safe IO（原子写/UTF-8/LF/路径禁越界/大小上限/文件锁）、只读 kernel_bridge
  （动词白名单 + 写入型旗标拒绝，ADR 0001 机器校验）。
- WP-A 检索闭环：特征抽取（否定/数值/可选分级）、受控扩词（来源+关系全程
  provenance，LLM 挂点可选且不内置）、查询族规划（CNIPA ≤3 AND 仅在 CNIPA
  渲染层施加）、确定性 BM25 + RRF + 家族坍缩、覆盖/增量收益诊断、引证扩展
  任务、自适应控制器（停止原因如实记录，停止≠查全）、CLI `query plan/validate`
  与 `recall report`。
- WP-B 来源治理：能力矩阵（不支持字段报错不伪造）、cnipa/crossref 适配器复用
  内核 fetch 契约、号位归一（原文保留）、家族视图（未知家族不合并）、令牌桶
  + 指数退避（403/429 即停）、断点续采（页指纹幂等）、raw SHA-256 审计账本、
  OPS 适配器（OAuth/限速/断点，契约级测试、未实测联网，support_level=partial）、
  NPL 证据链（书目元数据≠披露证据，预印本/正式版分离）。
- WP-C 文档理解：命名空间无关 XML（DOCTYPE/ENTITY 一律拒绝）、权项从属树
  （悬空引用进 unresolved）、锚点四重绑定（raw_sha256/段落/text_hash/解析器
  版本，漂移即 stale）、OCR 低质降级不可自动引用、PDF 走 docling 选装。
- WP-D 证据与建议：特征×对比文件×证据矩阵（supported/linked/no_evidence 显式
  分格）、指纹变更→投影 stale、claim chart 草稿（组合假设≠创造性结论）、修改
  提案强制 requires_human_review + 内核门引用；CLI `evidence build` /
  `advisory review`。
- WP-E 态势（可选）：家族去重聚合（家族数与文献数分开）、缺失字段显式桶、
  离线 CSV/Markdown 报告、边界声明固定（稀疏≠技术空白）；CLI `landscape report`。
- WP-F：检索基准协议（`benchmarks/retrieval/` manifest schema + 冒烟夹具）、
  家族级评分器 `tools/score_retrieval.py`（空 gold 不默认满分、审计失败 exit 1、
  主题级 bootstrap CI）、统计单源 `tools/report_benchmark_stats.py`、安全/隐私
  边界测试、回放稳定性测试。
- 发行（O）：扩展 wheel 由 `build_skill_release.py` 产出到 `dist/extension/`（独立
  SUMS，不进 manifest/安装器/publish 名单）；release doctor 增 `extension-wheel`
  检查；CI 装 torch-free 扩展并跑 pytest 回归套件；`research/scripts/recall.py`
  薄封装（缺扩展 exit 3 + 安装指引）；SKILL/evals 新增召回增强意图与零命中
  边界用例（旧用例不误路由）。
- 参考：`docs/architecture/`（4.0-system/contracts/source-capabilities/
  document-model）、`docs/adr/0001 内核边界`、`0002 sidecar`、
  `docs/retrieval-evaluation.md`、skill references research 09/10、drafting 18、
  discovery 04（中英镜像齐备）。
- 兼容矩阵：skill 3.8.0 / kernel 0.9.0（protocol 1）不变；扩展兼容
  `patentkit >= 0.8.0`；扩展自身版本独立（当前 0.1.0），不参与 skill↔kernel
  版本配对。


## 2026-10-28 · 3.8.0 / patentkit 0.9.0 — explicit-LF kernel writes (cross-platform byte stability)

**Kernel 0.9.0** (patch `patentkit-0.1.2-to-0.9.0.patch`, SHA-256 `89aa48d5…`)

- Explicit `newline="\n"` on all 31 previously implicit `write_text` call sites (init
  template copies, assessment/backfill/census JSON, review CSV+JSON worksheets, fetch
  artifacts and logs, gate trackers, report/map/provenance/figures, delivery, revise,
  migrate, index, ingest, deadlines, chain, bibsync, cnipa). Kernel outputs are
  byte-identical across Windows and Linux — root fix for the benchmark fixture line-ending
  drift measured in 3.7.0 (115 files); the generator's `_force_lf()` stays as a safety net.
- New invariant regressions: `test_init_writes_lf_only` (template copy path) and
  `test_pipeline_writes_lf_only` (every kernel-touched byte in the golden pipeline;
  fixture-written files excluded). Kernel suite 761 tests: 747 passed / 14 skipped /
  0 failed. Binary write sites (mkstemp + `fdopen("wb")`, `shutil.copy2` evidence
  originals) intentionally untouched.
- Behavior: the review CSV worksheet (utf-8-sig) is LF on every platform now (was CRLF on
  Windows, matching Linux/CI which already produced LF); existing CRLF files on disk are
  not rewritten in bulk — they normalize only when the kernel itself rewrites them.

**Skill 3.8.0**

- Paired release for the kernel LF discipline: no skill-behavior changes, zero workspace
  migration, assessment protocol 1 unchanged.
- `bump_version.py --check` now also pins the two prose kernel-version statements in
  `release/patches/README.md` ("current kernel is **x**", "declares version `x`") — the
  0.8.0 round left both stale at 0.7.0; repaired this round.

## 2026-10-27 · 3.7.0 / patentkit 0.8.0 — revision↔conclusions linkage (V038), benchmark to 9 cases, structured support citations

**Kernel 0.8.0** (patch `patentkit-0.1.2-to-0.8.0.patch`, SHA-256 `f99d0e00…`)

- V038 revision↔conclusions linkage: `revise apply` marks existing conclusions stale
  (generated trackers exempt), `revise status` exits 1 while stale, `revise close` refuses
  until re-confirmed (`revise reconfirm --by`) or waived with a reason (`--waive --reason`,
  recorded in the ledger round); validate reports unprocessed stale / edited-after-reconfirm /
  waiver-not-in-ledger as errors. State in `05_novelty_conclusions/conclusions_state.yml`
  (zero migration).
- D-019 structured support citations: optional `citations` on `support_mapping` rows
  (confined `source` + `L`-range/`[NNNN]` `locator`); the drafting audit fails citations
  that do not resolve. Backward compatible.
- `build_kernel_patch`: normalize synthetic `a/b/`+`b/a/` paths for added/deleted files —
  empty new files previously produced headers `git apply` cannot parse.

**Skill 3.7.0**

- Benchmark expanded to 9 synthetic cases (review P1-1 range 8–12): new bm04 OCR (citation),
  bm05 valve (omission), bm06 drone light show (misjudgment, 5 docs), bm07 fridge (omission),
  bm08 3D-print monitoring (citation), bm09 smart lock (misjudgment, 4 docs). Totals: 37 features /
  417 judgment points / 142 citations (scorer vocabulary), gold gate `--gate perfect` green.
- Drafting references 13/15 updated in zh + en (V038 flow, structured citations);
  release notes and pairing updated for 3.7.0 / 0.8.0.
- Full verification: kernel 745 passed / 14 skipped on the dev tree and again on the
  CI-reconstructed patched tree; benchmark gold gate 9/9; pairing/evals/terminology/
  confidentiality guards green.

## 2026-10-27 · 3.6.0 / patentkit 0.7.0 — release doctor + synthetic patent benchmark

> Kernel unchanged (0.7.0; no rule or protocol changes). Pure release-engineering and
> evaluation-infrastructure round.

**Skill 3.6.0**

- `tools/release_doctor.py`: one-command release health check. `--offline` (in the CI check
  job): pairing points, four guard scripts, dual-zip build + manifest deep check + SUMS
  cross-check vs the publish script's asset list, per-platform installer smoke tests
  (one-click installs the kernel wheel in a throwaway venv). `--release` (new CI job after
  publish, ubuntu+windows matrix): audits the actual GitHub releases — tag/draft/latest/
  target_commitish, asset lists, per-asset sha256 vs SUMS, released-zip manifest, notes
  provenance — then reruns installer tests and an isolated kernel-wheel import against the
  downloaded assets (api.github.com only). Kernel tag not re-released in a no-kernel round
  is reported as a note, not a failure.
- `benchmarks/`: public synthetic benchmark measuring judgment behavior — citation accuracy
  (verbatim verification via the kernel's `assessment.passage`), technical-feature omission
  (ground truth × `feature_mapping`), and misjudgment rate (role/novelty/relevance/feature
  status/matrix cells/required citations; 40+ judgment points per case). Three cases with
  designed traps; each ships a participant scaffold (`workspace/`) and a reference solution
  (`gold/`, built through the real kernel commands, 0 errors / 0 warnings).
- `tools/score_benchmark.py`: reuses kernel validation (0 errors required) — no second rule
  set; `--suite --gold --gate perfect` locks scorer semantics in CI.
- `tests/test_benchmark_scorer.py`: controlled-corruption tests asserting the metrics
  degrade or the kernel rejects first (V029 fabricated-quote path).
- `tools/check_no_workspace_data.py`: allows the `benchmarks/` prefix (synthetic corpus
  justification); real data remains forbidden.

## 2026-10-26 · 3.5.0 / patentkit 0.7.0 — P0–P4 release integration (local; not pushed, not published)

> Version-paired release-integration snapshot of the P0–P4 upgrade. Skill **3.5.0** requires
> kernel **0.7.0**; `release/patches/patentkit-0.1.2-to-0.7.0.patch` reconstructs the kernel
> from the verified public 0.1.2 sdist. No GitHub Release or remote push was performed.

**Kernel 0.7.0** (patch `patentkit-0.1.2-to-0.7.0.patch`)

- P0: `contracts.py` (12 versioned schemas, canonical fingerprints) + `workspace_upgrade.py`
  (non-destructive `upgrade check/apply`).
- P1: `source_intake.py`, `discovery.py`, `discovery_handoff.py` (`intake`/`discovery` commands,
  G-I control layer, G-I-gated handoff).
- P2: `draft.py` (DraftingPlan/atoms/claims/support, G-D audit, `concept`/`review_draft` gate,
  impact propagation).
- P3: `figure_plan.py` (`figures plan/render/validate`, deterministic SVG + optional PNG,
  F-001…F-014).
- P4: `delivery.py` (frozen PatentDocumentModel, DOCX/optional PDF, delivery manifest, human
  sign-off bound to the manifest fingerprint, `deliver check` E-001…E-012,
  `draft gate --to release_ready`; CNIPA XML `not_attempted`).
- Full regression: **737 passed / 11 skipped / 0 failed**; golden snapshots unchanged;
  G-S/V001–V037/protocol-1 semantics untouched.

**Skill 3.5.0**

- New `patent-discovery` payload (zh + en references 00–03, glossary) and three-skill release
  engineering (full package + drafting-only package; installers accept all three skills).
- Drafting references 14–17 (structured pipeline, claims/support, professional figures,
  delivery pipeline; zh + en) and SKILL hard constraints 9–12; evals 33 cases / 3 skills;
  terminology pairing `drafting 00,09–17` + 12 new anchors.
- Version pairing updated across builders, installers, CI, tests, docs, notes and the patch
  pointer; `tools/bump_version.py --check` green; `tools/build_kernel_patch.py` fixed to apply
  patches in a real temporary git repository (git 2.53 no-op in non-repo dirs) and now verifies
  the applied tree byte-for-byte against the dev tree, plus an optional `--verify-against`
  same-version equivalence check.

**Upgrade notes**: install `patentkit-0.7.0` first; overwrite the skill packages with `--force`;
existing workspaces stay readable — run `python -m patentkit upgrade check` (read-only) and then
`upgrade apply` to add `10_discovery/` and `11_delivery/` non-destructively.

## 2026-10-26 · Unreleased — P4 complete delivery (development line)

> **Local development line; no release, no push.** P4 of the upgrade plan: frozen
> PatentDocumentModel, DOCX/PDF delivery artifacts, delivery manifest with hash checks and
> human sign-off bound to the manifest fingerprint, `release_ready` gate, and the CNIPA XML
> research interface. Kernel distribution patches are rebuilt at release-integration time.

**Kernel** (`patentkit/delivery.py`, `patentkit/contracts.py`, `patentkit/draft.py`)

- `deliver build` — builds one frozen **PatentDocumentModel** (claims/paragraphs/abstract/figures,
  input hashes, gates snapshot, fingerprint) from the current `review_draft` state, then generates
  a review-copy DOCX (claims / specification / abstract / figures with embedded PNG when Pillow is
  available) and an optional PDF preview via a local converter; a missing converter is reported as
  not generated (never faked). Delivery artifacts live under `11_delivery/`.
- `deliver check` — E-001…E-012: missing/stale snapshot, artifact hash mismatch, manuscript vs
  model inconsistency, missing paragraphs, unknown figure citations, changed research gates,
  draft-audit errors, unsigned/expired sign-off, manifest schema, missing independent claim or
  abstract, false official-format claims; W-001/W-002 warnings.
- `deliver sign` — human sign-off bound to the manifest content fingerprint (excluding the
  sign-off); any later manifest change invalidates it (E-009).
- `draft gate --to release_ready` — requires the current `review_draft` state, zero delivery
  check errors and a valid sign-off; the state records the manifest hash and is demoted to
  `concept` when the delivery or model becomes stale.
- CNIPA XML stays `not_attempted`: `export_cnipa_xml()` fails closed, `cnipa_format_notes.md`
  documents the research checklist, E-012 blocks false compliance claims.
- Tests: 18 new delivery tests (happy path, every deliberate failure, PDF present/absent, CNIPA
  fail-closed, CLI); kernel regression **737 passed / 11 skipped / 0 failed**; golden snapshots
  unchanged.

**Skill payload** (`drafting/`)

- New reference `17-delivery.md` (zh + en mirror): inputs, commands, manifest/validation files,
  E-001…E-012 codes, sign-off/invalidation semantics, CNIPA XML status and pre-delivery checklist.
- `SKILL.md` (and English mirror): Line D step D8 (delivery), hard constraint 12 (frozen-snapshot
  delivery, human sign-off, no compliance/submission claims before CNIPA XML verification),
  result-format row "delivery state"; reference table entry.
- Evals grew to 33 cases (delivery trigger; submit-claim refusal); terminology pairing extended
  to drafting 17 with four new anchors.

**Unchanged**: G-S-01…05, evidence levels, assessment protocol 1, V001–V037, revise/provenance/
attest/ledger semantics, golden snapshots. No release has been published; `release_ready` is an
internal delivery gate, not official-filing compliance.

## 2026-10-26 · Unreleased — P3 professional figures (development line)

> **Local development line; no release, no push.** P3 of the upgrade plan: structured figure
> plans, deterministic rendering and figure-text validation. Kernel distribution patches are
> rebuilt at release-integration time.

**Kernel** (`patentkit/figure_plan.py`, source tree)

- `figures plan` — derives figure-plan skeletons from the P2 drafting plan / claim atoms
  (system block diagram + method flowchart by default or from `drawing_requirements`), with
  deterministic reference signs; legacy `*.figure.yml` specs are normalized.
- `figures render` — deterministic black-white SVG (grid/chain layout, orthogonal edges, marks;
  no timestamps/scripts/external links, same plan → identical bytes); optional 300-DPI PNG via
  Pillow (missing dependency is reported as not generated, never faked).
- `figures validate` — locatable findings F-001…F-014: schema, duplicate ids, dangling/self/
  duplicate edges, isolated nodes, type-required content, marks (in-figure duplicates are errors;
  same sign across figures is a warning requiring human confirmation), layout options, manuscript
  `图N` citation closure, drafting-plan coverage and support-mapping figure references. Reuses the
  existing V033 mark check instead of duplicating it.
- The renderer cannot create or delete parts/edges: geometry comes only from the plan. Rendering
  refuses structurally invalid plans.
- `draft audit` gained D-018 (figure validation findings; errors block `review_draft`).
- `contracts.py`: figure nodes accept numeric ids/legacy compatibility, optional `kind`,
  `spec_refs` and `notes`; tests: 21 new figure tests; kernel regression
  **717 passed / 11 skipped / 0 failed**; golden snapshots unchanged.

**Skill payload** (`drafting/`)

- New reference `16-figures.md` (zh + en mirror): figure-plan schema, commands, F-001…F-014
  codes, deterministic-rendering contract and human-review discipline.
- `SKILL.md` (and English mirror): Line D step D7 (figures), hard constraint 11 (structured
  figure plan, no text-to-image-only drawings, human visual review mandatory), result-format row
  "figure consistency"; reference table entry.
- Evals grew to 31 cases (figure trigger; text-to-image refusal); terminology pairing extended
  to drafting 16 with three new anchors.

**Unchanged**: G-S-01…05, evidence levels, assessment protocol 1, V001–V037, revise/provenance/
attest/ledger semantics, golden snapshots.

## 2026-10-26 · Unreleased — P2 structured drafting (development line)

> **Local development line; no release, no push.** P2 of the upgrade plan
> (`docs/patent-skill-upgrade-implementation-plan.md`): structured drafting model and the
> two-state writing gate. Kernel distribution patches are rebuilt at release-integration time.

**Kernel** (`patentkit/draft.py`, source tree)

- `draft plan` — generates a schema-valid DraftingPlan from a **human-confirmed** candidate and
  its confirmed facts, snapshotting the research gates and binding the candidate content
  fingerprint (`idea_fingerprint`; a changed candidate marks the plan stale, D-003).
- `draft atoms import|review` — claim-feature atoms with fact references; imported as `pending`,
  human confirmation is bound to the **atom content fingerprint** (editing text invalidates it,
  D-017), so self-claimed confirmation cannot survive content changes.
- `draft claims import` — structured claims validated for numbering (contiguous from 1), at least
  one independent claim, earlier-parent references, cycle rejection and known atom ids.
- `draft support import|review` — claim/atom → paragraphs/facts/figures support matrix with
  human semantic review; empty paragraph mapping is rejected as not-covered.
- `draft audit` — G-D findings D-001…D-017, reusing the existing `provenance` and `revise`
  checks instead of re-implementing hashing or revision ledgers.
- `draft status` / `draft gate` — dual-state writing gate: `concept` by default; `review_draft`
  requires zero audit errors, **G-S-01/02/03 PASS**, fingerprint-current atoms, confirmed support
  review; a `bundle_fingerprint` makes any model change stale and reverts the state.
- `draft impact --claim-no N` — change propagation to affected atoms/paragraphs/figures/facts and
  dependent claims (plan §5.2 item 6), feeding the existing revision loop.
- `contracts.py`: `drafting_plan` gains optional `idea_fingerprint` (staleness binding).
- Tests: 17 new draft tests (structure, audit, gate, staleness, impact); kernel regression
  **696 passed / 11 skipped / 0 failed**; golden snapshots unchanged.

**Skill payload** (`drafting/`)

- New references `14-drafting-pipeline.md` and `15-claims-and-support.md` (zh + en mirrors) with
  the command table, G-D audit codes, dual-state gate rules and the claim/support checklist.
- `SKILL.md` (and English mirror): Line D structured drafting, hard constraints 9/10
  (fingerprint-bound atom confirmation; `review_draft` gate), result-format row "structured state".
- Evals grew to 29 cases (structured-claims trigger; review_draft-gate refusal); terminology
  pairing extended to drafting 14–15 with five new anchors.

**Unchanged**: G-S-01…05, evidence levels, assessment protocol 1, V001–V037, revise/provenance/
attest/ledger semantics, golden snapshots. `release_ready` remains unimplemented (P4).

## 2026-10-26 · Unreleased — patent-discovery skill (P1 development line)

> **Local development line; no release, no push.** Describes the P1 delivery of the upgrade
> plan (`docs/patent-skill-upgrade-implementation-plan.md`): the kernel gains the discovery
> contracts/commands and the repository gains the third skill payload. Kernel distribution
> patches are rebuilt at release-integration time, not here.

**Repository / skill payload**

- New `discovery/` skill payload (`patent-discovery`, metadata version 3.4.0): Chinese-primary
  `SKILL.md`, four references (`00-discovery-protocol`, `01-material-intake`,
  `02-facts-and-ideas`, `03-human-review-and-handoff`), shared `glossary.md` copy, English
  mirrors under `references.en/`, and desktop metadata (`agents/openai.yaml`).
- Release builder now ships three skill payloads in the full package (drafting single package
  unchanged); installers accept `patent-discovery`; evals grow to 27 cases anchored to three
  `SKILL.md` files; terminology pairing extended to discovery `00-03` with a three-way
  byte-identical glossary; secrecy guard covers the new payload.
- Repository README documents the development line; no release assets were published.

**Kernel capabilities exercised by this skill** (source tree; reach the public patch later)

- `patentkit.contracts`: new `discovery_handoff` contract and idea *content* fingerprint
  (status fields excluded from confirmation binding).
- `patentkit.source_intake`: md/docx/pdf_text/py/m/csv/json/controlled Simulink text intake with
  SHA-256 + locator scheme + parsed cache; fail-closed on binary models, path/symlink escapes,
  oversized files; no execution and no network.
- `patentkit.discovery`: schema-validated fact/idea import with source-hash binding, human
  decision ledger bound to content fingerprints, fact review, search-priority ranking and the
  G-I check layer (G-I-001…025).
- `patentkit.discovery_handoff`: G-I-gated research handoff drafts (handoff JSON + query seed +
  target draft + audit event); never writes research directories and never produces G-S results.

**Unchanged**: G-S-01…05, evidence levels, assessment protocol 1, V001–V037, revise/provenance/
attest/ledger semantics, golden snapshots.

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
