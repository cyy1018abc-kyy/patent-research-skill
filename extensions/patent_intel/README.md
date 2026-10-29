# patent_intel — 专利研究技能 4.0 可选扩展

`patent_intel` 是 patent-research-skill 4.0 的**独立可选组件**：检索策略与查全率诊断、
多来源受控采集、专利文档解析、证据投影与权项修改建议。它不替代内核
[`patentkit`](https://github.com/cyy1018abc-kyy/patent-research-skill)——证据等级、
G-S 门禁、判断与签核仍然只由内核规则和人工确认决定；本扩展只产生**可回溯的
proposal / 只读分析**，绝不写内核候选、绝不自动确认。

## 安装

```bash
pip install extensions/patent_intel            # 最小安装：仅标准库
pip install "patent_intel[kernel]"             # + 读取 patentkit 工作区
pip install "patent_intel[kernel,pdf,dense,ops]"  # 全量可选能力
```

## 快速开始

```bash
python -m patent_intel doctor --root <workspace>       # 环境/工作区/扩展能力自检（只读）
python -m patent_intel query plan --root <ws> --axis N1 --json   # 查询族草案（proposal）
python -m patent_intel recall report --root <ws> --json          # 覆盖与收益报告
```

## 边界（与内核的关系）

| 能力 | 归属 |
|---|---|
| 证据等级（asserted/attested/verified）、G-S 门禁、V 系列校验 | `patentkit` 内核 |
| 查询库人工审批、`ingest`、`validate`、`draft`/`revise` 签核 | `patentkit` 内核 |
| 查询扩展、排序诊断、覆盖缺口统计、文档解析、证据投影 | `patent_intel`（本包） |

数据存放：本扩展所有状态写入独立 sidecar `<workspace>/.patent-intel/`（可用
`--state-dir` / `PATENT_INTEL_STATE_DIR` 显式指定），内核工作区文件零修改；
删除 sidecar 即完全卸载本扩展的痕迹，内核校验结果不变。

## 状态

v0.1.0：WP-0 架构与兼容层（contracts / safe_io / kernel_bridge / CLI doctor）。
检索、采集、解析、证据、态势各域随 4.0 各工作包逐步交付；未交付的命令不存在于
`--help`，不提供占位实现。
