# 对比矩阵（TGT-9001，合成案例金解）

| 维度 \ 对比文件 | D1 | D2 | D3 |
|---|---|---|---|
| **N1：信标发送时刻估计** | ○ | — | — |
| **N2：漂移估计与补偿** | — | ○ | — |
| **N3：动态信标周期** | — | — | ○ |
| **N4：重同步请求** | — | — | — |
| **整体闭合** | ○ | ○ | ○ |

## 每列输出

D1 — Low-power broadcast time synchronization method for sensor networks  ZZ900011A1 (P 编号 P-001)
- 申请人：Chenguang Microelectronics Research Institute
- 公开年：2019
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900011A1.md#L10：汇聚节点在射频开启前的最后一步将本地时刻写入该字段
- 区别点：直接写入而非按队列深度预测修正，手段未完全重叠
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D2 — Dual-message clock drift calibration device  ZZ900012A1 (P 编号 P-002)
- 申请人：Hengshi Precision Instruments Co.
- 公开年：2020
- 命中轴：N2
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900012A1.md#L12：统计时间戳偏差的变化趋势，得到从站晶振相对主站的漂移斜率
- 区别点：有漂移估计与补偿，但手段为双向报文而非信标间隔
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D3 — Listening schedule method for event-driven medium access control  ZZ900013A1 (P 编号 P-003)
- 申请人：Qingwu Communication Technology Laboratory
- 公开年：2021
- 命中轴：N3
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900013A1.md#L13：根据信道占用统计的稳定性决定延长幅度
- 区别点：动态调整的对象是监听间隔而非信标周期，但按稳定性调整的思想一致
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

