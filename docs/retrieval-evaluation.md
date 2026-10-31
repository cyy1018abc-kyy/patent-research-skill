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

1. **查询族**不得跨 train/val/test 重复（`check_leakage.py` 硬门）；蓝图 §12 的
   「同族不跨 split」落在评测单元（查询）维度；查询族作为更晚查询的 gold 出现
   属固定语料正常结构，计数公开不设门；
2. 固定语料基准中同一目标族作为多个不同时期查询的 gold 属预期属性，**不是**
   泄漏——计数在 manifest `leakage_report` 透明公开；
3. 按申请/公开日期做时间切分时记录 `time_split_key`；
4. 查询扩展（WP-A）在评测运行中不得读取 test split 的 gold；
5. 外部实时索引不是固定语料——凡引用实时检索的数字必须标注检索日期与不可重复性；
6. 报告缺失字段与未标注候选的 pool bias（`gold_completeness: pool_biased`）。

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

## 4. 判定门（预注册冻结）

门值与规则冻结在 `benchmarks/retrieval/gate.yaml`，**先于任何跑分提交**——git 历史
顺序即预注册证明；协议哈希记入 gate.yaml，此后报告回显该哈希。本节文字为门的
来源依据，与 gate.yaml 冲突时以 gate.yaml 为准（两者由哈希绑定）：

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

## 6. Phase V 结果与定级（2026-10-31，预注册门执行）

**门结论：FAIL → 「实验性增强」**（数值全部出自 `benchmarks/retrieval/results/2026-10-31-phase-v.json`，协议哈希 dbbe348f… 与 gate.yaml 锁定一致）。

| 指标 | 基线（BM25，3 固定请求） | 扩展管线（≤3 请求） |
|---|---|---|
| Family Recall@100（宏平均，312 test 主题） | 26.18pp | 23.68pp |
| 配对 bootstrap 95% CI（主题级差值） | — | 增益 −2.50pp，CI [−3.75, −1.28] |

两门（≥+5pp、CI 下界 >0）均未达，且 CI 上界 < 0：**同预算下扩展管线显著低于基线**，不是"无差异"。

分组（均值 pp / 主题数）：

| 分组 | 基线 | 扩展 |
|---|---|---|
| IN（90） | 28.05 | 26.10 |
| MIXED（216） | 26.13 | 23.33 |
| OUT（6） | **0.0** | **0.0** |
| era1 早期（171）/ era2 晚期（141） | 25.47 / 27.05 | 23.45 / 23.96 |

**失败分析**（供 4.1 立项，不改门不改 Gold）：

1. 扩展的查询策略（特征拆分 → 单特征/短查询 + 词典扩展）在**长文本词法检索**上弱于整篇 TAC 查询——该策略为 CNIPA 式短查询交互场景设计，本地全语料 BM25 下整篇查询天然占优；
2. 词典扩展的种子词为 CNIPA 域导向，未桥接 DAPFAM 的跨域词汇缺口；
3. **OUT 词法零召回（两侧同，top-200 亦零）**：跨域主题（无 IPC3 交集、词汇不同）对纯词法检索不可达——这是 DAPFAM 基准的设计要点，也是 4.1-A3（跨领域迁移检索）的直接动因；
4. 边界：本轮比较仅覆盖「词法引擎 + 同预算」运作化，不评价扩展在工作流场景的价值主张（查询提案、审计账本、多来源治理）。

**定级**：扩展检索能力维持「实验性增强」；README/CHANGELOG/notes 不出现"已证明查全率提升"表述。私有专家主题（20–40）与 EX-01 双评审完成后按 gate.yaml claim_rule 复议。

## 附录 A：数据源许可核查记录（Phase V / V1-1，2026-10-29 取证）

### A.1 DAPFAM（主选公开数据源）

- **来源**：HuggingFace `datalyes/DAPFAM_patent`（<https://huggingface.co/datasets/datalyes/DAPFAM_patent>，
  本机经镜像 `hf-mirror.com` 访问——直连 huggingface.co:443 在本工作环境不可达，探测记录见 A.3）。
- **许可**：**CC-BY-NC-SA-4.0**（数据集页 license 标签实测确认，获取日期 2026-10-29）。
  - **NC（非商业）**：语料本体与任何派生数据集不得进入商业发行物；本仓库 skill 发行包
    （zip/wheel）永不包含语料或其派生文件——`benchmarks/retrieval/corpus/` 整目录 gitignore。
  - **SA（相同方式共享）**：若未来发布基于语料的派生数据集（如子采样主题包），须以同许可
    发布并注明来源与变更——当前决策是不发布任何派生数据集，只公开评测报告中的聚合数字。
  - **BY（署名）**：任何引用 DAPFAM 数字的报告必须携带引用条目（Ayaou et al., 2025，
    arXiv:2506.22141）与本附录许可注记。
- **数据形状**（实测，2026-10-29）：`corpus.parquet` 45,336 目标专利族全文
  （1,096.7 MB）；`queries.parquet` 1,247 查询族（59.8 MB）；`qrels_all.parquet`
  ≈49,869 条关系（0.8 MB）。评测日期跨度 1964-06-26 → 2023-06-20；IN/OUT 域
  标签 = 查询与目标是否共享 IPC3。
- **Gold 性质**：qrels 含**抽样负例**；正例 IN ≈19,736 / OUT ≈5,193，为
  **引证代理标签**——不是法律意义上的完整先前技术集合。因此 manifest 固定
  `gold_completeness: pool_biased`，所有报告自动携带 caveat（§3）。
- **与本文协议的衔接**：主题即查询族（topic_id = DAPFAM query family id），
  gold = qrels 正例族；IN/OUT 标签直接支撑 §3 的 domain 分组报告。

### A.2 CLEF-IP（备选，未启用）

- 数据入口：TU Wien ResearchData（<https://researchdata.tuwien.at/records/jqrsc-jbq51>），
  需注册申请，分发条款以届时官方文本为准；启用条件 = DAPFAM 不可用（下载失败或
  许可状况变化）。截至本记录日期未申请、未下载、未使用。

### A.3 网络通道探测记录（2026-10-29，本工作机）

| 目标 | 结果 | 用途 |
|---|---|---|
| `huggingface.co:443` | 不可达（connect timeout / 000） | 官方通道不可用 |
| `hf-mirror.com:443` | 200 OK | **实际下载通道**（`fetch_corpus.py --endpoint` 默认值来源） |
| `pypi.org` 直连 | 失败（No matching distribution） | 依赖安装走清华镜像（pyarrow 26.0.0 已装） |
