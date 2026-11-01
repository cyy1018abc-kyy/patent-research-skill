# patent-research-skill

> An **Agent Skill** for patent prior-art search, novelty/inventiveness self-check,
> evidence-chain management, and acceptance gates (G-S).
> Works with Claude Code, Codex CLI, and the Codex desktop app.

This repository contains only distributable assets: the skill source, installers,
the release builder, and release notes.
**No real project data, patent drafts, target IDs, or candidate IDs are included**;
the sample workspace is synthetic (`TGT-0002`).

## Skill 4.1.0 / kernel 0.10.0 — adaptive retrieval: identity/accounting discipline, evaluator & policy scheduling, fusion pipeline, preregistered ablation

Headline of this release — the retrieval layer upgrade (extension **patent_intel 0.2.0**;
kernel unchanged), per the adaptive retrieval roadmap (Stage 0–3 + WP-L1/L2/L3/L5):

- **Identity & accounting discipline**: queries carry explicit `feature_ids`; a document
  id never masquerades as a family id (`family_basis`, unknown refuses family ids);
  candidate / suspected / confirmed relevance are separate buckets (only explicit
  marking moves a family between them); coverage is recorded per technical feature —
  the old defect that reported feature coverage as always-zero is fixed.
- **Evaluator & policies**: versioned `RetrievalGapReport` (unknown never degrades to
  not_found; proxy metrics only without a gold set), the disclosed/partially/not_found/
  unknown feature state machine, gap→action mapping, and a benefit-driven
  `MarginalUtilityPolicy` (deterministic, explainable, honest soft stops) with every
  decision recorded — the default GapFirstPolicy keeps the legacy order.
- **Data foundations**: content-addressed `RawArtifactRegistry` (hash-verified, physical
  paths untouched), multilingual `PublicationRecord`, field-level `FieldConflictLog`
  (human confirmations are never overwritten), uncertain family refs deferred — never
  merged; `CorpusManager` with idempotent imports, restorable corpus snapshots, frozen
  evaluation corpora, and index manifests whose failed builds never invalidate the
  previous active index.
- **Fusion & reranking**: per-query weighted-RRF fusion with honest channel accounting
  (errored/absent channels recorded, never zero-filled), optional rerank stage behind
  a contract-checked interface (`IdentityReranker` default), §8.3 accounting on
  acquisition results, `recall --dense`.
- **Preregistered ablation (ABL-1, 312 test topics, zero network)**: A0 reproduces the
  archived Phase V baseline byte-identically (26.18%); **RRF fusion beats max merging
  (+2.15pp, CI [+1.20,+3.11]) — the program's first gate-passing positive claim**;
  the roadmap's initial BM25F weights are rejected (−2.93pp, significant negative);
  no config beats uniform BM25 overall. The Phase V gate stays FAILED — claims are
  strictly scoped to merger choice.
- Live sources stay `partial` until the runbook rehearsal completes
  ([docs/live-rehearsal-runbook.md](docs/live-rehearsal-runbook.md)).

## Skill 4.0.0 / kernel 0.10.0 — the patent-audit skill: coverage ledger, adversarial validation, independent review

Release 4.0.0 shipped a **fourth skill payload**, `audit/` (`patent-audit`), adapting
the six-phase harness of Cloudflare's `security-audit-skill` (MIT) to the patent-search
domain (attack-surface content not ported; see [docs/adr/0004-audit-harness.md](docs/adr/0004-audit-harness.md)
and Credits below):

- **Coverage ledger** (`12_audit/run-<N>/audit-ledger.json`): one stateful unit per
  element × data source × classification symbol; coverage is the ledger, not a narrative.
- **Adversarial validation + independent review**: every "element ↔ prior art" mapping
  goes to a disproof-first verifier, then a fresh reviewer re-checks every verbatim
  quote and locator; confirmed records carry an independent-review mark.
- **Three-verdict findings** (`findings.json`): confirmed / needs_validation / rejected,
  with impact categories (X/Y/A) separated from evidence certainty; two zero-dependency
  Python validators (`audit/scripts/validate_findings.py`, `validate_ledger.py`) enforce
  the contract.
- **Audit-mode benchmark regression**: `tools/score_audit_findings.py` scores findings
  against the bm01/bm02 gold truth (mapping coverage/precision, evidence integrity,
  verdict discipline); CI locks the gold self-check at perfect.

