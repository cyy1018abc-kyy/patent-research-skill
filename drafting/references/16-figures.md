# 16 · 专业附图（Figure Plan / Render / Validate）

> 本文件定义 P3 附图引擎：结构化**附图规格**（figure plan）、确定性渲染与图文一致性校验。
> 原则：**排版不决定技术事实**——渲染器只能按规格画，不能新增/删除部件或连线；
> 自动检查只做机械核对，**不能替代人工看图复核**；正式附图不得仅依赖文本生图结果。

## 1. 附图规格（`07_drafting/figures/*.figure.yml`）

```yaml
figure_id: FIG-1
type: block_diagram          # block_diagram | flowchart | connection | state_machine
title: 图1 系统框图
parts:                        # flowchart 用 steps，state_machine 用 states
  - id: S1
    label: 检测单元
    source_refs: [FACT-001]   # 可选：该部件来自哪条事实
  - id: S2
    label: 控制单元
connections:
  - { from: S1, to: S2, label: 负载变化率信号 }
mark_mapping: { S1: "10", S2: "20" }   # 附图标记（1–3 位数字；跨图同号 = 同一部件）
layout_options: { direction: LR, columns: 3 }   # LR|TB；columns 仅多列图有效
spec_refs: ["0005"]          # 说明书引用该图的段落号
```

- 兼容旧格式：`figure:`（=figure_id）、`name:`（=label）、数字 id（标记号）自动归一化。
- **节点 id 稳定**；`mark_mapping` 缺省时按固定顺序自动编号（10/20/30…）。
- 类型要求：`block_diagram`/`connection` 需 `parts`；`flowchart` 需 `steps`；`state_machine` 需 `states`。
- 流程图节点可带 `kind: terminal|decision|process|data`（只影响画法形状）。

## 2. 命令

```powershell
# 1) 从 P2 撰写计划与权项原子生成附图规格（默认 dry-run）
python -m patentkit figures plan --root .\workspace
python -m patentkit figures plan --root .\workspace --apply

# 2) 确定性渲染（SVG 无依赖；PNG 需可选依赖 Pillow，300 DPI）
python -m patentkit figures render FIG-1 --root .\workspace
python -m patentkit figures render FIG-1 --root .\workspace --format png

# 3) 图文一致性校验（F-001…F-014；V033 标记核对复用既有实现）
python -m patentkit figures validate --root .\workspace

# 4) 原有能力不变
python -m patentkit figures check --root .\workspace
python -m patentkit figures draw FIG-1 --root .\workspace
```

## 3. 校验码（`figures validate`）

| 代码 | 级别 | 含义 |
|---|---|---|
| F-001 | error | 规格不是合法 YAML / 契约 schema 违规 |
| F-002 | error | 同一 figure_id 出现在多个文件 |
| F-003 | error | 图内节点 id 重复 |
| F-004 | error | 连线端点不存在（无效边） |
| F-005 | warn | 孤立节点（未参与任何连线） |
| F-006 | error/warn | 标记映射引用未知节点（error）；节点缺标记（warn）；图内重复标记（error）；跨图同号（warn，需人工确认是否同一部件）；标记非 1–3 位数字（error） |
| F-007 | error | 类型所需内容为空（如流程图无 steps） |
| F-008 | error/warn | 说明书引用了不存在的图（error）；图未被说明书引用（warn） |
| F-009 | error/warn | 支持映射引用了未知图号（有图规格时 error；尚无附图时 warn） |
| F-010 | warn | 撰写计划的图纸需求未被任何附图规格覆盖 |
| F-011 | error | 布局参数非法（direction 非 LR/TB、columns 非正整数） |
| F-012 | warn | 重复连线 |
| F-013 | warn | 自环连线 |
| F-014 | warn | `source_refs` 不是 FACT 编号 |
| V033 | warn | 复用既有「图内标记 ↔ 说明书标记」双向核对（启发式，只提醒不自动改） |

## 4. 附图渲染的确定性约定

- 同一规格**多次生成字节一致**；SVG 内无时间戳、无脚本、无外部链接（只有 xmlns 命名空间）。
- 几何由规格顺序与 `layout_options` 决定：多列图按行列排布，流程图按步骤顺序纵向排布；
  连线使用正交折线，箭头固定大小；黑底白线、无渐变。
- SVG 是**规范产物**；PNG（300 DPI）为可选光栅输出（依赖 Pillow；不同平台字体可能略有差异，
  不作为逐字节回归对象）。缺转换依赖时明确报"未生成"，不伪造。
- 渲染器**不创造也不删除**部件/连线：规格没有的，图画不出来；规格有的，图不会丢。

## 5. 纪律与人工复核

1. 附图规格由人/AI 依据**已确认事实**填写；渲染器不参与技术判断。
2. 自动检查（F-001…F-014、V033）只保证机械一致性；**技术结构是否正确必须人工看图确认**。
3. 改稿导致规格变化后：重新 `figures validate`、重新渲染，并核对 `draft impact` 给出的受影响段落/附图。
4. 正式提交的附图为黑白线条图；复杂工程图允许导入人工确认过的 CAD/工程原图，不强制自动排版。
5. P4 交付门（`release_ready`）未实现前，附图只是底稿素材，不得宣称"可直接提交"。
