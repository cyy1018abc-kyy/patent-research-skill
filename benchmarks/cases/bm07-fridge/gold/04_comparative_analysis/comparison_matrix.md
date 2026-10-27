# 对比矩阵（TGT-9007，合成案例金解）

| 维度 \ 对比文件 | D1 | D2 | D3 |
|---|---|---|---|
| **N1：密封抽屉与均流膜** | ● | — | — |
| **N2：乙烯自动分解** | — | ○ | — |
| **N3：双参数独立调节** | ○ | — | — |
| **N4：开门保冷阀** | — | — | ● |
| **整体闭合** | ○ | ○ | ○ |

## 每列输出

D1 — Zero-degree fresh-keeping drawer with flow-equalizing membrane  ZZ900071A1 (P 编号 P-001)
- 申请人：Xiansu Home Appliance Research Institute
- 公开年：2019
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900071A1.md#L10：抽屉进气口安装微孔均流膜，把点式送风分散为面式微流；02_search_logs/raw/ZZ900071A1.md#L12：湿度调节为单参数：抽屉内湿度传感器读数低于设定值时，开启水盒补湿风路
- 区别点：密封抽屉见 [0003]；[0007] 自认不做氧浓度控制、不设分解模块；只有湿度单参数，无氧浓度独立气路；[0008] 开门仅靠密封唇条被动保温，无主动保冷阀
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D2 — Ethylene catalytic decomposition device for refrigerated cabinets  ZZ900072A1 (P 编号 P-002)
- 申请人：Jiexian Environmental Technology Co.
- 公开年：2020
- 命中轴：N2
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900072A1.md#L12：乙烯浓度超过启动门限时接通紫外灯珠，浓度回落到停止门限以下后断开
- 区别点：按浓度自动启停的机制相同，但为独立装置而非冰箱内嵌（[0007]）；[0008] 自认不调节湿度与氧浓度
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D3 — Air damper delay closing mechanism for freezers  ZZ900073A1 (P 编号 P-003)
- 申请人：Ningshi Refrigeration Equipment Factory
- 公开年：2021
- 命中轴：N4
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900073A1.md#L12：本机构在开门后让风门保持开启一段延时
- 区别点：[0009] 自认不涉及气体成分调节；[0007] 延时结束后关闭并形成独立保冷空间，与 F4 的开门延时关闭保冷一致；对象为整柜送风非抽屉独立阀
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

