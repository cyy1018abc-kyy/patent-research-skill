# 09 · 召回增强（patent_intel 扩展，可选）

> **边界先行**：本参考文档描述的能力来自可选扩展 `patent_intel`（4.0 新增）。
> 扩展只产生**查询提案与离线诊断**；证据等级、G-S 门禁、`query_library.yml` 的
> 人工审批流程仍由内核 `patentkit` 与你本人决定。扩展未安装时，research 主流程
> 一切照旧——本文的全部内容都可以跳过。

## 它做什么

| 能力 | 命令 | 性质 |
|---|---|---|
| 技术轴 → 查询族提案（单特征/宽召回/特征交叉/跨领域迁移） | `python research/scripts/recall.py plan --axis N1` | 提案，需人工批准 |
| 离线召回诊断（BM25 覆盖 + 增量收益 + 未覆盖子域） | `python research/scripts/recall.py report` | 只读工作区，报告写 sidecar |
| 环境自检 | `python -m patent_intel doctor --root <ws>` | 只读 |

## 什么时候用它

1. **开新轴前**：`plan` 看查询族草案，把有价值的查询抄进 `query_library.yml`
   走既有审批（扩展自己不改库）。
2. **检索中期**：`report` 看哪些轴零命中、哪条查询带来了独立新增族——增量收益
   低的查询方向不值得再烧配额。
3. **复核扩词**：每条扩词都带 `relation`（synonym/hypernym/translation…）与
   来源特征；**上下位词与译文只是检索网，不等价于法律特征**——判断披露与否仍以
   原始特征表述对照文献原文。

## 什么时候不用

- 已有 3 条 CNIPA 子查询用满且覆盖判断完成 → 扩展帮不上 G-S 门禁；
- 需要 `verified` 证据 → 唯一路径是内核 `fetch-*`/`ingest` 契约，扩展没有旁路；
- 报告说某轴零命中 → 只说明**这个候选语料**没命中，**不是**查无现有技术的证明。

## 停止条件（诚实声明）

自适应检索在「预算耗尽 / 连续零新增 / 人工终止」时停止——**停止 ≠ 查全**。
报告的 caveat 字段会原样提醒；写结论时不要引用扩展输出来论证「没有更接近的文献」。

## 4.2 新能力（W3/W4 接线，advisory 不变）

| 能力 | 命令 | 性质 |
|---|---|---|
| 每查询贡献账本（新族/边际收益/重复查询） | `python -m patent_intel contribution report --report <完整 controller dump>` | 只读派生；汇总计数版报告会被诚实拒绝 |
| 一等批处理入口（冻结语料 + 主题清单 → 结果文件） | `python -m patent_intel bench run --corpus-dir … --topics … --side baseline\|extension --out-dir …` | `--approve` 为显式审批旗标，缺省不批准=零行 |
| 数据源五态诊断（ready/blocked/skip/planned/unknown） | `python -m patent_intel doctor sources [--only ID …]` | 默认离线零联网；`blocked>0` 退出码 1 |
| 时间建议视图（公开日/优先权日结构化） | `recall report --dates-file <json> --target-filing-date YYYY-MM-DD` | 建议性输出，**永不改变召回与排序**；日期冲突/缺失显式标注 |

边界不变：贡献账本是**候选级**核算（候选≠相关）；`planned` 源=许可未核实、
不可执行；时间建议不构成相关性或现有技术结论；批处理产物遵守与交互运行
相同的诚实记账（逐请求含零增益）。
