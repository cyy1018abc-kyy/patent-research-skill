# 对比矩阵（TGT-9004，合成案例金解）

| 维度 \ 对比文件 | D1 | D2 | D3 |
|---|---|---|---|
| **N1：版面分割** | ● | — | — |
| **N2：单字候选识别** | ○ | ○ | — |
| **N3：上下文重排序** | ○ | — | — |
| **N4：低置信回传标注** | — | — | ● |
| **整体闭合** | ○ | ○ | ○ |

## 每列输出

D1 — Template matching recognition method for ticket images  ZZ900041A1 (P 编号 P-001)
- 申请人：Wentong Information Processing Institute
- 公开年：2018
- 命中轴：N1
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900041A1.md#L10：对二值化图像按行、列统计墨点密度，投影谷点即文本行与列的边界；02_search_logs/raw/ZZ900041A1.md#L11：按相似度打分并输出得分最高的若干候选字及对应分值；02_search_logs/raw/ZZ900041A1.md#L12：命中词条的字段按词库校正
- 区别点：有候选打分，但识别器是模板匹配而非轻量卷积网络；有上下文校正，但为词库匹配而非语言模型重排序
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D2 — End-to-end scene text recognition device  ZZ900042A1 (P 编号 P-002)
- 申请人：Shijie AI Laboratory
- 公开年：2020
- 命中轴：N2
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900042A1.md#L13：整行识别准确率优于主流分切方法
- 区别点：[0006] 端到端整行识别，无显式版面切分；同为网络识别，但整行输出、无单字 Top-K 候选（[0006]）
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

D3 — Human annotation feedback system for recognition models  ZZ900043A1 (P 编号 P-003)
- 申请人：Zhongzhi Data Service Co.
- 公开年：2021
- 命中轴：N4
- 关系：部分重叠
- 关键段落：02_search_logs/raw/ZZ900043A1.md#L11：截留样本进入人工标注队列，标注员在标注界面上给出正确结果并提交
- 区别点：[0006] 增量更新与自动回归测试补全闭环
- 来源等级：verified（raw/ 与全文齐备）
- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）

