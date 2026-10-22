# patent-research-skill 安装与使用

> **这是什么**：一个可独立分发的「专利调研」技能包 —— 把专利现有技术检索、新颖性/创造性自检、
> 证据链管理的**方法论**（`SKILL.md` + `references/`）和**可重复执行的操作**（`scripts/`）打包在一起，
> 让 Codex CLI / Codex 桌面端 / Claude Code 等能读写本地文件、执行本地命令的客户端直接使用。
>
> **不包含**：任何真实项目的候选清单、检索日志、判定结论、稿件正文。技能包可公开/组内自由分发。

## 包内结构

```
patent-research-skill/
├── SKILL.md          主入口：何时触发、执行顺序、硬约束、结果格式（常驻客户端 context）
├── references/       6 份方法论文档，按需加载（04 证据等级制度是前提）
├── scripts/          状态/校验/门禁/报告 薄封装（规则实现仍在 patentkit 内核）
├── assets/           报告模板、空白对比矩阵、示例数据（合成数据）
└── README.md         本文件
```

## 安装

### 方式 A：从发布包安装（推荐）

发布包（`dist/patent-research-skill-v<版本>.zip`）自带安装脚本、示例工作区与 sha256 清单，
不必手工改目录名。三步：

1. **装内核**（只装一次）：
   ```powershell
   pip install patentkit                    # 有发布源时
   pip install "git+https://<内网git地址>"   # 或内网 git
   ```
2. **解压并安装**（脚本会把技能目录改名为 `patent-research/` 并跑自检）。
   没有 zip？直接从 [`skill-v2.3.0` Release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/skill-v2.3.0)
   下载 `patent-research-skill-v2.3.0.zip`（附件附 SHA-256）。

   Windows：
   ```powershell
   Expand-Archive .\patent-research-skill-v2.3.0.zip -DestinationPath .\pkg
   pwsh -File .\pkg\install.ps1 -DryRun           # 先预览，不写文件
   pwsh -File .\pkg\install.ps1 -Client both      # Claude Code + Codex CLI
   ```

   macOS / Linux / WSL：
   ```bash
   unzip patent-research-skill-v2.3.0.zip -d pkg
   ./pkg/install.sh --dry-run
   ./pkg/install.sh --client both
   ```
3. **验证**：安装脚本会用包内 `samples/示例工作区/`（合成数据）跑一次自检；也可手动：
   ```powershell
   python "$HOME/.claude/skills/patent-research/scripts/status.py" --root ".\pkg\samples\示例工作区"
   ```

> 升级：`install.ps1 -Force` / `install.sh --force`；卸载：`-Uninstall` / `--uninstall`；
> 自定义位置：`-Dest <技能根目录>` / `--dest <目录>`。完整说明见发布包内 `INSTALL.md`。

### 方式 B：手工放置（仓库内开发 / 无脚本环境）

#### 1. 安装内核 `patentkit`

技能包只做「怎么做事」，阈值与判定在 `patentkit` 内核里：

```powershell
pip install patentkit                 # 有内网源/发布包时
# 或在仓库开发：cd <仓库根>; pip install -e ".[dev]"
```

要求：Python ≥ 3.11；依赖 `jsonschema`、`PyYAML`（pip 自动装）。

#### 2. 放置技能包

| 客户端 | 放哪 |
|---|---|
| Claude Code（用户级） | `~/.claude/skills/patent-research/`（整个目录） |
| Claude Code（项目级） | `<工作区>/.claude/skills/patent-research/` |
| Codex CLI | 客户端支持 skills 目录时同上；只认 `AGENTS.md` 时，把 `SKILL.md` 正文并入工作区 `AGENTS.md`，保留 `references/` 相对路径 |
| Codex 桌面端（ChatGPT App） | 用户级 `~/.agents/skills/patent-research/`（`install.ps1 -Client both` 已覆盖）；侧边栏 **Skills** 可见，对话里用 `@` 选择；`agents/openai.yaml` 提供显示名与 `@` 默认提问 |
| 其它本地客户端 | 能读本地文件、能执行命令的，用自己的规则文件引用 `SKILL.md` 即可 |

> **目录名必须改成 `patent-research/`**（= `SKILL.md` 的 `name`），直接沿用
> `patent-research-skill/` 可能识别不到；复制时排除 `__pycache__` 等缓存。
> 不同客户端的技能发现机制会变，以 P3 跨客户端测试记录为准（见仓库 `跨客户端测试/`）。

#### 3. 自检

```powershell
cd <你的专利工作区>                     # 有 workspace.yml 的目录
python <skill目录>/scripts/status.py    # 期望 exit 0，打印目标/门禁/校验/下一步
```

工作区还没有？先初始化：

```powershell
python -m patentkit init <你的专利目录> --target TGT-0002 --title "发明名称"
```

