# 合成专利案例行为基准（patent-research benchmark）

> 全部数据为**编造**：技术方案、申请人、公开号（`ZZ` 前缀为不存在的国家码）均为虚构，
> 不含任何真实申请材料。仓库保密守卫（`tools/check_no_workspace_data.py`）已将
> `benchmarks/` 前缀放行——放行理由是"合成语料"，真实工作区数据仍然禁止放入本目录。

## 目的

衡量技能（代理 + patentkit 内核 + 薄封装脚本）在受控合成案例上的**判断行为**，
三个指标对应外部评审 P1-1 的三个关注点：

| 指标 | 回答的问题 | 数据来源 |
|---|---|---|
| 证据引用准确性 | 引用的"原文"真的在所引文档的所引段落里吗？真值要求的支撑引文都引到了吗？ | 引文逐字核验 |
| 技术特征遗漏 | 目标技术特征里，有哪几条在分析中丢了？ | 特征披露真值 × feature_mapping |
| 误判率 | 逐条判断（角色/新颖性状态/相关度/矩阵格/结论必引）与真值差多少？ | 逐判断点比对 |

基准只考**判断链**（评估 → 确认 → 对比矩阵 → 结论），不考检索执行：语料已作为
`raw/` 工件与检索日志预置在工作区，候选已 ingest。G-S-01/G-S-02 的规模门在
合成语料上必然 FAIL（语料只有个位数文献），这是设计使然；评分不读门禁结果。

## 与内核的边界（不立第二套规则）

评分器**不重新实现任何 V 规则**：先跑 `patentkit` 的 `api.validate`（0 error 才评分），
引文核验直接调用内核 `patentkit.assessment.passage()`（`ref#L<n>` 行定位 + quote 逐字
包含——与评估协议同一套语义）。评分器新增的只有一件事：把工作区产物与案例真值做比对。

## 目录结构（每个案例）

```
benchmarks/cases/<case-id>/
  case.yaml            # 元数据 + 参赛任务指令（含 feature_mapping 填写约定）
  corpus/
    target_claims.md   # 目标技术说明与权利要求（特征 F1..Fn 的权威载体）
    prior_art/*.md     # 对比文献全文；[00xx] 段落，**一段必须恰好一行**（L 行号 ↔ 段落号 的映射依赖它）
    hits/*.csv         # 检索命中清单（ingest 的 raw 导出；一篇文献恰好出现在一个 CSV）
  ground_truth.yaml    # 真值：特征/逐候选判定/披露矩阵/期望引文（段落号形态）
  workspace/           # 脚手架 = 参赛起点（glossary/日志/raw/候选就绪，判断字段 untouched）
  gold/                # 参考解：全部判断点与真值一致；CI 用 --gate perfect 锁定评分器
```

`workspace/` 与 `gold/` 由 `benchmarks/build_cases.py` 从 corpus + ground_truth 生成
（金解的评估/确认/attest 走真实内核命令）。生成器同时校验真值里的每条引文都能通过
内核 `passage()`——真值自己先过一遍它给参赛者设的关卡。

## 参赛流程

1. 复制 `workspace/` 到任意目录（推荐，避免把产物写回仓库）。
2. 按技能 `patent-research` 的执行顺序工作：`review export` → 逐候选评估（含
   `feature_mapping`）→ `review assess --apply` → 人工确认 `review confirm --apply`
   → `attest --apply` → 填 `04_comparative_analysis/comparison_matrix.md` → 写
   `05_novelty_conclusions/*.md`。
3. 评分：`python tools/score_benchmark.py --case benchmarks/cases/<case-id> --workspace <目录>`，
   加 `--json` 得机器可读报告。

## 结构化约定（基准定义；内核 schema 对这些字段保持开放）

**feature_mapping**（评估单里的判断字段，逐候选逐特征）：

```json
{
  "F1": {"status": "partial", "ref": "02_search_logs/raw/ZZ900011A1.md",
         "locator": "L6", "quote": "……原文……", "note": "只写到直接写入时刻，无预测修正"},
  "F6": {"status": "absent"}
}
```

* `status ∈ {disclosed, partial, absent}`；`disclosed/partial` 必须带 `ref + locator(L 形) + quote`，
  且逐字通过内核 `passage()`；`absent` 不需要引文。
* 对比矩阵每列输出的**关键段落**行使用 `路径#L行号：原文摘句` 形态（分号分隔多条），
  评分器按同一语义核验。

**对比矩阵**：`04_comparative_analysis/comparison_matrix.md`，沿用技能自带模板；
每列输出首行必须含候选 ID（`D1 — 标题 (P-001)` 形态），评分器靠它把列映射到候选。

## 指标口径

* **citation_precision** = 逐字核验通过的引文 / 全部引文。引文取自三个面：
  候选 `assessment.basis` 的 problem/means、`feature_mapping` 的 quote、对比矩阵每列
  输出的关键段落指针。
* **citation_coverage** = 真值 `expected_citations`（`ref + 段落号`）中已被任一通过核验的
  引文覆盖的比例。
* **feature_omission_rate** = 遗漏特征数 / 真值特征总数。遗漏 = 真值认为某候选以
  `disclosed/partial` 披露了该特征，而工作区没有任何候选把它标成 `disclosed/partial`
  （或标了但引文核验失败）。
* **misjudgment_rate** = 误判点 / 判断点。判断点：每候选的 `role`、`novelty_check`、
  `relevance_problem`、`relevance_means`（精确匹配）；逐（候选 × 特征）披露状态；
  逐（真值轴 × 候选）矩阵格（期望格由披露状态聚合导出：轴内任一 `disclosed`→●，
  否则任一 `partial`→○，否则—）；结论必引 ID。
* 容差：全部精确匹配。案例设计保证判断点区分度（相近档位不会同时可辩）。

## CI 与防"橡皮图章"

* `tools/score_benchmark.py --suite benchmarks/cases --gate perfect` 对所有 gold/
  跑满分门（评分器语义被真值锁定）。
* `tests/test_benchmark_scorer.py` 对 gold 的受控变体（替换引文/抹掉特征/翻转一格）
  断言指标**必须退化**——评分器不是只会打满分的图章。
