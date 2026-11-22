# 预注册协议 V3 —— 4.3 组件阶梯（P0-GAP 字段覆盖 · Dense 通道）

**冻结时点**：2026-11-21（G4 项目方裁定「按推荐」，2026-11-20）；本协议与 `gate-v3.yaml`、
`run_v3_ladder.py`、`score_v3.py` **同一提交冻结**，早于任何 runs/ 评测产物与 results/ 报告；
git 历史顺序即预注册证明。此后本协议与门值不得修改（哈希锁定）。

## 0. 范围与承继

- 主门（Phase V 判定门）维持 **FAIL →「实验性增强」**，本协议不重开主门；ABL-1 宣称
  （RRF 优于逐文档 max，+2.15pp）维持，不因本协议改写。
- 本协议管辖且仅管辖以下两步的宣称；其余结论一律「可用但无宣称」。
- **Cross-Encoder 重排不入本阶梯**（G4 裁定砍除）：CE1 smoke（2026-11-21，24 题，
  top-50 重排）实测 recall@10 −2.3pp / MRR@10 −7.4pp——负先验在册（`results/ce-smoke-2026-11-20.json`），
  重排如需再评估须另立协议。
- smoke 先行（24 题接线验证），全量 312 题按 V3-0→V3-1→V3-2 顺序执行，不得择优；
  V2-0/V3-0 类复现门无论 smoke 结果都必须全量执行。

## 1. 数据与隔离

- 数据集：DAPFAM_patent（Ayaou et al., 2025, arXiv:2506.22141；CC-BY-NC-SA-4.0——
  语料与派生文件永不进入发行包，引用须携带条目）。
- 冻结快照（与 gate.yaml / gate-ablation.yaml / gate-v2.yaml 同一快照，2026-10-29）：
  corpus.parquet `469fe8e0…7526d6`、queries.parquet `b5ad91a6…2bcbe`、qrels_all.parquet `e51ae4e1…4f74`。
- split：与主门一致（earliest_claim_date 时间切分，test=312）；`check_leakage.py` 先于计分复跑。
- **零网络硬门**：任何计分运行 `network_requests` 必须 = 0。
- dense 通道索引来源（provenance）：`DenseIndex`（ids+float32 矩阵+manifest），由
  `build_dense_index.py` 于 2026-11-21 在同一冻结快照上构建，文档视图 = title+abstract，
  模型 = snowflake-arctic-embed-m-v2.0（Apache-2.0，本地权重快照，零下载）；
  其 manifest `corpus_sha256` 必须等于 corpus.parquet 冻结哈希（否则本轮作废），
  index manifest sha256 记入 V3-2 run meta。

## 2. 配置定义（常量锁定）

- **V3-0（锚）**：与 V2-0/ABL-1 A0 逐字段相同——BM25 等权字段，3 条机械请求
  （full TAC / title+abstract / claims），逐文档 max merge，k1=1.5，b=0.75，k_per_request=200。
  **必须与归档 Phase V baseline.jsonl 逐字节一致**（sha256；mismatch = harness 缺陷，
  修复后全量重跑，门值不变）。
- **V3-1（字段覆盖）**：索引换 **TACD-head**——title+abstract+claims+description，
  其中 description 按空白词截前 **2500 词**（词数换算口径与 2026-11-20 gap-smoke 相同；
  全文不可行的内存边界已在 `results/gap-smoke-2026-11-20.json` memory_note 登记）；
  k1=1.5，b=0.75 不变；请求与合并语义与 V3-0 完全一致（3 机械请求、max merge）。
  **唯一变化 = 索引字段覆盖**——本步隔离字段覆盖的贡献。
- **V3-2（Dense 通道）**：V3-1 的 3 条词法请求 rankings + **1 条 dense ranking**
  （持久化 DenseIndex 全量 45,336 矩阵暴力余弦，查询文本 = 查询族 title+abstract——
  与索引文档视图对齐），RRF 融合（k=60，等权）over ≤4 channels。
  复合性声明：本步相对 V3-1 的差值包含 dense 通道与「RRF 取代 max merge」两部分；
  RRF 部分有 ABL-1 在册正向先验（+2.15pp），本步按计划 F4 检验 dense-on-top-of-fusion。
- 密集通道实现纪律：索引消费经 `load_configured_dense_index()`（INT2 接线），
  编码器 = `DenseRetriever.encode_query`（fastembed 本地快照，零网络）；
  每主题 dense 请求数 = 1，计入预算。

## 3. 指标

- 主指标：family_recall_at_100（宏平均，gold-known-incomplete 口径与主门一致）。
- 次指标（随报告全量发表）：recall@50 / recall@200 / NDCG@100 / MRR /
  unique_relevant_yield_per_100_requests。
- 分组必报：domain（IN/OUT/MIXED，OUT 为本轮一等报告轴）+ era（前后半）；
  失败组照实发表。

## 4. 判定门（逐步，宏均值 over test 主题）

| 步 | 比较 | min_mean_gain_pp | CI 门 | bootstrap |
|---|---|---|---|---|
| 字段覆盖 | V3-1 − V3-0 | **≥ +5.0** | 95% 配对自举 CI 下界 > 0 | n=10000，seed 20261121 |
| Dense 通道 | V3-2 − V3-1 | **≥ +2.0** | 同上 | 同上 |

- 门值依据（G4 裁定记录）：V3-1 的 5.0pp 上调自草案的 3.0pp——2026-11-20 gap-smoke
  实测 A→B 差 ~6.5pp（train/val 72 题），留噪声余量；smoke 数据不进任何宣称。
- 任一门未过 ⇒ 该组件「可用但无宣称」；负增益照实发表。
- 不得为过门修改 gold、门值、协议或配置常量（哈希锁定）；返工重跑门值不变，新旧报告都归档。

## 5. 预算

| 配置 | 每主题请求上限 |
|---|---|
| V3-0 | 3 |
| V3-1 | 3 |
| V3-2 | 4（3 词法 + 1 dense） |

每个执行过的请求都计数（含零增益）。

## 6. 审计完整性

- 非授权网络请求 = 0（硬门）。
- run meta 与文件哈希逐条一致（score 审计门）：gate/protocol sha、快照哈希、
  dense index manifest sha256（V3-2）。
- smoke 报告 `claims: false`；全量报告的 `claims` 仅在门通过时对该步为 true。

## 7. 诚实边界

- 主门 FAIL 不重开；本阶梯任何结果不解除「实验性增强」定级，声明面升级唯一路径 =
  E2 私有主题 + EX-01 双评审后的 claim_rule 复议（G6，本协议范围外）。
- OUT 组参照线（论文 0.1368 doc / 0.1521 passage）仅作归因对照发表，不构成本协议门。