## 在客户端里怎么用

说人话即可，例如：

- 「看看这个专利工作区的状态」→ 触发 `scripts/status.py` / `patentkit status`
- 「N1 轴的检索式是什么」→ 读 `references/02` + `patentkit search-plan --axis N1`
- 「跑一遍新颖性核查」→ 按 `SKILL.md` 执行顺序走 0–4 步，结论按「结果格式」输出
- 「交稿前核对权项数值有没有依据」→ 读 `references/06` + `scripts/check.py`

**硬约束**（完整版见 `SKILL.md`）：门禁 PASS 只认 `verified` 列；不替用户判定 `relevance`；
跑不了工具时必须标「⚠️ 未经验证工具校验」。模型代判一律降为 `asserted`。

## 脚本一览

| 脚本 | 作用 | 常用参数 | 退出码 |
|---|---|---|---|
| `scripts/status.py` | 目标/门禁/校验/候选/下一步 | `--root` `--json` | 0 / 2 / 3 |
| `scripts/validate.py` | 一致性校验 V001–V028 | `--strict` `--root` `--json` | 0 通过 / 1 失败 |
| `scripts/gates.py` | 五门 × 三列验收门 | `--target` `--root` `--json` | 0 全 PASS / 1 未全 PASS |
| `scripts/report.py` | 生成对比 run 骨架 | `--target` `--out` `--root` | 0 / 1 / 2 / 3 |
| `scripts/check.py` | `validate --strict` + `gates` | `--root` `--json` | 0 / 1 / 2 / 3 |

**退出码约定**：`0` 成功；`1` 业务失败（校验有错/门未全 PASS）；`2` 工作区定位失败；
`3` 依赖缺失（未装 `patentkit` 或 Python < 3.11）。

> 注意：`patentkit gates` 原生命令把「门未全 PASS」当 exit 2；脚本层为区分「工作区错误」
> 归一为 exit 1。CI 若依赖原始退出码，直接用 `patentkit` 命令。

工作区解析顺序与内核一致：`--root` → 环境变量 `PATENTKIT_WORKSPACE` → 向上找 `workspace.yml`。
想在任何目录都能用，设一次：

```powershell
[Environment]::SetEnvironmentVariable("PATENTKIT_WORKSPACE", "<你的专利工作区>", "User")
```

## 升级

1. `pip install -U patentkit`（内核）
2. 用新版本 zip/目录替换技能包目录（旧目录可先改名备份）
3. 跑一次 `python scripts/status.py --json` 与 `python scripts/check.py`，确认退出码与字段兼容
4. 版本兼容：技能包 `metadata.version` ↔ 内核发行版本（唯一来源 `patentkit.__version__`，`pyproject.toml` 动态读取）；跨大版本升级见发布包 `manifest.json`

## 卸载

删除技能包目录即可；`pip uninstall patentkit` 移除内核（工作区数据不受影响）。

## 兼容性与证据等级上限

| 客户端能力 | 能做什么 | 证据等级上限 |
|---|---|---|
| 读本地文件 + 执行命令（Claude Code、Codex CLI、Cursor、Cline…） | 全流程：检索 → 入库 → 门禁 → 报告 | `verified` |
| 只读文件、不能执行命令 | 只能按 references 讲方法、检查文档 | `asserted` |
| 纯对话（网页版，不能读本地文件） | 只能上传 `references/` 当知识库讲方法 | `asserted` |

> **保密边界**：真实工作区的候选标题、判定结论、稿件正文**不要贴给公网客户端**。
> 技能包本身不含数据，但不代表把数据贴到云端就安全。

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `exit 2`，提示「找不到工作区」 | 当前目录不在工作区内 | `cd` 进工作区 / 加 `--root` / 设 `PATENTKIT_WORKSPACE` |
| `exit 3`，提示未安装 `patentkit` | 内核没装或装到了别的 Python | 用同一解释器 `pip install patentkit`，`python -c "import patentkit"` 验证 |
| 输出中文乱码 | 控制台编码不是 UTF-8 | 脚本已强制 UTF-8；客户端捕获时按 UTF-8 解码 |
| 门禁全 FAIL 但数据看着齐 | 看的是 `asserted` 列，或缺 `raw/` 产物 | 读 `references/04`、`references/05`，补 `raw/` 与 `capture_mode=live` 日志 |
| 校验报 V009/V013 | 没有原始产物却标了 `verified` | 重跑检索并落 `raw/`；不要改数据绕过 |

## 安全与许可

- 技能包**不含可执行二进制、不含网络代码**；脚本只调用本地 `patentkit` 读工作区数据。
- 分发包**不含 `.git`**；发布前用干净副本做安全扫描（SkillSpector，`degraded` 的 analyzer 如实标注）。
- 许可：Apache-2.0（与 `patentkit` 及依赖的方法论一致）。
