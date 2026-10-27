---
name: patent-drafting
description: >
  专利撰写底稿：交底书（发明/实用新型）、权利要求书与说明书骨架、审查意见（OA）
  答复底稿、多轮改稿闭环，以及撰写期的数值溯源、附图标记与政策口径核对。
  前提是检索侧（patent-research 技能）的证据链已就绪；本技能产出**底稿并标注缺口**，
  不替代专利代理师，不预测授权。工具不可用/未运行时，回答必须以
  「⚠️ 未经验证工具校验」开头。
  当用户要写交底书、起草权利要求、写说明书、梳理发明点成申请文件、
  回复审查意见/OA、改稿并留变更记录、核对数值能不能写进权项、
  把技术方案落成结构化权项并做支持映射、或把审阅稿交付成申请文件包并出交付清单时使用。
  命中「写交底书」「权项怎么写」「说明书支持」「OA 怎么答复」「改稿闭环」
  「这个数值能写吗」「结构化权项」「支持映射」「申请文件包」「交付清单」等说法时优先触发。
license: Apache-2.0
metadata:
  version: 3.7.0
---

# 专利撰写（底稿）

> **配套**：`patentkit >= 0.8.0`（规则唯一实现）+ 姊妹技能 `patent-research`（证据链与验收门）。
> **定位**：把检索成果转化为可交付的底稿——交底书、权要/说明书骨架、OA 答复稿。
> 产出永远是「底稿 + 缺口清单」，不构成法律意见，不预测授权前景。

## 何时触发

| 该用 | 不该用 |
|---|---|
| 交底书（发明/实用新型）五段式起草 | 检索/查新/验收门（用 patent-research 技能） |
| 权利要求层次设计与数值范围自检 | 出具法律意见、替代专利代理师 |
| 说明书支持性映射、实施例组织 | 预测授权概率（谁都不许承诺） |
| 审查意见（OA）拆条-回链-答复底稿 | 侵权分析（默认不做，见 docs/scope-decisions.md） |
| 多轮改稿：补丁→变更日志→重过门 | 修改检索数据/候选清单（那是 research 的域） |

## 前置条件（不满足就先回 research 技能）

1. **G-S-01～G-S-03 至少达标**（`patentkit gates` 看 verified 列）——检索不足时写交底书，
   等于把风险写进权利要求；
2. 对比矩阵已填，D 列每篇有证据等级与判定状态（`patentkit ledger`）；
3. 数值声明溯源登记已建（`patentkit provenance scan`）。

前置纪律的独立摘要见 [`references/00-prerequisites.md`](references/00-prerequisites.md)
（证据三级、五门口径、判断合格性——与 research 技能 / patentkit 内核同源）。

## 执行顺序（按需分线，不要全量展开）

### A. 交底书 / 申请文件线

| # | 步骤 | 读 | 做 |
|---|---|---|---|
| A1 | 对账 | [`00-prerequisites`](references/00-prerequisites.md) | `patentkit ledger`：背景技术只引用账本内编号（V034 同款纪律） |
| A2 | 骨架 | [`09-交底与申请文件`](references/09-disclosure-drafting.md) | 五段式起草；说不清的进 open_questions，**禁止编造** |
| A3 | 权要 | [`10-权利要求撰写`](references/10-claim-drafting.md) | 零披露原子进独权；数值层从权落在 A 级溯源范围内 |
| A4 | 自检 | [`10`](references/10-claim-drafting.md) | `patentkit provenance check` + support_mapping_table 逐原子映射 |

### B. OA 答复线

| # | 步骤 | 读 | 做 |
|---|---|---|---|
| B1 | 期限 | [`11-OA 答复`](references/11-oa-response.md) | `patentkit deadlines list`（以官方发文为准） |
| B2 | 拆条 | [`11`](references/11-oa-response.md) | 每条意见一行；审查员引用的文献先入候选清单再进对比 |
| B3 | 回链 | [`11`](references/11-oa-response.md) | 特征对照复用对比矩阵格式；论点按三层判定反向应用 |
| B4 | 修改 | [`13-改稿闭环`](references/13-revision-loop.md) | 任何权项修改走闭环：补丁→日志→attest→重过门 |

