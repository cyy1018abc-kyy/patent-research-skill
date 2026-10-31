# Gold 仲裁记录（ARBITRATION）

- 协议：`docs/annotation-protocol.md` §3.4。本目录（`gold/worksheets/`）整体
  gitignore（本地留存），本文件是模板与索引，随仓库提交以固定表式。
- 每条分歧一行；仲裁后由 `tools/annotation_agreement.py --arbitrated` 汇总进
  qrels；分歧必须全部闭环（ κ 计算用仲裁前数值留档，见下）。

## 模板

| topic_id | doc_id | label_1 | label_2 | 仲裁结论 | 理由（一句话） | 仲裁人 | 日期 |
|---|---|---|---|---|---|---|---|
| TP-xxxx | <family_id> | 1 | 2 | 2 | 说明书第 x 段披露了必需特征 | <姓名> | 2026-11-xx |

## 一致性留档

| 轮次 | overall κ | 低于门主题 | 措施 |
|---|---|---|---|
| 预标定（10 主题，不入 gold） | _填_ | _填_ | 校准口径要点 |
| 正式标注（仲裁前） | _填_ | _填_ | 分歧仲裁 |
| 仲裁后复核 | _填_ | _填_ | — |
