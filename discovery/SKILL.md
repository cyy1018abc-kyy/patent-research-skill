---
name: patent-discovery
description: >
  研发材料到专利候选点的挖掘：来源材料登记、技术事实抽取、专利候选点生成与排序、
  发明人人工确认（内容指纹绑定），以及向检索技能（patent-research）的交接草案。
  本技能只产出「候选点 + 缺口清单」，不替代检索证据链，不预测新颖性/创造性/授权；
  工具不可用/未运行时，回答必须以「⚠️ 未经验证工具校验」开头。
  当用户要梳理研发材料、从设计文档/代码/仿真数据里找专利点、抽取技术事实、
  生成或评审专利候选点、确认发明点、把候选交接给检索时使用。
  命中「专利点挖掘」「技术事实」「专利候选点」「交底前材料梳理」「交接检索」
  「人工确认」「内容指纹」等说法时优先触发。
license: Apache-2.0
metadata:
  version: 3.5.0
---

# 专利点挖掘（Discovery）

> **配套**：`patentkit >= 0.7.0`（规则与数据契约的唯一实现）+ 姊妹技能 `patent-research`
> （检索/证据链/验收门）与 `patent-drafting`（撰写底稿）。
> **定位**：把私有研发材料变成**可追溯、可人工确认、可交接**的专利候选点。
> 产出永远带缺口清单；确认只能由发明人做出，模型输出永远是 proposed。

## 何时触发

| 该用 | 不该用 |
|---|---|
| 来源材料登记（Word/PDF/Markdown/代码/CSV/受控 Simulink 导出） | 检索、查新、验收门（用 patent-research 技能） |
| 从材料中抽取技术事实（逐条带来源定位与引文） | 写交底书/权要/说明书（用 patent-drafting 技能） |
| 生成 3–5 个专利候选点、排序优先级 | 判定新颖性/创造性/授权概率（谁都不许承诺） |
| 发明人对候选与事实做人工确认（内容指纹绑定） | 修改检索候选清单/证据等级（那属于 research 的域） |
| 生成交接草案（目标/技术轴/查询种子）交给检索技能 | 把候选点直接当检索结果或 G-S 结论 |

## 执行顺序（四阶段，按序推进；每步先 dry-run）

| # | 阶段 | 读 | 做 |
|---|---|---|---|
| A1 | 材料登记 | [`01-材料登记`](references/01-material-intake.md) | `python -m patentkit intake register <文件…> [--apply]`：SHA-256、定位方案、解析缓存 |
| A2 | 技术事实 | [`02-事实与候选`](references/02-facts-and-ideas.md) | AI 逐条抽取 → 写 FACT JSON → `patentkit discovery facts import <JSON…> --apply` |
| A3 | 候选点 | [`02-事实与候选`](references/02-facts-and-ideas.md) | 生成 3–5 个 IDEA → `discovery ideas import <JSON…> --apply` → `discovery ideas rank` |
| A4 | 确认与交接 | [`03-人工确认与交接`](references/03-human-review-and-handoff.md) | `discovery facts review` → `discovery review <决策 JSON…> --apply` → `discovery handoff --idea IDEA-001 --apply` |

协议全文与 G-I 检查表见 [`00-挖掘协议`](references/00-discovery-protocol.md)。

## 硬约束（不得违反）

1. **原始材料只进私有工作区**：不上传、不外发；不执行材料里的代码/宏/模型（`.slx/.mdl` 明确拒绝，需先导出受控文本）。
2. **无来源不事实**：每条技术事实必须带来源登记 ID、定位（行/段落/页）与引文，且哈希与 `source_manifest` 一致；做不到的写进 uncertainties。
3. **模型输出永远是 proposed**：AI 可以提议事实与候选，但不能自证「已确认」；确认只来自发明人的人工决策。
4. **确认绑定内容指纹**：确认后技术内容任何实质改动都会使旧确认过期（保留审计记录）；需要重新确认。
5. **效果不得编造**：未验证的技术效果保留 `to_be_verified`；不得把推断写成实验实测。
6. **不预判检索结论**：新颖性/创造性/授权只由 patent-research 在真实检索证据上计算；本技能不产生 G-S PASS/FAIL。
7. **交接前 G-I 必须 PASS**：未确认候选、未确认事实、未知来源/事实、哈希不符均阻塞交接，不提供绕过开关。
8. **工具不可用/未运行时**，回答以「⚠️ 未经验证工具校验」开头；不得伪装已核验。

## 结果格式（凡输出候选/事实/交接一律用它，不得缺项）

| 项 | 要求 |
|---|---|
| **候选点状态** | 每个 IDEA 的 review_status（proposed/confirmed/rejected）与确认是否有效（指纹） |
| **来源追溯** | 每个必要技术特征 → FACT → 来源 ID + 定位 + 哈希核验结果 |
| **缺口清单** | 无法证实的效果、缺失材料、待发明人确认项逐条列出 |
| **交接摘要** | G-I 检查结果（error/warn 计数）+ handoff 文件路径 + 下一步检索命令 |
| **未验证标注** | 工具未跑或数据不全时明确写「⚠️ 未经验证工具校验」 |

## 参考文档（按需加载）

| 文件 | 什么时候读 |
|---|---|
| [`00-discovery-protocol.md`](references/00-discovery-protocol.md) | **最先读**；四阶段、数据契约、G-I 检查表、命令索引 |
| [`01-material-intake.md`](references/01-material-intake.md) | 材料登记、支持格式、定位方案、安全边界 |
| [`02-facts-and-ideas.md`](references/02-facts-and-ideas.md) | FACT/IDEA 字段、状态机、排序、正反例 |
| [`03-human-review-and-handoff.md`](references/03-human-review-and-handoff.md) | 人工确认、指纹失效、交接门控与输出物 |
| [`glossary.md`](references/glossary.md) | 中英术语对照（三技能同一份，CI 锁定同步） |

> 命令统一为 `python -m patentkit <子命令>`（intake / discovery）；本技能不携带脚本，
> 规则与数据契约都在内核。跨技能导航走文内「姊妹技能」说明，不要在安装后使用 `../` 相对链接。