### C. 政策口径线（开工/交稿前扫一遍）

读 [`12-政策雷达`](references/12-policy-radar.md)；发现口径变化登记 `docs/policy-log.md`，
「待改」未清零不得交稿。

### D. 结构化撰写管线（P2；内核校验结构，AI 负责正文）

| # | 步骤 | 读 | 做 |
|---|---|---|---|
| D1 | 撰写计划 | [`14-结构化管线`](references/14-drafting-pipeline.md) | `patentkit draft plan --idea IDEA-001 --apply`（要求候选/事实已人工确认） |
| D2 | 权项原子 | [`15-原子与支持映射`](references/15-claims-and-support.md) | `draft atoms import` → 发明人 `draft atoms review`（确认绑定内容指纹） |
| D3 | 结构化权项 | [`15`](references/15-claims-and-support.md) | `draft claims import`：编号/引用顺序/循环/原子存在性由内核校验 |
| D4 | 支持映射 | [`15`](references/15-claims-and-support.md) | `draft support import` + `draft support review`：每个权项原子→段落/事实/附图 |
| D5 | 审计与门 | [`14`](references/14-drafting-pipeline.md) | `draft audit` → `draft status` → `draft gate --to review_draft`（需 G-S-01/02/03 PASS） |
| D6 | 改稿影响 | [`14`](references/14-drafting-pipeline.md) | `draft impact --claim-no N` 报告受影响段落/附图/从权，再走 13 号改稿闭环 |
| D7 | 专业附图 | [`16-专业附图`](references/16-figures.md) | `figures plan`（系统框图/方法流程图）→ `figures validate` → `figures render`；图文一致与人工看图复核 |
| D8 | 交付 | [`17-交付管线`](references/17-delivery.md) | 写 `07_drafting/manuscript/{claims,specification,abstract}.md` → `deliver build`（DOCX，可选 PDF）→ `deliver check` → 人工 `deliver sign` → `draft gate --to release_ready` |

## 硬约束（不得违反）

1. **先检索后撰写**：前置条件不满足时，先回 research 技能补，不在证据不足上动笔。
2. **结论与引用只来自账本**：引用不在 `patentkit ledger` 内的文献编号 = 编造，V034 会拦。
3. **数值必须溯源**：权项/说明书里的每个数值都要有 A/B/C 来源（V031/V032）；
   C 级（实施例示例）必须显式声明，不得伪装实测。
4. **说不清就登记**：材料不足的问题写入 open_questions，**绝不编造参数、步骤或实验结果**。
5. **改稿走闭环**：一个补丁只解决一个登记问题；实质变更会使相关人工确认失效并需重新确认
   （这是特性不是 bug）；禁止顺手改无关内容。
6. **不承诺授权、不写「必将授权」**；条款归类不确定时标注「需代理师确认」。
7. **工具不可用/未运行时**，回答以「⚠️ 未经验证工具校验」开头；不得伪装已核验。
8. **稿件在库外**：仓库只留 registry/台账/映射表；稿件正文绝不入库（保密红线）。
9. **结构化模型先行**：权项原子/权项/支持映射由内核 `patentkit draft` 校验；原子与支持映射的
   人工确认绑定内容指纹——改文本后旧确认自动失效，必须重新确认（D-017 会拦）。
10. **双状态写作门（review_draft 门禁）**：未达到 G-S-01/02/03 时只能停留在 `concept`；
    标记 `review_draft` 必须通过 `draft gate`（审计无 error、原子与支持映射人工确认、
    候选指纹当前）。P4 之前不产生正式交付件，不得把底稿说成"可直接提交"。
