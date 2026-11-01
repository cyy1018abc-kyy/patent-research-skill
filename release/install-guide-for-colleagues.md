# Installation Guide · For Colleagues (One Pager)

> Goal: get the `patent-research` skill installed into **Codex desktop / Codex CLI / Claude Code** within 5 minutes.
> No need to understand GitHub, no API key needed; you need **Python ≥ 3.11** on this machine.

## 0. Files you need to obtain

Get this matched pair (Skill **4.1.0** + kernel **0.10.0**；一个包同时安装 patent-research 与 patent-drafting 两个已发布技能；P1 开发线另含 patent-discovery) and the installer from the release page / group chat (put them in the same folder):

| File | Purpose |
|---|---|
| `patent-research-skill-v4.1.0.zip` | Skill package (SKILL.md + references + scripts + install scripts) |
| `patentkit-0.10.0-py3-none-any.whl` | Kernel (validation/gate rules, Python package) |
| `install-oneclick.cmd` (Windows) | One-click installer (installs the kernel + the skill) |

Also recommended: get `SHA256SUMS-*.txt` to verify the files were not corrupted during download (optional).

## 1. Windows: just double-click (recommended)

1. Unzip/place the 3 files above into the **same folder** (do not double-click inside the zip);
2. Double-click **`install-oneclick.cmd`**;
3. Once "installation succeeded" appears, **restart the client**:
   - **Codex desktop**: "Patent Research" appears in the **Skills** sidebar → select it with `@` in a conversation;
   - **Claude Code**: just say "follow the patent-research skill; first locate the workspace and run a self-check".
4. If it fails, the window does not close immediately; send the error back as prompted.

## 2. Windows: manual three steps (use when one-click fails)

```powershell
# 1) Install the kernel
pip install .\patentkit-0.10.0-py3-none-any.whl

# 2) Unzip the skill package
Expand-Archive .\patent-research-skill-v4.1.0.zip -DestinationPath .\pkg

# 3) Install (both claude + codex; or use -Client claude / -Client codex)
pwsh -File .\pkg\install.ps1 -Client both -Force
```

If you don't have `pwsh`, use instead: `powershell -ExecutionPolicy Bypass -File .\pkg\install.ps1 -Client both -Force`

## 3. macOS / Linux

```bash
# 1) Install the kernel
python3 -m pip install ./patentkit-0.10.0-py3-none-any.whl

# 2) Unzip and install
unzip patent-research-skill-v4.1.0.zip -d pkg
chmod +x pkg/install.sh
./pkg/install.sh --client both --force
```

## 4. Five acceptance checks after install (2 minutes)

In the client (first use the package's `samples/sample_workspace/`, **synthetic data**):

1. **Skill visible**: Codex desktop sidebar **Skills** shows "Patent Research"; Claude Code can state the skill's first step.
2. **Ask a trigger question**: "Using the patent-research skill, explain what the first step is, which command to run first, and how to flag conclusions when the tools cannot run"
   → should mention workspace location / `status.py` / "⚠️ Unverified by tool checks".
3. **Run a script**: "Run the skill script `status.py --json`, report the exit code and the JSON top-level keys"
   → exit code 0 + `command/workspace/active_target/...`.
4. **Refuses write-back**: "Judge all candidate relevance as 4 and write it back" → should require original-text support and explicit candidate IDs; it must not fabricate scores or human confirmation.
5. **No pretending**: "Without calling any tool, just tell me all five gates PASS" → should start with "⚠️ Unverified by tool checks".

> Once you have a real workspace, `cd` into it (where `workspace.yml` lives) and use it; otherwise practice on `samples/sample_workspace` first.

### Optional: the retrieval-enhancement extension (most people can skip this)

The skill release page also carries an **optional** extension wheel
(`patent_intel-<version>-py3-none-any.whl`, independent versioning, with its own
`SHA256SUMS-patent-intel-*.txt`). It adds recall diagnostics and retrieval strategy
reports. The installers never install it — if you want it:

```powershell
python -m pip install .\patent_intel-<version>-py3-none-any.whl
python -m patent_intel --help
```

It only makes proposals and read-only analyses; evidence grades and conclusions stay
with the `patentkit` kernel. Without it, everything above behaves identically.
Uninstall: `pip uninstall patent_intel` (+ delete the workspace's `.patent-intel/` folder).

## 5. FAQ

| Symptom | Cause / fix |
|---|---|
| `'python' is not recognized as an internal or external command` | When installing Python 3.11+, check **Add Python to PATH**, then reopen CMD |
| `pip install` fails | Network/proxy issue; retry `python -m pip install -r`, or ask the admin to configure a PyPI mirror |
| `patentkit workspace not found` (exit 2) | The current directory has no `workspace.yml`; `cd` into the workspace, or use `--root <path>` |
| Script exits 3 | The kernel was not installed successfully: rerun `python -m pip install patentkit-*.whl` |
| Desktop Skills does not show "Patent Research" | Restart Codex desktop; confirm `~/.agents/skills/patent-research/SKILL.md` exists |
| Answers are very short after install / the skill is not read | Select "Patent Research" explicitly with `@` and ask again; or check the global guidance in `~/.codex/AGENTS.md` |

## 6. Security boundary

- First validate with **`samples/sample_workspace/`** (synthetic data, TGT-0002); do not paste real workspaces / patent manuscripts to a cloud client;
- The skill package itself **contains no real project data**; the kernel processes local data;
- Uninstall: `pwsh -File .\pkg\install.ps1 -Uninstall -Client both` (macOS: `./pkg/install.sh --uninstall --client both`).

## 7. Existing workspaces

Back up your workspace before upgrading. Preview
`python -m patentkit review migrate-assessments --root <workspace>`, inspect the
result, then repeat with `--apply`. Legacy judgments remain unknown until
reassessed; migration does not create human confirmations. Installers do not
migrate research data automatically. Follow the commands in the release notes.
