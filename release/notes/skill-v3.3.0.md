# Patent Research Skill 3.3.0（数据源半成品预置）

Requires **patentkit 0.5.0, assessment protocol 1**（不变）, Python 3.11+.

## 什么变了（内核 minor：新数据源骨架 + 接入契约固化）

- **`patentkit fetch-bigquery`（G-S-04 专用普查，默认 dry-run）**：普查对象清单
  （near_prior_art / family 且 family 或 cited_by 有缺口的候选）+ SQL 骨架 +
  费用模板，零写入；`--run` 需要 `google-cloud-bigquery` 与 GCP 凭据
  （先 dry-run 查询取 bytes_billed 出费用预估、确认后执行并按契约落 raw+log）；
  `--fill <raw> [--apply]` 从已归档普查工件回填候选 family/cited_by
  （只补空缺、不覆盖人工数据；离线可测）。
- **OPS XML ingest**：`read_raw` 支持 `.xml`（OPS exchange-document 导出；
  namespace 前缀无关、按 localname 匹配；标题/摘要 zh 优先）。OPS 结果 XML 落
  raw/ 后即可 ingest 成 verified 候选。
- **数据源接入契约固化**（docs/data-sources.md）：五条验收标准的工程落点——
  raw 工件先于一切、日志如实声明、可 ingest、dry-run 默认/凭据显式、登记与评测；
  附 OPS 注册与限速策略（配额数字以官方门户当时公告为准，不入库）。
- CNIPA epub 每查询 3 条的上限不变；本release 不接任何真实账号——
  真实检索任务来的当天按契约 `--run` 并登记 policy-log 即可。

## 升级

安装本包覆盖旧目录即可（`--force`）；**内核必须同步升到 0.5.0**（技能封装层会拒绝旧内核）；
工作区无需迁移（新命令均为可选，dry-run 不产生任何数据）。

## Download and install

Download `patent-research-skill-v3.3.0.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.5.0-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.5.0).
Verify against `SHA256SUMS-skill-v3.3.0.txt`（覆盖两个 zip）。
