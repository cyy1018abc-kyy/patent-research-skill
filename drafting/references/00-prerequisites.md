# 00 撰写线前置纪律（独立摘要）

> 本篇是撰写线需要的检索侧纪律的**独立摘要**——不依赖 patent-research 技能安装即可读。
> 权威实现始终在 `patentkit` 内核（gates.py / assessment.py）；本文与 research 技能的
> 01–08 号文档同源，细则以那边为准。

## 证据三级（来源可追溯性）

| evidence_level | 含义 | 可否用于严格 PASS |
|---|---|---|
| verified | live 采集、可复现的 raw 工件，保留在工作区内 | 可以，且须满足各门判定要求 |
| attested | 外部材料，工作区内有 SHA-256 绑定 | 不可以 |
| asserted | 未经核实的自述 | 不可以 |

**AI 打分不降级真实来源；人工确认不升级 asserted。** 来源等级与判断（谁判的、依据够不够）
是两件独立的事。

## 五项验收门（G-S，PASS 只看 verified 列）

| 门 | 阈值 |
|---|---|
| G-S-01 | 候选清单：专利 ≥200 + 文献 ≥200 |
| G-S-02 | 每轴 ≥10 篇受支持判定（两维度 ≥4 + 每轴 problem/means 原文引用） |
| G-S-03 | ≥5 篇 near_prior_art 且有绑定当前指纹的显式人工确认 |
| G-S-04 | 近端/同族的 family 与 cited_by 完整 |
| G-S-05 | 检索日志 100% 可复现（live + raw 工件） |

**撰写线的最低门槛：G-S-01～G-S-03 达标。** 门 FAIL = 检索不足，不是改口径。

## 判断合格性（评估协议 1 的要点）

- relevance = min(问题维度, 手段维度)；两维度都要有原文引用（ref + locator + quote + rationale）；
- AI 可打 G-S-02 分；G-S-03 只认显式人工确认（绑定判断指纹）；
- 实质变更（分数/角色/轴/理由/引用）使确认失效，须重新评估并重新确认；
- 来源 verified ≠ 判断正确；账本（`patentkit ledger`）里判定状态 unknown/needs_review 的
  条目不得作为依据。

## 三层判定（写 OA 答复与权要时的论证骨架）

1. **单篇新颖性**：单独一篇是否覆盖全部核心特征（novelty_check: blocking/covered/partial/untouched）；
2. **组合创造性**：2–3 篇组合是否显而易见；**零披露原子**（任何组合拼不出的特征）是独权的核心；
3. **技术效果**：效果是否必须以区别特征为前提（量化优先，映射 D 列差异）。

## 撰写线常用的内核命令

```powershell
patentkit ledger                # 证据账本：结论/背景技术只引用账本内编号
patentkit gates                 # 五门状态（前置条件检查）
patentkit provenance scan/check # 数值声明 A/B/C 溯源
patentkit figures check         # 附图标记与正文双向一致
patentkit attest --check        # 稿件 sha256 漂移检测
patentkit deadlines list        # 期限台账（以官方发文为准）
```