The 3.5.0 P0–P4 capability base and the 3.10.0/3.11.0 guideline adaptation remain
unchanged ([docs/patent-skill-upgrade-implementation-plan.md](docs/patent-skill-upgrade-implementation-plan.md)):

- **P0** versioned data contracts + non-destructive workspace upgrade (`upgrade check/apply`);
- **P1** the third **patent-discovery** skill (material intake → technical facts → patent
  candidates → human confirmation → research handoff, G-I control layer);
- **P2** structured drafting (DraftingPlan → ClaimAtom → Claim → SupportMapping, G-D audit,
  `concept`/`review_draft` writing gate) and change-impact propagation;
- **P3** the professional figure engine (`figures plan/render/validate`, deterministic SVG,
  F-001…F-014 figure-text checks);
- **P4** complete delivery (frozen PatentDocumentModel → DOCX/optional PDF → delivery manifest
  with artifact SHA-256 → human sign-off bound to the manifest fingerprint → `release_ready`).
  CNIPA XML remains **not attempted** until independently researched and verified.

The kernel is reconstructed in CI from the public 0.1.2 sdist plus
`release/patches/patentkit-0.1.2-to-0.10.0.patch`; the full package ships all four skills.
The skill-matrix decision (2026-10-25, see
[docs/skill-matrix-plan.md](docs/skill-matrix-plan.md)) still describes the split into
**research** and **drafting** (OA merged into drafting), 3.6.0 additionally ships
`patent-discovery`, 4.0.0 additionally ships `patent-audit`, and 4.1.0 upgrades the
retrieval layer (extension 0.2.0). Everything below still
describes the 2.5.0 Chinese-primary + delivery-safety release, which 3.x inherits in full.

## Skill 3.6.0 — release doctor + synthetic patent benchmark

Kernel unchanged (0.7.0 at the time). Two additions for maintainers and evaluators:

- **`tools/release_doctor.py`** — one-command release health check. Offline mode runs
  pairing points, guard scripts, a fresh dual-zip build with manifest/SUMS deep checks and
  per-platform installer smoke tests; release mode audits the *actual* GitHub releases
  (assets, hashes vs SHA256SUMS, released-zip manifest, notes) and reruns installer tests
  plus an isolated kernel-wheel import against the downloaded assets.
