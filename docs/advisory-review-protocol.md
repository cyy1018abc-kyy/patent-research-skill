# EX-02 权项修订建议评审协议（Phase V / V2-5）

- 状态：v1.0 冻结。对应 blueprint §11 EX-02：对生成的权项修订建议检查说明书
  支持、是否引入新内容、区别特征的证据来源；**自动分数不得替代代理师法律判断**。
- 评审对象：扩展 `advisory/`（amendment_proposal / claim_chart / gap_analysis）
  在**私有主题工作区**上产出的修订建议（proposal，非已提交权项）。
- 评审者：代理师（≥1 名；有第二评审时按 EX-01 的独立性规则执行）。

## 1. 评审位定义（每条 proposal 三问，全部必答）

| 位 | 问题 | 取值 |
|---|---|---|
| S1 说明书支持 | 修改后的权项表述能否由说明书原文直接或概括支持？ | supported / partial / unsupported |
| S2 新内容引入 | 是否引入了原始申请未记载的内容（新葱/NLM 风险）？ | none / borderline / new_matter |
| S3 证据来源 | 建议所依据的区别特征证据来源是否可追溯（工件哈希/定位符有效）？ | traceable / stale / missing |

## 2. 流程

1. 从扩展 `advisory review` 导出建议清单（proposal_id、目标权项、change 摘要、
   evidence_refs）到 `benchmarks/retrieval/ex02/proposals-<日期>.csv`（本地留存）；
2. 评审人在同目录 `review-<评审者>-<日期>.csv` 填三问 + 备注；列冻结为
   `proposal_id,topic_id,S1,S2,S3,notes,reviewer,reviewed_at`；
3. 结论语义：`new_matter ≠ none` 或 `S1 = unsupported` 的建议**必须标记
   `requires_human_review=true` 且不得进入底稿**——扩展的强制约束
   （`advisory/policy.py`）与本协议一致，评审表用于抽核该约束是否生效；
4. 抽核记录随 Phase V 收盘归档；发现约束失效 = 4.0 缺陷，走缺陷流程而非改数据。

## 3. 边界

- 本协议不改变内核 draft/revise 门禁与 V038 人工流程——扩展建议永远只是
  proposal；本表是**审计抽核**，不是权项修改的授权通道。
- 评审产出（含具体案件内容）本地留存，不入公共仓库。
