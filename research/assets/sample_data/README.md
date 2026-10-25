# 示例数据（合成；仅用于演示字段）

> ⚠️ 这里的数据是**编造的占位值**，只演示「候选清单长什么样」。
> **不要**把它当检索证据、不要复制进真实工作区、不要据其下任何结论——它没有 `raw/` 支持，
> 真实流程里只能算 `asserted`。

| 文件 | 用途 |
|---|---|
| `candidates_example.json` | 一条合成候选，演示 `03_candidates/` 的字段与证据等级记法 |
| `search_log_example.json` | 一条合成检索日志，演示 `raw/` 引用与 `capture_mode` 字段 |

用法：对照 [references/01-检索框架](../references/01-search-framework.md) 的采集纪律
与字段约定，理解「日志 → raw/ → 候选 → 门禁」的链路——不是抄内容。
真实工作区里，候选由 `patentkit ingest` 从 `raw/` 原始响应生成，从不手写。
