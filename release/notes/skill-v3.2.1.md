# Patent Research Skill 3.2.1（端到端金样回归）

Requires **patentkit 0.4.1, assessment protocol 1**（不变）, Python 3.11+.

## 什么变了（纯测试基建，无内核规则/命令变更）

- **端到端金样回归**（内核 0.4.1 新增 `regression_tests/golden/`）：固定合成工作区
  跑完整管线——ingest → 评估（AI）→ 人工确认（评估后重取指纹）→ validate →
  gates → 账本 → 查询规划 → 报告 → docx 导出 → map/chain HTML → 改稿一轮 ——
  每阶段输出与 `expected/` 快照逐字节比对；另有连跑两遍的确定性自检。
  易变值（生成时间戳、当天日期、工作区路径）在比较前 redact；夹具固定日期是
  被断言的数据，不 redact。期望快照用 `GOLDEN_UPDATE=1` 重生成，须人工逐行审查。
- 技能侧无功能变更（版本配对升级）。

## 升级

安装本包覆盖旧目录即可（`--force`）；内核同步升到 0.4.1（仅测试资产差异，规则与
0.4.0 完全一致）；工作区无需迁移。

## Download and install

Download `patent-research-skill-v3.2.1.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.4.1-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.4.1).
Verify against `SHA256SUMS-skill-v3.2.1.txt`（覆盖两个 zip）。
