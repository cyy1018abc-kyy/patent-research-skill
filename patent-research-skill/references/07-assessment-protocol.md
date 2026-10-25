# 07 评估协议 1

要求 patentkit ≥0.2.0（0.3.0 同协议）。旧内核会被技能封装层拒绝。权威实现是
`patentkit/assessment.py`，由 gates、validate、CLI 与 API 共用；数量阈值仍在 `patentkit/gates.py`。

## 升级既有工作区

```bash
patentkit review migrate-assessments --root /path/to/workspace
patentkit review migrate-assessments --root /path/to/workspace --apply
```

迁移扩展候选 schema，并为缺失判断来源的记录补 `actor=unknown`。它保留分数、角色、
来源等级、工件与历史；**不发明**人工身份或确认。来路不明的分数在重新评估前不再
进入 G-S-02/G-S-03；其来源仍可用于 G-S-01。

## 评估（assess）

```bash
patentkit review export --format json --axis N1 --out assessment.json
patentkit review assess assessment.json --actor ai --by 模型名
patentkit review assess assessment.json --actor ai --by 模型名 --apply
```

导出行自带 `candidate_id` 与当前 `expected_fingerprint`。填写两个维度的分数、角色、
novelty_check、review_note 与 basis。basis 按目标限定轴为键；每个纳入的轴都要求
problem 与 means 两条引用：

```json
{
  "N1@TGT-0002": {
    "problem": {
      "ref": "02_search_logs/raw/source.json",
      "locator": "/hits/0/abstract",
      "quote": "定位到的原文原句",
      "rationale": "为什么这句话支持技术问题维度的打分"
    },
    "means": {
      "ref": "02_search_logs/raw/source.json",
      "locator": "/hits/0/abstract",
      "quote": "描述实现方式的原文原句",
      "rationale": "为什么这句话支持技术手段维度的打分"
    }
  }
}
```

把示例换成该候选真实的引用与文本。ref 是工作区相对路径的 UTF-8 文件，且不得越出
工作区；JSON 用 JSON Pointer，纯文本用 `L12-L16` 行区间。引文匹配校验的是**存在**，
不是语义正确。某轴没有完整 basis 则该轴不计数；两个分数必填，relevance 取最小值。

AI 与既有人工判断冲突时，建议存入 `assessment_proposals`，不改现行值；历史审阅痕迹与
排除标记同样受保守保护。人工复核后，用 `--actor human --by 审阅人姓名` 导入选定的
评估即「接受建议」——它产生新的判断与历史，但**不会**自动产生 G-S-03 确认。

## 确认已复核清单（confirm）

apply 之后**重新导出**拿到新指纹。从已复核行构造一个 UTF-8 JSON 数组，**只含**接受的
`candidate_id` 与 `expected_fingerprint` 两个字段，然后：

```bash
patentkit review confirm confirm.json --by 审阅人姓名
patentkit review confirm confirm.json --by 审阅人姓名 --apply
patentkit gates
```

只有真实的人工授权才能建立确认。每个候选当前必须有受支持的 `near_prior_art` 评估。
未知/重复/跨目标 ID、缺指纹或指纹过期都会在写入前**整批拒绝**。多目标时统一用
`--target TGT-xxxx`。

分数、角色、目标/轴、特征映射、理由、定位符与所引原文段落都绑进指纹。实质变更使
确认失效；作者拼写等无关元数据不失效。历史保留既往判断与捕获段落。失效的确认
永不授权 AI 覆盖人工决定。

## 兼容与极限

所有写命令默认 dry-run；文件先暂存再替换，普通写错误会回滚已完成的替换。这不是
断电级别的数据库事务：保留不可变的 raw 工件与工作区备份。

CSV 仍可用。新导出的 CSV 带 `expected_fingerprint`，原样保留。`review apply sheet.csv
--by 审阅人 --apply` 记录显式人工 actor；未署名的旧表保留 unknown 来源——时间戳本身
不能确立审阅人。CSV 永不产生 G-S-03 确认，也不使无支持判断合格。

`review progress` 用同一套合格性规则；`status --json` 暴露 `candidates.by_assessment_state`。
V029 报缺失/无支持/来路不明的判断；V030 报失效的人工确认。材料变更后先重新评估，
再重新确认。

工具校验引文匹配、分数一致性与指纹新鲜度；它不能证明语义正确，也不能验证命令背后
的自然人是审阅者本人。代理不得冒充人工审阅者。
