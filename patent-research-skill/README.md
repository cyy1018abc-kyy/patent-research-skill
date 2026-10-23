# patent-research-skill installation and usage

> **What this is**: a self-contained, distributable "patent research" skill package — it bundles the
> **methodology** for patent prior-art searching, novelty/inventive-step self-checks, and evidence-chain
> management (`SKILL.md` + `references/`) together with **repeatable operations** (`scripts/`), so that
> clients able to read/write local files and run local commands — Codex CLI / Codex desktop / Claude Code, etc. —
> can use it directly.
>
> **Not included**: candidate lists, search logs, determination conclusions, or manuscript text from any real
> project. The skill package can be distributed freely, publicly or within a team.

## Package layout

```
patent-research-skill/
├── SKILL.md          Main entry: when to use, execution order, hard constraints, result format (resident in client context)
├── references/       7 methodology documents, loaded on demand (04 evidence-level system is the prerequisite)
├── scripts/          Thin wrappers for status/validation/gates/report (rules stay in the patentkit core)
├── assets/           Report template, blank comparison matrix, sample data (synthetic)
└── README.md         This file
```

## Installation

### Option A: Install from the release package (recommended)

The release package (`dist/patent-research-skill-v<version>.zip`) ships with its own install scripts, a sample
workspace, and a sha256 manifest, so there is no need to rename directories by hand. Three steps:

1. **Install the kernel** (once):
   ```powershell
   pip install patentkit                    # when a release index is available
   pip install "git+https://<internal-git-url>"   # or from the internal git
   ```
2. **Extract and install** (the script renames the skill directory to `patent-research/` and runs a self-check).
   No zip? Download `patent-research-skill-v2.3.0.zip` directly from the
   [`skill-v2.3.0` Release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/skill-v2.3.0)
   (the attachment lists the SHA-256).

   Windows:
   ```powershell
   Expand-Archive .\patent-research-skill-v2.3.0.zip -DestinationPath .\pkg
   pwsh -File .\pkg\install.ps1 -DryRun           # preview first; writes no files
   pwsh -File .\pkg\install.ps1 -Client both      # Claude Code + Codex CLI
   ```

   macOS / Linux / WSL:
   ```bash
   unzip patent-research-skill-v2.3.0.zip -d pkg
   ./pkg/install.sh --dry-run
   ./pkg/install.sh --client both
   ```
3. **Verify**: the install script runs a self-check against the bundled `samples/sample_workspace/` (synthetic data);
   you can also do it manually:
   ```powershell
   python "$HOME/.claude/skills/patent-research/scripts/status.py" --root ".\pkg\samples\sample_workspace"
   ```

> Upgrade: `install.ps1 -Force` / `install.sh --force`; uninstall: `-Uninstall` / `--uninstall`;
> custom location: `-Dest <skill-root-dir>` / `--dest <dir>`. See `INSTALL.md` in the release package for details.

### Option B: Place it by hand (in-repo development / no-script environments)

#### 1. Install the `patentkit` kernel

The skill package only covers "how to do things"; thresholds and determinations live in the `patentkit` kernel:

```powershell
pip install patentkit                 # when an internal index/release package is available
# or develop in the repo: cd <repo-root>; pip install -e ".[dev]"
```

Development skill 2.4.0 requires patentkit ≥0.2.0 with assessment protocol 1. Install the matching built wheel before using these wrappers; older release installation examples below describe the previous distribution.

Requirements: Python ≥ 3.11; dependencies `jsonschema`, `PyYAML` (pip installs them automatically).

#### 2. Place the skill package

| Client | Where to put it |
|---|---|
| Claude Code (user level) | `~/.claude/skills/patent-research/` (the whole directory) |
| Claude Code (project level) | `<workspace>/.claude/skills/patent-research/` |
| Codex CLI | Same as above when the client supports a skills directory; if it only honors `AGENTS.md`, merge the body of `SKILL.md` into the workspace's `AGENTS.md` and keep the `references/` relative paths |
| Codex desktop (ChatGPT App) | User level `~/.agents/skills/patent-research/` (already covered by `install.ps1 -Client both`); visible under **Skills** in the sidebar, selectable with `@` in a conversation; `agents/openai.yaml` supplies the display name and the default `@` prompt |
| Other local clients | Anything that can read local files and execute commands can reference `SKILL.md` from its own rules file |

> **The directory name must be changed to `patent-research/`** (= the `name` in `SKILL.md`); keeping
> `patent-research-skill/` may prevent discovery. When copying, exclude caches such as `__pycache__`.
> Skill-discovery mechanisms differ between clients; the P3 cross-client test records are authoritative
> (see `cross_client_tests/` in the repository).

#### 3. Self-check

```powershell
cd <your patent workspace>              # the directory containing workspace.yml
python <skill-dir>/scripts/status.py    # expect exit 0; prints target/gates/validation/next steps
```

No workspace yet? Initialize one first:

