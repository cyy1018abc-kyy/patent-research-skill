# Installing `patent-research-skill`

> This is a **standalone distributable skill package**: for AI clients such as Codex CLI / Claude Code
> that can read/write local files and execute local commands. It contains the methodology (`SKILL.md` + `references/`) and
> executable scripts (`scripts/`), and **contains no search data or patent manuscripts from any real project**.
>
> Evidence conventions, the five acceptance gates, and other rules are implemented in the `patentkit` core; this package only covers "how to do things".

## Getting the installation package

- Skill package zip: <https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/skill-v3.3.1> →
  `patent-research-skill-v3.3.1.zip`
- Kernel wheel / sdist: <https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.5.1>
- Verification: `SHA256SUMS-*.txt` on the same page; on Windows you can check with `Get-FileHash <file> -Algorithm SHA256`.

## Prerequisites

| Dependency | Requirement | Check |
|---|---|---|
| Python | ≥ 3.11 | `python --version` |
| patentkit | >= 0.5.1, assessment protocol 1 | `python -m patentkit doctor` |

```powershell
python -m pip install ./patentkit-0.5.1-py3-none-any.whl
```

> You can install the skill package without the core, but the scripts will exit with code 3 and tell you to install `patentkit` first.

## Three-step installation

Run this in the **root of the unzipped release package** (the directory should contain `manifest.json`, `patent-research/`, `samples/`):

```powershell
# 1) Preview (writes no files)
pwsh -File .\install.ps1 -DryRun

# 2) Install: Claude Code by default (~/.claude/skills/patent-research/)
pwsh -File .\install.ps1 -Client claude
#    Codex CLI: ~/.agents/skills/patent-research/
pwsh -File .\install.ps1 -Client codex
#    Install both:
pwsh -File .\install.ps1 -Client both

# 3) Self-check (the install script already runs it by default; can also be run manually)
python "$HOME/.claude/skills/patent-research/scripts/status.py" --root ".\samples\sample_workspace"
```

macOS / Linux / WSL:

```bash
chmod +x install.sh
./install.sh --dry-run
./install.sh --client claude
```

### Where it installs

| Client | Default skills root | After installation |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `~/.claude/skills/patent-research/` |
| Codex CLI | `~/.agents/skills/` | `~/.agents/skills/patent-research/` |
| Custom | `-Dest <skills-root>` / `--dest <dir>` | `<dir>/patent-research/` |

> **The directory name must equal the `name` in `SKILL.md` (`patent-research`)** — clients identify skills by directory/name,
> so a wrong name may not be recognized. The install script handles this automatically.

## Verifying it works

1. After installation the self-check should show "✅ Self-check passed".
2. In the client, say: "run a patent novelty check" / "show the status of this patent workspace" /
   "what is the search query on the N1 axis" — the skill should trigger and execute the commands in `scripts/`.
3. Before using a real workspace, practice on the package's `samples/sample_workspace/` (synthetic data, do whatever you like).

## Upgrading

```powershell
# 1) Switch to the new package: unzip into a new directory, preview first
pwsh -File .\install.ps1 -DryRun

# 2) Install over the old version (replaces it)
pwsh -File .\install.ps1 -Client both -Force

# 3) Upgrade the kernel (if the release notes require it)
python -m pip install --upgrade ./patentkit-0.5.1-py3-none-any.whl
```

> Before upgrading, check `skill.version` and `compat.patentkit` in `manifest.json`;
> for cross-major upgrades follow the release notes. For a manual install, just replace the skill directory.

Before using existing research data, back it up and preview the schema migration:

```bash
python -m patentkit review migrate-assessments --root /path/to/workspace
python -m patentkit review migrate-assessments --root /path/to/workspace --apply
python -m patentkit validate --root /path/to/workspace --strict
```

Migration preserves source grades, records legacy judgment identity as unknown, and
does not create human confirmations. Prior gate counts may decrease. See the
[release notes](https://github.com/cyy1018abc-kyy/patent-research-skill/blob/main/release/notes/skill-v3.3.1.md).

## Uninstalling

```powershell
pwsh -File .\install.ps1 -Uninstall -Client both
```

The `patentkit` core is removed with `pip uninstall patentkit`; workspace data is unaffected.

## Manual installation (if you prefer not to use the scripts)

1. Copy `patent-research/` to the client's skills root and **rename it to `patent-research`** (that is already its name inside the package).
2. Make sure `SKILL.md` is at the top level of the directory.
3. Run the self-check: `python <skill-dir>/scripts/status.py --root samples/sample_workspace`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `install.ps1` reports "manifest.json not found" | not run from the release package root | `cd` to the unzipped directory and rerun, or `chmod +x install.sh` |
| Self-check exits 3 | `patentkit` not installed / Python version too low | `pip install patentkit`; confirm `python --version` ≥ 3.11 |
| Self-check exits 2 | workspace location failed | use `--root <workspace>`; or `cd` into the directory containing `workspace.yml` |
| The client does not recognize the skill | skill directory name ≠ the `name` in `SKILL.md` | rename the directory to `patent-research` |
| The client does not trigger automatically | client version/settings issue | manually `/patent-research`, or make the request more specific (search / novelty / evidence chain) |
| Chinese text shows garbled characters | console encoding | the scripts force UTF-8; clients should decode captured output as UTF-8 |

## Safety and confidentiality

- This package contains no real candidates, search logs, determination conclusions, or manuscript body text; `samples/` is **synthetic data**.
- The scripts only call the local `patentkit` to read the workspace you specify; they do not go online or upload anything.
- However, **the client itself may go online** (cloud inference): candidate titles, determination conclusions, and manuscript body text
  from a real workspace **must not** be pasted into a public-cloud client. A pure chat client can only reach the `asserted` level, and
  conclusions must be marked "⚠️ Unverified by tool checks".

## Package structure

```
patent-research-skill-v<version>/
├── manifest.json       version + compatibility + sha256 of all files
├── INSTALL.md          this file
├── install.ps1 / install.sh
├── patent-research/    ← what gets installed into the client
│   ├── SKILL.md        main entry: when to trigger / execution order / hard constraints / result format
│   ├── references/     7 methodology references (loaded on demand)
│   ├── scripts/        status / validate / gates / report / check
│   ├── assets/         report templates, blank comparison matrix, synthetic examples
│   └── README.md
└── samples/sample_workspace/  desensitized workspace (TGT-0002, synthetic data)
```
