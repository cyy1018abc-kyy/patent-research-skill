# patent-research-skill

> An **Agent Skill** for patent prior-art search, novelty/inventiveness self-check,
> evidence-chain management, and acceptance gates (G-S).
> Works with Claude Code, Codex CLI, and the Codex desktop app.

This repository contains only distributable assets: the skill source, installers,
the release builder, and release notes.
**No real project data, patent drafts, target IDs, or candidate IDs are included**;
the sample workspace is synthetic (`TGT-0002`).

## Skill 3.11.0 / kernel 0.10.0 — revision↔conclusions linkage (V038), 9-case benchmark, structured support citations

Three additions in this release (the P0–P4 upgrade of 3.5.0 below remains the capability base):

- **V038 — revision↔conclusions linkage.** A patch to the manuscript automatically marks the
  novelty conclusions stale; `revise status` exits 1 and `revise close` refuses until each
  stale conclusion is human-reconfirmed (`revise reconfirm --by <name>`) or explicitly waived
  into the ledger (`--waive --reason`). validate reports unprocessed stale conclusions as errors.
- **D-019 — structured support citations.** Drafting support mappings accept optional
  `citations` (`source` + `L`-range / `[NNNN]` `locator`) that the audit verifies against the
  workspace; unresolvable citations are errors.
- **Benchmark at 9 cases** (review P1-1 range 8–12): 45 features, 375 judgment points,
  140 citations; gold solutions score perfect in CI.

The P0–P4 upgrade plan of 3.5.0
([docs/patent-skill-upgrade-implementation-plan.md](docs/patent-skill-upgrade-implementation-plan.md))
remains the capability base:

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
`release/patches/patentkit-0.1.2-to-0.10.0.patch`; the full package ships all three skills.
The skill-matrix decision (2026-10-25, see
[docs/skill-matrix-plan.md](docs/skill-matrix-plan.md)) still describes the split into
**research** and **drafting** (OA merged into drafting), and 3.6.0 additionally ships
`patent-discovery`. Everything below still describes the 2.5.0 Chinese-primary +
delivery-safety release, which 3.x inherits in full.

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

Download the paired [Skill 3.11.0](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/skill-v3.11.0) and [patentkit 0.10.0](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.10.0) releases:

| Asset | Purpose |
|---|---|
| `patent-research-skill-v3.11.0.zip` | Full package: installs all three skills (patent-research + patent-drafting + patent-discovery), with installers + synthetic sample workspace |
| `patentkit-0.10.0-py3-none-any.whl` | Matching kernel: assessment protocol 1 + P0–P4 modules (contracts, upgrade, intake, discovery, draft, figures, delivery) |
| `install-oneclick.cmd` | Windows installer, also included in the ZIP |
| `INSTALL-colleagues.md` | One-page install guide (repo source: `release/install-guide-for-colleagues.md`) |

### Windows (one click)

Put the zip, the wheel, and `install-oneclick.cmd` (extracted from the zip) in the
same folder, then double-click `install-oneclick.cmd`.

### Manual (any platform)

```powershell
python -m pip install ./patentkit-0.10.0-py3-none-any.whl
Expand-Archive ./patent-research-skill-v3.11.0.zip -DestinationPath ./pkg
pwsh -File ./pkg/install.ps1 -Client both -Force
```

```bash
python3 -m pip install ./patentkit-0.2.0-py3-none-any.whl
unzip patent-research-skill-v3.11.0.zip -d pkg
chmod +x pkg/install.sh && ./pkg/install.sh --client both --force
```

After installation, restart the client:

- **Codex desktop**: open **Skills** in the sidebar, select "Patent Research", or type `@` to pick it.
- **Claude Code**: ask "use the patent-research skill to locate the workspace and run the self-check".

## Repository layout

```
research/                patent-research 技能：SKILL.md + references/(zh 01-08+glossary) + references.en/ + scripts/ + assets/
drafting/                patent-drafting 技能：SKILL.md + references/(zh 00,09-17+glossary)（OA 已并入；14-17 为 P2/P3/P4 结构化撰写、附图与交付管线）
discovery/               patent-discovery 技能（P1 开发线，未发布）：SKILL.md + references/(zh 00-03+glossary) + references.en/
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
- Skill 3.11.0: `patentkit` >= 0.10.0, assessment protocol 1 (docx export needs the optional `python-docx`)
- Codex CLI >= 0.161 (the desktop app bundles a newer runtime, no upgrade needed)

## Language

Since 2.5.0 the distributable skill runtime is **Chinese-primary**: `SKILL.md`, `references/`
(including the new 08–13 and `glossary.md`) and assets. The English edition is mirrored under
`references.en/` (research 01–08 and drafting 00/09–13 maintained on both sides since 3.11.0). Script and
kernel messages, installers, and release notes remain English (engineering layer).
Implementation plans and verification notes under `docs/` use Chinese.

## Credits & license

The methodology was informed by ideas from these public Agent Skills
(**no code or documentation is vendored**):

- `cn-patent-drafter` (Apache-2.0)
- `patent-disclosure-skill` (Apache-2.0)
- `patent-validity-checker` (Apache-2.0)

This repository is licensed under the **Apache-2.0** license (see [LICENSE](LICENSE)).

## Security notes

- All bundled data is synthetic. Do not upload unpublished material to cloud clients.
- The `patentkit` kernel is distributed as a wheel; its source is maintained separately.

## Optional extension: patent_intel (4.0 development line)

An independently versioned, strictly optional wheel (`patent_intel`, currently 0.1.0)
adds retrieval-recall tooling around the kernel without touching its authority:

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

Skill version: **3.11.0** (patent-research + patent-drafting; patent-discovery in the P1 development line),
companion kernel: **0.10.0**. See [CHANGELOG.md](CHANGELOG.md).
