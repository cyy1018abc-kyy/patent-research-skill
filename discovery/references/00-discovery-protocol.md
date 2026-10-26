# 00 · 挖掘协议（Discovery Protocol）

> 本文件是 patent-discovery（**专利点挖掘**）技能的协议全文：四阶段、数据契约、G-I 控制层、
> 命令索引与边界。本技能只做「材料 → 事实 → 候选点 → 人工确认 → 交接草案」；
> 检索、查新、撰写分别由姊妹技能 `patent-research`、`patent-drafting` 承担。

## 1. 四阶段（A1–A4）

| 阶段 | 名称 | 输入 | 内核动作 | 输出 |
|---|---|---|---|---|
| A1 | 材料登记 | 私有研发材料（库外或工作区 `materials/`） | `intake register`：哈希、定位方案、解析缓存 | `10_discovery/source_manifest.json` |
| A2 | 技术事实 | 解析缓存 + AI 阅读 | `discovery facts import`：Schema + 来源哈希绑定 | `technical_facts.jsonl` |
| A3 | 候选点 | 事实库 + AI 归纳 | `discovery ideas import` / `ideas rank` | `ideas/IDEA-xxx.json` |
| A4 | 确认与交接 | 候选 + 发明人决策 | `facts review` / `review` / `handoff` | 决策账本 + `handoff/` 草案 |

**每一步默认 dry-run**：只有显式 `--apply` 才写盘；AI 可以先把命令跑成 dry-run 给发明人过目。

## 2. 工作区布局

```
10_discovery/
├── source_manifest.json     # 契约 source_manifest（schema_version 1.0）
├── materials/SRC-xxx/       # --copy 时的材料副本（私有无害；原始件仍以工作区外为准）
├── parsed/SRC-xxx.txt       # 解析缓存（行/段落/页定位引用；不是权威原件）
├── technical_facts.jsonl    # 每行一条 technical_fact
├── ideas/IDEA-xxx.json      # 每个候选一个文件
├── decision_ledger.jsonl    # 不可变审计账本（决策/内容变更/交接事件）
└── handoff/                 # IDEA 交接草案（JSON + 查询种子 + 目标草案）
```

目录由 `python -m patentkit upgrade apply` 创建；`10_discovery` 编号只是默认值，
若工作区已占用该编号，内核会确定性回退并在 `upgrade_layout` 中可配置（见 P0 升级布局）。

## 3. 数据契约（schema_version = 1.0）

| 契约 | 写入者 | 关键字段 |
|---|---|---|
| `source_manifest` | `intake register` | `source_id`(SRC-xxx)、`kind`、`path`、`sha256`、`locator_scheme`、`extraction_status`、`confidentiality=private` |
| `technical_fact` | `discovery facts import` | `fact_id`(FACT-xxx)、`statement`、`source_refs[]`（source_id/locator/quote/source_sha256）、`support_status`、`human_review`、`uncertainties` |
| `idea` | `discovery ideas import` | `idea_id`(IDEA-xxx)、`working_title`、`technical_problem`、`essential_features[]`（F-xxx + fact_refs）、`technical_effects[]`、`review_status` |
| `idea_decision` | `discovery review` | `decision_id`、`idea_id`、`idea_fingerprint`、`reviewer`、`decision`、`timestamp`、`source_snapshot_sha256` |
| `discovery_handoff` | `discovery handoff` | `handoff_id`(HO-xxx)、`idea_fingerprint`、`target_id`、`target_mode`、`essential_features[]`、`fact_refs[]`、`source_refs[]`、`query_seed_path` |

契约由内核 `patentkit.contracts` 唯一实现；字段/枚举以该模块为准（本文只做导读）。

## 4. G-I 控制层（技术事实确认门）

| 组 | 代码 | 含义 |
|---|---|---|
| 来源 | G-I-001 ~ G-I-006 | 清单不可读 / 未登记 / 路径不可用 / 文件缺失 / 哈希不符 / 解析缓存缺失 |
| 事实 | G-I-007 ~ G-I-010、G-I-023 | 无事实 / Schema 违规 / 重复 ID / 来源未登记或哈希不符 / 账本不可读 |
| 决策 | G-I-011 ~ G-I-014、G-I-025 | 决策 Schema/重复/未知 IDEA/确认过期（warn）/账本不可读 |
| 候选 | G-I-015 ~ G-I-018、G-I-022、G-I-024 | Schema/未知事实/无支持事实/事实未确认（warn）/IDEA 文件重复/目录不可读 |
| 交接 | G-I-019 ~ G-I-021 | handoff 文档缺失或非法 / 交接过期（warn）/引用未知 IDEA |

`discovery check` 输出 `{ok, errors, warnings}`；**handoff 只在 errors=0 且必要事实全部 confirmed 时放行**。

## 5. 命令索引

| 命令 | 作用 | 写盘点 |
|---|---|---|
| `patentkit intake register <文件…> [--apply] [--no-copy] [--kind K] [--max-bytes N]` | 材料登记 | `--apply` 才写 |
| `patentkit discovery facts import <JSON/目录…> [--apply]` | 事实导入校验 | `--apply` 才写 |
| `patentkit discovery facts review --ids F1[,F2] --decision confirmed --by <label> [--apply]` | 事实人工确认 | `--apply` 才写 |
| `patentkit discovery ideas import <JSON/目录…> [--apply] [--force]` | 候选导入（强制 proposed） | `--apply` 才写 |
| `patentkit discovery ideas rank [--json]` | 检索优先级排序（非授权概率） | 只读 |
| `patentkit discovery review <决策 JSON/目录…> [--apply]` | 候选人工确认（指纹绑定） | `--apply` 才写 |
| `patentkit discovery status / check [--json]` | 概览 / G-I 检查 | 只读 |
| `patentkit discovery handoff --idea IDEA-001 [--target TGT-0002] [--apply]` | 交接草案 | `--apply` 才写 |

## 6. 状态机与审计

```
proposed ──confirm──> confirmed ──(内容变更)──> stale(旧确认保留，需重确认)
    │
    └──reject──> rejected
```

- 账本事件：`fact_review`、`decision`、`content_changed`、`handoff`（不可变，追加写入）。
- 确认绑定的是建议内容指纹（不含 `review_status`）；状态字段变化不会让确认失效，技术内容变化会。

## 7. 与其他技能的边界

| 本技能 | 交给谁 |
|---|---|
| 材料登记 / 技术事实 / 候选点 / 人工确认 / 交接草案 | — |
| 检索、查新、证据等级、G-S 验收门 | `patent-research`（把 handoff 查询种子转成正式检索） |
| 交底书 / 权利要求 / 说明书 / OA 答复 / 改稿闭环 | `patent-drafting`（前提是 research 门禁就绪） |
| 新颖性/创造性/授权预测 | **谁都不做**；本技能不产生任何法律结论 |

## 8. 失败模式（先报告，不要绕开）

1. 材料在库外且未加 `--copy` → 明确报错，提示复制进私有工作区；
2. 材料变化导致哈希不符 → 旧登记保持，要求重新登记（不得静默覆盖）；
3. PDF 无文本 / 加密 / 扫描件 → 记录 `unsupported/failed`，明确说明"需可提取文本的 PDF"；
4. `.slx/.mdl` 等二进制模型 → 明确拒绝，要求导出受控文本摘要；
5. 候选/事实 JSON 不合契约 → 拒绝写入，并给出字段级问题；
6. 未确认就交接 → G-I 阻塞并列出全部原因（没有 force 通道）；
7. 工具不可用/未运行 → 输出以「⚠️ 未经验证工具校验」开头。
