# 12 政策雷达：审查口径与书式变化追踪

> 对标 patent-disclosure-skill 的 patent-exam-policy。**工具不自动联网嗅探**（保密边界），
> 这里是一份**人工核查清单**：每次开工前/交稿前扫一遍，把「口径变了」翻译成
> 「本流程哪一步受影响」。

## 核查源（官方为准）

| 源 | 看什么 | 影响哪里 |
|---|---|---|
| 国知局「审查指南」修订公告 | 创造性判断口径、计算机程序/算法类权利要求形态 | [03](03-three-tier-determination.md) 三层判定、[10](10-claim-drafting.md) 权项形态 |
| 国知局表格/书式页面 | 请求书/摘要/费用减免书式版本 | [09](09-disclosure-drafting.md) 申请文件清单 |
| cponline 上传要求 | 附图分辨率/格式/大小限制 | [08](08-figures.md) 附图规格 |
| 专利法/实施细则修订 | 期限（申请费/实审/OA 答复）、宽限期 | `patentkit deadlines` 的 PRESETS 与 [11](11-oa-response.md) |
| 非正常申请认定口径 | 权项堆叠、同日申请策略 | [09](09-disclosure-drafting.md) 的 1+N 布局建议（`patentkit layout`） |

## 变化登记格式

发现口径变化时，在仓库 `docs/policy-log.md` 记一行：

```markdown
- 2026-XX-XX | 来源：官方公告链接 | 变化：一句话 | 影响：references/XX 的第 X 节 | 处置：已改/待改 + 责任人
```

**登记了但没改 references 的，视为未处理**——交稿清单要过一遍 policy-log 的「待改」。

## 已固化为工具的口径（变更需改内核）

- 期限预设：`patentkit/deadlines.py` 的 PRESETS（申请费 2 个月/实审 3 年/OA 4+2 个月/年费周年）；
- 附图要求：`patentkit figures`（黑白线条、标记一致性）；
- 五门口径：`patentkit/gates.py`（变更走 CHANGELOG + 回归测试，不接受口头放宽）。

> **法定期限以官方发文/通知书为准**：deadline 工具是提醒台账，不是法律意见；
> 电子送达 15 日推定收到等规则以现行规定为准。

## 节奏建议

- 每个新项目开工时：全清单扫一遍（半小时内）；
- 交稿前：只查「影响交稿物」的两行（书式 + 附图）；
- 季度：对照一次 审查指南 修订目录。
