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

### 已就位的半成品（0.5.0）

- **`fetch-bigquery`（G-S-04 专用普查）**：默认 dry-run（普查对象清单 + SQL 骨架 +
  费用模板，零写入）；`--run` 需 `google-cloud-bigquery` + GCP 凭据，先 dry-run 查询
  取 bytes_billed 出费用预估、确认后执行并按契约落 raw+log；`--fill <raw> [--apply]`
  从已归档普查工件回填候选的 family/cited_by（只补空缺、不覆盖人工数据，离线可测）。
  SQL 基于 `patents-public-data.patents.publications` 公开形态，**真实 `--run` 前
  必须对照当时 schema 复核列名**——这是骨架的性质，不是缺陷。
- **OPS XML ingest**：`read_raw` 支持 `.xml`（OPS exchange-document 导出，
  namespace 前缀无关、按 localname 匹配；zh 优先取标题/摘要）。OPS 的结果 XML
  落 raw/ 后即可 ingest 成 verified 候选。

### OPS 注册与限速策略（有真实任务时执行）

- 注册：Espacenet OPS 门户申请开发者账号与 key；**配额与限流阈值以门户当时公告为准**
  （本仓库不硬编码可能过期的数字），key 走环境变量，不入库；
- 限速：默认串行 + 指数退避，收到 403/429 一律停下落盘已完成部分再退出
  （增量可续），绝不重试风暴；
- 落盘：同契约第 1/2 条——每页响应即 raw 工件，`complete` 按实际抓取范围声明。

## 待办（有真实任务时）

- [x] BigQuery 同族/引证普查脚本骨架（G-S-04 专用）+ 费用预估模板 → `fetch-bigquery`
- [x] OPS 注册与限速策略文档（本页）
- [x] `read_raw` 支持 OPS XML 导出格式
- [ ] 真实 GCP 凭据下的首次 `--run`（按契约登记 policy-log）
- [ ] 真实 OPS key 下的首次检索（按契约登记 policy-log）
