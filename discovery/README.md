# patent-discovery（专利点挖掘技能）

> 从私有研发材料到**可追溯、可人工确认、可交接**的专利候选点。
> 本目录是 `patent-research-skill` 仓库下的第三个技能载荷（v3.9.0），
> 与 `research/`（检索/证据链）和 `drafting/`（撰写底稿）共用唯一内核 `patentkit`。

## 何时使用

- 要把设计文档、Word/PDF、代码、CSV、受控 Simulink 导出整理成专利候选点；
- 要逐条抽取**技术事实**并保留来源定位与哈希；
- 要生成/评审 3–5 个候选点，并由发明人做人工确认；
- 要把确认过的候选交接给 `patent-research` 做检索（交接草案，不是检索结果）。

## 不做什么

- 不做检索、查新、验收门（那是 `patent-research` 技能）；
- 不写交底书/权要/说明书（那是 `patent-drafting` 技能）；
- 不预测新颖性/创造性/授权，不产生任何 G-S 结论；
- 不上传、不外发、不执行任何研发材料。

## 安装

随全量安装包一起安装（`manifest.json` schema 2 会枚举 `patent-research`、`patent-drafting`、
`patent-discovery` 三个技能目录）。命令行安装：

```powershell
pwsh -File .\install.ps1 -Client claude -Force   # 或 -Client codex / both
```

内核要求：`patentkit >= 0.9.0`（`python -m patentkit doctor` 自检）。

## 工作区

本技能使用工作区中的 `10_discovery/`（由 `python -m patentkit upgrade apply` 创建）：

```
10_discovery/
├── source_manifest.json     # 来源材料登记（路径/哈希/定位方案/状态）
├── materials/SRC-xxx/       # 外部材料复制进工作区（--copy，默认）
├── parsed/SRC-xxx.txt       # 解析缓存（仅供定位引用；原始材料仍是权威）
├── technical_facts.jsonl    # 技术事实（逐条带来源与引文）
├── ideas/IDEA-xxx.json      # 专利候选点（proposed/confirmed/rejected）
├── decision_ledger.jsonl    # 人工决策与审计事件（不可变账本）
└── handoff/                 # 交接草案（handoff JSON + 查询种子 + 目标草案）
```

## 快速开始

```powershell
# 1) 登记材料（默认 dry-run，--apply 才写）
python -m patentkit intake register .\materials --root .\workspace --apply

# 2) 导入 AI 抽取的技术事实（Schema + 来源哈希校验）
python -m patentkit discovery facts import .\facts --root .\workspace --apply

# 3) 导入候选点并查看检索优先级
python -m patentkit discovery ideas import .\ideas --root .\workspace --apply
python -m patentkit discovery ideas rank --root .\workspace

# 4) 人工确认（发明人）
python -m patentkit discovery facts review --ids FACT-001 --decision confirmed --by inventor --root .\workspace --apply
python -m patentkit discovery review .\decisions --root .\workspace --apply

# 5) G-I 检查 + 交接草案
python -m patentkit discovery check --root .\workspace
python -m patentkit discovery handoff --idea IDEA-001 --root .\workspace --apply
```

详细方法与纪律见 [`SKILL.md`](SKILL.md) 与 `references/`。
