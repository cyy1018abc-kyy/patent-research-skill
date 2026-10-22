---
name: patent-research
description: >
  专利现有技术检索、新颖性/创造性自检、检索证据链与验收门（G-S）管理。
  工具不可用/未运行时，回答必须以「⚠️ 未经验证工具校验」开头。
  当用户要做专利检索、找现有技术、评估新颖性/创造性、核查检索证据是否充分、
  判断验收门是否 PASS、核对证据等级（verified/attested/asserted）、
  整理检索留痕、交稿前核对权项与说明书时使用。
  支持多目标工作区；命中「跑一遍新颖性核查」「N1 轴检索式」「补检索」
  「五项验收门是不是 PASS」「asserted 能不能当依据」「证据等级」等说法时优先触发。
license: Apache-2.0
metadata:
  version: 2.3.1
---

# 专利调研

> **配套**：`patentkit`（Python 内核，规则实现在这里）+ 本包 `scripts/`（薄封装）。
> 没有工具也能按 `references/` 工作，但结论必须标注「⚠️ 未经验证工具校验」。

## 何时触发

| 该用 | 不该用 |
|---|---|
| 专利/论文的现有技术检索、查全查准 | 撰写权利要求/说明书正文（先走 04 对比，再回稿） |
| 新颖性、创造性的**初步**判断 | 出具法律意见、替代专利代理师或审查员 |
| 整理检索留痕、核对验收门（G-S） | 单独问法条/程序问题（查官方，不走本流程） |
| 交稿前证据充分性、权项数值依据核对 | 修改目标专利正文（本流程只给差异点与风险） |

## 执行顺序（按序，不要跳）

**先读 [`references/04-证据等级制度.md`](references/04-证据等级制度.md)** —— 它是理解其它一切的前提：
分不清「自述」和「证据」，后面每一步都会假 PASS。

| # | 阶段 | 读 | 做 | 检查点 |
|---|---|---|---|---|
| 0 | 定位与自检 | — | `python scripts/status.py`（无脚本时 `patentkit status`） | 工作区、`active_target` 正确；校验无 error |
| 1 | 广度检索 | [`01-检索框架`](references/01-检索框架.md) | `patentkit search-plan --axis N1` → `patentkit fetch-cnipa` / `fetch-crossref` → `patentkit ingest --apply` | **G-S-01**：专利 ≥200 + 文献 ≥200（verified 列） |
| 2 | 深度检索 | [`02-检索式模板`](references/02-检索式模板.md) | `patentkit review export --with-abstract` → **人工判定** → `patentkit review apply --apply` | **G-S-02**：每轴 ≥10 篇 relevance≥4，且缓冲 ≥+3 |
| 3 | 对比分析 | [`03-三层判定`](references/03-三层判定.md) | `patentkit report <TGT-ID>` → 填单篇/组合/技术效果三层 | **G-S-03** ≥5 近端；**G-S-04** 同族/被引完整 |
| 4 | 门禁 | [`05-验收门口径`](references/05-验收门口径.md) | `python scripts/gates.py`（或 `patentkit gates`） | 五门 **verified 列**全 PASS，不看 asserted |
| 5 | 交稿核对 | [`06-撰写与润色规范`](references/06-撰写与润色规范.md) | `python scripts/check.py` + `patentkit attest --check` | validate 0 error/warn；稿件 sha256 无漂移 |

> **脚本在哪**：`scripts/` 在本技能**安装目录**下（如
> `~/.claude/skills/patent-research/scripts/` 或 `~/.agents/skills/patent-research/scripts/`），
> **不在工作区里**。执行前先定位技能目录；或直接用等价的 `patentkit <子命令>`。
>
> 缺口只在 1、2、3 之间来回补：**门不过 ⇒ 检索不够**，不是改口径。

## 硬约束（不得违反）

1. **没有 `raw/` 原始产物就不许标 `verified`** —— `validate` 的 V009/V013 会拦。
2. **门禁 PASS 只认最严的 `verified` 列**；`asserted` 是历史成绩，不是通过依据。
3. **不替用户判定 `relevance` / `role`**。模型代判必须在 `review_note` 写「【模型代判】」+ 理由，结论降为 `asserted`。
4. **工具不可用 / 未运行时**，**回答开头必须显式写「⚠️ 未经验证工具校验」**，再给方法建议；不得省略、不得伪装成已验证。
5. **命中数 ≠ 核心文献数**：数据库的 `hits` 是全库命中面，不是「找到 N 篇」。
6. **主检索式最多 3 个 AND 子式**；IPC 作后置筛选，不写进主检索式。
7. **门禁 FAIL 不是「再想想」**，是「检索不够」—— 优先补检索/补判定，不是放宽阈值。
8. **阈值与判定口径只认 `patentkit/validate.py` 与 `patentkit/gates.py`**；本文件与 `references/` 只做解释，不另立第二套口径。

## 结果格式（输出调研结论时照此，缺一不可）

| 项 | 要求 |
|---|---|
| **结论** | 明确写「成立 / 存疑 / 不成立」（针对新颖性、创造性或证据充分性）；**不下「能否授权」结论** |
| **证据等级** | `verified` / `attested` / `asserted`；来源不是 `raw/` 的一律 `asserted` |
| **门禁状态** | 引用 `verified` 列的实际数值（例：G-S-02 最少轴 12 篇），不写「应该能过」 |
| **未验证标注** | 工具未跑或数据不全时，显式写「⚠️ 未经验证工具校验；以下为方法建议」 |

示例（数值为占位，勿照抄）：

```text
结论：单篇新颖性——存疑（D3 覆盖 N2/N5，未覆盖 N4）
证据等级：verified（25 篇近端，raw/ 齐全）
门禁：G-S-01 ✅ 210P/205L ｜ G-S-02 ✅ 最少轴 12 篇 ｜ G-S-03 ✅ 25 ｜ G-S-04 ✅ 25/25 ｜ G-S-05 ✅ 100%
未验证：无
```

## 参考（按需加载，不要一次全读）

| 文件 | 什么时候读 |
|---|---|
| [`04-证据等级制度`](references/04-证据等级制度.md) | **先读**；判 PASS、标证据等级前 |
| [`01-检索框架`](references/01-检索框架.md) | 建域、开新项目、采集纪律 |
| [`02-检索式模板`](references/02-检索式模板.md) | 构造检索式、按数据库语法改写 |
| [`03-三层判定`](references/03-三层判定.md) | 判 relevance、写对比矩阵与三层结论 |
| [`05-验收门口径`](references/05-验收门口径.md) | 门不过、缓冲不足、`validate` 报错时 |
| [`06-撰写与润色规范`](references/06-撰写与润色规范.md) | 交稿前权项-说明书数值/支持核对 |

> `scripts/` 与安装说明见本包 [`README.md`](README.md)。脚本只是 `patentkit` 的薄封装，
> 规则实现不在脚本里；未安装 `patentkit` 时脚本会给出安装提示（exit 3）。
