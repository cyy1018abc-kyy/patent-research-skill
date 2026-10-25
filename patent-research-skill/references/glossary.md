# 术语对照表（中 ⇄ 英）

> 单一权威：本表管理技能包与 references.en/ 之间的术语一致性；
> `evals/check_terminology.py` 在 CI 里逐对核对。改术语先改这里，再同步两版文档。

## 流程与角色

| 中文 | English | 说明 |
|---|---|---|
| 专利调研 / 查新 | patent research / novelty search | 本技能主场景 |
| 现有技术 | prior art | |
| 近端对比文件（D 列） | near prior art (column D) | role=near_prior_art |
| 普通池内候选 | pool candidate | role=pool |
| 排除 | excluded | 错映射/误命中/重复/跨目标 |
| 同族 | family | |
| 验收门 | acceptance gate (G-S) | G-S-01…05 |
| 证据链 | evidence chain | |
| 证据等级 | evidence level | verified/attested/asserted |
| 来源可追溯性 | source provenance | 与判断（judgment）独立 |
| 判断 / 判定 | assessment / judgment | |
| 人工确认 | human confirmation | 绑定判断指纹 |
| 指纹 | fingerprint | 实质内容哈希 |
| 评估协议 | assessment protocol | 当前版本 1 |
| 证据账本 | evidence ledger | `patentkit ledger` |
| 检索日志 | search log | 02_search_logs |
| 原始工件 | raw artifact | raw/ 目录 |
| 采集模式 | capture mode | live / retrospective |
| 缓冲 | buffer | G-S-02 阈值之上的余量 |
| 补检索 | supplementary search | |
| 交底书 | (patent) disclosure | 发明/实用/外观 |
| 申请文件 | application documents | 五书：请求书/说明书/权利要求书/摘要/附图 |
| 权利要求 | claim | 独权 independent / 从权 dependent |
| 说明书 | specification / description | |
| 实施例 | embodiment | |
| 有益效果 | beneficial effect | |
| 三层判定 | three-tier determination | 单篇新颖性/组合创造性/技术效果 |
| 零披露原子 | zero-disclosure atom | 任何组合拼不出的特征 |
| 审查意见（OA） | office action | |
| 答复底稿 | response draft | |
| 附图标记 | reference sign / figure mark | 10、20、31… |
| 数值声明溯源 | numerical-claim provenance | A/B/C 三级 |
| 自产材料 | in-house material | A 级 |
| 文献/对比文件 | retrieved document | B 级 |
| 实施例示例 | illustrative example | C 级，须显式声明 |
| 政策雷达 | policy radar | 口径变化追踪 |
| 改稿闭环 | revision loop | 补丁→日志→重过门 |
| 期限台账 | deadline ledger | `patentkit deadlines` |
| 1+N 布局 | 1+N portfolio layout | `patentkit layout` |
| 检索式 | query | 主式+子查询 |
| 子查询 | sub-query | cnipa_batches |
| 轴 | axis | N1…N6，限定式 N1@TGT-0002 |
| 目标 | target | TGT-xxxx |
| 工作区 | workspace | workspace.yml 所在目录 |
| 未经验证工具校验 | Unverified by tool checks | ⚠️ 前缀，硬约束 |

## 工具与交付

| 中文 | English |
|---|---|
| 查新报告（docx） | novelty-search report (export-docx) |
| 对比矩阵 | comparison matrix |
| 对比地图（HTML 总览） | patent map (offline HTML overview) |
| 修订台账 | revision ledger |
| 支持映射表 | support mapping table |
| 门禁三列 | three gate columns（verified / ≥attested / ≥asserted） |
| 干跑 | dry-run |
| 落盘 | persist / write to disk |
| 失败关闭 | fail-closed |
| 漂移 | drift（sha256 漂移） |
