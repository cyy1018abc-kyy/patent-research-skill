# 对比矩阵（TGT-9008，合成案例金解）

| 维度 \ 对比文件 | D1 | D2 | D3 |
|---|---|---|---|
| **N1：电流纹波判别** | ● | — | — |
| **N2：逐层成像比对** | — | ● | — |
| **N3：缺陷回退重打** | — | — | ○ |
| **N4：样本入库更新** | — | — | — |
| **整体闭合** | ○ | ○ | ○ |

## 每列输出

D1 — Extruder motor current anomaly monitoring method  ZZ900082A1 (P 编号 P-001)
- 申请人：Luoxuan Extrusion Technology Institute
- 公开年：2021
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900082A1.md#L9：在挤出机电机驱动器上取样电流信号，按打印频率段做带通滤波提取纹波
- 区别点：判别输出见 [0005]（断丝/堵料三类）；[0008] 自认不涉及层图像或切片比对；[0006] 判别异常仅输出告警由人工停机；[0007] 特征库由厂商离线统一发布，非在线自动入库
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D2 — Online layer image quality inspection device for printing  ZZ900081A1 (P 编号 P-002)
- 申请人：Zengcai Visual Technology Co.
- 公开年：2020
- 命中轴：N2
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900081A1.md#L11：把层图像与切片软件导出的预览图逐层比对，输出轮廓偏移量与缺陷标记
- 区别点：[0008] 自认不采集挤出机电机信号；[0006] 检出缺陷报警并暂停、等人工处置，不回退重打；[0007] 层图像仅按时间存档供追溯，无样本入库更新机制
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D3 — Power-failure resume printing control device  ZZ900083A1 (P 编号 P-003)
- 申请人：Hengceng Intelligent Manufacturing Equipment Co.
- 公开年：2019
- 命中轴：N3
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900083A1.md#L13：续打的触发条件是断电事件，本装置不具备任何缺陷检测能力
- 区别点：按层号续打的机械与记录手段（[0003]/[0004]）可复用，但触发是断电而非缺陷回退
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

