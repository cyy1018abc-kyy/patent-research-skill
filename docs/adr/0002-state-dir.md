# ADR 0002 — sidecar 状态目录：扩展状态的唯一居所

- 状态：**已接受**（2026-10-28，WP-0 冻结）
- 背景：蓝图 §2「状态存储」、F-05 验收「增强缓存删除后，原工作区校验结果不变」。

## 背景

增强层需要保存查询草案、运行状态、归一化索引、证据投影与报告。若散落进内核
工作区目录，会出现三类问题：内核 `validate`/打包器扫描到陌生文件；「缓存」与
「内核事实」边界模糊；用户无法一键卸载扩展。

## 决策

1. **唯一写入区**：`<workspace>/.patent-intel/`（可用 `--state-dir` 或环境变量
   `PATENT_INTEL_STATE_DIR` 移出工作区）。内核工作区其他一切路径对扩展只读
   （ADR 0001）。
2. **目录布局固定**：`features/ queries/ runs/ index/ anchors/ evidence/
   advisory/ reports/ audit/ tmp/` + `manifest.json` + `config.json`。
   `manifest.json` 绑定所属工作区绝对路径——sidecar 被错配到别的工作区时立即
   报错，而不是悄悄混用两份事实。
3. **一切皆可重建**：除用户手写的 `config.json` 与人工审批记录外，所有内容都
   必须能从「内核工作区 + 原始工件 + 记录的输入参数」重新推导。删除 sidecar
   等价于完全卸载扩展痕迹。
4. **初版存储格式**：逐记录 JSON 文件（`write_json_atomic` 原子写、UTF-8、LF）。
   索引规模变大后允许引入 SQLite，但库文件同样只放在 sidecar 内，且必须可由
   JSON 视图重建。
5. **不修改内核文件**：`workspace.yml`、`glossary.yml`、候选、日志、结论一概
   不碰；与内核的耦合只有「读」与「白名单子进程调用」。

## 验收（已入测试）

- `test_config.py::test_layout_refuses_foreign_workspace` — 错配工作区立即拒绝。
- `test_workspace.py::test_sidecar_removal_leaves_kernel_validation_unchanged` —
  删除 sidecar 前后内核 `check --json` 输出逐字节一致（IT-04 的单测形态）。
- safe_io 的原子写/路径禁越界/大小上限测试保证 sidecar 自身不会被半写或越权。

## 后果

- 正面：卸载=删目录；内核打包与校验零感知；多工作区互不污染。
- 代价：查询库入库仍需人工经内核流程（无自动写 `query_library.yml` 的捷径）；
  报告默认不出现在内核工作区，需要时由用户显式导出。
