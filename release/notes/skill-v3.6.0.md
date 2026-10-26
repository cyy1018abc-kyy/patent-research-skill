# Patent Research Skill 3.6.0（发布体检自动化 + 合成案例行为基准）

Requires **patentkit 0.7.0, assessment protocol 1**, Python 3.11+.

内核与本轮**无改动**（0.7.0 不变；无新规则、无协议变化）。本版是纯发布工程 + 评测基建轮：

## 什么变了

- **release-doctor（`tools/release_doctor.py`）**：发布链路一键体检。
  - `--offline`（已入 CI check job）：版本配对点（复用 bump --check）、evals/术语/保密/链接
    四守卫、双 zip 构建 + manifest 深检（schema/skills/compat/逐文件哈希）+ SUMS 名单核对
    + 与发布脚本资产名单比对、按平台可用的安装器实测（ps1 / bash / one-click；one-click
    在一次性 venv 中装内核 wheel，不污染运行环境）。
  - `--release`（已入 CI 独立 job，publish 之后跑，双平台矩阵）：审计 GitHub **实际发布**——
    tag 存在性 / draft / latest / target_commitish、资产名单、逐资产 sha256 对 SUMS、
    发布 zip 的 manifest 深检、notes 同源性，并用**下载到的真实资产**重跑各平台安装测试
    与内核 wheel 隔离导入。全部走 api.github.com（github.com 直连被阻的环境也可用）。
  - 内核未升版的轮次不重发 kernel tag：release-state 对 kernel 的 target_commitish 差异
    降级为说明（配对由 manifest.compat 把关），skill tag 仍严格核对。
- **合成专利案例行为基准（`benchmarks/`）**：公开的编造语料基准，衡量技能判断行为的三个指标——
  **证据引用准确性**（precision + coverage，逐字核验直接复用内核 `assessment.passage`）、
  **技术特征遗漏**（真值披露 × feature_mapping）、**误判率**（role / novelty_check /
  relevance 两维 / 逐特征状态 / 对比矩阵格 / 结论必引，共 40+ 判断点/案例）。
  - 三个案例（无线传感网时间同步 / 电池组被动均衡 / 仓储多 AGV 调度），各自带陷阱设计
    （近邻段落误引、弱措辞披露、blocking 诱惑、关键词撞车排除项）；
  - 案例目录含 `workspace/`（参赛脚手架：日志/raw/候选就绪，判断字段 untouched）与
    `gold/`（参考解：评估→确认→attest→矩阵→结论，全走真实内核命令，0 error / 0 warn）；
  - `tools/score_benchmark.py`：评分器不重实现任何 V 规则——先跑内核 validate（0 error 才评），
    再做「工作区产物 ↔ 真值」比对；`--suite --gold --gate perfect` 已入 CI 锁定评分语义；
  - `tests/test_benchmark_scorer.py`：对 gold 的受控破坏断言「指标必须退化或被内核当场拦下」
    （V029 伪造引文拦截路径在内），防评分器变橡皮图章；
  - 全部公开号使用不存在的 `ZZ` 前缀国家码，保密守卫已将 `benchmarks/` 前缀放行
    （放行理由＝合成语料，真实数据仍然禁止）。

## 升级

- 已安装用户：重新覆盖安装技能包即可（`--force`）；内核与工作区数据零变化。
- 基准参赛方法见仓库 `benchmarks/README.md`。
