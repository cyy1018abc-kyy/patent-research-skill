# 15 · 权项原子与支持映射

> 本文件定义 **ClaimAtom（权项原子）**、**Claim（结构化权项）** 与 **SupportMapping（支持映射）**
> 的写法、校验规则与人工确认纪律。字段级权威是内核 `patentkit.contracts`（schema_version 1.0）。

## 1. 权项原子（ClaimAtom）

一个原子 = 一条可落到权利要求里的**技术特征**，必须带事实引用。

```json
{
  "schema_version": "1.0",
  "atom_id": "ATOM-001",
  "idea_id": "IDEA-001",
  "text": "检测能源装备的负载变化率",
  "fact_refs": ["FACT-001"],
  "importance": "essential",
  "depends_on": [],
  "review_status": "pending"
}
```

| 字段 | 规则 |
|---|---|
| `atom_id` | `ATOM-001` 递增；一个原子只属于一个候选 |
| `text` | 一个可独立引用的技术特征；不写效果、不写未证实参数 |
| `fact_refs` | ≥1，必须指向已确认的技术事实；**无事实不成原子** |
| `importance` | `essential`（必要特征）/ `optional`（可选特征） |
| `depends_on` | 依赖的其它原子（用于改稿影响传播） |
| `review_status` | 内核拥有：导入为 `pending`，`draft atoms review` 确认 |

**指纹规则**：原子的人工确认绑定**原子内容指纹**（不含 `review_status`）。确认后再改
`text`/`fact_refs`/依赖关系 → 旧确认自动失效（D-017），必须重新确认。

## 2. 结构化权项（Claim）

```json
{
  "schema_version": "1.0",
  "claim_no": 1,
  "claim_type": "independent",
  "parent_claim_no": null,
  "atom_ids": ["ATOM-001"],
  "supported_paragraphs": ["0005"]
}
```

内核强制校验（`draft claims import`）：

1. `claim_no` 唯一且**编号连续**（从 1 开始，不跳号）；
2. 至少一项**独立权项**；独立权项不得有父项；从权必须引用**更早**的权项；
3. 禁止循环引用（父链必须严格递减）；
4. `atom_ids` 必须存在；权项特征必须有事实来源（原子已带 `fact_refs`）；
5. `review_draft` 门禁还要求：每个权项原子都有段落支持映射且人工复核。

> 术语**先行基础**（antecedent basis）：权利要求中首次出现的术语必须在独权或更早权项中
> 有先行定义；本管线用"术语表 + 人工复核"约束，不自动改写正文。

## 3. 支持映射（SupportMapping）

```json
{
  "schema_version": "1.0",
  "rows": [
    {
      "claim_no": 1,
      "atom_id": "ATOM-001",
      "paragraphs": ["0005"],
      "fact_refs": ["FACT-001"],
      "figures": ["FIG-1"],
      "prior_art_diff": "D1 未公开负载变化率触发条件",
      "citations": [
        {"source": "10_discovery/sources/ZZ900099A1.md", "locator": "[0001]", "note": "负载检测手段"}
      ]
    }
  ],
  "review_status": "pending"
}
```

| 规则 | 说明 |
|---|---|
| 行键 | `(claim_no, atom_id)` 唯一；该原子必须属于该权项 |
| `paragraphs` | ≥1；说明书段落号（与稿件一致），空映射不算覆盖 |
| `citations` | 可选；结构化引用（内核 0.8.0 起，D-019）：`source` 为工作区相对路径（越界/不存在即 error），`locator` 为 `L<n>[-L<m>]` 行区间或 `[NNNN]` 段落号（越界/段落号不存在即 error）。写了就必须可解析——支持性引用不再只是自由文本 |
| `fact_refs` | 支持该特征的事实编号（与原子/事实库一致） |
| `figures` | 相关附图编号（P3 前可先按规划填，P3 校验图文一致） |
| `prior_art_diff` | 与对比文献的区别说明（引用账本内编号） |
| 人工复核 | `draft support review` 记录语义支持是否成立；门禁要求全部 confirmed |

## 4. 验收清单（`review_draft` 前逐项核对）

- [ ] 每个必要技术特征都有权项原子，且原子 `fact_refs` 指向已确认事实；
- [ ] 每个权项的每个原子都有 ≥1 段落支持映射，且支持映射经人工复核；
- [ ] 权项编号连续、从权引用更早权项、无循环、至少一项独权；
- [ ] 原子人工确认指纹当前（改过文本就重新确认）；
- [ ] 计划所绑候选未变化（变化则重新 `draft plan`）；
- [ ] G-S-01/02/03 均为 PASS（`draft gate` 会再核一遍）；
- [ ] 数值声明已在 `provenance` 登记；稿件哈希用既有 `attest`/`revise` 机制。

## 5. 反例（会被内核拒绝或门禁拦截）

| 做法 | 结果 |
|---|---|
| 原子没有 `fact_refs` | schema 拒绝（minItems 1） |
| 原子引用不存在的事实 | D-005 error |
| 直接改原子文本后沿用旧确认 | D-017 error，门禁阻塞 |
| 权项编号跳号 / 从权引用后面的权项 | 结构校验拒绝 |
| 支持映射段落为空 | 导入拒绝；门禁阻塞 |
| G-S 未 PASS 就标 `review_draft` | `draft gate` 阻塞并列出未过门禁 |
| 把推断效果写进权项正文 | 违反既有 drafting 硬约束（不得编造） |
