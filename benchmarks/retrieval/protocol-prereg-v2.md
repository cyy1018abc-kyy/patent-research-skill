# 检索消融协议 V2（4.2 / W4-EVAL，41A-3 跨域迁移）——预注册快照

> 本文件是 4.2 轮消融评测的协议快照，与 `gate-v2.yaml` 同一提交冻结；
> 本文件 SHA-256 记录于 gate-v2.yaml 的 `protocol_sha256`。
> 与 ABL-1（protocol-prereg-ablation.md，2026-11-01）的关系：ABL-1 的结论保持不变
> （BM25F 字段加权显著负增益 −2.93pp 被否决；RRF 融合 +2.15pp 过门是全项目首个
> 预注册正向宣称）。本协议在**放弃 BM25F**（被数据否决的路线不复活）的基础上，
> 把 ABL-1 的特征查询/RRF 步骤重建在统一等权 BM25 索引上，并追加本阶段唯一的
> 新组件步骤：**41A-3 语料共现跨域扩展**。修改本文件 §1–§5 语义 = 改协议，
> 必须重新预注册。

## §1 目的与宣称边界

- 目的：在冻结语料与同评分器下，量化 4.2 组件阶梯（特征查询 / RRF 融合 /
  **跨域共现扩展**）相对统一等权 BM25 基线的**逐步增益**；回答 4.1 蓝图
  41A-3 的预注册问题——「语料共现挖掘能否让 OUT（跨域）组从零召回变为有召回」。
- 宣称边界：任何「组件 X 提升检索」的宣称 = 该步同时通过 §4 的逐步判定门；
  未过门组件保持「可用但无宣称」。本协议任何结果都**不得**表述为
  「管线整体查全率提升」——主协议 gate.yaml 的 FAIL 结论（−2.50pp）保持不变。
- 负增益与零增益照实发表；不得为过门修改 gold、门值、评测协议、主题集或挖掘参数。

## §2 数据与预算

- 语料：DAPFAM_patent 冻结快照（corpus.parquet `469fe8e0…`、qrels_all.parquet
  `e51ae4e1…`、queries.parquet `b5ad91a6…`，与 ABL-1/Phase V 完全一致），TAC 视图；
  MANIFEST.sha256 逐文件核对。
- 主题：topics/public/manifest.json 的 **test split（312 主题）**；切分规则与
  Phase V/ABL-1 相同（earliest_claim_date 时序 60/15/25）；gold = citation-proxy
  positives。
- 预算：V2-0/V2-1/V2-2 每主题 ≤3 个索引请求；V2-3 每主题 ≤4（3 特征请求 +
  ≤1 跨域请求）；逐请求记账含零增益请求；并列按 family_id 升序。
- 挖掘输入纪律（41A-3 硬门）：共现挖掘**只接受 train/val 主题文本 + 语料快照**；
  test 主题混入挖掘输入 = 泄漏，`check_leakage.py --cooccurrence` 必须**先于**
  任何评分通过（exit 0）。
- 网络硬门：任何计分运行零网络请求；>0 ⇒ 本轮评测不通过。

## §3 配置阶梯（常量在此冻结）

所有配置共用同一 BM25 等权索引实例（引擎不是混淆变量）；请求构造如下：

| 配置 | 索引 | 请求构造 | 合并 |
| --- | --- | --- | --- |
| V2-0 基线 | BM25 等权（= v1/ABL-1 基线引擎路径） | 3 个固定机械请求：① full TAC ② title+abstract ③ claims | 逐文档 max |
| V2-1 = V2-0+特征查询 | 同 V2-0 | 从主题 TAC（title + ". " + abstract）确定性特征抽取（extract_features + DictionaryExpander 默认配置），取 single_feature 查询按计划序前 3 | 逐文档 max |
| V2-2 = V2-1+RRF | 同 V2-0 | 同 V2-1 的 3 个请求 | **RRF 融合**（k=60，等权，hybrid.rrf_fuse 现行实现）替代 max |
| V2-3 = V2-2+跨域 | 同 V2-0 | V2-2 的 3 个请求 + **≤1 个跨域请求**：计划内 cross_domain 查询（CooccurrenceMiner 产物经 CrossDomainExpander 注入，provenance 携带 split 与挖掘参数）；挖掘表无该主题种子条目时走字典回退路径（回退是配置的一部分，不是缺陷） | RRF（k=60，等权，含跨域请求共 ≤4 路输入） |

