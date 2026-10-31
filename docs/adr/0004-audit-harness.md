# ADR 0004 — 审计骨架：audit 技能引入覆盖率台账与对抗验证

- 状态：**已接受**（2026-11-01，skill 4.0.0 立项）
- 背景：v4.0 路线（「audit 能力改造路线」）；方法论改编自 Cloudflare
  `security-audit-skill`（MIT，Copyright (c) 2025-2026 Cloudflare, Inc.）及其博客
  《Build your own vulnerability harness》。风险登记表把「单 agent 自评虚高、
  引文漂移不可追溯」列为核心质量风险。
- 决策人：仓库维护者（Jackey yang / cyy1018abc-kyy）。

## 背景

`research` 技能产出的检索证据链（02_search_logs → 03_candidates →
04_comparative_analysis → 05_novelty_conclusions）由同一条会话链自评，
缺两类保障：① 覆盖率只有叙事陈述（「各轴都查过了」），没有逐格台账；
② 「要素↔对比文件」映射的提出者与复核者不分离，逐字引文无独立核对。
Cloudflare 的六阶段审计骨架（覆盖率台账 → 覆盖狩猎 → 对抗验证 → 结构化输出 →
独立复核 → 中立报告）恰好补这两类缺口，且其结论三态与双模式纪律与本仓库
「proposed/confirmed 分离、未验证必标注」的传统同构。

## 决策

1. **新增第四个技能载荷 `audit/`（`patent-audit`）**，与 research/drafting/discovery
   并列，随 manifest schema 2 分发；版本走 skill 4.0.0，进四技能统一配对。
2. **六阶段全部落在既有契约上**：台账单元 = 要素×数据源×分类号（`audit-ledger.json`，
   状态机沿用原件 planned/…/covered/candidate 等）；映射结论 = `findings.json`
   三态（confirmed/needs_validation/rejected，fingerprint 稳定）；要素分解 =
   `claims-map.md`（对齐原件 architecture.md 的 ≤1000 字上限）；运行产物只写
   `12_audit/run-<N>/`。
3. **确定性校验用 Python 移植，不引入 Node**：`audit/scripts/validate_findings.py`
   与 `validate_ledger.py` 为零依赖标准库脚本（借 MIT 原件逻辑，文件头注明
   derived from），走仓库 contracts/validate 风格（problems 列表、`--json`、
   退出码 0/1/2）。确认态四要素硬门：逐字引文 + 段落定位 + 独立复核标记 + 影响类目。
4. **双模式**：guidance 默认（不写审计工件），full audit 必须用户显式授权；
   语义两可先问一句再动手。
5. **默认单 agent 顺序模式**（对原件多 agent 并行的务实修正）：角色隔离用
   「独立复核轮次 + 提示词状态重置」实现；`--multi-agent` 显式开启才并行派发。
6. **不移植攻击面内容**：原件 12 个 ATTACK 类目文件不适用专利域，只借编排骨架
   （台账、状态机、三态、报告结构、反模式清单）。
7. **优先级与确定性分离**：破坏性（X/Y/A 影响类目，仅 confirmed）与证据确定性
   （confidence 低/中/高）两轴分开评、不得互折；影响类目不得高于已证实披露程度
   （X 要求全要素链声明）。
8. **审计基线可回归**：`tools/score_audit_findings.py` 用 bm01/bm02 的 gold 真值
   对 `findings.json` 评分（映射覆盖/映射精度/证据完整性/判定纪律），CI 以
   gold 自检锁分——这是 Cloudflare 原件没有的护城河。

## 机器校验

- `audit/scripts/validate_findings.py` / `validate_ledger.py`：阶段 A4/A5 后强制
  运行；`tests/test_audit_validate_findings.py`、`tests/test_audit_validate_ledger.py`
  锁行为。
- `tests/test_audit_benchmark.py`：gold 自检 + 退化夹具（改定位/改判级/缺引文）
  必须失分，防橡皮图章。
- `tools/check_reference_links.py`（按 SKILL.md 自动发现 `audit/`）、
  `tools/check_no_workspace_data.py`（显式加入 `audit/`）、
  `tools/check_explicit_encoding.py`（`audit/scripts` 入扫描根）随 CI 全量跑。

## 后果

- 正面：检索证据链有了可机检的覆盖主张与独立复核链；`12_audit/` 产物可整体删除，
  不污染被审计工作区；三态 + fingerprint 让多次审计可叠加（改源重验、未验不 suppression）。
- 代价：full audit 的 token 成本显著高于单轮检索复核（台账逐格 + 逐条对抗验证 +
  逐条独立复核）；缓解是 profile 分级与默认单 agent 顺序模式。
- 未来重议条件：与内核 `patent_intel` 扩展的 CoverageState/RetrievalGapReport
  契约合并（自适应检索线落地后）；多 agent 并行在真实运行数据支持成本收益时再开。
