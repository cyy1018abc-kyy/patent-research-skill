# patent-research-skill

> An **Agent Skill** for patent prior-art search, novelty/inventiveness self-check,
> evidence-chain management, and acceptance gates (G-S).
> Works with Claude Code, Codex CLI, and the Codex desktop app.

This repository contains only distributable assets: the skill source, installers,
the release builder, and release notes.
**No real project data, patent drafts, target IDs, or candidate IDs are included**;
the sample workspace is synthetic (`TGT-0002`).

## Skill 2.4.0 / kernel 0.2.0

Source provenance and judgment are now separate. Supported AI assessments may count for G-S-02; G-S-03 requires explicit human confirmation bound to the current judgment. See [assessment protocol](patent-research-skill/references/07-assessment-protocol.md), [implementation plan](docs/superpowers/plans/2026-10-23-source-assessment-separation.md), and [release and migration notes](release/notes/skill-v2.4.0.md). Back up existing workspaces and preview `python -m patentkit review migrate-assessments --root <workspace>` before applying migration. CI reconstructs the kernel from the [verified public source and patch](release/patches/README.md), builds both packages, and validates installation on Windows/Linux with Python 3.11/3.12 before publishing.

## Download & install

Download the paired [Skill 2.4.0](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/skill-v2.4.0) and [patentkit 0.2.0](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.2.0) releases:

| Asset | Purpose |
|---|---|
| `patent-research-skill-v2.4.0.zip` | Skill installation package (with installers + synthetic sample workspace) |
| `patentkit-0.2.0-py3-none-any.whl` | Matching kernel, assessment protocol 1 |
| `install-oneclick.cmd` | Windows installer, also included in the ZIP |
| `INSTALL-colleagues.md` | One-page install guide (repo source: `release/install-guide-for-colleagues.md`) |

### Windows (one click)

Put the zip, the wheel, and `install-oneclick.cmd` (extracted from the zip) in the
same folder, then double-click `install-oneclick.cmd`.

### Manual (any platform)

```powershell
python -m pip install ./patentkit-0.2.0-py3-none-any.whl
Expand-Archive ./patent-research-skill-v2.4.0.zip -DestinationPath ./pkg
pwsh -File ./pkg/install.ps1 -Client both -Force
```

```bash
python3 -m pip install ./patentkit-0.2.0-py3-none-any.whl
unzip patent-research-skill-v2.4.0.zip -d pkg
chmod +x pkg/install.sh && ./pkg/install.sh --client both --force
```

After installation, restart the client:

- **Codex desktop**: open **Skills** in the sidebar, select "Patent Research", or type `@` to pick it.
- **Claude Code**: ask "use the patent-research skill to locate the workspace and run the self-check".

## Repository layout

```
patent-research-skill/   SKILL.md + references/ + scripts/ + assets/ + agents/openai.yaml
release/                 installers (ps1/sh/oneclick), install docs, release notes
tools/                   reproducible ZIP builder + paired release publisher
.github/workflows/ci.yml  wheel/ZIP builds, regressions, installation and publication
```

## Build a release package

```bash
python -m pip install ./patentkit-0.2.0-py3-none-any.whl
python tools/build_skill_release.py --out dist --built-at 2026-10-23T00:00:00+00:00 --json
python -m unittest discover -s tests -v
```

## Requirements

- Python >= 3.11 (required by the skill scripts)
- Skill 2.4.0: `patentkit` >= 0.2.0, assessment protocol 1
- Codex CLI >= 0.161 (the desktop app bundles a newer runtime, no upgrade needed)

## Language

The distributable skill runtime is in English, including `SKILL.md`,
`references/`, script messages, assets, installers, and release notes. Implementation plans and verification notes under `docs/` use Chinese.

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

Skill version: **2.4.0**, companion kernel: **0.2.0**. See [CHANGELOG.md](CHANGELOG.md).
