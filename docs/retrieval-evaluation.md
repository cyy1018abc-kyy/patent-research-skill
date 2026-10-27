# 检索评测协议（Retrieval Evaluation Protocol）

- 状态：**v1（WP-F T-01 冻结）**。对应蓝图 §12；评分数值一律出自
  `tools/score_retrieval.py`，本文不得手工另报数字。
- 评分器契约见 `benchmarks/retrieval/manifest.schema.json` 与
  `benchmarks/retrieval/README.md`。

## 1. 评测对象与两条基线

1. **算法基线**：同一冻结公开语料上的 BM25（必要时加 dense/RRF/adaptive 变体），
   严格离线可复现：同语料快照 + 同查询 + 同参数 + 同种子 = 同一数值（UT-R01）。
2. **流程基线**：3.7.0 的原查询规划与采集链。实时外部索引会漂移，因此定量比较
   以「冻结原始响应回放」为准；联网实测结果单独呈现，标注为系统实测、不可作为
   可重复数值。

对比对象必须声明：语料快照哈希、查询集哈希、引擎版本、种子、预算（`RetrievalRun`
记录字段，见 `docs/architecture/contracts.md`）。

## 2. 数据与许可

| 数据 | 用途 | 许可边界 |
|---|---|---|
| 仓库内合成冒烟套件（`benchmarks/retrieval/fixtures/`） | CI 回归、评分器验收 | 随仓库许可，无真实专利文本 |
| CLEF-IP 公开任务派生 family ID | 算法基线对比 | 遵守 CLEF-IP 分发许可；**受限原始语料绝不打包进发行物**，只保留派生 ID 与许可注记 |
| DAPFAM | 同上 | CC-BY-NC-SA-4.0；**不得进入商业发行包** |
| 私有专家标注集（20–40 主题） | Critical Recall 与协议审查 | 不入公开仓库；Gold 不由待评系统自动生成（EX-01：≥2 名评审独立标注 + 仲裁记录） |

防泄漏规则（违反即评测无效）：

1. 同一专利家族不得跨 train/val/test（家族级切分，manifest `topic_id` 维度）；
2. 按申请/公开日期做时间切分时记录 `time_split_key`；
3. 查询扩展（WP-A）在评测运行中不得读取 test split 的 gold；
4. 外部实时索引不是固定语料——凡引用实时检索的数字必须标注检索日期与不可重复性；
5. 报告缺失字段与未标注候选的 pool bias（`gold_completeness: pool_biased`）。

## 3. 指标口径（全部由 score_retrieval.py 实现）

- **Family Recall@K**：前 K 个不同专利家族命中 gold 家族的比例；K=50/100/200；
  按主题宏平均；gold 为空的主题**排除出分母**并在 `topics_gold_zero` 单列——
  空集不得默认满分。
- **Critical Prior-art Recall**：人工确认的关键参考家族被检出比例；必须附
  「gold 非完整全集」警示（pool_biased 时报告自动携带 caveat）。
- **nDCG@100 / MRR**：排序质量；相关性级别在 manifest `relevance_levels` 定义。
- **Unique Relevant Yield / 100 requests**：每百次有效请求新增相关家族数；
  分母是实际发出的全部请求（含零收益请求）。
- **Coverage**：按 language / domain 切片的均值（检查语言与领域偏差）。
- **Audit Integrity**：run 条目数、唯一命中家族数、请求总数；评分器对未知
  topic、重复 (topic, rank)、负排名一律 exit 1。

置信区间：主题级配对 bootstrap（95%，固定种子），主题数 < 2 时输出
`degenerate=true` 的点估计并在渲染层明示——不允许小样本伪装统计结论。

## 4. 判定门（初始目标，正式评测后冻结）

- **PR 必过**：原九案例 9/9、全部扩展离线单测、证据/安全单测。
- **宣称「查全率提升」前**：≥100 个可复现公共测试主题 + 20–40 专家主题协议
  审查；同预算同候选 K 下 Family Recall@100 相对最强选定词法基线平均增益
  ≥5 个百分点，主题级配对 bootstrap 95% CI 下界 > 0；同时报告未达标分组。
  不允许用个别示例替代统计。
- 数据量/CI 不足 ⇒ 一律标注「实验性增强」，不得宣传已证明提升；**不得为过门
  修改 gold**（只允许调整宣传范围）。

## 5. 流程

1. 新套件 = 新目录：`manifest.json`（过 schema）+ 运行输出目录（JSONL）。
2. `python tools/score_retrieval.py --suite <dir> --runs <dir> --json` 得单一
   JSON 报告（`EvaluationReport` 形状，见 contracts.md）。
3. 报告原文入库存档（`benchmarks/retrieval/results/<date>-<suite>.json`），
   README/CHANGELOG 引用的统计只准由 `tools/report_benchmark_stats.py` 从这些
   报告生成（T-06，单一事实源）。
4. 改 gold = 改 manifest `version` 与 `qrels_version`，旧报告作废并在变更表登记。
