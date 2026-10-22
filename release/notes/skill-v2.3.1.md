# patent-research-skill v2.3.1

Agent Skill package for patent prior-art search, novelty/inventiveness self-check,
evidence-chain management, and acceptance gates (G-S).
Works with Claude Code, Codex CLI, and the Codex desktop app.

## Changes (2.3.0 -> 2.3.1)

- Repository documentation, release notes, and installer messages translated to English.
- The one-page install guide is shipped as `INSTALL-colleagues.md` (ASCII filename).
- Skill runtime content (`SKILL.md`, `references/`, script output, sample data) remains
  in Chinese because the skill targets Chinese patent practice.
- Kernel `patentkit` remains **0.1.1**.

## Assets

| Asset | SHA-256 |
|---|---|
| `patent-research-skill-v2.3.1.zip` | `03e8dcc161719b62bb90babea45e8cb6eb2b21a16baf4682ed0ba00de749ac4b` |
| `INSTALL-colleagues.md` | see `SHA256SUMS-skill-v2.3.1.txt` |
| `SHA256SUMS-skill-v2.3.1.txt` | — |

## Install

### Windows one click

1. Download `patent-research-skill-v2.3.1.zip` and `patentkit-0.1.1-py3-none-any.whl`;
2. Extract `install-oneclick.cmd` from the zip and put all three files in one folder;
3. Double-click `install-oneclick.cmd`.

### Manual

```powershell
pip install .\patentkit-0.1.1-py3-none-any.whl
Expand-Archive .\patent-research-skill-v2.3.1.zip -DestinationPath .\pkg
pwsh -File .\pkg\install.ps1 -Client both -Force
```

```bash
python3 -m pip install ./patentkit-0.1.1-py3-none-any.whl
unzip patent-research-skill-v2.3.1.zip -d pkg
chmod +x pkg/install.sh && ./pkg/install.sh --client both --force
```

## Requirements

- Python >= 3.11
- `patentkit` >= 0.1.1
- Codex CLI >= 0.161 (the desktop app bundles a newer runtime)

## Contains no real data

No real project data, patent drafts, target IDs, or candidate IDs.
The sample workspace is synthetic (`TGT-0002`).
