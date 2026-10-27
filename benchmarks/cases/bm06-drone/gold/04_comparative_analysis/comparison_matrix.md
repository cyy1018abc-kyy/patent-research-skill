# 对比矩阵（TGT-9006，合成案例金解）

| 维度 \ 对比文件 | D1 | D2 | D3 | D4 |
|---|---|---|---|---|
| **N1：灯色时序分配** | ○ | — | — | — |
| **N2：失效动态补位** | — | ● | — | — |
| **N3：越界就近降落** | — | — | ● | — |
| **N4：节拍对齐** | — | — | — | ● |
| **整体闭合** | ○ | ○ | ○ | ○ |

## 每列输出

D1 — UAV formation flight animation generation system  ZZ900061A1 (P 编号 P-001)
- 申请人：Tianmu Formation Technology Co.
- 公开年：2020
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900061A1.md#L11：地面站为每架无人机生成随坐标序列同步的变化指令表
- 区别点：分配的是变化指令表而非灯色时序表，且 [0008] 自认不涉及灯光载荷；[0006] 失效后剩余飞机原位不动、缺口人工评估——与动态补位相反；[0007] 越界执行自动返航，不是就近垂直降落
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D2 — Cooperative replacement method for plant protection UAV swarm  ZZ900062A1 (P 编号 P-002)
- 申请人：Woye Agricultural Equipment Co.
- 公开年：2021
- 命中轴：N2
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900062A1.md#L12：邻近的完好作业机按实时相对位置就近认领待分配条带
- 区别点：补位对象是作业条带而非表演位形，机制相同
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D3 — Geofence flight restriction device for civil UAVs  ZZ900063A1 (P 编号 P-004)
- 申请人：Qiongjie Flight Safety Technology Co.
- 公开年：2019
- 命中轴：N3
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900063A1.md#L13：飞控立即接管并在本机正下方就近实施垂直降落
- 区别点：与 F3 的越界就近降落一致；区别仅在触发场景为禁飞区而非表演区
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D4 — Stage lighting and music beat synchronization system  ZZ900064A1 (P 编号 P-005)
- 申请人：Shengguang Stage Equipment Co.
- 公开年：2018
- 命中轴：N4
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900064A1.md#L11：时序引擎按节拍时间轴排布灯效队列，使每次灯光颜色与亮度变化落在节拍点上
- 区别点：节拍对齐手段完整披露，但载体是地面舞台灯（[0007]），无无人机
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

