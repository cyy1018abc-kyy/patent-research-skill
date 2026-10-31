# 在线来源真实联调 Runbook（Stage 4 前置 · Task 7）

> 状态：**待执行** — 本 runbook 是真实联调的操作规程，不是联调已完成的声明。
> 在本 runbook 完整走完并登记 policy-log 之前，所有在线来源能力等级保持 `partial`，
> 不得在任何文档、报告或对话中宣称「已验证 / 已联调 / 可用」。

## 0. 纪律基线

- 不做重试风暴：403/429 一律停止采集，保留已完成页面（`BackoffStopped` 路径已有测试）。
- 每页响应立即落盘 raw + SHA-256 审计（OPS sidecar `raw/`；CNIPA 由内核写 `02_search_logs/raw/`）。
- 配额与限速以 EPO 门户当前政策为准，**不硬编码任何数字**。
- 凭据只经环境变量（`OPS_OAUTH_KEY` / `OPS_OAUTH_SECRET`），不进日志、账本、报错信息。
- 双门授权：`--confirm-network` 显式传入 **且** sidecar `config.json` 的
  `network_consent.allowed_sources` 含目标来源，缺一即拒。

## 1. EPO OPS 联调步骤

1. **登记**：`docs/policy-log.md` 新增一行（日期、操作者、目的、范围、预计请求量）。
2. **凭据**：导出 OPS OAuth key/secret；确认 `patent_intel[ops]` extra 已装。
3. **OAuth 冒烟**：仅取 token（`OpsAdapter._access_token()`），记录 HTTP 状态与
   `expires_in` 实测值；失败即停，不做第二来源尝试。
4. **单查询 dry-run → execute 一致性核对**：`dry_run` 预览的请求串必须与实际执行的
   请求串逐字符一致（一致性已有回归测试锚定；联调时人工再核对一次响应体）。
5. **分页实测**：`max_pages=2, page_size=25` 起步；记录 X-OPS-Range 实际行为、
   命中数字段、字段可用性（书目/摘要/家族/引证分别登记实测结论）。
6. **raw 归档核验**：每页 `raw/` 文件存在、SHA-256 与审计账本一致
   （`RawArtifactRegistry.verify_all()` 全部 ok）。
7. **403/429 演练**：故意用无效凭据触发 403（或等配额窗口触发 429），确认：
   已完成页面保留、failure ledger 记录 `http_403/429`、无重试。
8. **能力矩阵回填**：按实测修正 `OpsAdapter.capabilities()` 与
   `docs/data-sources.md`（分类字段是否声明，取决于 CQL `cpc=` 实测——未实测前维持
   只声明 `keywords`）。
9. **policy-log 收口**：登记实测时间窗、请求量、失败、配额观察；能力等级是否从
   `partial` 升级，由以上证据集体决定，任何一项缺失即维持 `partial`。

## 2. CNIPA 联调步骤

1. 确认外部 Playwright 工具（`cnipa_search.py`）可用且为当前登记版本。
2. 单查询（`--abstract`）走内核 `fetch-cnipa --apply`，核对：
   `result.hit_count` vs raw 记录数（`records_fetched`）vs `complete` 标志——
   三个数字必须分开报告（当前能力矩阵：单页 3 条，无完整翻页，不得宣称完整检索）。
3. 多子查询演练：用 `plan_cnipa_subqueries()` 拆分的子查询逐个执行，
   结果用 `dedupe_publication_records()` 去重；核对 `duplicates` 与 `conflicts` 统计。
4. 登记命中数/抓取数/完整性三元组到 policy-log。

## 3. 验收口径（Stage 4 判定）

- 每个来源的**真实**请求-响应证据链完整（raw + 哈希 + 审计 + policy-log）。
- 实测行为与能力声明逐项一致；不一致项要么修正实现、要么收缩声明，二者必居其一。
- `partial → full` 升级仅在上述全部完成时发生；升级本身在 policy-log 留痕。
- 联调数据可进入生产语料（经 Corpus Manager 增量导入），但**不自动**进入评测集。
