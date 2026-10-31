# 检索数据源扩展：评估与决策备忘（2026-10-25）

> 对应升级清单 P1-9。结论先行：**近期（0.3.x）不新增联网数据源、不解冻 MCP**；
> 把「新增源必须落 raw/ 才算 verified」的纪律先固化为接口约定，BigQuery/OPS 的接入
> 留给有真实检索任务时按本备忘的验收标准走。

## 候选源评估

| 源 | 能拿到什么 | 接入成本 | 关键风险 | 结论 |
|---|---|---|---|---|
| **Google Patents Public Datasets（BigQuery）** | 全量著录/摘要/同族/引证（patents-public-data） | 中：需要 GCP 账号 + BigQuery 配额；按量计费 | 费用与账号归属；「批量导出」与本项目「检索留痕」的语义差 | **条件接入**：仅在需要全量同族/引证普查（G-S-04）时启用；结果以导出文件落 `raw/`，日志记 `capture_mode=live` + 导出参数 |
| **Espacenet OPS**（官方 API） | 著录/全文/同族，配额明确 | 中：注册 key、限速 4GB/月 内免费 | key 管理；限速下的批量任务要增量落盘 | **条件接入**：作为 CNIPA 3 条上限的补充检索通道；同样走 raw/+log 纪律 |
| **pqai / patents-mcp / patent-mcp-server（开源）** | 语义检索 / Google Patents 数据的 MCP 封装 | 低（装包即用） | **证据链断裂**：MCP 返回值没有 raw 工件，最多 asserted | **不接入主线**；可作为人工预研工具，结论必须用 CNIPA/OPS 复检后落 raw/ 才升级 verified |
| **CNIPA epub（现状）** | 每查询 3 条，多子查询累积 | 已接入 | WAF、翻页被拦 | 维持现状（`fetch-cnipa --from-library`） |

## MCP 解冻决策（对照 docs 冻结条款）

维持**冻结**（只修 bug，不加工具）。理由：
1. 0.3.0 的七个新命令走 CLI/脚本即可被所有本地客户端调用，Mcp 不是唯一通道；
2. 新增 MCP 工具会把「证据链纪律」复制到第二个入口，历史上正是这种复制造成过
   口径分裂（A4 类问题）；
3. 解冻触发条件不变：出现**只能**以 MCP 形态提供的能力（如客户端内嵌 UI 回调）时
   再议，且新增工具必须内置 raw/ 落盘。

### 2026-10-25 复评（kernel 0.5.x 时点，含数据源演练证据）

结论：**继续冻结**，且理由比 0.3.0 时更充分。证据：

| 维度 | 现状 |
|---|---|
| 能力面差距 | MCP 12 工具（status/validate/gates/search_plan/candidates/references/doctor/ingest/bibsync/attest/fetch_cnipa/batch），CLI 23 个直通命令 + 5 个专用命令——0.3 以来全部新能力（provenance/figures/deadlines/export-docx/map/layout/ledger/queryplan/revise/chain/fetch-bigquery/backfill-doi/check）**只在 CLI**，没有任何客户端「只能经 MCP」触达 |
| 证据链纪律 | 新能力全部内嵌 raw/ 工件纪律（fetch-bigquery 契约、OPS ingest、revise 事务）；复制到 MCP 需要逐工具重建 raw/ 落盘，成本实打实、需求为零 |
| 实测证据 | 2026-10-25 数据源演练证明集成面以 CLI 为准（`--run` 交互确认、OPS XML 落盘 ingest）；金样回归也全部走 CLI/module 入口 |
| 使用数据 | 无任何 MCP 客户端使用反馈——「用户卡在缺 MCP 工具」这件事没有发生过一次 |

重新评估的触发条件（任一满足才再议）：
1. 出现**只能**以 MCP 形态提供的能力（如客户端内嵌 UI 回调）；
2. 目标客户端明确无法执行本地命令、只能挂 MCP server；
3. 出现真实的 MCP 用户反馈被缺工具阻塞（而非猜测）。
解冻时的工程要求不变：新增工具必须内置 raw/ 落盘 + 走 `evals/` 话术用例 +
`tests/test_mcp.py` 锁定工具数与注册表一致。

## 新数据源的统一验收标准（任何源都要过）

