# patent-research-skill

> An **Agent Skill** for patent prior-art search, novelty/inventiveness self-check,
> evidence-chain management, and acceptance gates (G-S).
> Works with Claude Code, Codex CLI, and the Codex desktop app.

This repository contains only distributable assets: the skill source, installers,
the release builder, and release notes.
**No real project data, patent drafts, target IDs, or candidate IDs are included**;
the sample workspace is synthetic (`TGT-0002`).

## Skill 3.4.0 / kernel 0.6.0 — multi-skill matrix + drafting English mirrors

Per the accepted skill-matrix decision (2026-10-25, see
[docs/skill-matrix-plan.md](docs/skill-matrix-plan.md)): the single skill is split into two
**research** and **drafting** (OA merged into drafting), shipped from one repository and one
full package; a standalone drafting-only package is also built. Everything below still
describes the 2.5.0 Chinese-primary + delivery-safety release, which 3.x inherits in full.

## Skill 2.5.0 highlights (inherited by 3.x)

Two headline changes over 2.4.0:

1. **Chinese-primary runtime.** `SKILL.md`, all 13 references and the assets are now the
   authoritative Chinese edition (the target practice is Chinese patent work); the English
   edition lives on as `references.en/` and is kept term-consistent by
   `evals/check_terminology.py`. A bilingual glossary (`references/glossary.md`) pins the
   terminology both ways.
2. **Delivery-safety layer (kernel 0.6.0).** `export-docx` (workspace-verbatim .docx search
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

Download the paired [Skill 3.4.0](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/skill-v3.4.0) and [patentkit 0.6.0](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.6.0) releases:

| Asset | Purpose |
|---|---|
| `patent-research-skill-v3.4.0.zip` | Full package: installs **both released** skills (patent-research + patent-drafting); the P1 development line additionally ships `patent-discovery` | Skill installation package (with installers + synthetic sample workspace) |
| `patentkit-0.6.0-py3-none-any.whl` | Matching kernel, assessment protocol 1 + delivery-safety layer |
| `install-oneclick.cmd` | Windows installer, also included in the ZIP |
| `INSTALL-colleagues.md` | One-page install guide (repo source: `release/install-guide-for-colleagues.md`) |

### Windows (one click)

Put the zip, the wheel, and `install-oneclick.cmd` (extracted from the zip) in the
same folder, then double-click `install-oneclick.cmd`.

### Manual (any platform)

```powershell
python -m pip install ./patentkit-0.6.0-py3-none-any.whl
Expand-Archive ./patent-research-skill-v3.4.0.zip -DestinationPath ./pkg
pwsh -File ./pkg/install.ps1 -Client both -Force
```

```bash
python3 -m pip install ./patentkit-0.2.0-py3-none-any.whl
unzip patent-research-skill-v3.4.0.zip -d pkg
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
python -m pip install ./patentkit-0.6.0-py3-none-any.whl
python tools/build_skill_release.py --out dist --built-at 2026-10-23T00:00:00+00:00 --json
python -m unittest discover -s tests -v
```

## Requirements

- Python >= 3.11 (required by the skill scripts)
- Skill 3.4.0: `patentkit` >= 0.6.0, assessment protocol 1 (docx export needs the optional `python-docx`)
- Codex CLI >= 0.161 (the desktop app bundles a newer runtime, no upgrade needed)

## Language

Since 2.5.0 the distributable skill runtime is **Chinese-primary**: `SKILL.md`, `references/`
(including the new 08–13 and `glossary.md`) and assets. The English edition is mirrored under
`references.en/` (research 01–08 and drafting 00/09–13 maintained on both sides since 3.4.0). Script and
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

## Version

Skill version: **3.4.0** (patent-research + patent-drafting; patent-discovery in the P1 development line),
companion kernel: **0.6.0**. See [CHANGELOG.md](CHANGELOG.md).
