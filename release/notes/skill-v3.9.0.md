# Patent Research Skill 3.9.0（可选扩展 patent_intel 0.1.0 发行 + 跨平台 CI 修复）

Requires **patentkit 0.9.0, assessment protocol 1**, Python 3.11+。内核本轮无变化
（0.9.0 延续，无需重装内核）。

## 什么变了

- **可选扩展 `patent_intel` 0.1.0 随库发行**（4.0 蓝图 WP-0..WP-F/O/IT 全工程层，
  PR #15）。独立版本 **0.1.0，不进 skill↔kernel 配对**。能力：查询规划与受控扩词
  （全部 proposal、可人工逐项拒绝）、本地 BM25/覆盖诊断、多来源采集治理
  （hits/fetched 严格分离、断点恢复、审计账本）、文档结构解析与哈希绑定定位、
  证据投影/覆盖矩阵/影响预览/claim chart 草稿（仅 proposal，强制复走内核门禁）、
  可选态势统计。检索评测基建：`benchmarks/retrieval`（schema + smoke 夹具）、
  `tools/score_retrieval.py`（Family Recall@K/nDCG/MRR/审计门）、
  `tools/report_benchmark_stats.py`（README/CHANGELOG 统计单源）。
  **内核边界**：只读动词白名单 + ACQUISITION_VERBS 分离，扩展永远无权写候选/
  等级/结论；不装扩展时三个 Skill 原工作流完全不变（IT-04 回归锁定）。
- **扩展发行（方案 A）**：skill release 附加 `patent_intel-0.1.0-py3-none-any.whl`
  与**独立** `SHA256SUMS-patent-intel-v0.1.0.txt`；原 manifest schema 2、双 zip、
  安装器全部不动（扩展不随安装器自动安装）。安装：从 Release 资产手动
  `pip install patent_intel-0.1.0-py3-none-any.whl`（见 release/INSTALL.md 扩展节）。
  `release_doctor --release` 新增两道扩展核验：**多 SUMS** 哈希审计（一份 release
  可带多份 SUMS，各自覆盖自己的资产）与扩展 wheel **隔离导入**断言。
- **跨平台 CI 修复（Phase L / WP-L1）**：① 新工具 stdout/stderr 统一钉 UTF-8
  （`_pin_utf8_stdio`）——修复 Windows CI 上 em-dash 经 cp1252 管道导致父测试
  UTF-8 读取线程死亡、流为 None 的四矩阵全红；② safe_io 路径包含检查把反斜杠
  按分隔符候选归一化（ADR 0003）——`..\` 形态穿越串在 POSIX 也拒绝，语义双平台
  一致；③ 新守卫 `tools/check_explicit_encoding.py` 入 CI：AST 全扫文件 IO 显式
  `encoding=` 与全部入口脚本 stdio 钉定（本地 PYTHONUTF8/PYTHONIOENCODING 掩盖
  的此类缺陷此后 PR 阶段即拦截）。
- **发布工程**：`evals/evals.json` 的 `skill_version` 是活配对点但此前不在 bump
  工具清单——本轮由残留扫描抓出并补入 `SKILL_PAIRING_FILES`。

## 升级

1. 内核 0.9.0 无变化，已装用户跳过；
2. 覆盖安装技能包（`--force`）即可获得全部 Skill 侧更新（评测意图、recall 增强
   路由、扩展缺失时的安全降级指引）；
3. **可选**：需要检索增强时，从 Release 资产手动安装扩展 wheel
   （`pip install patent_intel-0.1.0-py3-none-any.whl`）；不安装则一切照旧。
