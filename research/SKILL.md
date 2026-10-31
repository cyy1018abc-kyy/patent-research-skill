---
name: patent-research
description: >
  专利现有技术检索、新颖性/创造性自检、检索证据链与验收门（G-S）管理，以及交稿前的
  数值溯源、附图标记、结论引用核验与查新报告导出。
  工具不可用/未运行时，回答必须以「⚠️ 未经验证工具校验」开头。
  当用户要做专利检索、找现有技术、查新、评估新颖性/创造性、核查检索证据是否充分、
  判断验收门是否 PASS、核对证据等级（verified/attested/asserted）、整理检索留痕、
  交稿前核对权项与说明书、核对数值声明溯源（A/B/C）、核对附图标记、
  生成查新报告（docx/HTML）、查看证据账本或 1+N 布局时使用。
  支持多目标工作区；命中「跑一遍新颖性核查」「N1 轴检索式」「补检索」
  「五项验收门是不是 PASS」「asserted 能不能当依据」「证据等级」「数值溯源」
  「附图标记对不上」「召回增强」「查全诊断」「检索报告文件类型对照」等说法时优先触发。
license: Apache-2.0
metadata:
  version: 4.0.0
---

# 专利调研

> **配套**：`patentkit >= 0.10.0`（评估协议 1 的唯一规则实现）+ 本包 `scripts/`（薄封装）
> + 姊妹技能 `patent-drafting`（v3.0.0 起拆分：交底书/权要/OA 答复走那边）。
> 没有工具也能按 `references/` 工作，但结论必须标注「⚠️ 未经验证工具校验」。

## 何时触发

| 该用 | 不该用 |
|---|---|
| 专利/论文的现有技术检索、查全查准 | 出具法律意见、替代专利代理师或审查员 |
| 新颖性、创造性的**初步**判断 | 预测授权概率（谁都不许承诺） |
| 整理检索留痕、核对验收门（G-S） | 单独问法条/程序问题（查官方，不走本流程） |
| 交稿前证据充分性、权项数值依据核对 | 修改目标专利正文（本流程只给差异点与风险） |
| 查新报告/对比矩阵/证据账本等交付物生成 | 侵权分析（默认不做，边界见 references/09） |

## 执行顺序（按序，不要跳）

**先读 [`references/04-证据等级制度.md`](references/04-evidence-level-system.md)** —— 它是理解其它一切的前提：
分不清「自述」和「证据」、分不清「来源等级」和「判断主体」，后面每一步都会假 PASS。

| # | 阶段 | 读 | 做 | 检查点 |
|---|---|---|---|---|
| 0 | 定位与自检 | — | `python scripts/status.py`（首次安装后可跑 `scripts/self_test.py`） | 工作区、`active_target` 正确；校验无 error |
| 1 | 广度检索 | [`01-检索框架`](references/01-search-framework.md) | `patentkit search-plan --axis N1` → `patentkit fetch-cnipa` / `fetch-crossref` → `patentkit ingest --apply` | **G-S-01**：专利 ≥200 + 文献 ≥200（verified 列） |
| 2 | 深度检索 | [`02-检索式模板`](references/02-query-templates.md)，[`07-评估协议`](references/07-assessment-protocol.md) | 导出 JSON → 受支持的 AI/人工评估 → `patentkit review assess ... --apply` | **G-S-02**：每轴 ≥10 篇合格文献，缓冲 ≥+3；两维度都要有原文支持 |
| 3 | 对比分析 | [`03-三层判定`](references/03-three-tier-determination.md) | AI 推荐 → 人工逐条确认显式 ID 与指纹 → `patentkit review confirm ... --by <人名> --apply` → `patentkit report` | **G-S-03** ≥5 篇有效人工确认；**G-S-04** 同族/被引完整 |
| 4 | 门禁 | [`05-验收门口径`](references/05-acceptance-gates.md) | `python scripts/gates.py`（或 `patentkit gates`） | 五门 **verified 列**全 PASS，不看 asserted |
| 5 | 交稿核对 | [`06-撰写与润色规范`](references/06-drafting-and-polishing-rules.md)；多轮改稿闭环（13 号）属姊妹技能 `patent-drafting`，见其 references/13-revision-loop.md | `python scripts/check.py` + `patentkit attest --check` + 数值溯源（V031/V032）+ 附图标记（V033）+ 结论引用（V034） | validate 0 error/warn；稿件 sha256 无漂移；数值每条有 A/B/C 来源 |
| 6 | 交付物 | [`08-附图规范`](references/08-figures.md)（需要时） | `patentkit export-docx <TGT>`（docx 查新报告）/ `patentkit map <TGT>`（离线 HTML 总览）/ `patentkit ledger`（证据账本） | 交付物数字与工作区一致，无手工转写 |

**可选扩展（4.0 新增）**：已安装 `patent_intel` 扩展时，可用
`python scripts/recall.py plan --axis N1`（查询族提案）与
`python scripts/recall.py report`（离线查全诊断）辅助第 1–2 阶段——输出全部是
proposal/诊断，不改变门禁口径；扩展未安装时脚本 exit 3 并给安装指引，原流程照常。
细节与边界读 [`references/09-召回增强`](references/09-recall-enhancement.md)；
零命中/停止 ≠ 查全，结论引用扩展输出时必须带该限定语。

**撰写类需求转姊妹技能**（v3.0.0 起）：交底书/申请文件底稿、权利要求撰写、OA 答复、
多轮改稿闭环 → 技能 `patent-drafting`（本技能只负责其前置：门禁、账本、溯源就绪）。
多目标组合 → `patentkit layout`；提交后期限 → `patentkit deadlines`（以官方发文为准）。

