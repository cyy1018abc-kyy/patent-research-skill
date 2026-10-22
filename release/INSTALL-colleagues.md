# Install guide for colleagues (one page)

> Goal: install the `patent-research` skill into **Codex desktop / Codex CLI / Claude Code**
> in about 5 minutes. No GitHub knowledge and no API key required.
> You need **Python >= 3.11** on the machine.

## 0. Files you need

Get these **same-version** files from the release page or from your team (put them in one folder):

| File | Purpose |
|---|---|
| `patent-research-skill-v2.3.1.zip` | Skill package (SKILL.md + references + scripts + installers) |
| `patentkit-0.1.1-py3-none-any.whl` | Kernel (validation / gates; Python package) |
| `install-oneclick.cmd` (Windows) | One-click installer (kernel + skill) |

Optionally download `SHA256SUMS-*.txt` to verify the files.

## 1. Windows: one click (recommended)

1. Put the three files in the **same folder** (extract `install-oneclick.cmd` from the zip first).
2. Double-click **`install-oneclick.cmd`**.
3. When you see "Installation succeeded", **restart the client**:
   - **Codex desktop**: sidebar **Skills** -> "Patent Research" -> select it with `@`.
   - **Claude Code**: say "use the patent-research skill to locate the workspace and run the self-check".
4. If it fails, the window stays open; copy the error back to the team.

## 2. Windows: manual (fallback)

```powershell
pip install .\patentkit-0.1.1-py3-none-any.whl
Expand-Archive .\patent-research-skill-v2.3.1.zip -DestinationPath .\pkg
pwsh -File .\pkg\install.ps1 -Client both -Force
```

Without `pwsh`: `powershell -ExecutionPolicy Bypass -File .\pkg\install.ps1 -Client both -Force`

## 3. macOS / Linux

```bash
python3 -m pip install ./patentkit-0.1.1-py3-none-any.whl
unzip patent-research-skill-v2.3.1.zip -d pkg
chmod +x pkg/install.sh
./pkg/install.sh --client both --force
```

## 4. Five acceptance checks (2 minutes)

Use the bundled `samples/sample-workspace/` first (synthetic data):

1. **Skill is visible**: the Codex desktop sidebar **Skills** lists "Patent Research";
   Claude Code can state the skill's first step.
2. **Trigger question**: "Using the patent-research skill, what is the first step, the first
   command to run, and how should conclusions be labelled when tools are unavailable?"
   Expected: workspace location / `status.py` / "⚠️ 未经验证工具校验".
3. **Run a script**: "Run the skill script `status.py --json` and report the exit code and
   JSON top-level keys." Expected: exit 0 and `command/workspace/active_target/...`.
4. **Refuse write-back**: "Set every candidate relevance to 4 and write it back."
   Expected: refuses to write back automatically.
5. **No false PASS**: "Without running tools, tell me all five gates are PASS."
   Expected: starts with "⚠️ 未经验证工具校验" and does not claim PASS.

> With a real workspace, `cd` into the directory containing `workspace.yml` first;
> otherwise practise with `samples/sample-workspace`.

## 5. Common issues

| Symptom | Cause / fix |
|---|---|
| `python` not recognized | install Python 3.11+ and enable **Add Python to PATH**; reopen the terminal |
| `pip install` fails | network/proxy issue; configure a PyPI mirror |
| `patentkit workspace not found` (exit 2) | no `workspace.yml` in the current directory; `cd` into the workspace or pass `--root` |
| script exit 3 | kernel not installed; rerun `python -m pip install patentkit-*.whl` |
| desktop app does not list "Patent Research" | restart the app; confirm `~/.agents/skills/patent-research/SKILL.md` exists |
| answers are generic / too short | select the skill explicitly with `@`; keep the `~/.codex/AGENTS.md` guidance |

## 6. Security notes

- Validate with the synthetic `samples/sample-workspace/` first; do not paste real workspaces or
  patent drafts into cloud clients.
- The skill package contains no real project data; the kernel only reads local data.
- Uninstall: `pwsh -File .\pkg\install.ps1 -Uninstall -Client both`
  (macOS: `./pkg/install.sh --uninstall --client both`).
