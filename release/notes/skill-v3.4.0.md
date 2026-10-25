# Patent Research Skill 3.4.0（普查证据口径 + 数据源链路修正 + 安装引用闭环）

Requires **patentkit 0.6.0, assessment protocol 1**, Python 3.11+.

## 什么变了

本版来自评审排定的「普查证据与安装引用一致性」升级（P0 三项一并落地）：

- **G-S-04 改为核验普查记录（census）**：旧口径只查 `family`/`cited_by` 是否为数组，
  两个空数组即可 PASS，「未查」与「查过零命中」无法区分；参考文档的「非空数组」又让
  真正查过、确实零命中的记录永远不达标。现在每个普查对象（near_prior_art/family）在
  family 与 cited_by 两个维度各需一条有效普查记录：**查询对象、来源、时间、状态、
  原始工件及哈希**（新内核模块 `patentkit/census.py`）。零命中（`zero_hits`）计入完成；
  未查 / `partial` / `failed` / 工件缺失或被改不得冒充完整。记录由
  `fetch-bigquery --fill` 从归档工件自动生成，其他来源按 research 参考文档 05 的
  schema 手工补录。validate 新增 **V037**：记录存在但损坏（缺字段 / 哈希不符 /
  状态与工件矛盾）→ error；诚实的 partial/failed 不是损坏，由门禁口径处理。
  候选 schema 新增 `census` 属性——**旧工作区先跑 `patentkit migrate`** 再回填。
- **BigQuery 链路修正**（全部不需要凭据即可验证，真实 `--run` 仍按契约等真实任务）：
  1. dry-run 预检与正式执行**复用同一份 SQL + 同一组 `query_parameters`**
     （旧版预检不绑参数，参数化 SQL 的预检与执行是两个请求）；
  2. 被引（cited-by）子查询返回**引用方**文献号（旧版投影回被引方，量不出谁引用它）；
  3. 归档名带日期/目标/运行时刻/行数（`bigquery_<date>_<target>_<HHMMSS>_GS04_<rows>.jsonl`），
     **已存在的工件一律拒绝覆盖**；每个普查对象落一行（零命中也是一行，带 `found` 标记）；
  4. `--fill` 写普查记录（字段级工件绑定），工件必须在工作区 `02_search_logs/` 内，
     与登记日志核对 target（跨目标回填直接拒绝），只回填传入 target 的候选，
     **有人工评审痕迹的候选默认跳过**（`--force` 越过并追加
     `02_search_logs/backfill_audit.jsonl` 审计）；普查只补空缺，重复运行幂等；
  5. 费用预估改用官方 dry-run 的 `total_bytes_processed`，新增 `--max-cost-usd`
     预算上限（默认 5 美元，超过直接拒绝执行）。
- **双技能安装后的引用闭环**：修复双技能拆分后遗留的 66 处失效相对链接
  （research 的 13/10 号改技能交接说明、两份英文镜像的链接改为镜像目录内兄弟引用、
  样例 README 的相对路径）；新增 `tools/check_reference_links.py`——相对链接必须在
  **本技能载荷内**解析（安装用户拿到的是单个技能目录，`../` 跨技能链接在安装后是
  死链，跨技能导航走文内交接说明）。该检查进 CI：仓库树一遍 + 解包后的全量包与
  drafting 单包各一遍；unittest 同步覆盖（`tests/test_reference_links.py` +
  `test_release.py` 新增打包后复检）。
- 门禁输出新增逐对象失败明细（G-S-04 FAIL 会列出哪个候选、哪个维度、什么原因）；
  金样管线新增普查回填三阶段（回填→已确认候选跳过→`--force` 越过并审计）。
- **不做**：真实 GCP/OPS 凭据接入（等外部条件）；MCP 解冻（三项触发条件均未满足）；
  改稿闭环↔conclusions 联动（原 §十一第 1 项，顺延至下一轮，其预留的 V037 编号
  由本轮普查规则使用，联动规则将取 V038）。

## 升级

安装本包覆盖旧目录即可（`--force`）；**内核必须同步升到 0.6.0**（技能封装层会拒绝旧内核）；
**旧工作区先跑 `python -m patentkit migrate`** 刷新候选 schema（新增 census 属性），
再对普查对象执行 `fetch-bigquery --fill`。在 0.6.0 之前，G-S-04 由旧口径判过的
工作区会在下一次 `gates` 时如实转为 FAIL（未查 = 检索不足），按 05 号参考文档补普查即可。

## Download and install

Download `patent-research-skill-v3.4.0.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.6.0-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.6.0).
Verify against `SHA256SUMS-skill-v3.4.0.txt`（覆盖两个 zip）。
