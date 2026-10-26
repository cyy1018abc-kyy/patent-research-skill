# 对比矩阵（TGT-9003，合成案例金解）

| 维度 \ 对比文件 | D1 | D2 | D3 | D4 |
|---|---|---|---|---|
| **N1：车道分配** | ○ | ○ | — | — |
| **N2：本地避让** | — | — | ● | — |
| **N3：路口预约** | — | ○ | ○ | — |
| **N4：失效重分配** | — | — | — | ● |
| **整体闭合** | ○ | ○ | ○ | ○ |

## 每列输出

D1 — Urban road lane assignment system  ZZ900031B1 (P 编号 P-001)
- 申请人：Tongqu Smart Traffic Co.
- 公开年：2017
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900031B1.md#L13：当某一车道的实时拥堵度超过阈值时，系统将后续请求车辆优先分配至相邻较空车道
- 区别点：有拥堵度分配；无任务优先级维度，且场景为城市社会车辆（[0009] 自认不适用 AGV）；[0008] 固定配时信号灯，不涉及路口通行权管理
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D2 — AGV central scheduling system  ZZ900032A1 (P 编号 P-002)
- 申请人：Cangji Logistics Equipment Co.
- 公开年：2019
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900032A1.md#L10：按任务优先级从队列中取出任务，分配给空闲的自动导引车执行；02_search_logs/raw/ZZ900032A1.md#L15：信标灯按固定时序轮询放行各方向
- 区别点：有任务优先级；车道分配按固定路径（[0005]）且不考虑实时车辆密度（[0008]），拥堵度维度缺失；存在路口通行权管理，但为固定时序轮询，非预约-分配通行窗口；[0010] 故障任务等待人工恢复
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D3 — AGV autonomous obstacle avoidance control device  ZZ900033A2 (P 编号 P-003)
- 申请人：Xingwen Robotics Technology
- 公开年：2020
- 命中轴：N2
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900033A2.md#L10：障碍物进入制动包络时本地自主减速停车，全过程不依赖中央控制器；02_search_logs/raw/ZZ900033A2.md#L14：通行请求按收到顺序排队轮询处理，同一时刻仅放行一个方向，请求本身不携带预计占用时长
- 区别点：有请求-放行交互，但按序轮询、无互不冲突通行窗口的分配
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D4 — Robot swarm task reassignment method  ZZ900034A1 (P 编号 P-005)
- 申请人：Qunli Intelligent Equipment Research Institute
- 公开年：2021
- 命中轴：N4
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900034A1.md#L12：未完成任务按优先级排序后，重新分配至当前任务量最少的在役机器人
- 区别点：见评估记录
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

