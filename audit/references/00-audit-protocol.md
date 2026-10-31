# 00 — 审计协议（模式、角色、状态机、终止条件）

> 本文是 full audit 模式的权威协议。guidance 模式只需读本文 §1 与 §8。
> 骨架改编自 Cloudflare `security-audit-skill`（MIT）；攻击面类目未移植，
> 覆盖单元、判定语义与工件契约全部按专利检索域重写。

## 1. 两种模式

| | guidance（默认） | full audit（显式授权） |
|---|---|---|
| 允许的动作 | 方法讲解、单点核查、局部覆盖检查 | 六阶段全流程 + 写 `12_audit/run-<N>/` |
| 写文件 | 不写任何审计工件 | 只写运行目录内的契约文件 |
| 触发词 | 「帮我看看这条引用」「覆盖够不够」 | 「全面审计」「完整 audit」「出审计报告」 |

两可时先问一个聚焦问题再创建文件。**加载本技能 ≠ 授权全量审计。**

## 2. 角色与隔离

| 角色 | 职责 | 独立性要求 |
|---|---|---|
| **规划者（parent）** | 建台账、分派、汇总、写共享文件 | 唯一台账与 findings 写入者 |
| **狩猎者（hunter）** | 认领台账单元，执行检索/复核并记录 checks | 每单元一个认领；不评价别人单元 |
| **批评家（critic）** | 审视台账与 checks，找盲区、提议重派 | 每波狩猎后必跑；不能自己补查 |
| **证伪者（verifier）** | 对候选映射专职证伪（阶段 A3） | 不得是候选提出者 |
| **复核者（reviewer）** | 逐条核对最终记录的引文/定位/判级（阶段 A5） | 新鲜上下文；不得沿用 verifier 记忆 |

**单 agent 顺序模式（默认）**：六个阶段由同一会话按序执行；换角色时重置任务态
（只携带协议明文允许的输入，见 §4 的最小输入原则），用独立轮次模拟隔离。
`--multi-agent`（用户显式要求）才并行派发隔离 agent，写隔离规则见 §5。

## 3. 工件契约（run-metadata.json）

full audit 开始前，规划者写入运行目录 `12_audit/run-<N>/`（N 取下一个未用整数；
`--output` 可指向工作区外，但不得指向被审计工作区内部的其他目录）：

```json
{
  "run_id": "audit-<target>-run-<N>",
  "target": "TGT-xxxx（或目标专利号/项目代号）",
  "workspace": "被审计工作区根（只读）",
  "source_ref": "审计基线：工作区关键工件的 git 提交或文件哈希快照",
  "profile": "quick | standard | deep",
  "mode": "single | multi",
  "scope_paths": ["02_search_logs", "03_candidates", "..."],
  "budget": {"rounds": 12, "note": "单 agent 模式为轮次预算"},
  "claims_map": "claims-map.md",
  "ledger": "audit-ledger.json",
  "findings": "findings.json",
  "run_status": "in_progress | complete | incomplete",
  "incomplete_reason": "仅 incomplete 时非空"
}
```

事实变化才更新 metadata；候选状态只进台账与 findings.json。

## 4. 最小输入原则（隔离的实质）

每个角色只接收完成本职所需的最小输入：

- 狩猎者：认领单元的 coverage_id、starting_paths、可用的检索策略块；**不接收**
  其他单元的结果或其他角色的结论。
- 证伪者：候选记录本身 + 该单元 checks 路径 + `04-findings-contract.md` 中对应
  三态分支的字段契约；**不接收**提出者的推理过程或其他 verifier 的结论。
- 复核者：最终记录 + 证据文件本体；**不接收**阶段 A3 的判定记忆。

## 5. 写隔离

`run-metadata.json`、`claims-map.md`、`audit-ledger.json`、`findings.json`、
`REPORT.md`、`NEEDS-VALIDATION.md` 只由规划者写。多 agent 模式下每个 agent 拿到
`agents/<agent-id>/`（小写，`^[a-z0-9][a-z0-9_-]{0,63}$`，禁 Windows 保留名）下的
`scratch/`（agent 可写）与 `artifacts/`（父进程提升后才保留）；agent 永远不改共享
文件、被审计工作区或彼此目录。单 agent 模式下全部工件由会话直接写运行目录，
等价于「规划者写一切」。

## 6. 覆盖率台账状态机

