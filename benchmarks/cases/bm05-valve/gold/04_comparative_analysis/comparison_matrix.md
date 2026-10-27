# 对比矩阵（TGT-9005，合成案例金解）

| 维度 \ 对比文件 | D1 | D2 | D3 |
|---|---|---|---|
| **N1：阀位反馈** | — | ○ | — |
| **N2：开关速度曲线** | ○ | — | — |
| **N3：水锤预测预收** | — | — | ● |
| **N4：手动优先机构** | ○ | — | — |
| **整体闭合** | ○ | ○ | ○ |

## 每列输出

D1 — General purpose controller for motorized valves  ZZ900051A1 (P 编号 P-001)
- 申请人：Hengliu Automation Equipment Factory
- 公开年：2019
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900051A1.md#L11：开关过程的速度由用户在面板上设定，全程按同一速度运行；02_search_logs/raw/ZZ900051A1.md#L14：手动操作前需先用扳手卸下传动箱的联轴器销，再装上手轮直连轴
- 区别点：[0003] 反馈用电位器且 [0004] 承认磨损需标定，与磁致伸缩无接触方案不同；速度可调但单段恒速，[0005] 明言不做分段——与三段曲线相反方向；[0009] 自认不含压差检测与预测；人工两步切换，非故障时自动脱开的机械优先机构
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D2 — Magnetostrictive displacement sensor linearization method  ZZ900053A1 (P 编号 P-002)
- 申请人：Cigu Measurement Technology Co.
- 公开年：2021
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900053A1.md#L8：以波导丝上应变脉冲的传播时间测距，量程大、无接触磨损
- 区别点：披露磁致伸缩测距本体与无磨损优点（[0007] 列举闸门开度等应用），但未与阀位反馈结合
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D3 — Online water hammer protection system for water pipelines  ZZ900052A1 (P 编号 P-003)
- 申请人：Anliu Hydraulic Engineering Research Institute
- 公开年：2020
- 命中轴：N3
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900052A1.md#L13：先小行程预收阀位，待压力波衰减后再逐步收至全关
- 区别点：[0005] 压差+变化率预测峰值，与 F3 的预测预收一致
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