```powershell
python -m patentkit init <patent-directory> --target TGT-0002 --title "Invention title"
```

## How to use it inside a client

Just speak plainly, for example:

- "Check the status of this patent workspace" → triggers `scripts/status.py` / `patentkit status`
- "What is the query for the N1 axis?" → reads `references/02` + `patentkit search-plan --axis N1`
- "Run a novelty check" → follows steps 0–4 of the `SKILL.md` execution order and reports in the "Result format"
- "Check whether the claim values have support before hand-off" → reads `references/06` + `scripts/check.py`

**Hard constraints** (full version in `SKILL.md`): gate PASS is recognized only on the `verified` column;
supported AI judgments may count for G-S-02; G-S-03 needs explicit human confirmation. Source evidence_level remains unchanged by AI participation or human review. When tools cannot run, mark conclusions "⚠️ Unverified by tool checks". See references/07-assessment-protocol.md.

## Scripts at a glance

| Script | Purpose | Common arguments | Exit codes |
|---|---|---|---|
| `scripts/status.py` | Target/gates/validation/candidates/next steps | `--root` `--json` | 0 / 2 / 3 |
| `scripts/validate.py` | Consistency validation V001–V028 | `--strict` `--root` `--json` | 0 pass / 1 fail |
| `scripts/gates.py` | Five gates × three columns | `--target` `--root` `--json` | 0 all PASS / 1 not all PASS |
| `scripts/report.py` | Generate the comparison run skeleton | `--target` `--out` `--root` | 0 / 1 / 2 / 3 |
| `scripts/check.py` | `validate --strict` + `gates` | `--root` `--json` | 0 / 1 / 2 / 3 |

**Exit-code conventions**: `0` success; `1` business failure (validation errors / not all gates PASS);
`2` workspace location failure; `3` missing dependency (`patentkit` not installed or Python < 3.11).

> Note: the native `patentkit gates` command treats "not all gates PASS" as exit 2; the script layer
> normalizes it to exit 1 so that "workspace error" stays distinguishable. If CI depends on the original
> exit codes, call `patentkit` directly.

Workspace resolution follows the same order as the kernel: `--root` → environment variable `PATENTKIT_WORKSPACE` → search upward for `workspace.yml`.
To make it work from any directory, set it once:

```powershell
[Environment]::SetEnvironmentVariable("PATENTKIT_WORKSPACE", "<patent-workspace>", "User")
```

## Upgrade

1. `pip install -U patentkit` (the kernel)
2. Replace the skill package directory with the new zip/directory (you may rename the old directory as a backup first)
3. Run `python scripts/status.py --json` and `python scripts/check.py` once and confirm that exit codes and fields are compatible
4. Version compatibility: skill package `metadata.version` ↔ kernel release version (single source of truth: `patentkit.__version__`, read dynamically from `pyproject.toml`); for cross-major upgrades see `manifest.json` in the release package

## Uninstall

Delete the skill package directory; `pip uninstall patentkit` removes the kernel (workspace data is unaffected).

## Compatibility and evidence-level ceiling

| Client capability | What it can do | Evidence-level ceiling |
|---|---|---|
| Read local files + execute commands (Claude Code, Codex CLI, Cursor, Cline…) | Full workflow: search → ingest → gates → report | `verified` |
| Read files only, cannot execute commands | Can only explain the methodology from references and inspect documents | `asserted` |
| Conversation only (web version, cannot read local files) | Can only use uploaded `references/` as a knowledge base to explain the methodology | `asserted` |

> **Confidentiality boundary**: do **not** paste the candidate titles, determination conclusions, or manuscript
> text of a real workspace into public cloud clients. The skill package itself contains no data, but that does
> not mean pasting data into the cloud is safe.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `exit 2`, says "workspace not found" | The current directory is not inside a workspace | `cd` into the workspace / add `--root` / set `PATENTKIT_WORKSPACE` |
| `exit 3`, says `patentkit` is not installed | The kernel is not installed, or was installed into a different Python | With the same interpreter, `pip install patentkit`; verify with `python -c "import patentkit"` |
| Garbled output / mojibake | Console encoding is not UTF-8 | The scripts already force UTF-8; when capturing, decode as UTF-8 |
| All gates FAIL but the data looks complete | You are looking at the `asserted` column, or `raw/` artifacts are missing | Read `references/04`, `references/05`; add `raw/` and `capture_mode=live` logs |
| Validation reports V009/V013 | `verified` was tagged without raw artifacts | Re-run the search and persist `raw/`; do not change data to bypass it |

## Security and licensing

- The skill package contains **no executable binaries and no network code**; the scripts only call the local `patentkit` to read workspace data.
- The distribution package contains **no `.git`**; run a security scan on a clean copy before release (SkillSpector; analyzers reported as `degraded` are marked truthfully).
- License: Apache-2.0 (consistent with `patentkit` and the methodology it depends on).
