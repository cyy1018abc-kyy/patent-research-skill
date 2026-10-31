# 06 — 阶段 A6：中立报告

> 对应原件 Target-neutral reporting。报告从最终记录**派生**，不得改写判态、
> 影响类目、缺口或披露程度；A5 未通过的记录不得进报告结论。

## 1. REPORT.md 结构（按序）

1. **运行摘要**：profile、scope、模式（single/multi）、预算 spent/planned、
   审计基线（工作区快照标识）、旧 run 摄入情况；quick/scoped/预算受限/incomplete
   必须首句声明「部分覆盖」。两个必报指标：**台账覆盖率**与 **verifier 翻案率**。
2. **总体判断**（≤5 句）：证据链能否被信任、最大的风险是什么。
3. **confirmed 结论表**：影响类目（X/Y/A）、标题、要素、对比文件、一行披露说明。
   **不出现** rejected 记录。
4. **逐条展开**（每条 confirmed）：要素引用、对比文件与定位、逐字引文、
   区别特征、披露程度、影响类目理由、确定性（分开陈述）、独立复核标记。
5. **NEEDS VALIDATION 表**：标题、trace 摘要、确切缺失事实、local/external 下一步。
   **不标影响类目，不称 vulnerability/毁新颖**。
6. **建议节**：给 patent-research 的补检索/重引建议（只建议，不代执行）。
7. **覆盖摘要**：covered/candidate/blocked/deferred/not_applicable 计数 + 覆盖率
   + 最终批评家结果 + 重要排除（out_of_scope 及原因）。
8. **完整性声明**：incomplete 时逐条列出未验证 fingerprint 与台账单元，
   不得写成结论。

## 2. NEEDS-VALIDATION.md

每条待验记录独立成节：trace、已核实证据（引文逐字）、确切 blocker、
影响边界（哪个要素/哪条权利要求受影响）、local/external 核验计划。
按「证据强度 × 要素重要性」排序——这是**线索清单**，不是缺陷清单。

## 3. 中立性规则

- 报告语言与判态严格同源：confirmed 三态词、needs_validation 一律「待验证」、
  rejected 不出现（除非解释历史分歧）。
- 不发明 LOW 级结论凑数：干净运行可以零 confirmed，如实写「未发现可确认映射」
  并说明覆盖与验证的边界。
- 不给法律结论：报告不是无效/侵权意见书；授权前景语义交给 G-S 流程。
- 工作区内容不外发：报告示例引文只来自被审计工作区，报告文件本身留在
  运行目录；对外引用须经权利人同意。

## 4. 产物自检

报告写完后：双校验器重跑（findings + ledger）确认报告与 JSON 无分叉；
REPORT 中出现的每个 fingerprint 都能在 findings.json 找到；每个 confirmed
都带独立复核标记；未验证候选绝不以结论口吻出现。
