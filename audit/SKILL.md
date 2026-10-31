---
name: patent-audit
description: >
  检索证据链的结构化审计：权利要求要素分解、覆盖率台账（要素×数据源×分类号）、
  对抗验证每个「要素↔对比文件」映射、独立复核逐条引文与定位、产出三态结论
  （confirmed / needs_validation / rejected）与中立报告。
  本技能审查已有工作区的证据质量与覆盖缺口，不产生新的检索结论，不预测授权；
  guidance 模式默认只给方法与局部核查，全面审计（full audit）必须显式授权才执行。
  工具不可用/未运行时，回答必须以「⚠️ 未经验证工具校验」开头。
  当用户要审计检索覆盖、复核证据链、对抗式验证对比文件映射、检查引文是否逐字可溯、
  出具中立审计报告、找检索盲区时使用。
  命中「全面审计」「audit」「审计检索链」「覆盖率」「对抗验证」「独立复核」
  「证据链质量」「检索盲区」等说法时优先触发。
license: Apache-2.0
metadata:
  version: 4.0.0
---

# 检索证据链审计（Audit）

> **配套**：`patentkit >= 0.10.0`（工作区契约与校验命令）+ 姊妹技能 `patent-research`
> （被审计对象的产生方）。方法论改编自 Cloudflare `security-audit-skill`（MIT，
> 见仓库 README Credits）：覆盖率台账、对抗验证、独立复核、三态结构化结论。
> **定位**：回答「这份检索证据链**能不能被信任**」——用独立于检索者的角色重新
> 走一遍覆盖与证据，让每个结论要么带完整引文链，要么如实标记缺口。

## 何时触发

| 该用 | 不该用 |
|---|---|
| 全面审计一个已完成检索的工作区（显式授权后跑六阶段） | 首次检索、查新、补检索（用 patent-research 技能） |
| 核查某条「要素↔对比文件」映射的引文与定位 | 生成对比分析矩阵初稿（那是 research 的域） |
| 检查检索覆盖盲区（要素×数据源×分类号 缺格） | 预测新颖性/创造性/授权（谁都不许承诺） |
| 对抗式证伪候选映射（先假设它错，找出反证） | 修改候选清单/检索式（只提建议，不代为执行） |
| 出具中立审计报告（REPORT / NEEDS-VALIDATION） | 替权利人做法律决策；报告不是法律意见 |

## 两种模式（先问清，再动手）

- **guidance（默认）**：只做方法讲解、单点核查、局部覆盖检查。不创建审计运行
  目录，不写台账/结论文件；可以按需读工作区回答具体问题。
- **full audit（显式授权）**：用户明确要求「全面审计 / 完整 audit / 出审计报告」
  时，才按六阶段执行并写入 `12_audit/run-<N>/` 的全部工件。

请求语义两可时，先问一个聚焦问题再创建任何文件。

## 执行顺序（六阶段，full audit 模式）

| # | 阶段 | 读 | 做 |
|---|---|---|---|
| A1 | 概览与台账 | [`01-概览与覆盖率台账`](references/01-recon-claims-map.md) | 权利要求要素分解 → `claims-map.md`；按 要素×数据源×分类号 播种 `audit-ledger.json` |
| A2 | 覆盖率狩猎 | [`02-覆盖率狩猎`](references/02-coverage-hunting.md) | 逐台账单元做检索/复核并记录 checks；覆盖批评家（critic）找盲区 |
| A3 | 对抗验证 | [`03-对抗验证`](references/03-adversarial-validation.md) | 新角色 verifier 对每个候选映射专职证伪 |
| A4 | 结构化结论 | [`04-三态结论契约`](references/04-findings-contract.md) | 写 `findings.json` 三态记录；`python audit/scripts/validate_findings.py` 校验 |
| A5 | 独立复核 | [`05-独立复核`](references/05-independent-review.md) | 新角色逐条核对 confirmed/needs_validation 的逐字引文与段落定位 |
| A6 | 中立报告 | [`06-中立报告`](references/06-neutral-report.md) | 由结论派生 `REPORT.md` / `NEEDS-VALIDATION.md`，先过双校验器 |

