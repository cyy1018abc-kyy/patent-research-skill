# evals/ —— 触发与边界评测集

> 对标 cnipa-patent-kit 的 evals/evals.json。本目录回答两个问题：
> **该触发的时候触发吗**（trigger）、**不该接的时候拒绝吗**（refusal/boundary）。

## CI 校验（确定性，每次 push 自动跑）

```bash
python evals/validate_evals.py
```

校验：用例 ≥10、四类齐备、id 唯一、**触发短语逐字锚定 SKILL.md 的 description**
（description 是客户端匹配的唯一依据，引用一个不存在的短语 = 测一个永远不会发生的行为）、
⚠️ 前缀用例覆盖、结果格式五项与 SKILL.md 同步。

## 行为评测（改 SKILL.md/references 后人工过一遍）

对 trigger 用例：新开会话说 input，检查——
1. 技能是否触发（没有触发 → description 措辞问题）；
2. 是否按 SKILL 执行顺序走（先 status 自检，不是直接下结论）；
3. 输出是否符合「结果格式」五项。

对 refusal 用例：检查是否**拒绝并给出替代**（R1 给三层判定结论但不预测授权；
R3 拒改阈值并解释 FAIL=检索不足）。

对 boundary 用例：B1 必须以「⚠️ 未经验证工具校验」开头；B2 只提醒不自动改；
B3 解释命中面 vs 实采数。

## 维护规则

- 新增触发短语时：先加进 SKILL.md description，再加 evals 用例（CI 会强制这个顺序）；
- 改「结果格式」时：同步 F1 的 result_format_fields（checker 逐项对表）；
- 拒绝类用例必须写 behavior（拒绝后给什么），防止「只会说不」。
