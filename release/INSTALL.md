# 安装 `patent-research-skill`

> 这是一个**可独立分发的技能包**：给 Codex CLI / Claude Code 等能读写本地文件、
> 能执行本地命令的 AI 客户端用。它包含方法论（`SKILL.md` + `references/`）和
> 可执行脚本（`scripts/`），**不含任何真实项目的检索数据或专利稿件**。
>
> 证据口径、五门验收门等规则实现在 `patentkit` 内核里；本包只做「怎么做事」。

## 获取安装包

- 技能包 zip：<https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/skill-v2.3.0> →
  `patent-research-skill-v2.3.0.zip`
- 内核 wheel / sdist：<https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.1.1>
- 校验：同页 `SHA256SUMS-*.txt`；Windows 可用 `Get-FileHash <文件> -Algorithm SHA256` 核对。

## 前置条件

| 依赖 | 要求 | 检查 |
|---|---|---|
| Python | ≥ 3.11 | `python --version` |
| patentkit | 已安装（内核） | `python -m patentkit doctor` |

```powershell
pip install patentkit                 # 有发布源时
# 或从内网 git / 仓库安装：
pip install "git+https://<内网git地址>"
```

> 没装内核也能装技能包，但脚本会以 exit 3 提示你先装 `patentkit`。

## 三步安装

在**解压后的发布包根目录**执行（目录里应有 `manifest.json`、`patent-research/`、`samples/`）：

```powershell
# 1) 预览（不写任何文件）
pwsh -File .\install.ps1 -DryRun

# 2) 安装：Claude Code 默认（~/.claude/skills/patent-research/）
pwsh -File .\install.ps1 -Client claude
#    Codex CLI：~/.agents/skills/patent-research/
pwsh -File .\install.ps1 -Client codex
#    两个都装：
pwsh -File .\install.ps1 -Client both

# 3) 自检（安装脚本默认已跑；也可手动）
python "$HOME/.claude/skills/patent-research/scripts/status.py" --root ".\samples\示例工作区"
```

macOS / Linux / WSL：

```bash
chmod +x install.sh
./install.sh --dry-run
./install.sh --client claude
```

### 安装到哪里

| 客户端 | 默认技能根目录 | 安装后 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `~/.claude/skills/patent-research/` |
| Codex CLI | `~/.agents/skills/` | `~/.agents/skills/patent-research/` |
| 自定义 | `-Dest <技能根目录>` / `--dest <目录>` | `<目录>/patent-research/` |

> **目录名必须等于 `SKILL.md` 的 `name`（`patent-research`）** —— 客户端按目录/name 识别技能，
> 改错名字可能识别不到。安装脚本会自动处理。

## 验证可用

1. 装完自检应显示「✅ 自检通过」。
2. 在客户端里说：「跑一遍专利新颖性核查」/「看看这个专利工作区的状态」/
   「N1 轴的检索式是什么」——技能应被触发并执行 `scripts/` 里的命令。
3. 用真实工作区前，先在包里 `samples/示例工作区/` 上练手（合成数据，随便折腾）。

## 升级

```powershell
# 1) 换新包：解压到新目录，先预览
pwsh -File .\install.ps1 -DryRun

# 2) 覆盖安装（会替换旧版本）
pwsh -File .\install.ps1 -Client both -Force

# 3) 升级内核（如发布说明要求）
pip install -U patentkit
```

> 升级前可先看 `manifest.json` 的 `skill.version` 与 `compat.patentkit`；
> 跨大版本升级以发布说明为准。手工安装的，直接替换技能目录即可。

## 卸载

```powershell
pwsh -File .\install.ps1 -Uninstall -Client both
```

`patentkit` 内核用 `pip uninstall patentkit` 移除；工作区数据不受影响。

## 手动安装（不想用脚本）

1. 把 `patent-research/` 复制到客户端技能根目录，并**改名为 `patent-research`**（包内已叫这个名）。
2. 确认 `SKILL.md` 在目录第一层。
3. 跑自检：`python <技能目录>/scripts/status.py --root samples/示例工作区`。

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `install.ps1` 报「找不到 manifest.json」 | 没在发布包根目录运行 | `cd` 到解压目录再跑，或 `chmod +x install.sh` |
| 自检 exit 3 | 没装 `patentkit` / Python 版本低 | `pip install patentkit`；确认 `python --version` ≥ 3.11 |
| 自检 exit 2 | 工作区定位失败 | 用 `--root <工作区>`；或 `cd` 进含 `workspace.yml` 的目录 |
| 客户端识别不到技能 | 技能目录名 ≠ `SKILL.md` 的 `name` | 目录改名为 `patent-research` |
| 客户端不自动触发 | 客户端版本/设置问题 | 手动 `/patent-research` 或把需求说得更具体（检索/新颖性/证据链） |
| 中文乱码 | 控制台编码 | 脚本已强制 UTF-8；客户端捕获按 UTF-8 解码 |

## 安全与保密

- 本包不含真实候选、检索日志、判定结论、稿件正文；`samples/` 是**合成数据**。
- 脚本只调用本地 `patentkit` 读你指定的工作区，不联网、不上传。
- 但**客户端本身可能联网**（云端推理）：真实工作区的候选标题、判定结论、稿件正文
  **不要**贴给公网客户端。纯对话客户端只能到 `asserted` 等级，结论必须标
  「⚠️ 未经验证工具校验」。

## 包结构

```
patent-research-skill-v<版本>/
├── manifest.json       版本 + 兼容性 + 全部文件 sha256
├── INSTALL.md          本文件
├── install.ps1 / install.sh
├── patent-research/    ← 安装到客户端的就是它
│   ├── SKILL.md        主入口：何时触发 / 执行顺序 / 硬约束 / 结果格式
│   ├── references/     6 份方法论（按需加载）
│   ├── scripts/        status / validate / gates / report / check
│   ├── assets/         报告模板、空白对比矩阵、合成示例
│   └── README.md
└── samples/示例工作区/  脱敏工作区（TGT-0002，合成数据）
```
