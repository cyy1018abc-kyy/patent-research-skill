# Skill package patent-research-skill v2.3.3

Agent Skill installation package for "patent prior-art search / novelty & inventive-step self-check / search evidence chain and acceptance gates (G-S)".
Works with Claude Code, Codex CLI, and Codex desktop (ChatGPT App).

## Changes in this release (2.2.0 → 2.3.3)

- **Added a Windows one-click installer** `install-oneclick.cmd`: automatically checks Python ≥3.11 →
  installs the kernel wheel (falls back to `--user` on failure) → unzips the skill package → calls `install.ps1 -Client both -Force`;
  supports `--quiet` (for automated acceptance runs).
- **Added a one-page install guide** `install-guide-for-colleagues.md`: Windows one-click/manual, macOS/Linux, 5 acceptance checks,
  FAQ, security boundary (inside the package the guide is `install-guide-for-colleagues.md`; this Release asset uses the ASCII filename `INSTALL-colleagues.md`).
- Build-time validation: the release package must contain both files above; tests pin down the content (no empty shells).
- Kernel `patentkit` stays at **0.1.2**.

## Assets and verification

| Asset | SHA-256 |
|---|---|
| `patent-research-skill-v2.3.3.zip` | `9e8a2a4fbc400259a6ae7b2dd363b5a23c34081963ef063999ef555fa11dce03` |
| `INSTALL-colleagues.md` (one-pager, Chinese content) | `9e8a2a4fbc400259a6ae7b2dd363b5a23c34081963ef063999ef555fa11dce03` |
| `SHA256SUMS-skill-v2.3.3.txt` | — |

## Installation (three options)

### A. Windows one-click (simplest)

1. Download from this Release: `patent-research-skill-v2.3.3.zip` + `patentkit-0.1.2-py3-none-any.whl`;
2. Extract `install-oneclick.cmd` from the zip (put it in the same folder as the two files above);
3. Double-click `install-oneclick.cmd`; once "installation succeeded" appears, restart the client.

### B. Windows manual

```powershell
pip install .\patentkit-0.1.2-py3-none-any.whl
Expand-Archive .\patent-research-skill-v2.3.3.zip -DestinationPath .\pkg
pwsh -File .\pkg\install.ps1 -Client both -Force
```

### C. macOS / Linux

```bash
python3 -m pip install ./patentkit-0.1.2-py3-none-any.whl
unzip patent-research-skill-v2.3.3.zip -d pkg
chmod +x pkg/install.sh && ./pkg/install.sh --client both --force
```

> Without an internal Python index, the kernel can also be installed with `pip install "git+https://github.com/cyy1018abc-kyy/patent-research-skill.git@patentkit-v0.1.2"`.

## Verification record (2026-10-22)

- Claude Code 2.1.206: P3 13/13
- Codex CLI 0.161.0 / official free account: P3 13/13
- Codex desktop 26.1016.6573.0 (bundled runtime 0.163.0-alpha.11): spot checks 12/13, 10/13 (usable;
  selecting "Patent Research" explicitly via `@` is recommended)
- One-click installer end-to-end on this machine: exit 0, v2.3.3 successfully installed to `~/.claude/skills` + `~/.agents/skills`

## Requirements

- Python ≥ 3.11; `patentkit` ≥ 0.1.2 (installed automatically)
- The client can read/write local files and execute local commands
- Codex CLI requires ≥0.161; the desktop bundles 0.163 so no upgrade is needed

## Not included

Real project data, patent manuscripts, real target IDs / candidate numbers / publication numbers. The sample workspace is synthetic data (`TGT-0002`).
