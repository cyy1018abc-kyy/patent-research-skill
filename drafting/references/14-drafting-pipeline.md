# 14 · 结构化撰写管线（P2）

> 本文件定义「plan → 权项原子 → 权项 → 支持映射 → 双状态门」的结构化流程。
> 内核负责结构与审计，AI/发明人负责正文与确认；`patentkit draft` 是唯一入口。
> 本管线**不产生**任何交付件（DOCX/PDF 属 P4）；也不改变检索侧 G-S 语义。

## 1. 工作区文件（`07_drafting/`）

| 文件 | 内容 | 写入 |
|---|---|---|
| `drafting_plan.yml` | 契约 `drafting_plan`：目标、候选、保护主题、必要特征、图纸需求、open_questions、研究快照、候选内容指纹 | `draft plan --apply` |
| `claim_atoms.json` | `claim_atom` 列表（权项原子，逐条带事实引用） | `draft atoms import --apply` |
| `atom_review.json` | 原子人工确认记录（**绑定原子内容指纹**） | `draft atoms review --apply` |
| `claims_structured.json` | `claim` 列表（编号/类型/引用项/原子集合） | `draft claims import --apply` |
| `support_mapping.json` | `support_mapping`：claim/atom → 段落/事实/附图 | `draft support import --apply` |
| `support_review.json` | 支持映射的人工语义复核状态 | `draft support review --apply` |
| `drafting_state.json` | 双状态写作门（`concept` / `review_draft`）+ 模型包裹指纹 | `draft gate --apply` |
| `drafting_audit.jsonl` | 追加式审计（plan/atom/claim/support/state 事件） | 各命令自动 |

原有 `manuscript_registry.yml` / `revision_ledger.yml` / `numerical_provenance.yml` 保持不变；
稿件正文仍在库外或工作区受控目录，**仓库只留结构化模型**。

## 2. 命令

```powershell
# 1) 从人工确认的候选生成撰写计划（要求事实已确认、候选指纹当前）
python -m patentkit draft plan --idea IDEA-001 --target TGT-0002 --apply

# 2) 权项原子：导入 → 人工确认（确认绑定内容指纹）
python -m patentkit draft atoms import .\atoms --apply
python -m patentkit draft atoms review --ids ATOM-001,ATOM-002 --decision confirmed --by inventor --apply

# 3) 结构化权项（编号/引用顺序/循环/原子存在性由内核校验）
python -m patentkit draft claims import .\claims --apply

# 4) 支持映射（claim/atom → 说明书段落/事实/附图）+ 人工语义复核
python -m patentkit draft support import .\support --apply
python -m patentkit draft support review --claim-no 1 --atom-id ATOM-001 --decision confirmed --by inventor --apply

# 5) G-D 审计 + 状态 + 双状态门
python -m patentkit draft audit --root .\workspace
python -m patentkit draft status --root .\workspace
python -m patentkit draft gate --to review_draft --by inventor --apply

# 6) 改稿影响传播（改独立权项前先看会影响哪些段落/附图/从权）
python -m patentkit draft impact --claim-no 1
```

## 3. 双状态写作门

| 状态 | 含义 | 进入条件 |
|---|---|---|
| `concept` | 前期技术备忘录；门禁未就绪时的唯一合法状态 | 默认状态；任何模型变更自动回落到此 |
| `review_draft` | 正式申请底稿（可交代理师复核） | 审计无 error；**G-S-01/02/03 均 PASS**；原子全部人工确认且指纹当前；权项结构合法；每个权项原子都有段落支持且支持映射已人工复核；计划所绑候选指纹当前 |

- 状态记录 `bundle_fingerprint`：计划/原子/权项/支持映射任何实质变化都会让状态**自动失效**
  （`draft status` 显示 stale，回到 `concept`）——改稿后必须重新过门。
- **未实现 `release_ready`**：完整交付门（DOCX/PDF/manifest）在 P4；在此之前不得宣称可交付。

## 4. G-D 审计码（`draft audit`）

| 代码 | 级别 | 含义 |
|---|---|---|
| D-001 | error/warn | 无计划（warn）；计划 schema 违规（error） |
| D-002 | error | 计划引用的候选不存在或未人工确认 |
| D-003 | error | 计划过期（候选内容指纹已变） |
| D-004/D-005 | error | 原子 schema 违规 / 引用未知事实 |
| D-006 | warn | 原子引用的事实尚未人工确认 |
| D-007 | warn | 原子未人工确认（或确认记录缺失/过期） |
| D-008 | warn | 原子文本含数值声明，需 provenance 登记 |
| D-009 | error | 必要技术特征的事实未被任何权项原子覆盖 |
| D-010 | error | 权项 schema 违规 / 编号不连续 / 引用父项非法 / 原子未知 / 无独立权项 |
| D-011 | warn | 权项原子缺段落支持映射 |
| D-012 | warn | 支持映射尚未人工复核 |
| D-013 | error | 权项引用未知原子 |
| D-014 | warn | 计划仍有 open_questions（会阻止正式交付） |
| D-015 | error/warn | provenance 登记问题（复用既有检查，不重复实现） |
| D-016 | error/warn | 修订账本问题（复用既有 `revise` 检查） |
| D-017 | error | 原子自称 confirmed 但指纹绑定的人工确认记录缺失/过期 |

## 5. 与既有机制的关系

- **provenance**：原子文本的数值声明由既有 `provenance` 扫描/登记；审计直接调用既有检查。
- **attest / revise**：稿件哈希绑定与改稿闭环沿用既有命令；本管线只提供结构化模型与影响传播，
  不另造一套修订账本。
- **discovery**：计划只接受**人工确认**的候选；候选内容变化会让计划过期（D-003）。
- **research G-S**：`review_draft` 门禁直接读取 `gates` 计算结果，本管线不重算、不放宽。
