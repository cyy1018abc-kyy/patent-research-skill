# 03 · 人工确认与检索交接

> 本文件定义 A4 阶段：事实/候选的**人工确认**、确认失效规则，以及向 `patent-research`
> 的**交接草案**。核心原则：AI 只提议，确认由发明人做；交接是草案，不是检索结论。

## 1. 事实人工确认（G-I 前提）

必要技术特征所依赖的事实必须是 `human_review = confirmed`，否则交接阻塞。

```powershell
# 预览（dry-run）
python -m patentkit discovery facts review --ids FACT-001,FACT-002 --decision confirmed --by inventor --root .\workspace

# 写入（审计事件 fact_review 追加到不可变账本）
python -m patentkit discovery facts review --ids FACT-001,FACT-002 --decision confirmed --by inventor --root .\workspace --apply
python -m patentkit discovery facts review --ids FACT-003 --decision rejected --by inventor --root .\workspace --apply
```

- `--by` 只是**审计标签**，不是自然人身份认证；脚本/命令必须如实记录操作者标签。
- 拒绝的事实保留在库中（不删除），但引用它的候选无法通过交接门控。
- 重复确认同一状态 → 幂等跳过，不重复记账。

## 2. 候选人工确认（内容指纹绑定）

发明人评审 `ideas/IDEA-xxx.json` 后，用决策文档表达确认/驳回/要求修改：

```json
{
  "schema_version": "1.0",
  "decision_id": "DEC-001",
  "idea_id": "IDEA-001",
  "idea_fingerprint": "<当前候选内容指纹；由内核计算核对>",
  "reviewer": "inventor",
  "decision": "confirmed",
  "reason": "方案完整，特征可实施",
  "timestamp": "2026-10-26T10:30:00+08:00",
  "source_snapshot_sha256": "<确认时材料快照哈希>"
}
```

```powershell
python -m patentkit discovery review .\decisions --root .\workspace            # 预览
python -m patentkit discovery review .\decisions --root .\workspace --apply    # 记账 + 更新 review_status
```

### 指纹规则（重要）

- 确认绑定候选的**内容指纹**（结构：规范化 JSON 的 SHA-256，**不含** `review_status` 状态字段）。
- 仅状态变化（proposed→confirmed）不会让确认失效；
  任何技术内容变化（标题、问题、特征、效果、关系、不确定性、评分）都会让确认过期。
- 过期确认**不删除**：账本保留旧决策，`discovery check` 报 G-I-014 warn，交接被阻塞，
  需要发明人对当前内容重新确认（新 `decision_id`）。
- AI 不能自证确认，也不能覆写已有决策；决策文档里的指纹与当前内容不一致 → 内核拒绝记账。

### 决策取值

| decision | 效果 |
|---|---|
| `confirmed` | 候选 `review_status=confirmed`，可进入交接 |
| `rejected` | 候选 `review_status=rejected`，不得交接 |
| `revision_requested` | 候选回到 `proposed`，按意见修改后重新评审 |

## 3. 交接草案（handoff）

前置：`discovery check` 无 error；候选确认有效；每个必要特征有事实引用；引用事实均已 confirmed；
来源登记与哈希全部匹配。任一不满足 → **阻塞并列出全部原因**（不提供 --force）。

```powershell
python -m patentkit discovery check --root .\workspace
python -m patentkit discovery handoff --idea IDEA-001 --root .\workspace          # 预览
python -m patentkit discovery handoff --idea IDEA-001 --root .\workspace --apply  # 写草案
```

产出（均在 `10_discovery/handoff/`，不进入公开发布包）：

| 文件 | 内容 |
|---|---|
| `IDEA-001.handoff.json` | 契约 `discovery_handoff`：目标（existing/new_target_proposal）、必要特征与事实引用、来源、搜索轴、内容指纹、查询种子路径 |
| `IDEA-001.search_seed.md` | 每轴中英文查询种子占位；明确"这不是已执行的检索，G-S 未计算" |
| `IDEA-001.target_draft.md` | 目标/技术轴草案（不修改 `workspace.yml` 与既有目标数据） |

审计：账本追加 `handoff` 事件（handoff_id/idea_id/idea_fingerprint/target_id/target_mode/timestamp）。

## 4. 交接**不**做的事

1. 不写 `01_search_plan/query_library.yml`，不修改 `workspace.yml`、不新增/修改目标与轴线数据；
2. 不产生任何 G-S PASS/FAIL、不评估新颖性/创造性；
3. 不替代 `patent-research` 的 queryplan / fetch / ingest / review / gates 流程；
4. 不在未确认内容上交接（G-I 阻塞）；
5. 不把真实材料写进公开仓库、样例或日志。

## 5. 交接后的检索流程（交给 patent-research）

1. 用 `patentkit queryplan` 对照覆盖情况，补全未覆盖概念组（查询种子只是起点）；
2. 通过 `fetch-*` / `ingest` 采集入库，`review` 做 AI 评估 + 人工确认；
3. `patentkit validate` / `gates` 给出正式结论——**只有 research 侧的 G-S 与证据等级才是验收依据**；
4. 撰写阶段由 `patent-drafting` 接手，前提是 research 门禁已就绪。

## 6. 审计账本事件

| 事件 | 触发 | 关键字段 |
|---|---|---|
| `fact_review` | `discovery facts review --apply` | fact_id / decision / reviewer / timestamp |
| `decision`（idea_decision） | `discovery review --apply` | decision_id / idea_id / idea_fingerprint / decision / reviewer / timestamp |
| `content_changed` | `ideas import --force` 且内容变化 | idea_id / old_fingerprint / new_fingerprint / timestamp |
| `handoff` | `discovery handoff --apply` | handoff_id / idea_id / idea_fingerprint / target_id / target_mode / timestamp |

账本只追加不修改：任何"改历史"的做法都不被接受。
