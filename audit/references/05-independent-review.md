# 05 — 阶段 A5：独立复核

> 对应原件 Independent record verification。复核对象是**最终记录**（不是狩猎
> 散文），fresh 角色逐条核对；这是 confirmed 结论「可信任」的最后闸门。

## 1. 范围与角色

- 对每条 `confirmed` 与 `needs_validation` 最终记录各做一次独立复核；
  `quick` profile 允许 A3+A5 合并为一次（同一 verifier 完成证伪+复核），但
  **confirmed 永远不豁免独立复核**。
- 复核者不得是候选提出者或 A3 verifier（单 agent 模式 = 新的复核轮次，只带
  最终记录与证据文件本体）。

## 2. confirmed 复核清单（逐项核对）

1. **引文逐字**：每条 evidence 的 quote 与 ref 文档中 locator 指向的段落逐字符
   一致（标点与全半角一致；改写/意译/截断拼接都不算逐字）；
2. **定位命中**：locator 指向的段落确实包含支持该要素的内容；相邻段落冒充
   定位即退回；
3. **trace 真实**：element→disclosure（→effect）链条每跳的 ref 真实存在且语义
   相符；
4. **要素对齐**：element 引用与 claims-map 的要素陈述一致；distinctions 列表与
   原文比对无遗漏（漏列区别特征会导致 disclosure_extent 虚高）；
5. **披露程度**：full/partial 与原文逐特征比对后成立；
6. **影响类目**：X 必须有全要素链（element_coverage.all_elements true 且逐要素
   有映射）；partial 只允许 Y/A；reason 与证据一致；
7. **修复建议方向**（如有）：建议是否守住「不移动信任、不补写证据」的边界。

## 3. needs_validation 复核清单

1. trace 支持的只是 claimed_rationale（不是更强主张）；
2. blockers 逐条是**真外部事实**且本地确实核不到；
3. validation_plan 的 local/external 各自可执行且不要求外发工作区数据；
4. fingerprint 与旧记录（如有）一致。

## 4. 复核输出

```json
{"decision": "verified", "fingerprint": "MAP:E-01:ZZ900011A1"}
```
或
```json
{"decision": "replace", "reason": "…", "record": {…}}
```

- **非实质更正**（措辞、行号笔误）：直接应用，重跑校验器。
- **实质更正**（升格判态、改根因、改 trace/证据/披露程度/影响类目）：必须再给
  一个**未参与过该候选**的 fresh 复核者重验；预算不允许时把该记录移出
  findings.json，台账单元退回 candidate，run 记 `incomplete`。
- 每次应用更正后：重跑 `validate_findings.py` + `validate_ledger.py`，
  并在关联台账单元补一条 check（agent_id=reviewer）。
- 复核发现**新的独立根因**：新 fingerprint，按候选流程走 A3。

## 5. 指标落账

复核轮完成后统计 verifier 翻案率（见 `00-audit-protocol.md` §8），写进
REPORT §1 与 run-metadata 的完成摘要。翻案率不是坏消息——它是本方法论
存在的理由，如实记录。
