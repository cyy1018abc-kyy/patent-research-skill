# Patent Research Skill 4.0.0（audit 技能：检索证据链审计；kernel 0.10.0 延续）

Requires **patentkit 0.10.0, assessment protocol 1**, Python 3.11+。内核本轮**无变化**
（0.10.0 延续，无需重装内核）。扩展 `patent_intel` 0.1.0 延续（未变，无需重装）。

## 什么变了

- **新增第四个技能载荷 `audit/`（`patent-audit`）**——检索证据链的结构化审计，
  方法论改编自 Cloudflare `security-audit-skill`（MIT，见 README Credits；
  攻击面内容未移植，编排骨架按专利检索域重写）：
  - **六阶段**：claims-map 要素分解 + `audit-ledger.json` 覆盖率台账
    （要素×数据源×分类号 状态机）→ 覆盖率狩猎 + 批评家找盲区 → 对抗验证
    （verifier 证伪优先）→ `findings.json` 三态结论 → 独立复核（逐字引文+定位）
    → 中立报告（REPORT / NEEDS-VALIDATION）；产物只写 `12_audit/run-<N>/`。
  - **双模式**：guidance 默认（不写审计工件），full audit 须用户显式授权；
    **默认单 agent 顺序模式**（角色隔离用独立复核轮次实现），`--multi-agent`
    显式开启才并行派发。
  - **两轴分离**：破坏性（X/Y/A 影响类目，仅 confirmed，partial 禁 X）与证据
    确定性（low/medium/high）分开评分，不得互折。
- **确定性校验层（零第三方依赖）**：`audit/scripts/validate_findings.py`
  （confirmed 必带逐字引文+段落定位+独立复核标记；needs_validation 必带缺失
  事实+核验计划且**无**影响类目；rejected 必带证伪理由）与
  `validate_ledger.py`（台账状态机、coverage_id 确定性派生、attempts 归档）。
  文件头注明 derived from Cloudflare security-audit-skill (MIT)。
- **审计基准回归（bm01/bm02）**：`tools/score_audit_findings.py` 以 gold 真值对
  findings.json 评分（映射覆盖/映射精度/证据完整性/判定纪律），CI 锁 gold
  自检满分；退化夹具（定位漂移/误确认缺失要素/漏报/缺独立复核）全部失分。
- **接线**：四技能统一配对（SKILL_DIRS、manifest schema 2、双安装器、bump 配对
  点、evals 45 用例 AU1–AU5、保密/编码/链接三守卫、CI gold 自检 + compileall）。

## 安装与迁移

安装器清单、manifest schema 2、双 zip 结构不变（全量包现含四个技能）。已有用户：
内容更新，重装技能包即可；内核与扩展均无需重装。规则表 V001–V038 不变，评估
协议 1 不变。

## 边界（与上一版一致）

- 本技能产出底稿与判定辅助，不构成法律意见；不预测授权；审计报告不是法律意见；
- 期限工具是提醒台账，法定期限以官方发文/通知书为准；
- CNIPA XML 官方格式仍未实现（`official_format_status` 维持 `not_attempted`）。
