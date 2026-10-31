# EX-01 专家标注协议（私有 Gold 构建）

- 状态：v1.0（Phase V / V2-1 冻结，先于任何标注开始）。
- 适用：`benchmarks/retrieval/topics/private/` 的 20–40 个专家主题相关性标注；
  公开主题（DAPFAM）使用其自带引证代理 gold，不经本协议重标。
- 原则：Gold 不由待评系统生成（blueprint §12）；标注与待评系统输出**物理隔离**
  （评审者不得接触 runs/ 或 results/ 下任何文件）。

## 1. 评审者与独立性

1. **≥2 名评审**独立标注同一批主题；评审者各自持有独立工作表副本，禁止互看。
2. 评审者不得是待评系统的开发者；若只有 2 人且其一参与过扩展开发，须在仲裁表
   记录利益关系，且其权重在一致性统计中单列复核。
3. 评审者对每条标注给出 relevance 与 rationale（一句话即可）；rationale 缺失的
   标注视为无效，不计入 κ。

## 2. 相关性分级（relevance_levels 语义，nDCG 用）

| 级别 | 语义 | 判定标准 |
|---|---|---|
| 0 | 无关 | 无共同技术特征，或仅主题领域相同 |
| 1 | 部分相关（tangential） | 有共同特征但该特征对目标发明非必需/属惯用手段 |
| 2 | 披露必需特征（blocking） | 披露了目标发明的至少一项区别性必需特征，具备破坏新颖性/创造性的潜力 |

## 3. 工作表与流程

1. **工作表**：`gold/worksheets/reviewer-<名称>.csv`（utf-8-sig + LF），列固定：
   `topic_id,doc_id,relevance,rationale,reviewer,reviewed_at`——列名由
   `tools/annotation_agreement.py --check-columns` 校验，禁止增删改。
2. **预标定轮**：先标 10 个主题（从 val split 或主题池抽取，不进最终 gold），
   评审者对齐口径；预标定结果不进入 qrels。
3. **正式标注**：每主题针对其候选池（见 §5）逐条标注；允许对无候选证据的族标
   「未评估（blank）」——blank 不进 κ 分母、不进 gold。
4. **仲裁**：双方分歧导出至 `gold/ARBITRATION.md`（模板见同目录），第三人或双
   方协商裁决；仲裁表记录分歧点与理由，逐条可追溯。
5. **一致性门**：Cohen's κ ≥ 0.7（整体与逐主题，含仲裁前数值记录）。κ < 0.7 ⇒
   追加校准轮并扩大评审，**不得降标或放宽分级定义**。

## 4. Gold 汇总（V2-4）

1. 仲裁后用 `tools/annotation_agreement.py --build-qrels` 汇总为
   `gold/qrels.json`：`{topic_id: {family_id: relevance}}`，仅收录非 blank 条目；
2. 每主题的 Gold 适用日期与来源写入 qrels 元数据（`as_of`、`source`）——对比文
   件公开日晚于该日期者不得成为 gold（时间有效性）；
3. qrels 版本号：`private-qrels-<日期>`；任何修改 = 新版本，旧评测作废并登记。

## 5. 候选池（pool）构成

标注对象不是全库（45,336 族无法人工过），而是**候选池**：待评系统与基线在训练
集调参后、于该主题上的 top-200 并集 + 主题 source 检索的 top-200（防系统间盲区）。
`pool_biased` 口径由此而来；报告必须携带「Gold 仅覆盖候选池内判断」的 caveat
（`gold_known_incomplete: true` 恒置）。

## 6. 与内核评审体系的边界

本协议产出是 benchmark 工件，**不进入任何内核工作区**，不使用 patentkit 的
review assess/confirm、不产生 G-S 记录；内核评审语义（证据等级、五门）不适用于
本表。
