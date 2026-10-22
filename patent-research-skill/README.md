# patent-research-skill — installation & usage

> A standalone skill package for **patent prior-art search, novelty/inventiveness
> self-check, and evidence-chain management**. It bundles the methodology
> (`SKILL.md` + `references/`) with repeatable local scripts (`scripts/`) for clients
> that can read/write local files and run local commands: Codex CLI, Codex desktop,
> and Claude Code.

## Package layout

```
patent-research/              installed skill directory (name must equal SKILL.md `name`)
├── SKILL.md                  entry point: triggers / order / hard constraints / output format
├── references/               6 methodology documents, loaded on demand
├── scripts/                  status / validate / gates / report / check (+ README)
├── assets/                   report templates, blank comparison matrix, synthetic samples
├── agents/openai.yaml        desktop app metadata (name, description, default prompt)
└── README.md                 this file
```

## Installation

The recommended way is the installer from the release package:

```powershell
# Windows
pip install .\patentkit-0.1.1-py3-none-any.whl
Expand-Archive .\patent-research-skill-v2.3.1.zip -DestinationPath .\pkg
pwsh -File .\pkg\install.ps1 -Client both -Force
```

```bash
# macOS / Linux
python3 -m pip install ./patentkit-0.1.1-py3-none-any.whl
unzip patent-research-skill-v2.3.1.zip -d pkg
chmod +x pkg/install.sh && ./pkg/install.sh --client both --force
```

Or copy the `patent-research/` directory manually into:

| Client | User-level location |
|---|---|
| Claude Code | `~/.claude/skills/patent-research/` |
| Codex CLI / Codex desktop | `~/.agents/skills/patent-research/` |

The directory name must be `patent-research` (it must equal `name` in `SKILL.md`).

## After installation

- **Codex desktop**: restart the app; open **Skills** in the sidebar and select
  "Patent Research" (or type `@`). Keep the global `~/.codex/AGENTS.md` guidance:
  "for patent tasks, read `~/.agents/skills/patent-research/SKILL.md` first".
- **Claude Code**: ask "use the patent-research skill to locate the workspace and run
  the self-check".
- **Codex CLI**: run a prompt that names the skill, or use `Skills` if supported.

The recommended practice is explicit invocation (`@` in the desktop app); implicit
triggering also works when the task matches the skill description.

## Upgrade / uninstall

```powershell
pwsh -File .\pkg\install.ps1 -Client both -Force       # upgrade
pwsh -File .\pkg\install.ps1 -Uninstall -Client both   # uninstall
```

## Requirements

- Python >= 3.11 and the `patentkit` kernel (>= 0.1.1)
- A workspace containing `workspace.yml` (use the bundled synthetic sample first)
- Codex CLI >= 0.161; the desktop app bundles a newer runtime

## Troubleshooting

| Symptom | Fix |
|---|---|
| `workspace not found` | `cd` into a workspace (with `workspace.yml`) or use `--root` |
| script exit 3 | install the kernel: `pip install patentkit-*.whl` |
| desktop app does not show the skill | restart the app; confirm `~/.agents/skills/patent-research/SKILL.md` |
| generic answers | select the skill explicitly with `@`; keep the global AGENTS.md guidance |

## Language

Repository documentation and installers are in English. The skill's runtime content
(`SKILL.md`, `references/`, script output, synthetic sample data) is in Chinese because
the skill targets Chinese patent practice.

## License

Apache-2.0. The package contains no real project data.