- **[`benchmarks/`](benchmarks/README.md)** — a public benchmark of *synthetic* patent
  cases measuring citation accuracy (verbatim, via the kernel's own `passage` check),
  technical-feature omission, and misjudgment rate against per-case ground truth. Each case
  ships a participant scaffold and a reference solution; CI requires the reference
  solutions to score perfect (`--gate perfect`), and controlled-corruption tests ensure the
  scorer is not a rubber stamp. All publication numbers use the non-existent `ZZ` country
  prefix; no real application material may enter `benchmarks/`.

## Skill 2.5.0 highlights (inherited by 3.x)

Two headline changes over 2.4.0:

1. **Chinese-primary runtime.** `SKILL.md`, all 13 references and the assets are now the
   authoritative Chinese edition (the target practice is Chinese patent work); the English
   edition lives on as `references.en/` and is kept term-consistent by
   `evals/check_terminology.py`. A bilingual glossary (`references/glossary.md`) pins the
   terminology both ways.
2. **Delivery-safety layer (introduced in the 2.5.0 kernel series).** `export-docx` (workspace-verbatim .docx search
   report), `map` (offline self-contained HTML overview), `layout` (read-only 1+N portfolio
   view), `ledger` (evidence ledger; V034 rejects conclusions citing IDs outside it),
   `provenance` (numerical-claim A/B/C registry; V031/V032 fail closed), `figures`
   (mark consistency V033 + deterministic SVG), `deadlines` (statutory ledger), plus
   `scripts/self_test.py` for post-install self-checks.

Quality engineering added in the same release: `evals/` (14 trigger/refusal/boundary/format
cases, anchored to the SKILL description), `tools/check_no_workspace_data.py` (secrecy guard),
secrecy `.gitignore` rules, and a reconstructed `tests/conftest.py` so the kernel's full test
suite runs from the patched tree in CI.

Everything from 2.4.0 still holds: source provenance and judgment are separate ([assessment
protocol](patent-research-skill/references/07-assessment-protocol.md)); supported AI
assessments may count for G-S-02; G-S-03 requires explicit human confirmation bound to the
current judgment. CI reconstructs the kernel from the [verified public source and
patch](release/patches/README.md), builds both packages, and validates installation on
Windows/Linux with Python 3.11/3.12 before publishing.

## Download & install

Download the paired [Skill 4.1.0](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/skill-v4.1.0) and [patentkit 0.10.0](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.10.0) releases:

| Asset | Purpose |
|---|---|
| `patent-research-skill-v4.1.0.zip` | Full package: installs all four skills (patent-research + patent-drafting + patent-discovery + patent-audit), with installers + synthetic sample workspace |
| `patentkit-0.10.0-py3-none-any.whl` | Matching kernel: assessment protocol 1 + P0–P4 modules (contracts, upgrade, intake, discovery, draft, figures, delivery) |
| `install-oneclick.cmd` | Windows installer, also included in the ZIP |
| `INSTALL-colleagues.md` | One-page install guide (repo source: `release/install-guide-for-colleagues.md`) |

### Windows (one click)

Put the zip, the wheel, and `install-oneclick.cmd` (extracted from the zip) in the
same folder, then double-click `install-oneclick.cmd`.

### Manual (any platform)

```powershell
python -m pip install ./patentkit-0.10.0-py3-none-any.whl
Expand-Archive ./patent-research-skill-v4.1.0.zip -DestinationPath ./pkg
pwsh -File ./pkg/install.ps1 -Client both -Force
```

```bash
python3 -m pip install ./patentkit-0.2.0-py3-none-any.whl
unzip patent-research-skill-v4.1.0.zip -d pkg
chmod +x pkg/install.sh && ./pkg/install.sh --client both --force
```

After installation, restart the client:

- **Codex desktop**: open **Skills** in the sidebar, select "Patent Research", or type `@` to pick it.
- **Claude Code**: ask "use the patent-research skill to locate the workspace and run the self-check".

## Repository layout

```
research/                patent-research 技能：SKILL.md + references/(zh 01-08+glossary) + references.en/ + scripts/ + assets/
drafting/                patent-drafting 技能：SKILL.md + references/(zh 00,09-17+glossary)（OA 已并入；14-17 为 P2/P3/P4 结构化撰写、附图与交付管线）
discovery/               patent-discovery 技能：SKILL.md + references/(zh 00-03+glossary) + references.en/
audit/                   patent-audit 技能（4.0 审计线）：SKILL.md + references/(zh 00-07) + references.en/ + scripts/（零依赖校验器）
evals/                   trigger/refusal/boundary eval set + terminology consistency check (CI)
release/                 installers (ps1/sh/oneclick), install docs, patches, release notes
tools/                   reproducible ZIP builder + paired release publisher + secrecy guard
docs/                    design memos (skill matrix, data sources, scope decisions) + verification notes
.github/workflows/ci.yml  wheel/ZIP builds, regressions, evals, guards, installation and publication
```

> **P1/P2/P3/P4 development line (local, unreleased)**: `discovery/` implements the
> patent-discovery skill (material intake → technical facts → patent candidates → human
> confirmation → research handoff draft, G-I control layer). The drafting skill gained the P2
> structured pipeline (DraftingPlan → ClaimAtom → Claim → SupportMapping → two-state writing
> gate, G-D audit codes in `drafting/references/14`–`15`), the P3 professional-figure engine
> (`figures plan/render/validate`, F-001…F-014 checks, `drafting/references/16`) and the P4
> delivery pipeline (frozen PatentDocumentModel, DOCX/optional PDF, delivery manifest with
> human sign-off, `release_ready` gate, CNIPA XML still not attempted; `drafting/references/17`)
> plus the kernel-side `patentkit draft` / `deliver` commands. These are
> included in the full package built from this tree; the paired kernel capabilities live in the
> kernel source tree and only reach this repository through a rebuilt `release/patches/` patch at
> release-integration time. No release has been published for this line, and G-S / evidence /
> validation semantics are unchanged.

## Build a release package

```bash
python -m pip install ./patentkit-0.10.0-py3-none-any.whl
python tools/build_skill_release.py --out dist --built-at 2026-10-23T00:00:00+00:00 --json
python -m unittest discover -s tests -v
```

## Requirements

- Python >= 3.11 (required by the skill scripts)
- Skill 4.1.0: `patentkit` >= 0.10.0, assessment protocol 1 (docx export needs the optional `python-docx`)
- Codex CLI >= 0.161 (the desktop app bundles a newer runtime, no upgrade needed)

## Language

Since 2.5.0 the distributable skill runtime is **Chinese-primary**: `SKILL.md`, `references/`
(including the new 08–13 and `glossary.md`) and assets. The English edition is mirrored under
`references.en/` (research 01–08 and drafting 00/09–13 maintained on both sides since 3.10.0;
audit 00–07 bilingual since 4.1.0). Script and
kernel messages, installers, and release notes remain English (engineering layer).
Implementation plans and verification notes under `docs/` use Chinese.

## Credits & license

The methodology was informed by ideas from these public Agent Skills
(**no code or documentation is vendored**):

- `cn-patent-drafter` (Apache-2.0)
- `patent-disclosure-skill` (Apache-2.0)
- `patent-validity-checker` (Apache-2.0)
- [`cloudflare/security-audit-skill`](https://github.com/cloudflare/security-audit-skill) (MIT,
  © 2025-2026 Cloudflare, Inc.) — the `patent-audit` skill's six-phase audit harness
  (coverage ledger → adversarial validation → independent review → three-verdict
  findings → neutral report) is adapted from its orchestration skeleton, rewritten for
  the patent-search domain; see [docs/adr/0004-audit-harness.md](docs/adr/0004-audit-harness.md).
  Background reading: ["Build your own vulnerability harness"](https://blog.cloudflare.com/build-your-own-vulnerability-harness).
  No code or documentation is vendored; the deterministic validators in `audit/scripts/`
  re-implement the key rules in Python and say so in their file headers.

This repository is licensed under the **Apache-2.0** license (see [LICENSE](LICENSE)).

## Security notes

- All bundled data is synthetic. Do not upload unpublished material to cloud clients.
- The `patentkit` kernel is distributed as a wheel; its source is maintained separately.

## Optional extension: patent_intel (4.0 development line)

An independently versioned, strictly optional wheel (`patent_intel`, currently 0.1.0)
adds retrieval-recall tooling around the kernel without touching its authority:
**Status: experimental enhancement** — the preregistered Phase V evaluation
(DAPFAM, 312 public test topics, same-budget same-engine comparison) did **not**
meet the improvement gate: Family Recall@100 23.7pp vs 26.2pp for the BM25
baseline (mean gain −2.5pp, paired bootstrap 95% CI [−3.8, −1.3]); cross-domain
(OUT) recall is 0 for both sides at K=200. Numbers, groups and failure analysis:
[benchmarks/retrieval/results/](benchmarks/retrieval/results/) and
[docs/retrieval-evaluation.md §6](docs/retrieval-evaluation.md).




```bash
pip install extensions/patent_intel            # stdlib-only base
pip install "patent_intel[kernel]"             # + read the kernel workspace
python -m patent_intel doctor --root <ws>      # read-only self-check
python research/scripts/recall.py plan --axis N1      # query-family proposals
python research/scripts/recall.py report              # offline recall diagnostic
python tools/score_retrieval.py --suite benchmarks/retrieval/fixtures/smoke --runs <runs> --json
```

Boundaries (see [docs/adr/0001-kernel-boundary.md](docs/adr/0001-kernel-boundary.md)):
the kernel stays the sole authority for evidence levels, gates and sign-off; the
extension only produces proposals and read-only diagnostics inside its own sidecar
(`<ws>/.patent-intel/`, deletable without changing kernel validation). Online sources
(OPS) ship contract-tested but are **not live-run** from this repo; quota/limits
follow the provider portals. Architecture and data contracts:
[docs/architecture/4.0-system.md](docs/architecture/4.0-system.md),
[docs/architecture/contracts.md](docs/architecture/contracts.md).
Retrieval benchmark protocol: [docs/retrieval-evaluation.md](docs/retrieval-evaluation.md).

## Version

Skill version: **4.1.0** (patent-research + patent-drafting + patent-discovery + patent-audit),
companion kernel: **0.10.0**. See [CHANGELOG.md](CHANGELOG.md).
