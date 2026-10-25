# 13 多轮改稿闭环

> 对标 PatentClaw 的可追溯多轮改稿（独立问题 → 局部补丁 → 复审 → 变更记录），
> 与本仓库既有的 `attest` sha256 绑定整合。**核心原则：改稿必须可追溯、可回滚、
  不顺手改无关内容。**

## 闭环（每一轮都一样）

```
问题清单（每轮一个问题或一组相关问题）
   ↓ 局部补丁：只改对应字段/段落
变更日志（revision_ledger.md 加一行）
   ↓
attest --apply（重新绑定 sha256）
   ↓
重过门：validate --strict + gates + （涉及数值时）provenance check
   ↓ （涉及已确认的近端对比时）
重新评估 → 重新人工确认（指纹已变，旧确认自动失效——这是特性不是 bug）
```

## 变更日志格式（`07_drafting/revision_ledger.md`）

```markdown
| 轮次 | 日期 | 问题来源 | 改动（字段/段落级） | 触发的重验 | 确认状态 |
|---|---|---|---|---|---|
| R3 | 2026-10-25 | OA-X2 | 权2 数值范围 0.33-0.45→0.35-0.42 | provenance+support_mapping | 需重新确认 P-012 |
```

## 三条硬规则

1. **一个补丁只解决登记的问题**。顺手改别处 = 破坏其它改动的可追溯性，
   而且会让本已有效的人工确认静默失效；
2. **实质变更使确认失效是设计使然**（[07](07-assessment-protocol.md)）：
   改了分数/角色/轴/理由/引用，相关候选必须重新评估并重新人工确认；
   改作者拼写等元数据不失效；
3. **禁止「先改再补日志」**：没有变更日志行的改动，`attest --check` 报漂移时
   无法回答「谁在什么时候为什么改的」。

## 与工具的衔接

```powershell
python -m patentkit attest --check        # 漂移检测（改了没登记 → 报警）
python -m patentkit validate --strict     # 结构一致性
python -m patentkit provenance check      # 数值相关改动
python -m patentkit review export --format json --axis N1 --out re.json   # 重新评估入口
```

## 轮数上限

连续 3 轮同一问题仍未关闭 → 停下来把问题升级给发明人/代理师，
**不要**用反复改稿掩盖材料缺失（对应 [09](09-disclosure-drafting.md) 的 open_questions）。
