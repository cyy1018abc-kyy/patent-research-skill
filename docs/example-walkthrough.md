# 示例走查：从零到交付物（全部使用合成数据）

> ⚠️ 本文档所有「工作区数据」均为**合成示例**（`patentkit init` 模板 + 手工占位），
> 不含任何真实项目的候选、公开号或稿件。终端输出为真实命令的真实输出（2026-10-25，
> kernel 0.3.0 / skill 2.5.0）。

## 0. 安装后自检

```text
$ python scripts/self_test.py
技能自检（self-test）

  [OK  ] python: 3.12.14
  [OK  ] patentkit: patentkit 0.3.0 (assessment protocol 1; 需要 ≥0.3.0/1)
  [OK  ] sample_workspace: 18 个条目
  [OK  ] validate_clean_sample: error 0 / warn 0
  [OK  ] gates_empty_sample_not_pass: 空样例正确地未通过门禁
  [OK  ] export_docx_smoke: smoke.docx

结果：6/6 通过
```

六项里最有信息量的是最后两项**正反用例**：干净样例必须校验通过（正），
空样例必须**不**通过门禁（反）——门禁若被硬编码成永远通过，这两项会互相拆穿。

## 1. 初始化工作区与全局状态

```text
$ python -m patentkit init demo_ws --target TGT-0002 --title "示例：合成燃料电池水管理"
$ python -m patentkit status
Workspace  : ...\demo_ws
Active target : TGT-0002  示例：合成燃料电池水管理
Candidates : 0
Search logs: 0 (live 0 / retrospective 0)
Validation : error 0 / warn 0 / total 0
Acceptance gates:  [ N/A] G-S-01 … [ N/A] G-S-05   ← 数据为空，全部 N/A 而不是假装 FAIL
Next steps:
  · No search logs yet — G-S-05 requires live logs + raw artifacts…
```

多目标组合视图（`patentkit layout`）在数据不足时**拒绝指定主件**：

```text
→ verified 证据都为 0 — 数据不足，暂不建议指定主件（继续补检索）
空轴 = 该轴 verified 计数为 0；先补检索再谈布局
```

## 2. 数值溯源：fail-closed 是什么样子

稿件里写了数值（`07_drafting/claims.md`，合成）：

```text
1. 一种燃料电池水管理装置，其特征在于，膜厚度为 3 mm，工作温度为 80-95℃。
2. …分离效率达到 99.2% 以上。
```

```text
$ python -m patentkit provenance scan --manuscript 07_drafting/claims.md --out 07_drafting/numerical_provenance.yml
[WRITE] 07_drafting/numerical_provenance.yml (2 statements) — fill sources, then run provenance check

$ python -m patentkit provenance check
[NUM-001] 1. …膜厚度为 3 mm，工作温度为 80-95℃
    claim_ref: _(未填)_
    ⚠️ 无来源 — 待补
…
问题:
  [V031] NUM-001: no source — a numerical claim without provenance is built on air
  [V031] NUM-002: no source — …
2 problem(s) — fix the registry, not the rule        ← exit 1；修登记表，不是改规则
```

人工在 yml 里给每条补 `sources`（A=自产材料 / B=候选文献 / C=显式声明的示例值）后，
`check` 才会转绿——**没有「跳过」按钮**，这就是 fail-closed。

## 3. 附图标记：warn 而不擅改

```text
$ python -m patentkit figures check
[V033] *: component-like marks in the manuscript not declared by any figure spec: 1
mark mismatches are warnings — confirm with the figure before editing; the rule never auto-deletes a mark
```

这里的 `1` 来自合成说明书里「权利要求1」的编号——**启发式抽取的已知噪声**，所以 V033
只警告、永不自动删标记；真差异（图里有 31、正文没有）同样会列出，由人对图复核。

## 4. 交付物：数字零手工转写

```text
$ python -m patentkit export-docx TGT-0002
[WRITE] 2026-10-25_TGT-0002_report.docx
内容全部来自工作区数据；三层级判定与结论段落需人工填写后再交付

$ python -m patentkit map TGT-0002     # 离线 HTML 总览（无外链无脚本，可内网打开）
$ python -m patentkit figures draw FIG-1   # 确定性 SVG 框图（提交前转 300DPI 黑白位图）
```

docx 里的门禁表、D 列、证据分级全部取自工作区实时状态；三层判定是显式的
「人工填写」占位——**文档不发明结论**。

## 5. 结论引用必须命中账本

```text
$ python -m patentkit ledger TGT-0002
证据账本 — TGT-0002（结论可引用的证据清单；引用不在账本中的编号会被 V034 拦截）
（该目标暂无候选）
```

此时在 `05_novelty_conclusions/` 写「P-907 披露了 N1 轴」会立刻被
`validate` 的 V034 拦下（error）——编造引用在交付前就死掉，而不是活在文档里。
