# 来源能力矩阵（Source Capabilities）

- 生成口径：与 `patent_intel.sources.registry.describe()` 一致（代码是事实源，
  本文档是人读镜像；B-06 约定——真实联调结果变化时先改代码，再同步本页）。
- **诚实声明**：截至 2026-10-28，本仓库**没有执行过**任何一次真实 OPS/GCP 联网
  检索；所有联网适配器的 `support_level` 都是 `partial`（契约已在无凭据环境 +
  桩传输层验证，未做真实线上运行）。`full` 只在完成一次真实联调并登记
  `docs/policy-log.md` 后授予。

| source | 支持等级 | 凭据 | 查询字段 | 分页 | 单查询上限 | 许可状态 | 备注 |
|---|---|---|---|---|---|---|---|
| `cnipa` | partial | 否（外部工具 playwright） | keywords/abstract/class/title/applicant | 否（首页） | 3 条/页 | public_export | 走内核 `fetch-cnipa` 契约；部分抓取显式 `complete=false` |
| `crossref` | partial | 否 | keywords | 是 | 未声明 | official_api | 走内核 `fetch-crossref`；书目元数据 ≠ 披露证据（见 npl.py） |
| `ops` | partial | 是（OPS_OAUTH_KEY/SECRET 环境变量） | keywords/class | 是 | 未声明 | official_api | OAuth + 限速 + 断点 + sidecar raw 归档；403/429 即停；**未实测**；配额以 OPS 门户为准 |
| `bigquery` | planned（内核 `fetch-bigquery` 已具备） | GCP 凭据 | SQL（骨架） | — | — | 按量计费 | G-S-04 普查专用；费用门 `--max-cost-usd`；扩展暂不重复封装 |
| `manual export` | full（人工导入路径） | — | — | — | — | 视来源 | 无授权 API 时的合规通道：人工导出文件 → 内核 `ingest` |

## 纪律（对全部来源生效，来源详见 docs/data-sources.md）

1. raw 工件先于一切；没有 raw 的数据最高 `attested`，不可能 `verified`；
2. `hits_reported` 与 `records_fetched` 分开记录；`complete=false` 必须带原因；
3. 403/429 一律停止并落盘已完成部分（`BackoffStopped`），不重试风暴；
4. 凭据只走环境变量，绝不入日志/账本/错误消息；
5. 每个采集页在 sidecar `audit/raw_ledger.jsonl` 有 SHA-256 条目（Audit Integrity
   指标的数据源）；失败批次的保留内容记入 `failure_ledger.jsonl`；
6. 升级 `support_level` 需要真实联调证据 + policy-log 登记。

## 升级记录

| 日期 | 来源 | 变更 | 证据 |
|---|---|---|---|
| 2026-10-28 | 全部 | 初版矩阵；全部联网源 partial（未实测） | tests/test_sources.py、test_source_infra.py（桩传输） |