台账单元状态（`audit-ledger.json`，schema 见 `01-recon-claims-map.md` §4）：

| 状态 | agent_id | reviewed_paths / checks | result_fingerprints | unresolved |
|---|---|---|---|---|
| `planned` | null | 空 | 空 | 空 |
| `not_applicable` / `out_of_scope` / `deferred` | null | 空 | 空 | 必须写原因 |
| `in_progress` | 认领者 | 空 | 空 | 空 |
| `blocked` | 认领者 | 两者非空（部分证据） | 空 | 必须写阻塞点 |
| `covered` | 认领者 | 两者非空 | 空 | 空 |
| `candidate` | 认领者 | 两者非空 | 非空 | 可选 |

规则：

1. **台账即覆盖主张**。任何「已查过」的叙事不构成覆盖证据；只有单元内 checks
   （每次检索/复核一条：执行者、方法、检索式或复核对象、命中文档）算数。
2. `attempts` 是追加式归档：单元被批评家重派前，把原状态、执行者、checks、
   fingerprints 与 `reassignment_reason` 追加进 attempts，然后 wave+1、换执行者、
   清空活跃证据。只有 blocked/covered/candidate 可归档。
3. 多次审计叠加：读旧 run 的台账与 findings，**同源 confirmed** 可携带但必须重过
   当前独立验证；**改源单元**必须重新狩猎；旧 needs_validation/deferred/blocked
   全部转成当前工作。任何旧状态都不抑制当前覆盖。

## 7. Profile 与预算

| profile | 用法 | 狩猎 | 批评家 | 验证/复核 |
|---|---|---|---|---|
| `quick` | 小目标、复检、快速回看 | 单元粗化到 要素×源（分类号合一），恰好 1 波 | 恰好 1 次（波后） | A3 与 A5 合并为一次独立复核 |
| `standard` | 默认 | 按台账全格 hunting，波次到干净通过 | 每波后 + 最终独立一次 | A3、A5 分离 |
| `deep` | 高风险目标 | 单元按要素细分，波次到干净通过 | 每波后 + 最终独立一次 | A3、A5 分离；covered 单元抽检二刷 |

预算 = 单 agent 模式的**轮次预算**（默认值可由目标规模推算并在 metadata 记录）。
先预留：A1 概览轮、每波后的批评家轮、最终批评家轮、至少一轮证伪/复核。
剩余轮次不足以覆盖预留时：不启动狩猎，把受影响单元标 `deferred`（原因
`budget_cannot_reserve_critics_and_validation`），run_status 记 `incomplete` 并在
报告披露。**永远不悄悄突破预算，也永远不省掉独立复核。**

## 8. 覆盖计算与两个必报指标

- **台账覆盖率** =（狩猎完成单元数，即 `covered` + `candidate`）／（可行动单元数 =
  总数 − not_applicable − out_of_scope）。`candidate` 表示该单元的狩猎承诺已经
  完成、且登记了候选映射——它与 `covered` 同属完成态（bm01 首次端到端运行的
  教训：只数 covered 会把已完成狩猎、登记了候选的单元误计为未覆盖）；
  `blocked`/`deferred`/`planned` 不计入。写进 REPORT §7；quick/scoped 运行必须
  自称「部分覆盖」。
- **verifier 翻案率** =（阶段 A3/A5 被降级或推翻的候选数）／（进入独立验证的候选数）。
  翻案率>0 是「单 agent 自评虚高」的直接证据，如实写进 REPORT，不粉饰。

## 9. 终止条件（恰好两个，不许停在中间）

1. **complete**：A6 工件全部写完，双校验器（findings + ledger）通过，且每个台账
   候选都有独立处置（confirmed/needs_validation/rejected 或明确的 incomplete 理由）。
2. **incomplete**：`run_status: "incomplete"` + 精确 `incomplete_reason`
   （如 `validation_budget_exhausted`、`budget_cannot_reserve_critics_and_validation`），
   且报告首页披露缺口；未验证的候选只留在台账，**不进 findings.json**。

## 10. 与被审计工作区的边界

- 只读工作区；不执行任何 `--apply`/`--run`/`--force`/`--fill`。
- 审计发现的修改建议（如「补检索式」「重引段落」）写进 REPORT 的建议节，
  由 `patent-research` 的正常流程执行。
- 工作区里没有的部署性事实（如同族法律状态、审查历史）不得臆测——按
  needs_validation 处理，写明缺失事实与核验计划。
