# patent-audit（检索证据链审计技能）

> 独立复核检索证据链：覆盖率台账 + 对抗验证 + 逐字引文核对 + 中立报告。
> 本目录是 `patent-research-skill` 仓库下的第四个技能载荷（v4.1.0），
> 与 `research/`（检索/证据链）、`drafting/`（撰写底稿）、`discovery/`（专利点挖掘）
> 共用唯一内核 `patentkit`。
> 方法论改编自 Cloudflare `security-audit-skill`（MIT）：六阶段审计骨架
> （覆盖率台账 → 对抗验证 → 独立复核 → 三态结论 → 中立报告），
> 按专利检索域重写；未移植其任何攻击面内容（安全攻击类目不适用于专利域）。

## 何时使用

- 要审计一个**已完成检索**的工作区：覆盖是否有盲区、证据是否逐字可溯；
- 要对「要素↔对比文件」映射做**对抗式验证**（先假设映射错，找反证）；
- 要给每条 confirmed 结论配**独立复核过的**逐字引文与段落定位；
- 要出具**中立审计报告**：confirmed / needs_validation / rejected 三态，缺口如实列出。

## 不做什么

- 不做首次检索、查新、补检索（那是 `patent-research` 技能）；
- 不写交底书/权要/说明书（那是 `patent-drafting` 技能）；
- 不预测新颖性/创造性/授权，不产生 G-S 结论，报告不是法律意见；
- 不修改被审计工作区：审计只读工作区、只写 `12_audit/`；
- 不上传、不外发工作区内容；全面审计必须用户显式授权（guidance 模式是默认）。

## 安装

随全量安装包一起安装（`manifest.json` schema 2 会枚举 `patent-research`、`patent-drafting`、
`patent-discovery`、`patent-audit` 四个技能目录）。命令行安装：

```powershell
pwsh -File .\install.ps1 -Client claude -Force   # 或 -Client codex / both
```

内核要求：`patentkit >= 0.10.0`（`python -m patentkit doctor` 自检）。

## 工作区

审计运行产物写在 `12_audit/`（可被 `--output` 覆盖到工作区外）：

```
12_audit/
└── run-<N>/
    ├── run-metadata.json      # 运行参数（profile/scope/模式/状态）
    ├── claims-map.md          # 权利要求要素分解 × 分类号 × 检索起点（≤1000 字）
    ├── audit-ledger.json      # 覆盖率台账（要素×数据源×分类号 的单元状态机）
    ├── findings.json          # 三态结论（confirmed/needs_validation/rejected）
    ├── REPORT.md              # 中立审计报告（由结论派生）
    ├── NEEDS-VALIDATION.md    # 待验证清单（无影响类目）
    └── agents/<id>/artifacts/ # 各角色的检索/复核工件（父进程写）
```

## 快速开始

```powershell
# 1) 校验器自检（任何时候可跑，零依赖）
python audit/scripts/validate_findings.py  .\12_audit\run-1\findings.json
python audit/scripts/validate_ledger.py    .\12_audit\run-1\audit-ledger.json

# 2) full audit（在 agent 会话里显式请求）
#    "对这个工作区做全面审计（full audit），输出 REPORT.md"
#    → 六阶段：台账 → 覆盖狩猎 → 对抗验证 → 三态结论 → 独立复核 → 中立报告

# 3) 审计结论对照基准评分（bm01/bm02 有 gold，见 benchmarks/）
python tools/score_audit_findings.py --case benchmarks/cases/bm01-timesync `
    --findings .\12_audit\run-1\findings.json --json
```

详细方法与纪律见 [`SKILL.md`](SKILL.md) 与 `references/`。
