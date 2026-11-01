# Patent Research Skill 4.1.0（自适应检索与消融证据；kernel 0.10.0 延续）

Requires **patentkit 0.10.0, assessment protocol 1**, Python 3.11+。内核本轮**无变化**
（0.10.0 延续，无需重装内核）。扩展 `patent_intel` **0.1.0 → 0.2.0**（需重装扩展 wheel，
安装器/独立 SUMS 同步）。

## 什么变了

本轮把检索从「查询工具集合」升级为可解释、可评估、可复现的自适应检索系统
（依据 `patent_research_skill_adaptive_retrieval_roadmap_v1.md`，Stage 0–3 全部 +
落地计划 WP-L0/L1/L2/L3/L5）：

- **身份与覆盖口径修正**（Stage 0）：查询任务显式携带 `feature_ids`（校验非空+唯一）；
  `RunOutcome.family_basis` 三态——unknown 不得携带 family ids（文档 id 永不冒充
  家族 id）；候选/疑似/确认相关三桶分账（只能显式标注，命中数不自动升级）；
  覆盖按技术特征 id 记录（修复旧控制器把 query_type 当 concept 致特征覆盖恒 0 的缺陷）；
  OPS 能力声明收缩到实际可构造的 `{"keywords"}`（原声明 class 但请求构造不消费，
  过滤器被静默丢弃），并以注册表级不变量测试永久锚定「声明字段必被消费」。
- **检索评估与策略调度**（Stage 1）：`RetrievalGapReport` 版本化契约（unknown 不得
  降级 not_found 入契约校验；metrics 必带 `gold_available` 布尔——无标注集只报代理
  指标，不伪造真实 Recall）；`RetrievalEvaluator` 特征覆盖状态机
  （disclosed / partially_disclosed / not_found / unknown）+ 缺口→建议动作映射；
  `MarginalUtilityPolicy` 收益驱动调度 `U=(w1·ΔC+w2·ΔR+w3·ΔD)/(λ1·cost+ε)`
  （确定性、可解释）+ 诚实软停止 `soft_stop_policy`；每次选择记录
  `{policy, reason, utility}`。默认策略 GapFirstPolicy 保持原序。
- **数据底座**（Stage 2）：`RawArtifactRegistry` 内容寻址登记（RA-<source>-<sha[:16]>、
  存在/哈希/字节数三重校验、verify_all 审计；CNIPA 工作区与 OPS sidecar 物理路径
  一律不动）；`PublicationRecord`（公开号+kind code 唯一定位；多语言 {lang: text}；
  field_completeness obtained/missing/unknown 封闭词表）；`FieldConflictLog` 字段级
  多源值全保留、caller 优先级解决、人工确认不被自动覆盖；家族引用 confidence=uncertain
  一律挂账（deferred）不合并。
- **语料生命周期**（Stage 3）：`CorpusManager` 增量导入幂等且分账（无法确信解析的编号
  计 failed 不入键）；内容寻址语料快照（CS-<sha[:16]>）+ 漂移验证 + 恢复；评测语料按
  文件 SHA-256 manifest 冻结注册（内容变化即拒绝；与生产语料结构隔离）；`IndexManifest`
  绑定语料快照+引擎/解析器版本；索引构建失败保留旧 active manifest。
- **多通道融合与重排**（WP-L1/L2）：`rrf_fuse` 支持通道权重（默认行为不变）；
  `FusionPipeline` 逐查询融合——失败/缺席通道留痕不当 0 分、无通道拒融合、家族折叠、
  可选重排阶段（`IdentityReranker` 保底；重排器合约=候选集不变，违约拒用、异常降级，
  全程 `RerankAccount` 留痕）；`recall --dense` CLI。
- **统一结果分账**（WP-L5，roadmap §8.3）：`AcquisitionResult` 增
  records_normalized / new_publications / new_families——adapter 只填能诚实算的，
  语料增量按调用方状态经 `account_new` 填充，uncertain 编号与 uncertain 家族引用
  一律不计入。
- **CNIPA 多子查询与联调准备**（Task 7）：`plan_cnipa_subqueries()` 确定性拆分
  （term 级特征归因保留）；`dedupe_publication_records()` 按确信规范化编号去重
  （冲突保留不重写）；OPS dry-run↔execute 同查询串一致性测试；
  `docs/live-rehearsal-runbook.md` 真实联调规程（来源维持 `partial` 直至按规程完成）。
- **消融证据 ABL-1**（预注册门执行，312 test 主题，零联网）：A0 与 Phase V 归档基线
  逐字节一致（26.18%）；**A3−A2 = +2.15pp CI[+1.20,+3.11] 过门——RRF 融合显著优于
  max 合并（首个预注册正向宣称）**；BM25F 初始权重被数据否决（−2.93pp 显著负增益，
  「未评测不得固化」告诫被证实）；特征查询无显著效应；所有配置均未超均匀 BM25 基线；
  主门（Phase V）保持 FAIL 不重开，本宣称仅限融合方式选择。

## 安装与迁移

安装器清单、manifest schema 2、双 zip 结构不变（全量包含四个技能）。已有用户：
技能包内容更新，重装技能包即可；**内核无需重装（0.10.0 延续）；扩展 wheel 升级
0.2.0 需重装**（新增 artifacts/corpus/normalization 与 evaluator/policy/reranker/
fusion_pipeline 模块）。规则表 V001–V038 不变，评估协议 1 不变。

## 边界（与上一版一致）

- 本技能产出底稿与判定辅助，不构成法律意见；不预测授权；审计报告不是法律意见；
- 期限工具是提醒台账，法定期限以官方发文/通知书为准；
- CNIPA XML 官方格式仍未实现（`official_format_status` 维持 `not_attempted`）；
- CNIPA/OPS 在线来源维持 `partial`——真实联调按 runbook 完成并登记 policy-log 前，
  不得宣称「已验证/可用」。
