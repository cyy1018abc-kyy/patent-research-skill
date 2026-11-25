# 22 · 正文骨架（`draft render`，4.3 / M3）

> 结构化模型（计划 → 原子 → 权项 → 支持映射 → 附图规格）已经有了，正文却要从头手敲：
> 编号、引用语、段落号、附图说明在手敲中最容易与模型漂移。`draft render` 直接由模型生成
> **正文骨架**——模型里有的照搬，模型里没有的留成显式空槽 `【待补：…】`。
> 渲染器**从不编造技术内容**；空槽未填，`draft lint` 报 M-016（error），交付门拦截。

## 1. 命令

```powershell
python -m patentkit draft render --root .\workspace            # dry-run：打印三份骨架与空槽计数
python -m patentkit draft render --root .\workspace --apply    # 写入 07_drafting/manuscript/
python -m patentkit draft render --root .\workspace --apply --force   # 覆盖已有稿件（先备份！）
```

- 已有稿件时 `--apply` **拒绝覆盖**（稿件里是人写的正文），必须显式 `--force`；
- 同时写出支持映射**建议** `07_drafting/render/support_suggestion.json`（权项原子 → 段落），
  它只是提案：`draft support import 07_drafting/render/support_suggestion.json --apply` 后仍须
  `draft support review` 人工语义复核（D-012）。

## 2. 生成什么、留什么

| 部分 | 由模型生成 | 留成空槽 `【待补：…】` |
|---|---|---|
| 权利要求书 | 编号、独立/从属结构、引用语「根据权利要求N所述的…」（取自 `parent_claim_no`）、主题名称、特征部分（原子文本原样） | 独立权项前序部分（与最接近现有技术共有的特征）；方法/用途权项与计划主题不对应时的主题名称 |
| 说明书 | 五部分标题（按申请类型用「发明内容 / 实用新型内容」「本发明 / 本实用新型」）、连续段落号、技术方案段（每项权项一段，供支持映射引用）、附图说明（逐图取自附图规格标题）、实施方式里每图的部件与附图标记清单 | 技术领域、背景技术（只写账本内文献）、技术问题、有益效果、各部件形状构造连接关系、实施例 |
| 说明书摘要 | 主题 + 独立权项 1 的特征 | 主要用途与有益效果 |

- **实用新型保护对象是产品**：计划主题像方法（以「方法 / 工艺」结尾）时，权项主题渲染为
  「一种【待补：产品名称…】」，不会把方法主题写进实用新型权项。
- 附图标记：说明书里写成「壳体1」；权项里的标记请在填空时按「壳体(1)」括注（lint M-010 提醒）。

## 3. 推荐流程（D8 之前）

1. 模型就绪（`draft audit` 无 error），附图已规划/导入；
2. `draft render --apply` → 填完所有 `【待补：…】`（AI 起草 + 人工核对；说不清的进 open_questions，**不得编造**）；
3. `draft support import 07_drafting/render/support_suggestion.json --apply` → `draft support review`；
4. `draft lint` 零 error（M-016 清零）→ `draft gate --to review_draft` → `deliver build`。

## 4. 保证与边界

- 骨架填空后（不改结构）`draft lint` 零发现——由内核测试锁定（实用新型与发明两类）；
- 改了模型（原子/权项/附图）后想同步正文：重新 `render` 会覆盖正文，需 `--force` 并自行合并已写内容；
  本版不做增量合并；
- 骨架只是格式与一致性的起点，**不是可提交稿**；技术内容、法律措辞仍由人负责。
