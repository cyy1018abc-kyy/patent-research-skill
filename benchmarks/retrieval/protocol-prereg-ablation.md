# 消融评测协议（Phase L3 / ABL-1）——预注册快照

> 本文件是消融评测的协议快照，与 `gate-ablation.yaml` 同一提交冻结；
> 本文件 SHA-256 记录于 gate-ablation.yaml 的 `protocol_sha256`。
> 与 Phase V 主协议（protocol-prereg.md）的关系：主协议的判定门保持 FAIL 结论不变
> （扩展管线 −2.50pp）；本协议是**组件归因**研究，不重开主门、不构成任何
> 「查全率提升」宣称。修改本文件 §1–§5 语义 = 改协议，必须重新预注册。

## §1 目的与宣称边界

- 目的：在冻结语料与同评分器下，量化检索管线各组件（BM25F 字段加权 / 特征查询 /
  RRF 融合）相对 A0 基线的**逐步增益**，回答「哪个组件贡献了什么 / 哪个组件在害什么」
  ——为 WP-L2 Cross-Encoder 选型与后续调参提供证据，替代直觉决策。
- 宣称边界：任何「组件 X 提升检索」的宣称 = 该步同时通过 §4 的逐步判定门；
  未过门组件保持「可用但无宣称」。本协议的任何结果都**不得**表述为
  「管线整体查全率提升」——那个宣称仍由主协议 gate.yaml 管辖且已 FAIL。
- 负增益与零增益照实发表；不得为过门修改 gold、门值、评测协议或主题集。

## §2 数据与预算

- 语料：DAPFAM_patent 冻结快照（corpus.parquet `469fe8e0…`、qrels_all.parquet
  `e51ae4e1…`、queries.parquet `b5ad91a6…`），TAC 视图（title_en + abstract_en +
  claims_text），与 Phase V 完全一致；MANIFEST.sha256 逐文件核对。
- 主题：topics/public/manifest.json 的 **test split（312 主题）**，切分规则与 Phase V
  相同（earliest_claim_date 时序 60/15/25）；gold = citation-proxy positives。
- 预算：每主题 ≤3 个索引请求（与 v1 同预算，逐请求记账含零增益请求）；
  合并规则按各配置定义（§3）；并列按 family_id 升序。
- 网络硬门：任何计分运行零网络请求；>0 ⇒ 本轮评测不通过。

## §3 配置阶梯（常量在此冻结）

所有配置共用同一 BM25 索引族实例（引擎不是混淆变量）；请求构造如下：

| 配置 | 索引 | 请求构造 | 合并 |
| --- | --- | --- | --- |
| A0 基线 | BM25 等权（= v1 基线引擎路径） | 3 个固定机械请求：① full TAC ② title+abstract ③ claims | 逐文档 max |
| A1 BM25F | BM25F 字段加权 | 同 A0 的 3 个机械请求（按各自字段子集打分） | 逐文档 max |
| A2 BM25F+特征查询 | 同 A1 | 从主题 TAC（title + ". " + abstract）确定姓特征抽取
  （extract_features + DictionaryExpander，default 配置），取 single_feature 查询按计划序前 3 | 逐文档 max |
| A3 = A2+RRF | 同 A1 | 同 A2 的 3 个请求 | **RRF 融合**（k=60，等权）替代 max |

冻结常量：
- BM25F 字段权重：title **3.0** / abstract **2.0** / claims **2.0**（roadmap §4.1 初始
  建议值适配 TAC；DAPFAM claims_text 为不分独/从权的整块 ⇒ 取 2.0，偏离说明在此留痕，
  不得在跑分后调整）；
- RRF：k=60、等权、并列按 doc id 升序（hybrid.rrf_fuse 现行实现）；
- 特征抽取：extract_features 默认参数（DictionaryExpander 种子词典），不额外注入
  主题特定词典；
- A0 复现要求：A0 全量 run 与归档的 Phase V `baseline.jsonl` **逐字节一致**
  （同引擎版本 + 同语料 + 同主题 + 同请求）——不一致 = 评测工装缺陷：
  修复后全部配置全量重跑（门值不变）。

## §4 指标与判定门

- 评分器：`score_phase_v.py` 原样复用（family 级；gold=0 主题单独报告不进分母）；
  主指标 family_recall_at_100（macro over test topics），副指标同主协议
  （Recall@50/@200、nDCG@100、MRR、unique_relevant_yield_per_100_requests）。
- 分组报告：domain（IN/OUT/MIXED）、era（前后半）；失败分组必须发表。
- **逐步判定门**（仅用于「组件 X 有提升」的宣称）：
  Δ(A_k − A_{k−1}) 宏平均 ≥ **2.0pp** 且 per-topic 配对 bootstrap 95% CI 下界 > 0
  （n=10000，seed=20261101）。所有逐步 Δ 无论正负全部报告。
- 主协议整体门（5.0pp）不在本协议重开；A3−A0 的差距仅作归因陈述，不构成宣称。

## §5 执行纪律

1. **smoke 先行**：test split 按切分序前 **24** 主题 × A0..A3；smoke 只验证方向性
   （全部配置无崩溃、A0 smoke family_recall_at_100 > 0、A3 请求预算未超限），
   smoke 结果**不进任何宣称**、不与全量混算。
2. smoke 通过后跑全量；执行顺序固定 A0→A1→A2→A3，全部主题重跑，不得择优。
3. 缺陷返工：门值不变，全部主题重跑，新旧报告都归档（沿用主协议 preregistration_rule）。
4. 归档：runs/*.jsonl + meta-*.json（预算台账、引擎参数、快照哈希）+
   results/ablation-<date>.json；A0 与 v1 基线的 SHA-256 比对记录在报告内。
5. 报告必须包含：逐步 Δ 及 CI、失败分组、预算实际消耗、A0 复现核验结论、
   「停止/未覆盖 ≠ 查全」声明。