1. 每次查询落 `raw/` 工件（原始响应或导出文件）+ `02_search_logs/*.log.json`；
2. `result.complete` 如实声明；命中数与实采数分开记录（硬约束 5）；
3. `ingest` 能从该 raw 格式生成候选骨架（`read_raw` 支持新格式）；
4. 在 `docs/policy-log.md` 登记（如涉及官方口径变化）；
5. 走一遍 `evals/` 的 B3 用例（命中数 ≠ 实采数）确认话术不误导。

## 数据源接入契约（0.5.0 固化）

上表五条验收标准是**任何**新数据源进入主线的前置条件，以下为工程落点——
新增源 = 新增一个满足本契约的模块，而不是在旧模块里开洞：

1. **raw 工件先于一切**：每次查询的原始响应/导出文件落 `02_search_logs/raw/`，
   没有工件的数据最高只能算 `attested`，不可能 `verified`（这是模型层的判定，
   不是文档约定）；
2. **日志如实声明**：`02_search_logs/*.log.json` 记 `capture_mode=live`、
   `result.complete` 如实（部分命中必须写 false）、命中数与实采数分开；
3. **可 ingest**：`read_raw` 支持该源格式（现有分发：JSON 按内容识别 CNIPA /
   Crossref / Google Patents，`.csv/.tsv` 表格，`.xml` OPS 导出），新格式加
   `parse_*` 函数 + 夹具测试；
4. **dry-run 默认**：联网形态默认拒绝或需要显式凭据（例：`fetch-bigquery --run`
   无 `GOOGLE_APPLICATION_CREDENTIALS` 直接退出），凭据与配额永远归真实任务；
5. **登记与评测**：涉及口径变化进 `policy-log.md`；话术过 `evals/` 用例。

### 已就位的半成品（0.5.0 预置；0.6.0 按普查证据口径修正）

- **`fetch-bigquery`（G-S-04 专用普查）**：默认 dry-run（普查对象清单 + SQL 骨架 +
  费用模板，零写入）；`--run` 需 `google-cloud-bigquery` + GCP 凭据，先以**同一份
  SQL + 同一组参数**跑 dry-run（预检与执行的请求完全一致），按 dry-run 返回的
  `total_bytes_processed` 出费用预估，超过 `--max-cost-usd`（默认 5）直接拒绝；
  确认后执行，**每个普查对象落一行**（零命中也是一行，带 `found` 标记），归档名
  带日期/目标/运行时刻/行数（`bigquery_<date>_<target>_<HHMMSS>_GS04_<rows>.jsonl`），
  已存在的工件一律拒绝覆盖；`--fill <raw> [--apply]` 从**工作区
  `02_search_logs/` 内**的已归档普查工件回填候选的 family/cited_by，并**同源写入
  G-S-04 普查记录**（census，见 research 参考文档 05）——工件与登记日志核对
  target（跨目标回填直接拒绝），只回填传入 target 的候选，有人工评审痕迹的候选
  默认跳过（`--force` 越过并追加 `02_search_logs/backfill_audit.jsonl` 审计），
  普查只补空缺、不覆盖人工数据，重复运行幂等。
  SQL 基于 `patents-public-data.patents.publications` 公开形态，**真实 `--run` 前
  必须对照当时 schema 复核列名**——这是骨架的性质，不是缺陷。0.6.0 修正：被引
  子查询返回的是**引用方**（citing）的文献号（旧版投影回被引方，量不出引用它的文献）。
- **OPS XML ingest**：`read_raw` 支持 `.xml`（OPS exchange-document 导出，
  namespace 前缀无关、按 localname 匹配；zh 优先取标题/摘要）。OPS 的结果 XML
  落 raw/ 后即可 ingest 成 verified 候选。

### OPS 注册与限速策略（有真实任务时执行）

- 注册：Espacenet OPS 门户申请开发者账号与 key；**配额与限流阈值以门户当时公告为准**
  （本仓库不硬编码可能过期的数字），key 走环境变量，不入库；
- 限速：默认串行 + 指数退避，收到 403/429 一律停下落盘已完成部分再退出
  （增量可续），绝不重试风暴；
- 落盘：同契约第 1/2 条——每页响应即 raw 工件，`complete` 按实际抓取范围声明。

## 实跑前契约演练（2026-10-25，无凭据）

