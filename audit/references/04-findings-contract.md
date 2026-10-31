# 04 — 阶段 A4：findings.json 三态结论契约

> 对应原件 Structured output（report-schema.json + validate-findings.cjs）；
> 字段按专利域重写，校验器用 Python 实现（`audit/scripts/validate_findings.py`，
> 零第三方依赖；文件头注明 derived from Cloudflare security-audit-skill, MIT）。

## 1. 三个判态的分工

| 判态 | 含义 | 必有 | 禁有 |
|---|---|---|---|
| `confirmed` | 证据链完整且经独立证伪未破 | 映射理由、逐字引文证据、披露程度、影响类目、确定性、独立复核标记 | claimed_rationale、blockers、validation_plan、refutation |
| `needs_validation` | 路径成立但缺一个决定性事实 | claimed_rationale、blockers（≥1）、validation_plan（local/external 至少一项） | impact、disclosure_extent、confidence、distinctions、independent_review、mapping_rationale、refutation |
| `rejected` | 已被反证推翻（留档防重犯） | claimed_rationale、refutation（证伪理由） | impact、confidence、independent_review、blockers、validation_plan、mapping_rationale |

三态共有：`verdict`、`fingerprint`、`title`、`description`、`element`（claims-map
要素引用）、`trace`（要素→披露→效果 的链条）、`evidence`（逐字引文数组）。

## 2. 关键字段规则（校验器逐条强制）

- **fingerprint**：`^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$`，源派生、跨判态稳定
  （惯例 `MAP:<要素ID>:<对比文件标识>`）；全文档唯一且按字典序排序。
- **trace**：`kind` 枚举 `element|disclosure|effect`；首项必为 `element`，末项必为
  `disclosure` 或 `effect`，中间只允许 `disclosure`；每项带 `ref`（工作区相对路径
  #段落/行 定位）与 `description`。
- **evidence**：每条 `{ref, locator, quote, description}`——`ref` 是安全相对路径
  （禁反斜杠/盘符/`..`/绝对路径），`locator` 非空（如 `[0004]` 或 `L12`），
  `quote` 是**逐字**引文。confirmed 的 evidence ≥1。
- **impact（破坏性轴）**：仅 confirmed。`category` 枚举对齐检索报告类目——
  `X`（单篇毁新颖性）/ `Y`（组合影响创造性）/ `A`（背景）；`X` 必须同时给
  `element_coverage.all_elements == true`（全要素链声明），否则校验失败。
  **overall 不得高于已证实的披露程度**：`disclosure_extent: "partial"` 时只允许
  `Y` 或 `A`。
- **confidence（确定性轴）**：仅 confirmed，`low|medium|high` + 理由；与 impact
  两轴分开，不得互折（高确定性不抬破坏性，高破坏性不抬确定性）。
- **independent_review**：仅 confirmed，`{status: "verified", reviewer: <id>}`；
  没有经过阶段 A5 的 confirmed 是协议违规。
- **needs_validation.validation_plan**：`local`（本地可核：同族检索、官方登记簿、
  原文重新获取）与 `external`（需人工/外部授权源：审查历史、权利人确认）至少一项。
- **rejected.refutation**：写明证伪类型（引文不符/定位冒充/特征未披露/日期不利/
  相关性不成立）+ 反证定位。

## 3. 文档级规则

顶层是数组；≤1000 条；输入 ≤5 MiB、嵌套 ≤64 层；按 fingerprint 字典序排序；
重复 fingerprint 判错。字段集合**封闭**（additionalProperties 禁止）：不得把狩猎
过程的包装字段带进记录。

## 4. 运行校验器

```bash
# 结构校验（任何时候）
python audit/scripts/validate_findings.py findings.json

# 带证据核验：逐条检查 ref 存在、locator 命中段落、quote 逐字出现
python audit/scripts/validate_findings.py findings.json --workspace <工作区根>

# 机读结果
python audit/scripts/validate_findings.py findings.json --json
```

退出码：`0` 通过 / `1` 校验失败（problems 列出全部问题，上限 100 条）/
`2` 用法或环境错误。`--json` 输出单一 JSON 文档（`{"ok":…, "errors":[…]}`）。
通过只证明格式与字段纪律；语义对错仍由 A3/A5 的独立角色负责。

## 5. 生产提示词用分支拷贝

让生成方（verifier/reviewer）照抄 `findings-schema.json` 中对应判态的分支
（含 additionalProperties: false），不许自由发挥字段名。改契约必须同步改：
本文件、`findings-schema.json`、`audit/scripts/validate_findings.py`、
`tools/score_audit_findings.py` 与两侧测试。
