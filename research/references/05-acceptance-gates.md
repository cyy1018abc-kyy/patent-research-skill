# 05 验收门口径

> **口径已代码化**：`patentkit/gates.py`，用 `python -m patentkit gates` 计算。
> 每门按证据等级各算一列；**PASS 只认最严的 `verified` 列**（见 [04](04-evidence-level-system.md)）。

## 五门口径

| 门 | 判据 | 阈值 |
|---|---|---|
| **G-S-01** | 阶段 1 候选清单 | **专利 ≥200 + 文献 ≥200**（按 `kind` 计） |
| **G-S-02** | 阶段 2 主轴覆盖 | 每轴 **≥10 篇**带当前受支持 AI/人工评估的文献：两维度 ≥4 且有每轴原文引用；excluded 不计 |
| **G-S-03** | 阶段 3 近端对比 | **≥5 篇** `role=near_prior_art` 且有绑定当前判断指纹的有效显式人工确认 |
| **G-S-04** | 同族与被引普查完整 | `role ∈ {near_prior_art, family}` 的 family 与 cited_by 各有一条**有效普查记录**（查过 + raw 工件在库且哈希一致）；**零命中也算查过** |
| **G-S-05** | 可复现性 | `capture_mode=live` 且 `raw/` 工件存在非空 **100%** |

## 三次历史口径修正（原口径是错的）

1. **G-S-03** 原来写「`novelty_check=blocking` 计数 ≥5」—— **错**。「是否阻挡新颖性」与
   「近端对比文件有几篇」是两个语义。现改计 `role=near_prior_art`，两者解耦。

2. **G-S-04** 原来硬编码「存在专利 1、专利 2」—— **不可泛化**。
   现改为引用目标专利自己的对比文献集。

3. **G-S-04** 后来只检查 `family`/`cited_by` 是否为数组——两个空数组就能 PASS，
   **「未查」与「查过无命中」无法区分**；而字面的「非空数组」又让真正查过、
   确实零命中的记录永远不达标。0.6.0 起改为核验**普查记录**（见下节）。

## G-S-04 的普查记录（census）

每个普查对象在候选 JSON 里带 `census` 字段，family 与 cited_by **两个维度分别记录**：

| 字段 | 含义 |
|---|---|
| `doc_number` | 查询对象（与候选 `url_or_doc_number` 归一化后一致） |
| `source` / `query_id` | 来源库与查询族（如 `BQ` / `GS04`；手工普查写实际来源） |
| `at` | 查询时间（带时区 ISO8601） |
| `status` | `complete`（查过有命中）/ `zero_hits`（查过零命中）/ `partial` / `failed`（查询未完成） |
| `artifact` + `artifact_sha256` | 原始工件（工作区相对路径，通常在 `02_search_logs/raw/`）与其哈希 |

门禁判定（实现：`patentkit/census.py`，门禁只调它）：

| 情形 | G-S-04 |
|---|---|
| 未查（无记录） | ❌ 不完整 |
| 查过、零命中、工件在库且哈希一致（`zero_hits`） | ✅ 计入完成 |
| 查过、有命中、工件在库且哈希一致（`complete`） | ✅ 计入完成 |
| `partial` / `failed` / 工件缺失 / 工件被改（哈希不符） / 记录指向别的查询的工件 | ❌ 不得冒充完整 |

写入方式：`python -m patentkit fetch-bigquery --fill <raw.jsonl> --apply`——工件由
`fetch-bigquery --run` 归档时**每个普查对象一行**（零命中也是一行），回填自动生成记录。
其他来源（OPS、epub 手工普查）按上表 schema 手工补录 `census` 字段（工件用实际落盘的
raw 文件，哈希用 `patentkit ledger` 同款 sha256），旧工作区先跑 `patentkit migrate`
刷新候选 schema。

记录**存在但损坏**（缺字段 / 哈希不符 / 状态与工件内容矛盾）由 validate **V037** 拦截；
诚实的 `partial`/`failed` 不是数据损坏，validate 不报——但门禁不给它算完整。
「没查」与「查了没查完」都是检索不足，按门禁纪律补查，不是放宽口径。

## G-S-02 的缓冲纪律

`G-S-02` 是最容易「刚过就翻红」的门。

| 状态 | 含义 | 动作 |
|---|---|---|
| 某轴 ≥4 篇数 = 10 | 零缓冲；一次重判就 FAIL | **必须补检索** |
| 某轴 = 11–12 | 缓冲 +1~+2；仍脆弱 | 建议补到 +3 |
| 某轴 ≥ 13 | 缓冲 +3 及以上 | 安全 |

**怎么补**：先看该轴池子是否 100% 已判——是，则问题不是「判得不够」而是「搜得不够」，
只有新子查询能救。跑 `python -m patentkit queryplan --axis <轴>`：给出已登记未执行的
子查询、概念要素组覆盖缺口与确定性补查骨架（见 [02](02-query-templates.md)）。

## validate 与 gates 的分工

| | 管什么 | 不过的后果 |
|---|---|---|
| `validate` | **数据结构一致性**（V001–V037） | 任何 `error` → exit 1 |
| `gates` | **验收门**（5 门 × 3 列） | 任一门不 PASS → exit 2 |

V029 校验判断来源/支持；V030 报告失效的人工确认。V031/V032 管数值溯源，
V033 管附图标记（仅 warn），V034 拦「结论引用了账本外的证据编号」，
V035/V036 管改稿台账（结构错误 / 改了没登记），V037 管普查记录的完整性
（存在但损坏的 census → error；诚实未完成 → 门禁管）。
来源等级与判断合格性相互独立，详见 [07-评估协议](07-assessment-protocol.md)。

两者都要过。CI 入口是 `python -m patentkit check`（= `validate --strict` + `gates --quiet`）。

## 常见 FAIL 与修法

| 症状 | 原因 | 修法 |
|---|---|---|
| G-S-01 文献侧 0 | 只检了专利 | 用 `fetch-crossref` 补文献 |
| G-S-02 某轴 9 篇 | 池子已全判 | 加子查询；不要重判 |
| G-S-03 N/A | 全是 `pool` | 先做受支持的推荐，再由人工显式确认候选 ID 与当前指纹 |
| G-S-04 N/A | 同上（无 near_prior_art） | 同上 |
| G-S-04 FAIL「未查」 | 普查对象没有 census 记录 | `fetch-bigquery --fill <工件> --apply`，或按普查记录表手工补录 |
| G-S-04 FAIL「哈希不符」 | 工件被改动 / 记录过期 | 重跑普查得到新工件后重新 `--fill`；不要手改哈希 |
| G-S-05 <100% | 有日志缺 `raw/` | 重跑那次检索 |
| `validate` 报 V018 | near_prior_art 未进任何 run | 跑 `patentkit report <TGT-ID>` |
| V031/V032 报错 | 数值声明无来源/引用无效 | 补 `07_drafting/numerical_provenance.yml` 的 A/B/C 来源 |
| V034 报错 | 结论引用了不存在的 P-xxx | 先 `patentkit ledger` 核对，改结论或先补文献 |
| V037 报错 | census 记录存在但损坏 | 重跑 `fetch-bigquery --fill`（工件是唯一权威来源）；人工记录按表修复 |
