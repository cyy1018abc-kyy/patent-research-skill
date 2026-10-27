# 对比矩阵（TGT-9009，合成案例金解）

| 维度 \ 对比文件 | D1 | D2 | D3 |
|---|---|---|---|
| **N1：复用感应区唤醒** | — | ○ | — |
| **N2：双因子撤销** | ○ | — | — |
| **N3：机械旋钮优先** | — | — | ○ |
| **N4：低电禁远程** | ○ | — | — |
| **整体闭合** | ○ | ○ | ○ |

## 每列输出

D1 — Multi-factor smart door lock control system  ZZ900091A1 (P 编号 P-001)
- 申请人：Shoumen Smart Technology Co.
- 公开年：2020
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900091A1.md#L14：开启后撤销离家状态需要依次验证指纹与 NFC 卡两项因子；02_search_logs/raw/ZZ900091A1.md#L15：电量低于告警门限时，面板指示灯变红并向手机推送低电提醒
- 区别点：[0003] 指纹模组为独立感应区、与把手分体，[0005] 还承认轮询功耗——与复用感应区相反；双因子撤销已披露，但为可选增强且为"依次验证"而非"同时生效"；[0010] 电机驱动为常态、旋钮仅应急备用——无机械优先于电子的直连结构；有低电门限与提醒，但同段明确"远程开锁功能保持可用"——与拒绝远程相反
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D2 — Press-to-wake integrated mobile terminal  ZZ900092A1 (P 编号 P-002)
- 申请人：Zhangxin Mobile Devices Co.
- 公开年：2019
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900092A1.md#L9：把压感层与指纹传感层叠合在同一感应区内
- 区别点：按压唤醒+指纹同区的手段完整披露（[0004] 上电识别），但载体是移动终端侧框而非门锁把手
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D3 — Mechanical-priority opening device for fire exit doors  ZZ900093A1 (P 编号 P-004)
- 申请人：Antao Door Control Engineering Co.
- 公开年：2021
- 命中轴：N3
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900093A1.md#L11：无论电控处于何种状态，人力推动推杆都经离合机构直接拉开门闩
- 区别点：机械优先结构完整披露（[0006] 纯机械件可靠性佐证），但对象是疏散推杆与门闩，非住宅锁旋钮与离合锁体
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

