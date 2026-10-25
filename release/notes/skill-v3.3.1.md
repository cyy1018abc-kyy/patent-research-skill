# Patent Research Skill 3.3.1（数据源契约演练 + drafting 金样）

Requires **patentkit 0.5.1, assessment protocol 1**, Python 3.11+.

## 什么变了（patch 级：无新规则、无新命令）

本版来自「真实数据源实战 → drafting 金样 → MCP 解冻评估」一轮的三件事：

- **数据源契约演练**（`docs/data-sources.md` 新增实录节 + 凭据日 runbook）：契约每一条
  已在发布版内核 + 真实 CLI 上逐条演练（dry-run 零写入、`--run` 双守卫、`--fill` 幂等
  回填、OPS XML 全链 ingest、V 系列联动均如实触发）；真实联网仍未发生——本机无 GCP/OPS
  凭据，且 `bigquery.googleapis.com` 直连超时被阻（OPS 端点可达、无 key 403，符合预期）。
- **drafting 侧端到端金样回归**（`regression_tests/test_golden_pipeline_drafting.py`）：
  撰写线内核环节——provenance scan/check、figures check/draw（SVG）、deadlines
  list/check、revise apply/status/close 闭环、`check --json`——在同一夹具工作区整体
  对 10 份快照 + 连跑两遍逐字节一致的确定性测试；夹具新增 `09_deadlines/` 台账与一条
  B 级数值溯源（NUM-003，研究侧 DOCX 快照相应多一行）。
- **MCP 解冻复评**（`docs/data-sources.md`）：结论**继续冻结**——CLI 23 直通 + 5 专用
  命令 vs MCP 12 工具，不存在「只能经 MCP」触达的能力；三项再评估触发条件已固化成文。
- 演练/金样揪出并修复的**三个内核缺陷**（各带回归测试）：
  1. `check --json` 原先把 `--json` 透传给 validate 与 gates，输出两个连排 JSON 文档
     （`json.load` 直接 Extra data）——现合并为单一 `{"check": …, "gates": …}` 文档，
     复合退出码语义不变（validate --strict 阻断码优先——error 或 warning——否则 gates
     全 PASS→0、其余→2）；
  2. `fetch-bigquery --fill` 遇坏工件抛裸 traceback——现转 `[FATAL]` + exit 2
     （`load_census_raw` 的 ValueError 契约不变）；
  3. `deadlines list --root` 原本不收 `--root`（argparse 直接报错）——现子命令前后
     两个位置都生效（子解析器 SUPPRESS 默认值，旧的前置形式不受影响）。
- 工作区无迁移；规则表（V001–V036）、验收门、评估协议全部不变。

## 升级

安装本包覆盖旧目录即可（`--force`）；**内核必须同步升到 0.5.1**（技能封装层会拒绝旧内核）；
工作区无需迁移（本版不新增任何命令与规则）。

## Download and install

Download `patent-research-skill-v3.3.1.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.5.1-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.5.1).
Verify against `SHA256SUMS-skill-v3.3.1.txt`（覆盖两个 zip）。
