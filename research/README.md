# patent-research 技能：安装与使用（检索/查新/证据链）

> **这是什么**：可独立分发的「专利调研」技能（v3.0.0 起与 `patent-drafting` 拆分为两个技能、同一发布包安装）。——**方法论**（`SKILL.md` + `references/`）
> + **可复现操作**（`scripts/` 薄封装 + `patentkit` 内核）。任何能读写本地文件、执行本地命令的
> 客户端（Codex CLI / Codex 桌面 / Claude Code / Cursor / Cline…）都能直接用。
>
> **不含**：任何真实项目的候选清单、检索日志、判定结论或稿件正文。本包可自由分发（公开或团队内）。
>
> **语言**：自 2.5.0 起运行时文档为**中文主版本**（目标场景是中国专利实践）；
> 英文镜像存于 `references.en/`（01–08 与 00/09–13 双侧维护）。

## 3.4.0 新增（普查证据口径，内核 0.6.0）

| 能力 | 命令 |
|---|---|
| G-S-04 改核验普查记录（census）：查过 + 工件哈希绑定，零命中也算查过；未查/部分/失败不得冒充完整 | `patentkit gates`（判定见 `patentkit/census.py` 与 references/05） |
| 从归档普查工件回填 family/cited_by 并自动写普查记录；人工评审候选默认跳过（`--force` 留审计） | `patentkit fetch-bigquery --fill <raw> [--apply] [--force]` |
| 普查费用预估与预算上限（官方 dry-run `total_bytes_processed` 口径） | `patentkit fetch-bigquery --run [--max-cost-usd 5]` |
| 旧工作区候选 schema 刷新（新增 census 属性，V037 随之生效） | `python -m patentkit migrate` |

（安装后引用闭环为纯检查能力：`tools/check_reference_links.py`，CI 对仓库树与解包双 zip 各跑一遍。）

## 3.2.0 新增（检索规划与改稿闭环，内核 0.4.0）

| 能力 | 命令 |
|---|---|
| 每轴检索覆盖规划：已登记 vs 已执行子查询、G-S-02 缓冲、确定性补查骨架（只追加进查询库） | `patentkit queryplan [--axis N1] [--apply]` |
| 证据链全景：日志→候选池→D 列→判定→账本→五门，一页离线 HTML | `patentkit chain <TGT>` |

（改稿闭环 `patentkit revise` 属于 patent-drafting 技能，见其 references/13。）

## 2.5.0 新增（交付安全层，内核 0.3.0）

| 能力 | 命令 |
|---|---|
| .docx 查新报告（数字全部来自工作区，零手工转写） | `patentkit export-docx <TGT>` / `scripts/export_docx.py` |
| 离线自包含 HTML 对比总览（无外链无脚本） | `patentkit map <TGT>` |
| 1+N 多目标组合视图（只读） | `patentkit layout` |
| 证据账本（结论只准引用账本内的编号，V034 拦截） | `patentkit ledger` |
| 数值声明 A/B/C 溯源（V031/V032 fail-closed） | `patentkit provenance scan/check` |
| 附图标记双向一致性（V033 warn）+ SVG 框图 | `patentkit figures check/draw` |
| 提交后期限台账（以官方发文为准） | `patentkit deadlines list/check/init` |
| 安装后自检（六项正反用例 + docx 冒烟） | `scripts/self_test.py` |

## 包结构

```
patent-research-skill/
├── SKILL.md          主入口：何时触发 / 执行顺序 / 硬约束 / 结果格式（常驻客户端上下文）
├── references/       13 篇方法论文档 + glossary.md 术语表（按需加载；04 最先读）
├── references.en/    英文镜像（01–07 双侧维护；术语一致性由 evals/check_terminology.py 锁定）
├── scripts/          status/validate/gates/report/check/self_test/export_docx 薄封装
├── assets/           检索报告模板、空白对比矩阵、合成示例数据
└── README.md         本文件
```

## 安装

### 方式 A：用发布包安装（推荐）

发布包（`dist/patent-research-skill-v<版本>.zip`）自带安装器、合成样例工作区与
SHA-256 清单，无需手工改名。三步：

1. **装内核**（一次性）：
   ```powershell
   python -m pip install ./patentkit-0.10.0-py3-none-any.whl
   # 需要 docx 导出时加可选依赖：
   python -m pip install python-docx
   ```
