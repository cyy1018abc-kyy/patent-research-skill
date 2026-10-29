# 私有专家主题引入协议（Phase V / V1-4）

- 状态：v1.0 冻结。目标：20–40 个来自真实工作流的脱敏主题，构成私有专家标注集
  （`benchmarks/retrieval/topics/private/`，整目录 gitignore，本地留存）。
- 门：`benchmarks/retrieval/gate.yaml` 的 claim_rule——「查全率提升」最终宣称
  需本集完成 EX-01 双评审标注。

## 1. 脱敏模板（每主题一条 JSON，字段强制）

```json
{
  "source_id": "PRIV-<NNN>",
  "invention_statement": "<发明点陈述：技术特征级描述，不含客户名/项目名/编号>",
  "technical_axis": "<技术轴（对齐 glossary 轴名）>",
  "gold_families": ["<公开族号，如 US2020/0123456 的族 ID>"],
  "gold_as_of": "<Gold 适用日期（ISO）：公开日晚于此日期的文献不得成为 gold>",
  "gold_source": "<来源：审查档案/检索报告/人工确认记录的脱敏指称>",
  "declassification_review": "<脱敏复查人/日期>"
}
```

脱敏红线：不得出现申请人/发明人/代理案号/内部项目代号；发明点陈述改写为技术
特征语言；gold 族号是公开事实，允许保留。

## 2. 引入流程

1. 从既有真实工作区（01–08 目录产物）挑选 20–40 个**已有人工确认结论**的目标；
2. 按模板登记，逐条脱敏复查；
3. 与公开语料重叠剔除：gold 族 ∩ DAPFAM 目标族 = 0 命中后才收编（复用
   `check_leakage.py` 的族一致性检查口径）；
4. 每主题进入 EX-01 标注池（候选池构成见 `docs/annotation-protocol.md` §5）。

## 3. 留痕

- 本目录内容永不提交；`gate.yaml` 报告阶段引用的只有聚合计数（主题数、κ、
  recall），与本地哈希清单（`topics/private/MANIFEST.sha256`，本地生成）。
