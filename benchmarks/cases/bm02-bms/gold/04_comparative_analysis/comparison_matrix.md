# 对比矩阵（TGT-9002，合成案例金解）

| 维度 \ 对比文件 | D1 | D2 | D3 |
|---|---|---|---|
| **N1：单体电压巡回采样** | ● | — | — |
| **N2：均衡开启时机** | — | ○ | — |
| **N3：占空比温度修正** | — | — | — |
| **N4：采样复用与余热利用** | — | ○ | ○ |
| **整体闭合** | ○ | ○ | ○ |

## 每列输出

D1 — Distributed battery balancer  ZZ900021A1 (P 编号 P-001)
- 申请人：Xuneng Power Systems Co.
- 公开年：2019
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900021A1.md#L11：每五十毫秒完成一轮全部电芯的电压巡回采样
- 区别点：[0007] 明确"全过程均可执行"，与"仅恒压阶段"相反；[0008] 占空比固定为二分之一，无温度修正；[0009] 热量自然散失，未用于预热
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D2 — Charging management and auxiliary task scheduling chip  ZZ900022A1 (P 编号 P-002)
- 申请人：Xinyuan Electronics Technology Co.
- 公开年：2021
- 命中轴：N2
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900022A1.md#L17：在恒压阶段，充电电流纹波对高精度采样的干扰最小，适合安排精密测量类任务；02_search_logs/raw/ZZ900022A1.md#L15：调度器暂停该窗口内的电压巡回采样，待任务完成后恢复巡回节拍
- 区别点：披露了恒压阶段启动重负载辅助任务的时机原理，但未提及均衡；暂停巡回+ADC 分时复用的机制在 [0009]/[0010] 披露，但服务于辅助测量任务而非均衡支路电流
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D3 — Battery preheating device for low temperature environment  ZZ900023A1 (P 编号 P-004)
- 申请人：Cold Region Vehicle Electrical Research Institute
- 公开年：2020
- 命中轴：N4
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900023A1.md#L13：加热元件采用正温度系数热敏电阻片，直接贴附于电芯侧面
- 区别点：[0004] 采集的是温度而非端电压；披露了贴附电芯的电阻加热，但为独立 PTC 回路而非均衡电阻余热经导热件传导
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

