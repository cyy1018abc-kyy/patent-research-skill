# patent-research-skill

> 面向「专利现有技术检索 / 新颖性创造性自检 / 检索证据链与验收门（G-S）」的 **Agent Skill** 发行仓库。
> 支持 Claude Code、Codex CLI、Codex 桌面端（ChatGPT App）。

本仓库只包含**可分发物**：技能包源码、安装器、构建工具与发行说明。
**不含任何真实项目数据、专利稿件、目标 ID 或候选编号**；示例工作区为合成数据（`TGT-0002`）。

## 下载与安装

到 [Releases](https://github.com/cyy1018abc-kyy/patent-research-skill/releases) 下载：

| 附件 | 说明 |
|---|---|
| `patent-research-skill-v<版本>.zip` | 技能包（含安装脚本 + 脱敏示例工作区） |
| `patentkit-<版本>-py3-none-any.whl` | 内核（Python 包；`patentkit` ≥0.1.1） |
| `INSTALL-colleagues.md` | 给同事的一页纸安装说明 |

### Windows 一键

把 zip、wheel、`install-oneclick.cmd`（从 zip 解压）放同一文件夹，双击 `install-oneclick.cmd`。

### 手动（任意平台）

```powershell
pip install ./patentkit-0.1.1-py3-none-any.whl
Expand-Archive ./patent-research-skill-v2.3.0.zip -DestinationPath ./pkg
pwsh -File ./pkg/install.ps1 -Client both -Force
```

```bash
python3 -m pip install ./patentkit-0.1.1-py3-none-any.whl
unzip patent-research-skill-v2.3.0.zip -d pkg
chmod +x pkg/install.sh && ./pkg/install.sh --client both --force
```

安装后重启客户端：Codex 桌面端侧边栏 **Skills** 出现「专利调研」，对话里用 `@` 选择；
Claude Code 直接说「按 patent-research 技能……」即可。

## 目录

```
patent-research-skill/   SKILL.md + references/ + scripts/ + assets/ + agents/openai.yaml
release/                 安装脚本（ps1/sh/oneclick）、安装说明、发布说明
tools/build_skill_release.py   发布包构建（manifest + sha256 + 脱敏示例工作区）
.github/workflows/ci.yml       构建冒烟 + 安装脚本 dry-run
```

## 构建发布包

```bash
pip install pyyaml
PATENTKIT_COMPAT_VERSION=0.1.1 python tools/build_skill_release.py --out dist --json
# 默认生成含 samples/示例工作区 的 zip（需要本机装有 patentkit >=0.1.1）
```

## 要求

- Python ≥ 3.11（技能脚本运行需要）
- `patentkit` ≥ 0.1.1（从 Releases 的 wheel 安装）
- Codex CLI ≥ 0.161（桌面端自带新版运行时，无需升级）

## 关于基底 skills 与许可

本技能的方法论参考了以下公开 Agent Skills 的思路（**未 vendor 其代码/文档**）：

- `cn-patent-drafter`（Apache-2.0）
- `patent-disclosure-skill`（Apache-2.0）
- `patent-validity-checker`（Apache-2.0）

本仓库代码与技能包以 **Apache-2.0** 发布（见 [LICENSE](LICENSE)）。

## 安全边界

- 技能包与示例数据均为合成内容；使用真实工作区时请勿把未公开材料上传到云端客户端；
- 内核 `patentkit` 按 wheel 分发；本仓库不含其源码。

## 版本

当前技能包 **2.3.0**；变更见 [CHANGELOG.md](CHANGELOG.md)。
