# 技能包 patent-research-skill v2.3.0

面向「专利现有技术检索 / 新颖性创造性自检 / 检索证据链与验收门（G-S）」的 Agent Skill 安装包。
Claude Code、Codex CLI、Codex 桌面端（ChatGPT App）通用。

## 本版变化（2.2.0 → 2.3.0）

- **新增 Windows 一键安装器** `install-oneclick.cmd`：自动检查 Python ≥3.11 →
  安装内核 wheel（失败回退 `--user`）→ 解压技能包 → 调 `install.ps1 -Client both -Force`；
  支持 `--quiet`（自动化验收用）。
- **新增一页纸安装说明** `安装说明-给同事.md`：Windows 一键/手动、macOS/Linux、5 条验收、
  常见问题、安全边界（随包内为中文名 `安装说明-给同事.md`；本 Release 附件用 ASCII 文件名 `INSTALL-colleagues.md`）。
- 构建期校验：发布包必须包含以上两文件；测试锁定内容（非空壳）。
- 内核 `patentkit` 保持 **0.1.1** 不变。

## 附件与校验

| 附件 | SHA-256 |
|---|---|
| `patent-research-skill-v2.3.0.zip` | `affdd410919ef21ab6f3157d421d46af3ccf066003ba60710f428d957fcd1f16` |
| `INSTALL-colleagues.md`（一页纸，中文内容） | `666bb0253d103254f96aa03fa30938817026e996da007a674758e115ef517a02` |
| `SHA256SUMS-skill-v2.3.0.txt` | — |

## 安装（三种方式）

### A. Windows 一键（最简单）

1. 从本 Release 下载：`patent-research-skill-v2.3.0.zip` + `patentkit-0.1.1-py3-none-any.whl`；
2. 从 zip 里解压出 `install-oneclick.cmd`（与上面两个文件放同一文件夹）；
3. 双击 `install-oneclick.cmd`，看到「安装成功」后重启客户端。

### B. Windows 手动

```powershell
pip install .\patentkit-0.1.1-py3-none-any.whl
Expand-Archive .\patent-research-skill-v2.3.0.zip -DestinationPath .\pkg
pwsh -File .\pkg\install.ps1 -Client both -Force
```

### C. macOS / Linux

```bash
python3 -m pip install ./patentkit-0.1.1-py3-none-any.whl
unzip patent-research-skill-v2.3.0.zip -d pkg
chmod +x pkg/install.sh && ./pkg/install.sh --client both --force
```

> 没有内网 Python 源时，内核也可 `pip install "git+https://github.com/cyy1018abc-kyy/patent-research-skill.git@patentkit-v0.1.1"`。

## 验证记录（2026-10-22）

- Claude Code 2.1.206：P3 13/13
- Codex CLI 0.161.0 / 官方免费账号：P3 13/13
- Codex 桌面端 26.1016.6573.0（内置运行时 0.163.0-alpha.11）：抽查 12/13、10/13（可用；
  建议 `@` 显式选择「专利调研」）
- 一键安装器本机端到端：exit 0，成功安装 v2.3.0 到 `~/.claude/skills` + `~/.agents/skills`

## 要求

- Python ≥ 3.11；`patentkit` ≥ 0.1.1（自动安装）
- 客户端能读写本地文件、执行本地命令
- Codex CLI 需 ≥0.161；桌面端自带 0.163 无需升级

## 不含

真实项目数据、专利稿件、真实目标 ID / 候选编号 / 公开号。示例工作区为合成数据（`TGT-0002`）。
