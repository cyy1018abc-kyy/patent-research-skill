# Retrieval Benchmark（4.0 新增，与原九案例基准分开）

本目录存放**检索查全率基准**（blueprint §12），与 `benchmarks/cases/` 的九个
合成判断链案例互不替代：那边评「证据链与判断流程」，这边评「检索算法与流程的
查全/排序/成本」。协议全文见 `docs/retrieval-evaluation.md`。

## 目录

```text
benchmarks/retrieval/
├── README.md              # 本文件
├── manifest.schema.json   # 套件清单 schema（topics / gold / split / 许可注记）
└── fixtures/              # 合成冒烟套件（无真实专利文本，CI 用）
```

## 套件清单（manifest.json）

每个评测套件一个目录，内含 `manifest.json`，字段受 `manifest.schema.json` 约束：

- `suite` / `version` / `qrels_version`：套件标识与 gold 版本（改 gold 必须升版本）；
- `gold_completeness`: `complete | pool_biased | unknown`——CLEF-IP 式引证代理
  标签必须如实标 `pool_biased`，评分器会给 Critical Recall 自动附 caveat；
- `families`：出版物号 → 家族 ID 映射（允许 run 文件引用出版物号）；
- `topics[]`：每主题 `topic_id (TP-NNNN)`、`split`、语言/领域标签、
  `gold_families`、可选 `critical_families` 与 `relevance_levels`；
  **空 gold 必须显式 `gold_known_incomplete: true`**，且这类主题被排除出
  Recall 分母、单独报告——绝不默认满分。

## 运行文件（runs/*.jsonl）

每行一个命中：`{"topic_id":"TP-0001","family_id":"FAM-1","rank":1,"score":12.5}`
（或 `"publication_number":"EP..."` 由 manifest 映射到家族；同家族多成员自动
坍缩取最优排名，家族绝不重复计数）。

## 评分

```bash
python tools/score_retrieval.py --suite benchmarks/retrieval/fixtures/smoke \
    --runs <run-dir> --json
```

依赖扩展包（指标实现在 `patent_intel.retrieval.metrics`）：
`pip install -e extensions/patent_intel --no-deps`。CI 的测试 job 会先安装。

约束：未知 topic、重复 (topic, rank)、非法 rank、全空 gold → exit 1（审计失败，
不是 0 分）；bootstrap CI 按主题重采样、固定种子、主题数 < 2 时输出退化标记。