> **脚本在哪**：`scripts/` 在本技能**安装目录**下（如
> `~/.claude/skills/patent-research/scripts/` 或 `~/.agents/skills/patent-research/scripts/`），
> **不在工作区里**。执行前先定位技能目录；或直接用等价的 `patentkit <子命令>`。
>
> 缺口只在 1、2、3 之间来回补：**门不过 ⇒ 检索不够**，不是改口径。

## 硬约束（不得违反）

1. **没有 `raw/` 原始工件不得标 `verified`** —— 校验规则 V009/V013 会拦。
2. **门 PASS 只认最严的 `verified` 列**；`asserted` 是历史留痕，不是通过依据。
3. **来源分级与判断相互独立。** 评估时保持 `evidence_level` 不变。AI 打 G-S-02 分必须带每轴
   problem/means 原文引用、定位符与理由；摘要或正文在充分时均可。AI 可推荐 `near_prior_art`，
   但 G-S-03 只认对显式 ID 与当前指纹的有效人工确认。绝不冒充人工审核，也不把含糊回复当确认。
   AI 冲突意见只是 proposal，永不覆盖人工决定。实质变更使确认失效；无关元数据修正不失效。
4. **工具不可用/未运行时**，回答必须以「⚠️ 未经验证工具校验」开头，再给方法论建议；不得省略，
   也不得把结果伪装成已核验。
5. **命中数 ≠ 核心文献数**：数据库的 `hits` 是全库命中面，不是「找到 N 篇」。
6. **主检索式最多 3 个 AND 子句**；IPC 用作后置过滤，不写进主式。
7. **门 FAIL 不是「再想想」** —— 它的意思是「检索不充分」：优先补检索/补判定，不是放宽阈值。
8. **数值阈值在 `patentkit/gates.py`；判断合格性在 `patentkit/assessment.py`，由 gates 与校验共用。**
   本文件、references 与薄封装只解释规则，**不得另立第二套**。
9. **结论只能引用证据账本里存在的编号**：`05_novelty_conclusions/*.md` 引用了不存在的 P-xxx/L-xxx
   会被 V034 拦下（先 `patentkit ledger` 核对，再写结论）。
10. **数值声明必须溯源**：启用数值溯源登记后，任何无 A/B/C 来源的数值句都是 error（V031），
    C 级（实施例示例）必须显式声明，不得伪装成实测数据。

## 结果格式（凡报告调研结论一律用它，不得缺项）

| 项 | 要求 |
|---|---|
| **结论** | 明确写「成立 / 存疑 / 不成立」（针对新颖性、创造性或证据充分性）；**不得结论能否授权** |
| **证据等级** | 只表述来源：`verified` / `attested` / `asserted`；外部哈希绑定材料可为 attested；判断主体单独报告 |
| **判定状态** | 分开列 actor、每轴原文依据、人工确认有效/待定/失效；来源 verified 不代表判断正确 |
| **门禁状态** | 引用 `verified` 列的实际数值（如 G-S-02 最小轴 12 篇）；不得写「应该能过」 |
| **未验证标注** | 工具未跑或数据不全时，明确写「⚠️ 未经验证工具校验；以下为方法论建议」 |

示例（数值是占位，不要照抄）：

```text
结论：单篇新颖性 — 存疑（D3 覆盖 N2/N5，未覆盖 N4）
证据等级：verified（最近对比文献 25 篇，raw/ 完整）
门禁：G-S-01 ✅ 210P/205L ｜ G-S-02 ✅ 最小轴 12 ｜ G-S-03 ✅ 25 ｜ G-S-04 ✅ 25/25 ｜ G-S-05 ✅ 100%
未验证：无
```

## 参考文档（按需加载，不要一次全读）

| 文件 | 什么时候读 |
|---|---|
| [`04-证据等级制度.md`](references/04-evidence-level-system.md) | **最先读**；判断 PASS 或标证据等级之前 |
| [`01-检索框架.md`](references/01-search-framework.md) | 建域、开新项目、采集纪律 |
| [`02-检索式模板.md`](references/02-query-templates.md) | 构造检索式、按各库语法改写 |
| [`03-三层判定.md`](references/03-three-tier-determination.md) | 判相关性、填对比矩阵、写三层结论 |
| [`05-验收门口径.md`](references/05-acceptance-gates.md) | 门 FAIL、缓冲不足、`validate` 报错 |
| [`06-撰写与润色规范.md`](references/06-drafting-and-polishing-rules.md) | 交稿前权项-说明书数值/支持核对 |
| [`07-评估协议.md`](references/07-assessment-protocol.md) | 评估导入、显式批量确认、冲突、指纹与迁移 |
| [`08-附图规范.md`](references/08-figures.md) | 画图/附图标记核对（V033）、图与正文一致性 |
| [`glossary.md`](references/glossary.md) | 中英术语对照（与英文版 references.en/ 保持一致） |

> 交底书/权要/OA 答复/改稿闭环的方法论（09–13 号文档）自 v3.0.0 起随姊妹技能
> `patent-drafting` 分发；本技能的交稿核对（第 5 阶段）只覆盖证据侧的
> 数值溯源/附图标记/结论引用校验。

> 本包 [`README.md`](README.md) 有 `scripts/` 用法与安装说明。脚本只是 `patentkit` 的薄封装，
> 规则不在脚本里。未安装 `patentkit` 时脚本会打印安装指引（exit 3）。