2. **解压并安装**（脚本会把技能目录改名为 `patent-research/` 并跑自检）。
   没有 zip？从 [GitHub Releases](https://github.com/cyy1018abc-kyy/patent-research-skill/releases)
   下载最新的 `skill-v<x>` Release（附件附 SHA-256）。

   Windows：
   ```powershell
   Expand-Archive .\patent-research-skill-v2.5.0.zip -DestinationPath .\pkg
   pwsh -File .\pkg\install.ps1 -DryRun           # 先预览；不写任何文件
   pwsh -File .\pkg\install.ps1 -Client both      # Claude Code + Codex CLI
   ```

   macOS / Linux / WSL：
   ```bash
   unzip patent-research-skill-v2.5.0.zip -d pkg
   ./pkg/install.sh --dry-run
   ./pkg/install.sh --client both
   ```
3. **验证**：安装器会对包内 `samples/sample_workspace/`（合成数据）跑自检；也可手工：
   ```powershell
   python "$HOME\.claude\skills\patent-research\scripts\self_test.py"
   ```

> 升级：`install.ps1 -Force` / `install.sh --force`；卸载：`-Uninstall` / `--uninstall`；
> 自定义位置：`-Dest <目录>` / `--dest <目录>`。详见发布包内 `INSTALL.md`。

### 方式 B：手工放置（仓内开发 / 无脚本环境）

#### 1. 安装 `patentkit` 内核

技能包只讲「怎么做」；阈值与判定都在内核：

```powershell
python -m pip install patentkit          # 有发布源时
# 或仓内开发：cd <repo-root>; pip install -e ".[dev]"
```

开发版技能 2.5.0 要求 patentkit ≥0.3.0（评估协议 1；0.3.0 新增 export-docx/map/layout/
ledger/provenance/figures/deadlines）。Python ≥ 3.11；依赖 `jsonschema`、`PyYAML`。

#### 2. 放置技能包

| 客户端 | 位置 |
|---|---|
| Claude Code（用户级） | `~/.claude/skills/patent-research/`（整个目录） |
| Claude Code（项目级） | `<工作区>/.claude/skills/patent-research/` |
| Codex CLI | 同上（支持技能目录时）；只认 `AGENTS.md` 时，把 `SKILL.md` 正文并入工作区 `AGENTS.md`，保持 `references/` 相对路径 |
| Codex 桌面（ChatGPT App） | 用户级 `~/.agents/skills/patent-research/`（`install.ps1 -Client both` 已覆盖）；侧栏 **Skills** 可见，会话内用 `@` 选择；`agents/openai.yaml` 提供显示名与默认提示词 |
| 其它本地客户端 | 能读本地文件 + 执行命令的，都可在自己的规则文件里引用 `SKILL.md` |

> **目录名必须改成 `patent-research/`**（= `SKILL.md` 里的 `name`）；保留
> `patent-research-skill/` 可能导致不被发现。复制时排除 `__pycache__` 等缓存。

#### 3. 自检

```powershell
python <技能目录>/scripts/self_test.py    # 六项检查；期望 exit 0
```

还没有工作区？先建一个：

```powershell
python -m patentkit init <专利目录> --target TGT-0002 --title "发明名称"
```

## 在客户端里怎么用

直接说人话，例如：

- 「看看这个专利工作区的状态」→ `scripts/status.py` / `patentkit status`
- 「N1 轴的检索式是什么」→ 读 `references/02` + `patentkit search-plan --axis N1`
- 「跑一遍新颖性核查」→ 按 `SKILL.md` 执行顺序 0–4 走完，按「结果格式」汇报
- 「交稿前把权项数值都核一遍」→ `references/06` + `scripts/check.py` + `provenance check`
- 「导出 Word 查新报告」→ `scripts/export_docx.py TGT-0002`
- 「附图标记对不对」→ `patentkit figures check`

**硬约束**（全文见 `SKILL.md`）：门 PASS 只认 `verified` 列；受支持的 AI 判定可计入
G-S-02；G-S-03 需要显式人工确认；来源 `evidence_level` 不因 AI 参与或人工复核而改变；
工具不能跑时结论以「⚠️ 未经验证工具校验」开头。详见 `references/07-评估协议.md`。

## 脚本一览

| 脚本 | 用途 | 常用参数 | 退出码 |
|---|---|---|---|
| `scripts/status.py` | 目标/门禁/校验/候选分布/下一步 | `--root` `--json` | 0 / 2 / 3 |
| `scripts/validate.py` | 一致性校验 V001–V034 | `--strict` `--root` `--json` | 0 过 / 1 不过 |
| `scripts/gates.py` | 五门 × 三列 | `--target` `--root` `--json` | 0 全 PASS / 1 未全 PASS |
| `scripts/report.py` | 对比 run 骨架 | `--target` `--out` `--root` | 0 / 1 / 2 / 3 |
| `scripts/check.py` | `validate --strict` + `gates` | `--root` `--json` | 0 / 1 / 2 / 3 |
| `scripts/self_test.py` | 安装后自检 | `--json` | 0 / 1 / 3 |
| `scripts/export_docx.py` | docx 查新报告（可选依赖） | `<TGT>` `--out` | 0 / 1 / 2 / 3 |

**退出码约定**：`0` 成功；`1` 业务失败；`2` 工作区问题；`3` 缺依赖（内核 /
Python<3.11 / python-docx）。

> 注：原生 `patentkit gates` 把「未全 PASS」记为 exit 2；脚本层归一成 1。CI 依赖原生
> 退出码时直接调 `patentkit`。

工作区定位与内核一致：`--root` → 环境变量 `PATENTKIT_WORKSPACE` → 向上找 `workspace.yml`。
想在任意目录可用：

```powershell
[Environment]::SetEnvironmentVariable("PATENTKIT_WORKSPACE", "<专利工作区>", "User")
```

## 升级

1. `pip install -U patentkit`（或换装新 wheel）
2. 用新 zip/目录替换技能包目录（可先把旧目录改名备份）
3. 跑一遍 `python scripts/self_test.py`，确认退出码与字段兼容
4. 版本兼容：技能包 `metadata.version` ↔ 内核版本（单一来源：`patentkit.__version__`，
   由 `pyproject.toml` 动态读取）；跨大版本升级看发布包内 `manifest.json`

## 卸载

删除技能包目录；`pip uninstall patentkit` 移除内核（工作区数据不受影响）。

## 兼容性与证据等级上限

| 客户端能力 | 能做什么 | 证据等级上限 |
|---|---|---|
| 读本地文件 + 执行命令（Claude Code、Codex CLI、Cursor、Cline…） | 全流程：检索 → ingest → 门禁 → 交付（docx/HTML） | `verified` |
| 只读文件、不能执行命令 | 按 references 讲方法论、检查文档 | `asserted` |
| 纯对话（网页版，读不了本地文件） | 把 `references/` 当知识库讲方法论 | `asserted` |

> **保密边界**：**不要**把真实工作区的候选标题、判定结论、稿件正文粘进任何公网云端
> 客户端。技能包本身不含数据，但这不等于把数据贴进云端是安全的。
> 仓库层还有 `tools/check_no_workspace_data.py` 保密守卫与 `.gitignore` 红线兜底。

## 排障

| 症状 | 原因 | 修法 |
|---|---|---|
| `exit 2`，提示 workspace not found | 当前目录不在工作区内 | `cd` 进工作区 / 加 `--root` / 设 `PATENTKIT_WORKSPACE` |
| `exit 3`，提示 patentkit 未安装 | 内核未装，或装到了另一个 Python | 同一解释器 `pip install patentkit`；`python -c "import patentkit"` 验证 |
| export_docx `exit 3` | 未装可选依赖 python-docx | `pip install "patentkit[docx]"` 或 `pip install python-docx` |
| 输出乱码 | 控制台编码不是 UTF-8 | 脚本已强制 UTF-8；外部捕获时按 UTF-8 解码 |
| 五门全 FAIL 但数据看着齐 | 看的是 `asserted` 列，或 `raw/` 缺失 | 读 `references/04`、`references/05`；补 `raw/` 与 `capture_mode=live` |
| validate 报 V009/V013 | 没有 raw 工件却标了 verified | 重跑检索并落 `raw/`；不要改数据绕过 |
| validate 报 V031/V032 | 数值声明无 A/B/C 来源 | `provenance scan` 重建骨架并人工补 sources |
| validate 报 V034 | 结论引用了账本外编号 | `patentkit ledger` 对账；改结论或先补文献 |

## 安全与许可

- 技能包**不含可执行二进制、不含联网代码**；脚本只调用本地 `patentkit` 读写工作区数据；
  `map` 生成的 HTML 无外链无脚本，离线可开。
- 发布包不含 `.git`；发布前在干净副本上做安全扫描（SkillSpector；报告为 `degraded` 的
  分析器如实标注）。
- 许可：Apache-2.0（与 `patentkit` 及其依赖的方法论一致）。
