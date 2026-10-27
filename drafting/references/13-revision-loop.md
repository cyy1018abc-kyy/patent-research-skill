# 13 多轮改稿闭环

> 对标 PatentClaw 的可追溯多轮改稿（独立问题 → 局部补丁 → 复审 → 变更记录），
> 与本仓库既有的 `attest` sha256 绑定整合。**核心原则：改稿必须可追溯、可回滚、
  不顺手改无关内容。** 内核 0.4.0 起，闭环由 `patentkit revise` 强制执行——
  补丁、台账、重绑定在同一个事务里完成，「改了没登记」从纪律变成可检出的错误。

## 闭环（每一轮都一样）

```
问题清单（每轮一个问题或一组相关问题）
   ↓ 写补丁文件（YAML：round / issue / source / changes[]，每条改动带字段级定位）
revise apply patch-R4.yml   ←  文件修改 + revision_ledger.yml 台账 + 登记表重绑定，同一事务
   ↓
按台账 revalidate 提示重验：validate --strict + gates（必做）
   + provenance check（数值）/ figures check（附图）/ 重新人工确认（改了判定相关内容）
   ↓
revise close --round R4     ←  重验通过后关闭该轮（close 前会再做一次链条完整性检查）
   ↓ （涉及已确认的近端对比时）
重新评估 → 重新人工确认（指纹已变，旧确认自动失效——这是特性不是 bug）
```

## 补丁文件格式（`revise apply` 的唯一入口）

```yaml
schema: 1
round: R4                      # 与台账中已有轮次不得重复
issue: OA-X2                   # 问题标识
source: office action          # 问题来源
changes:
  - file: 07_drafting/claims.md  # 必须已登记在 manuscript_registry.yml
    field: 权2 数值范围            # 人类可读的字段/段落定位
    find: "0.33-0.45"              # 必须在目标文件中**恰好出现一次**，否则整包拒绝
    replace: "0.35-0.42"
    revalidate: [provenance, confirmations]  # 可选；validate+gates 恒为必做，不用列
```

三条硬规则由此变成结构性质：

1. **一个补丁只解决登记的问题**——工具只应用 changes 里声明的 find→replace，
   顺手改的内容没有补丁条目，进不了文件；
2. **实质变更使确认失效是设计使然**（见 [00 前置纪律](00-prerequisites.md)的判断合格性一节）：
   声明了 `revalidate: [confirmations]` 的改动，apply 输出会显式提醒重新评估与重新人工确认；
3. **禁止「先改再补日志」**——`revise status` 与 validate 的 V036 把「当前文件 sha256 ≠
   台账轮次后 sha256」报为错误（status exit 1；validate 非 strict 为 warn、strict 升级拦截）。
   `attest --check` 的漂移报告从此有「谁在什么时候为什么改的」可查：台账里每条改动
   记录前后 sha256。台账结构本身坏掉是 V035 error。

## 轮数上限

同一问题累计 3 轮 → `revise status` 显式报警：停下改稿，把问题升级给发明人/代理师，
**不要**用反复改稿掩盖材料缺失（对应 [09](09-disclosure-drafting.md) 的 open_questions）。
关闭某轮用 `revise close --round R4 --note "重验证据一句话"`；链条完整性检查不过时 close 会拒绝。

## 改稿 ↔ 结论联动（内核 0.8.0 起，V038）

稿件被补丁改动 ⇒ `05_novelty_conclusions/*.md` 全部自动标 stale（内核生成的
`five_acceptance_gates_tracking.md` 除外——它是 gates 按需重算的活视图）。在重确认或
豁免之前：`revise status` exit 1、`revise close` 拒绝、validate 报 V038 error。
处理方式二选一（都要显式记录判断主体）：

```powershell
python -m patentkit revise reconfirm --file 05_novelty_conclusions/conclusions.md --by <人名>
python -m patentkit revise reconfirm --file <结论> --waive --reason <理由一句话> --by <人名>
```

豁免写入使其 stale 的那一轮台账（`conclusion_waivers`）；重确认绑定文件 sha256——
之后再改结论文件会被 V038 拦下（改过就得重新确认）。状态存于内核管理的
`05_novelty_conclusions/conclusions_state.yml`；没有该文件的旧工作区零迁移。

## 命令速查

```powershell
python -m patentkit revise apply patch-R4.yml   # 原子应用（任一 find 命中数≠1 则整包拒绝、零写入）
python -m patentkit revise status               # 轮次表 + 链条完整性 + stale 结论清单（→ exit 1）
python -m patentkit revise reconfirm --by <人名> # stale 结论重确认（或 --waive --reason 豁免入台账）
python -m patentkit revise close --round R4     # 重验通过后关闭（有 stale 结论时拒绝）
python -m patentkit attest --check              # 漂移检测（登记表视角，与台账互为印证）
python -m patentkit validate --strict           # 结构一致性（V035/V036/V038）
python -m patentkit review export --format json --axis N1 --out re.json   # 重新评估入口
```
