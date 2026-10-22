# patent-research-skill

> An **Agent Skill** for patent prior-art search, novelty/inventiveness self-check,
> evidence-chain management, and acceptance gates (G-S).
> Works with Claude Code, Codex CLI, and the Codex desktop app.

This repository contains only distributable assets: the skill source, installers,
the release builder, and release notes.
**No real project data, patent drafts, target IDs, or candidate IDs are included**;
the sample workspace is synthetic (`TGT-0002`).

## Download & install

Download from [Releases](https://github.com/cyy1018abc-kyy/patent-research-skill/releases):

| Asset | Purpose |
|---|---|
| `patent-research-skill-v<version>.zip` | Skill package (with installer + synthetic sample workspace) |
| `patentkit-<version>-py3-none-any.whl` | Kernel (Python package; `patentkit` >= 0.1.2) |
| `INSTALL-colleagues.md` | One-page install guide (repo source: `release/install-guide-for-colleagues.md`) |

### Windows (one click)

Put the zip, the wheel, and `install-oneclick.cmd` (extracted from the zip) in the
same folder, then double-click `install-oneclick.cmd`.

### Manual (any platform)

```powershell
pip install ./patentkit-0.1.2-py3-none-any.whl
Expand-Archive ./patent-research-skill-v2.3.3.zip -DestinationPath ./pkg
pwsh -File ./pkg/install.ps1 -Client both -Force
```

```bash
python3 -m pip install ./patentkit-0.1.2-py3-none-any.whl
unzip patent-research-skill-v2.3.3.zip -d pkg
chmod +x pkg/install.sh && ./pkg/install.sh --client both --force
```

After installation, restart the client:

- **Codex desktop**: open **Skills** in the sidebar, select "Patent Research", or type `@` to pick it.
- **Claude Code**: ask "use the patent-research skill to locate the workspace and run the self-check".

## Repository layout

```
patent-research-skill/   SKILL.md + references/ + scripts/ + assets/ + agents/openai.yaml
release/                 installers (ps1/sh/oneclick), install docs, release notes
.github/workflows/ci.yml       build smoke test + installer dry-run
```

## Build a release package

```bash
pip install pyyaml
PATENTKIT_COMPAT_VERSION=0.1.1 python tools/build_skill_release.py --out dist --json
# produces a zip including samples/sample-workspace (requires patentkit >= 0.1.2 locally)
```

## Requirements

- Python >= 3.11 (required by the skill scripts)
- `patentkit` >= 0.1.2 (install the wheel from Releases)
- Codex CLI >= 0.161 (the desktop app bundles a newer runtime, no upgrade needed)

## Language

The repository and the skill runtime are fully in English, including `SKILL.md`,
`references/`, script messages, assets, installers, and release notes.

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

Current skill version: **2.3.3**. See [CHANGELOG.md](CHANGELOG.md).