真实联网**没有**跑：本机无 GCP 凭据、无 OPS key，且本机直连 `bigquery.googleapis.com`
超时被阻——真实 `--run` 必须在 googleapis.com 可达的网络环境执行。除此之外，契约的每一条
都已在发布版 0.5.0 内核 + 真实 CLI 上逐条演练过（工作区：init → ingest → 演练命令全链）：

| 契约条款 | 演练结果 |
|---|---|
| dry-run 默认零写入 | `fetch-bigquery`（文本与 `--json`）跑在真实工作区，前后文件清单逐项一致 |
| `--run` 双守卫 | 无 `google-cloud-bigquery` → `[FATAL]` exit 2；有库无凭据（桩库注入，不触网）→ `[FATAL]` exit 2 |
| `--fill` 只补空缺 | 干跑 → `--apply` → 重复 apply 幂等（第二轮 0 写入）；坏工件在 CLI 层 `[FATAL]` exit 2 |
| OPS XML 可 ingest | exchange-document 落 raw/ → `ingest --raw` → `verified` 候选（zh 标题/摘要优先、申请人入档） |
| 日志如实/命中分离 | `capture_mode=live`、`complete` 如实；回填后 G-S-04 PASS（verified=1/1） |
| 规则联动 | 缺 bib 触发 V004、未评估触发 V029、无 run 支撑触发 V018——均如实报出，未被数据源路径绕开 |

演练抓出并已修复两个内核缺陷（回归测试随修复入库）：

1. `check --json` 把 `--json` 透传给 validate 与 gates，输出两个连排 JSON 文档
   （`json.load` 直接 Extra data）——现合并为单一文档 `{"check": …, "gates": …}`，
   复合退出码语义不变（validate 阻断码优先，否则 gates 全 PASS→0、其余→2）；
2. `fetch-bigquery --fill` 遇坏工件抛裸 traceback——现转 `[FATAL]` + exit 2。

### 凭据到位当天（runbook）

1. `pip install google-cloud-bigquery`；`GOOGLE_APPLICATION_CREDENTIALS` 指向服务账号 JSON；
2. **复核 SQL 列名**：对照当时 `patents-public-data.patents.publications` schema
   （dry-run 输出里带完整 SQL，骨架性质见上节）；
3. `python -m patentkit fetch-bigquery --run`——先出 bytes_processed 费用预估
   （超 `--max-cost-usd` 会拒绝），确认后才执行、结果自动落
   `raw/bigquery_<date>_<target>_<HHMMSS>_GS04_<rows>.jsonl` + 配套 `.log.json`；
4. `fetch-bigquery --fill <raw> --apply` → `gates`（G-S-04 现在核验普查记录）与
   `check`（V 系列复核；记录损坏走 V037）；
5. 按契约在 `docs/policy-log.md` 登记接入事件。OPS 首检索同法：key 走环境变量，
   结果 XML 落 `02_search_logs/raw/` → `ingest --raw` → 登记；403/429 即停，已完成部分落盘。

## 待办（有真实任务时）

- [x] BigQuery 同族/引证普查脚本骨架（G-S-04 专用）+ 费用预估模板 → `fetch-bigquery`
- [x] OPS 注册与限速策略文档（本页）
- [x] `read_raw` 支持 OPS XML 导出格式
- [x] 无凭据契约演练（2026-10-25，见「实跑前契约演练」节；两个内核缺陷已修）
- [ ] 真实 GCP 凭据下的首次 `--run`（按契约登记 policy-log）
- [ ] 真实 OPS key 下的首次检索（按契约登记 policy-log）

### 2026-10-30 复评（Phase V / V4-2，4.0 扩展已随库发行时点）

结论：**继续冻结**。逐条复核：

| 复核项 | 结果 |
|---|---|
| 「只能以 MCP 形态提供的能力」是否出现 | 否——4.0 扩展（patent_intel 0.1.0）同样以 `python -m patent_intel` CLI 形态交付，与本地客户端全兼容；未出现客户端内嵌 UI 回调类需求 |
| 双入口纪律复制风险 | 更高——扩展引入了第二套只读边界（ADR 0001），再加 MCP 第三入口只会放大口径分裂面；扩展边界由 kernel_bridge 白名单守住，无需 MCP |
| raw/ 落盘前置 | 不适用（本轮无新增工具） |

维持「只修 bug，不加工具」；下次复核随 4.1 立项。
