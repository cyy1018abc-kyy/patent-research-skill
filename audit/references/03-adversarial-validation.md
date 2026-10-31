# 03 — 阶段 A3：对抗验证（证伪优先）

> 对应原件 Candidate validation。立场反转：verifier 的第一假设是
> 「这条映射是错的」，任务是为它找反证；找不到才算通过。

## 1. 证伪者提示词（逐字使用，`<>` 处填值）

```text
你不是这条候选映射的提出者。请尽力证伪它：
要素 <element_ref> ↔ 对比文件 <prior_art_ref>，初判披露 <full/partial>。
只允许：读工作区（02_search_logs/raw 的原文、03_candidates、既有日志）。
不允许：联网补检索；修改工作区；沿用提出者的推理。
证伪清单（逐项过）：
1. 引文核对：逐字引文是否真的出现在定位段落里？改一个字即证伪；
2. 定位核对：段落是否支持该要素？相邻段落冒充定位即证伪；
3. 特征核对：要素的全部技术特征（含隐含限定）都被披露了吗？
   列出区别特征（distinguishing features），一条未披露即 full→partial；
4. 时间核对：对比文件的公开日早于目标的申请日/优先权日吗？证据在哪？
5. 相关性核对：披露所在实施例是主流方案还是边缘/劣化实施例？
6. 判级核对：按 04 号契约，初判的影响类目是否高于证据支持的披露程度？
输出（恰好一个 JSON 对象，无散文）：
{"decision": "confirmed|needs_validation|rejected", "record": {…}}
record 必须符合 04-findings-contract.md 中对应三态分支的字段契约；
提出者的措辞可以整体替换。保序指纹：同一根因 fingerprint 不变。
```

## 2. 判定规则

| 场景 | 处置 |
|---|---|
| 引文/定位/特征/时间任一硬伤 | `rejected`，写明证伪理由与反证定位 |
| 路径成立但缺决定性外部事实（同族法律状态、优先权核实、原文获取失败） | `needs_validation`，写明缺失事实 + 核验计划 |
| 证伪失败且证据链完整 | `confirmed`，逐字段重写 record |

- needs_validation **不是**低置信 confirmed 的停车场：必须能说出「缺哪一个事实、
  谁能在哪里核到它」；说不出就 rejected。
- 降级（confirmed→needs_validation）与驳回（→rejected）都要在关联台账单元记
  一条 check（agent_id=verifier）。
- 预算不足时：未验证候选只留在台账（candidate 状态），**不进 findings.json**，
  run 记 `incomplete`，理由 `validation_budget_exhausted`。

## 3. 合并

规划者按 fingerprint 合并：同一根因只留一条最终记录；verifier 返回的 fingerprint
不一致时，只有确认是「真正不同的根因」才允许新指纹（走新候选流程）。格式损坏或
散文包裹的 verifier 输出**直接作废重跑**，不做人工修补。

## 4. 单 agent 模式实现

同一会话内执行 A3 时：先输出全部候选的「证伪清单执行记录」（作为独立轮次的
中间产物），再逐条产出三态 JSON。证伪轮次不得引用自己 A2 轮次的判断理由，
只引用工作区证据。
