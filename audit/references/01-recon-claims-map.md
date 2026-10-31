# 01 — 阶段 A1：概览、要素分解与覆盖率台账

> 对应原件（security-audit-skill）的 Reconnaissance + coverage-ledger；
> 覆盖维度从「入口面×信任边界×子系统×攻击类」改为「要素×数据源×分类号」。

## 1. 概览 agents（多 agent 模式并行四问；单 agent 模式按序四轮）

只读被审计工作区与本仓库方法论文档，不联网、不补检索。每问产出带定位的事实
（工作区相对路径 + 段落/行号），返回给规划者汇总。

- **1a 目标与权利要求**：目标的技术方案是什么？独权逐要素是什么、从权附加哪些
  特征、各要素声称的技术效果是什么？从 `07_drafting/claims.md`（或 target_claims）
  与 `00_methodology` 提取，逐要素给引用定位。
- **1b 既有证据盘点**：`02_search_logs/`（含 raw/ 与查询日志）、`03_candidates/`、
  `04_comparative_analysis/`、`05_novelty_conclusions/` 各有什么？每条日志的
  数据源、检索式、命中数与 capture_mode 是什么？哪些候选已有引文、哪些是叙事？
- **1c 数据源与分类号版图**：既有检索用了哪些数据源（CNIPA/OPS/EPO/其他）？
  覆盖了哪些 IPC/CPC 分类号、哪些时间窗？工作区声明过的检索协议
  （`01_search_plan`）承诺了什么？
- **1d 基线对照**：目标所在技术域的「常规检索基线」是什么（同类主题通常要查
  哪几类源、哪个分类面、是否含非专利文献）？只作校准用，不构成覆盖豁免。

## 2. claims-map.md（≤1000 字）

规划者汇总四问，写 `claims-map.md`：

1. 目标一句话 + 保护主题类型；
2. **要素表**：每个要素一行——要素 ID（`E-01`…或对齐既有 F 编号）、要素陈述、
   来源定位、技术效果关联；
3. 数据源清单（含每个源的数据范围与已知限制）；
4. 分类号清单（初步相关面，标注确定性）；
5. 旧审计的缺口/改源重验目标（有旧 run 时）。

要素 ID 是后续一切结论与台账单元的锚点，运行内不得改名。

## 3. 播种 audit-ledger.json

对「要素 × 数据源 × 分类号组」的每个实质组合播种一个单元（profile 粗化规则见
`00-audit-protocol.md` §7）。范围外的组合记 `out_of_scope`（不是 covered）。

```json
{
  "schema_version": "patent-audit-ledger/1",
  "run_id": "…",
  "target": "…",
  "profile": "standard",
  "mode": "single",
  "units": [
    {
      "coverage_id": "E-01::cnipa-fulltext::G06F",
      "canonical_refs": {
        "element": "claims-map.md#E-01",
        "source": "02_search_logs/queries.jsonl#cnipa-fulltext",
        "klass": "claims-map.md#klass/G06F"
      },
      "element": "发送时刻估计值由队列深度预测修正",
      "source": "cnipa-fulltext",
      "klass": "G06F",
      "starting_paths": ["02_search_logs/raw/"],
      "query_plan_block": null,
      "prior_status": "none",
      "attempts": [],
      "wave": 1,
      "status": "planned",
      "agent_id": null,
      "reviewed_paths": [],
      "checks": [],
      "result_fingerprints": [],
      "unresolved": []
    }
  ]
}
```

## 4. coverage_id 派生规则（确定性，校验器会重算）

1. 三个规范引用都必须 Unicode NFC、无控制/格式/分隔符码点、无首尾空白；
2. 每个引用按 UTF-8 字节做 RFC 3986 百分号编码（仅 `A-Z a-z 0-9 - . _ ~` 不转义，
   其余转大写 `%HH`）；
3. 以 `element::source::klass` 顺序用 `::` 连接。
4. 同一语义组合出现两个不同 canonical 引用 = 规范身份冲突，禁止静默合并；
   重复 coverage_id 直接判错。

## 5. checks 记录（单元内追加）

| 字段 | 要求 |
|---|---|
| `agent_id` | 执行者（单 agent 模式用阶段化 ID，如 `a2-hunter`） |
| `method` | `search`（执行了检索，带日志工件）/ `source`（复核了文档，无工件）/ `local`（本地核验，带提升工件） |
| `description` | 检索式/复核对象与判定 |
| `reviewed_paths` | 本次实际读过的工作区路径（非空） |
| `artifact` | `search`/`local` 必须给 `agents/<agent_id>/artifacts/` 下相对路径；`source` 为 null |

单元级 `reviewed_paths` 恒等于全部 checks 的并集。播种后与每次台账更新后运行
`python audit/scripts/validate_ledger.py <ledger>`，全部错误修复后才允许分派狩猎。

## 6. prior run 摄入

存在旧 run 时逐条读其台账与 findings：同源 confirmed → 携带（`prior_status:
"prior_confirmed_same_source"`）且必须重过独立验证；改源 → 建重验单元；旧
needs_validation/deferred/blocked/out_of_scope → 全部转当前 `planned`。旧账本的
空缺不是「查过了」的证据。