11. **附图由结构化 figure plan（附图规格）决定**：系统框图/方法流程图先写规格再渲染；渲染器不得创造或删除
    部件/连线，**不得仅依赖文本生图**；自动检查（F-001…F-014、V033）不替代人工看图复核，
    正式提交前必须逐图人工确认。
12. **交付只来自同一冻结快照**：`deliver build` 生成 PatentDocumentModel + 申请文件包（DOCX 审阅稿，
    PDF 预览需本地转换器，缺失如实报告）；`deliver check` 零 error 且**人工签核**（签核绑定清单指纹）
    才能 `draft gate --to release_ready`。改任何输入（候选/计划/原子/权项/支持映射/稿件/图规格/门禁）
    都会使旧交付失效，必须重建并重新签核。CNIPA XML **未实现/未验证**之前，**不得宣称**材料合规或
    「可直接提交」；`release_ready` 只是内部交付门。

## 结果格式（凡交付底稿一律用它，不得缺项）

| 项 | 要求 |
|---|---|
| **底稿状态** | 明确「初稿 / 复核稿 / 待发明人补充」；附版本与日期 |
| **gap 清单** | 说不清的部分逐条列出：缺什么材料、找谁补、阻塞哪一段 |
| **证据引用** | 引用的每篇对比文献 = 账本内编号 + 证据等级 + 判定状态 |
| **数值溯源** | 本稿包含的数值声明数与 A/B/C 分布；未溯源的数值不得出现 |
| **结构化状态** | plan/原子/权项/支持映射计数 + `draft audit` 结果 + 当前写作门（concept / review_draft，是否 stale） |
| **附图一致性** | `figures validate` 结果（F-001…F-014 摘要）+ 已渲染图号 + 是否已人工看图复核 |
| **交付状态** | `deliver check` 摘要（E-xxx/W-xxx）+ 产物清单与哈希 + 签核状态 + 当前写作门（`release_ready` 是否 stale） |
| **未验证标注** | 工具未跑或数据不全时，明确写「⚠️ 未经验证工具校验」 |

## 参考文档（按需加载）

| 文件 | 什么时候读 |
|---|---|
| [`00-prerequisites.md`](references/00-prerequisites.md) | **最先读**；证据三级/五门/判断合格性的独立摘要 |
| [`09-disclosure-drafting.md`](references/09-disclosure-drafting.md) | 交底书五段式、细则 20–23 映射、申请文件清单 |
| [`10-claim-drafting.md`](references/10-claim-drafting.md) | 独权/从权层次、数值范围自检、支持性映射 |
| [`11-oa-response.md`](references/11-oa-response.md) | OA 拆条表、三层反向论证、答复底稿结构 |
| [`12-policy-radar.md`](references/12-policy-radar.md) | 审查口径/书式/附图要求变化追踪 |
| [`13-revision-loop.md`](references/13-revision-loop.md) | 多轮改稿闭环：补丁→日志→重过门 |
| [`14-drafting-pipeline.md`](references/14-drafting-pipeline.md) | **P2** 结构化管线：plan→原子→权项→支持映射→双状态门（G-D 审计码） |
| [`15-claims-and-support.md`](references/15-claims-and-support.md) | 权项原子/结构化权项/支持映射的字段、校验规则与验收清单 |
| [`16-figures.md`](references/16-figures.md) | **P3** 专业附图：figure plan 规格、确定性渲染、F-001…F-014 校验与人工复核纪律 |
| [`17-delivery.md`](references/17-delivery.md) | **P4** 交付管线：冻结快照、DOCX/PDF、交付清单、E-001…E-012、签核与失效语义、CNIPA XML 现状 |
| [`glossary.md`](references/glossary.md) | 中英术语对照（与 patent-research 技能同一份，CI 锁定同步） |

> 命令直接用 `python -m patentkit <子命令>`（provenance / figures / deadlines / attest /
> ledger / gates / validate / draft）；本技能不带脚本封装——规则都在内核，撰写线不需要第二套入口。
> 完整检索侧工作流见姊妹技能 `patent-research`。
