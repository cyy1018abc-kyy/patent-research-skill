# Install `patent-research-skill`

> A standalone, distributable skill package for AI clients that can read/write local
> files and run local commands (Codex CLI, Claude Code, Codex desktop app).
> It contains the methodology (`SKILL.md` + `references/`) and executable scripts
> (`scripts/`). It contains **no real project data or patent drafts**.

## Prerequisites

| Dependency | Requirement | Check |
|---|---|---|
| Python | >= 3.11 | `python --version` |
| patentkit | installed (kernel) | `python -c "import patentkit; print(patentkit.__version__)"` |
| Client | Codex CLI >= 0.161 / Claude Code >= 2.1.206 / current Codex desktop app | — |

```powershell
pip install patentkit-0.1.1-py3-none-any.whl
```

## Quick install

Extract the release zip, then run the installer from the package root:

```powershell
Expand-Archive .\patent-research-skill-v2.3.1.zip -DestinationPath .\pkg
pwsh -File .\pkg\install.ps1 -DryRun          # preview
pwsh -File .\pkg\install.ps1 -Client both     # Claude Code + Codex
```

macOS / Linux:

```bash
unzip patent-research-skill-v2.3.1.zip -d pkg
chmod +x pkg/install.sh
./pkg/install.sh --dry-run
./pkg/install.sh --client both
```

Options:

| Option | Meaning |
|---|---|
| `-Client claude` | install only for Claude Code (`~/.claude/skills`) |
| `-Client codex` | install only for Codex (`~/.agents/skills`) |
| `-Client both` | install both |
| `-Dest <dir>` | custom skills root (a `patent-research/` directory is created) |
| `-DryRun` / `--dry-run` | print actions without writing |
| `-Force` / `--force` | overwrite an existing installation |
| `-NoSelfCheck` / `--no-self-check` | skip the post-install smoke test |
| `-Uninstall` / `--uninstall` | remove the installed skill |

The installer copies the payload to a directory named `patent-research` (the value of
`name` in `SKILL.md`), then runs a smoke test against the bundled synthetic
`samples/sample-workspace/` if `patentkit` is installed.

Exit codes: `0` success, `1` failure (self-check failed / destination exists), `2` invalid package.

## Verify

```powershell
python "$HOME/.agents/skills/patent-research/scripts/status.py" --root .\pkg\samples\sample-workspace
```

Expected: exit code 0 and a JSON object with `workspace`, `active_target`, `gates`, `ok`, ...

Then restart the client:

- **Codex desktop**: sidebar **Skills** -> select "Patent Research" (or `@`).
- **Claude Code**: ask "use the patent-research skill, locate the workspace and run the self-check".

## Upgrade / uninstall

```powershell
pwsh -File .\pkg\install.ps1 -Client both -Force      # upgrade
pwsh -File .\pkg\install.ps1 -Uninstall -Client both  # uninstall
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `manifest.json not found` | run the installer from the extracted package root |
| self-check fails / script exit 3 | `patentkit` is not installed: `pip install patentkit-*.whl` |
| `workspace not found` (exit 2) | `cd` into a directory containing `workspace.yml`, or pass `--root` |
| desktop app does not list the skill | restart the app; confirm `~/.agents/skills/patent-research/SKILL.md` exists |
| skill answers are generic | select the skill explicitly with `@`; keep the global `~/.codex/AGENTS.md` guidance |
