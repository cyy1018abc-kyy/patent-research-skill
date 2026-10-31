# 数据契约规范（WP-0 冻结稿 v0.1）

所有 `patent_intel` 记录类型定义在 `extensions/patent_intel/src/patent_intel/contracts.py`，
由 `tests/test_contracts.py` 全量锁定。本文是给人看的口径说明；冲突时以代码与测试为准。

## 1. 通用规则

1. **每条记录自带四件套**：`schema_version`（整数，当前 1）、`record_type`、
   `owner`（归属工作包，如 `WP-A`）、`created_at`（ISO-8601 UTC，必须带时区）。
2. **读取纪律**：
   - `schema_version` 高于本构建支持值 → `UnsupportedSchemaError`（拒绝解读，
     绝不猜测字段含义）；
   - 必填字段缺失或为 None → `RecordValidationError`；
   - **未知字段原样保留**（存进 `extra`，序列化时回传）——旧写入方的数据穿过
     新读取方不丢失；
   - 记录在构造时自检（`__post_init__` → `validate()`），非法记录无法存在于内存。
3. **枚举是封闭字符串集合**：新增取值必须同步改 contracts 常量与测试。
4. **时间**：一律 ISO-8601 UTC（`+00:00`）；展示层负责本地化。
5. **哈希**：SHA-256，小写十六进制 64 位；凡是「证据指针」字段（raw_sha256、
   text_hash、results_sha256）都按此校验。

## 2. 记录类型与所有权

| 类型 | 归属 | 关键不变量 |
|---|---|---|
| `FeatureSpec` | WP-A（查询视图；基准事实归 Discovery/patentkit） | `source_refs` 非空；`negation` 与 `requiredness=negation` 一致 |
| `QuerySpec` | WP-A | `provenance` 每项必须带 `feature_id`（UT-Q03：无来源的扩词=unverified proposal）；`approved=false` 才能离开 sidecar；`feature_ids` 是覆盖记账的权威特征维度（缺省=覆盖未知，不得以 axis/query_type 顶替） |
| `SearchRun` | WP-B | `hits_reported` ≠ `records_fetched`；`complete=false` 必须给 `incomplete_reason`；`failed` 必须给 `error` |
| `RawArtifactRef` | WP-B | sha256 必填；`path` 相对工作区或 state dir |
| `PatentRecord` | WP-B | `source_refs[].{source, raw_ref}` 强制（可回溯）；原始 ID 字符串不重写；`identifier_confidence ∈ {exact, normalized, uncertain}` |
| `DocumentAnchor` | WP-C | `raw_sha256`+`text_hash`+`parser_version` 三绑定；`verification_status ∈ {unverified, machine_parsed, human_confirmed, stale}` |
| `RetrievalRun` | WP-A/WP-F | 可复现信封：数据集哈希、查询集哈希、引擎版本、种子、预算 |
| `EvaluationReport` | WP-F | 指标数字只来自 `tools/score_retrieval.py`；手写报告不合法 |
| `EvidenceProjection` | WP-D | `relation ∈ {discloses, partially_discloses, teaches_against, cites, cited_by, family_of}`；只是视图，不是内核真值 |
| `AdvisoryProposal` | WP-D | `requires_human_review=false` 是契约违规（构造即抛错） |

## 3. 与内核记录的关系

- 内核 `02_search_logs/*.log.json`（`db/target/actor/capture_mode/query/result`
  契约，见 `docs/data-sources.md`）由内核独占写入；扩展只通过
  `kernel_bridge.read_search_logs` 读取。
- 内核候选 `03_candidates/*.json` 的 `evidence_level` 判定归内核；扩展的
  `PatentRecord` 索引**不是**候选，不进入门禁计数。
- raw 工件晋升 `verified` 的唯一路径：内核 `ingest`（`docs/data-sources.md`
  契约第 1–5 条）。扩展不复制、不模拟该逻辑。

## 4. 演进规则

1. 加可选字段：改 `SPEC`（带默认值），本构建即可读写，旧文件照常读取——
   schema_version 不动。
2. 加必填字段或改语义：`SCHEMA_VERSION += 1`，`from_dict` 自然拒绝旧记录；
   同时在 `docs/architecture/` 下补迁移说明。目前不存在迁移器（v1 是初版）。
3. 弃用字段：先停止写入并保留读取（记入本文变更表），下个 major 再物理删除。
4. 任何契约改动必须同轮更新：`contracts.py`、`test_contracts.py`、本文、
   `docs/adr/0001-kernel-boundary.md`（若涉及边界）。

## 变更表

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-10-28 | 1 | 初版：十类记录 + 通用规则（WP-0 冻结） |