冻结常量：
- 挖掘参数（mine_cooccurrence.py）：`--splits train,val --min-cooccurrence 2
  --min-lift 2.0 --min-df 2 --max-df-ratio 0.05 --max-terms-per-seed 8`；
  种子视图 = 主题 title_en + abstract_en（claims 排除——挖掘是 train 侧数据准备，
  不是计分请求）；产物 `topics/public/cooccurrence.json`（digest 戳记），
  其 SHA-256 记入每个 V2-3 run 的 meta（`mining_artifact_sha256`）。
- RRF：k=60、等权、并列按 doc id 升序。
- 特征抽取：extract_features 默认参数，不注入主题特定词典。
- BM25F 不复活：ABL-1 已判定负增益，本阶梯不再含字段加权配置。
- V2-0 复现要求：V2-0 全量 run 与归档的 Phase V `baseline.jsonl` **逐字节一致**
  ——不一致 = 评测工装缺陷：修复后全部配置全量重跑（门值不变）。
- Cross-Encoder 重排：本轮**不进阶梯**（单列不入主门；选型 smoke 仍待补数据）。

## §4 指标与判定门

- 评分器：`tools/score_retrieval.py` 原样复用（family 级；gold=0 主题单独报告
  不进分母）；主指标 family_recall_at_100（macro over test topics），副指标
  同主协议（Recall@50/@200、nDCG@100、MRR、unique_relevant_yield_per_100_requests）。
- 分组报告：domain（IN/OUT/MIXED——**OUT 组为本协议一等报告轴**，即 V2-3 的动因）、
  era（前后半）；失败分组必须发表。
- **逐步判定门**（仅用于「组件 X 有提升」的宣称）：
  Δ(V2-k − V2-(k−1)) 宏平均 ≥ **2.0pp** 且 per-topic 配对 bootstrap 95% CI 下界 > 0
  （n=10000，**seed=20261107**）。所有逐步 Δ 无论正负全部报告。
- 主协议整体门（5.0pp）不在本协议重开；V2-3−V2-0 差距仅作归因陈述，不构成宣称。

## §5 执行纪律

1. **泄漏硬门先于一切跑分**：`check_leakage.py --manifest … --cooccurrence …`
   通过后（含 `--inject cooccurrence` 注入自检证明检查器不是橡皮图章）才允许
   执行任何计分运行。
2. **smoke 先行**：test split 按切分序前 **24** 主题 × V2-0..V2-3；smoke 只验证
   方向性（全部配置无崩溃、V2-0 smoke family_recall_at_100 > 0、请求预算未超限、
   V2-3 的跨域请求在预算内执行），smoke 结果**不进任何宣称**、不与全量混算。
3. smoke 通过后跑全量；执行顺序固定 V2-0→V2-1→V2-2→V2-3，全部主题重跑，不得择优。
   （V2-0 smoke 仅为接线验证；逐字节复现核验永远跑全量。）
4. 缺陷返工：门值不变，全部主题重跑，新旧报告都归档（沿用主协议
   preregistration_rule）。
5. 归档：runs/*.jsonl + meta-*.json（预算台账、引擎参数、快照哈希、挖掘产物哈希）
   + results/v2-ladder-<date>.json；V2-0 与 Phase V 基线的 SHA-256 比对记录在报告内。
6. 报告必须包含：逐步 Δ 及 CI、失败分组（含 OUT 组单独结论）、预算实际消耗、
   V2-0 复现核验结论、「停止/未覆盖 ≠ 查全」声明。