默认**单 agent 顺序模式**：六个阶段由同一会话按序完成，角色分离用「提示词 + 状态
重置」实现；只有用户显式说多智能体（`--multi-agent`）才并行派发隔离 agent。
协议全文（状态机、终止条件、profile、预算）见 [`00-审计协议`](references/00-audit-protocol.md)。

## 硬约束（不得违反）

1. **先授权后全量**：guidance 模式不写审计工件；full audit 必须是用户显式请求。
2. **逐字引文或降级**：confirmed 结论必须带逐字原文（verbatim quote）+ 段落定位
   （locator），且校验器逐条复核；做不到的自动降级 needs_validation，不得补抄。
3. **破坏性与确定性分离**：破坏性（X/Y/A 影响类目）只给 confirmed 结论，且不得
   高于已证实的披露程度；needs_validation/rejected 永远没有影响类目。证据确定性
   （confidence）单独评，两轴不得互相折算。
4. **verifier 与产生者隔离**：每条候选映射由「专职证伪」的角色复核；同一结论的
   提出者不得自证 confirmed（单 agent 模式下用独立复核轮次模拟隔离）。
5. **台账即覆盖主张**：覆盖率只认 `audit-ledger.json` 里的单元状态与 checks 记录；
   「我看过一遍了」不是覆盖证据。
6. **三态必留痕**：needs_validation 必须写明缺失的决定性事实与可行的核验计划；
   rejected 必须记录证伪理由；两者都不进 REPORT 的结论表。
7. **不重写被审计工作区**：审计只读工作区、只写 `12_audit/`；修改建议写进报告，
   不代为执行任何 `--apply`。
8. **工具不可用/未运行时**，回答以「⚠️ 未经验证工具校验」开头；不得伪装已核验。

## 结果格式（凡输出审计结论一律用它，不得缺项）

| 项 | 要求 |
|---|---|
| **结论三态** | 每条结论标注 confirmed / needs_validation / rejected 与 fingerprint |
| **证据链** | confirmed：要素引用 + 对比文件 + 逐字引文 + 段落定位 + 独立复核标记 |
| **影响类目** | 仅 confirmed：X/Y/A + 理由；与证据确定性分开陈述 |
| **缺口清单** | 台账未覆盖单元、blocked/deferred 原因、needs_validation 待验事实 |
| **未验证标注** | 工具未跑或数据不全时明确写「⚠️ 未经验证工具校验」 |

## 参考文档（按需加载）

| 文件 | 什么时候读 |
|---|---|
| [`00-audit-protocol.md`](references/00-audit-protocol.md) | **full audit 前必读**；模式、角色、状态机、终止条件、profile 与预算 |
| [`01-recon-claims-map.md`](references/01-recon-claims-map.md) | 阶段 A1：要素分解、claims-map、台账播种规则与 coverage_id |
| [`02-coverage-hunting.md`](references/02-coverage-hunting.md) | 阶段 A2：狩猎波次、checks 记录、覆盖批评家 |
| [`03-adversarial-validation.md`](references/03-adversarial-validation.md) | 阶段 A3：证伪优先的 verifier 提示词与判定规则 |
| [`04-findings-contract.md`](references/04-findings-contract.md) | 阶段 A4：findings.json 三态字段、影响/确定性两轴、校验器用法 |
| [`05-independent-review.md`](references/05-independent-review.md) | 阶段 A5：逐条复核清单、重大更正的再验证规则 |
| [`06-neutral-report.md`](references/06-neutral-report.md) | 阶段 A6：REPORT/NEEDS-VALIDATION 结构与中立性规则 |
| [`07-anti-patterns.md`](references/07-anti-patterns.md) | 十二条反模式（照抄清单≠审计、自评虚高、引文漂移…） |

> 校验器脚本随技能载荷分发（`audit/scripts/validate_findings.py` 与
> `validate_ledger.py`，纯 Python 标准库，零第三方依赖）；运行方式见 04 号文档。
> 跨技能导航走文内「姊妹技能」说明，不要在安装后使用 `../` 相对链接。
