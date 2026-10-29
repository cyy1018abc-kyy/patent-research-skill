# ADR 0003 — 路径包含检查把反斜杠按分隔符候选归一化（双平台一致拒绝）

- 状态：**已接受**（2026-10-29，Phase L / WP-L1）
- 背景：PR #15 CI 在 Ubuntu 暴露 `test_traversal_writes_refused[..\\..\\workspace.yml]`
  未触发 `PathEscapeError`——POSIX 上反斜杠不是分隔符，该字符串是一个合法
  **文件名**，包含检查按 POSIX 语义拒绝它反而不成立；而同一字符串在 Windows
  CI 上是真实的越界路径。

## 背景

safe_io 的包含检查（`ensure_contained`）原先只按运行平台的 `pathlib` 语义解析
候选路径。这产生一个双平台语义裂缝：Windows 构造的穿越串（`..\..\evil`）在
Windows 上被拒、在 POSIX 上被当作普通文件名**放行并落盘**。专利工作区的工件
（归档、夹具、审计包）经常跨平台搬运——Windows 上组装的目录在 POSIX 侧解包
再写回时，这条裂缝就成了越界写入通道。

## 决策

1. **归一化优先**：`ensure_contained` 在任何检查之前把候选路径中的 `\` 全部改写
   为 `/`，再走原有解析与 `relative_to` 包含判断。效果：
   - `..\..\workspace.yml` 在 **所有平台** 一律 `PathEscapeError`（测试双矩阵断言）；
   - `sub\dir\record.json`（反斜杠分隔但未越界）在所有平台照常接受并解析到
     root 内的规范位置。
2. **不接受「POSIX 合法文件名」辩护**：含反斜杠的文件名在专利工作流中没有合法
   场景；歧义一律向安全侧收敛（refuse）。这是 blueprint §3.2 规则 9（供应链
   安全）在跨平台场景的推论。
3. **不引入平台分支**：不写 `if os.name == "nt"` 之类的差异化语义——两条规则
   （拒绝/接受）在 ubuntu+windows 四矩阵必须产生相同结果，这本身就是测试断言
   （IT-07 平台一致性口径的延伸）。
4. **影响面**：仅 `patent_intel.io.safe_io.ensure_contained` 一个函数；所有写入
   原语（`write_text_atomic`/`write_json_atomic`）经由它获得该语义，调用方无需
   感知。

## 验收（已入测试）

- `extensions/patent_intel/tests/test_safe_io.py`：
  `test_containment_refuses_backslash_and_mixed_traversal`（Windows 形态/混合形态
  ×4，双平台全拒）+ `test_containment_accepts_backslash_inside_path`（反斜杠分隔
  的 root 内路径照常接受）。
- `tests/test_security_privacy.py::test_traversal_writes_refused`：参数表覆盖
  Windows 形态、POSIX 形态、混合形态，四矩阵同结果。
