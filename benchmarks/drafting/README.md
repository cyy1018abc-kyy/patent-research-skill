# 撰写正文一致性基准（drafting benchmark，4.3 / M2）

衡量内核 `draft lint`（`patentkit.manuscript_lint`，交付门 E-016 同一实现）在**合成**稿件上的
检出率与误报。规则只在内核实现一次；评分器 `tools/score_drafting.py` 只做「实际发现 ↔ 期望清单」比对。

## 案例

| 案例 | 类型 | 内容 | 期望 |
|---|---|---|---|
| `dm01-um-clean` | 实用新型 | 结构完整、引用正确、标记括注、五部分齐全 | 零发现（任何级别都算误报） |
| `dm02-um-defects` | 实用新型 | 在 dm01 上逐项注入 13 个正文缺陷 | 13 条 |
| `dm03-inv-clean` | 发明 | 系统 + 方法独立权项（方法引用系统）、单引用从属 | 零发现 |
| `dm04-inv-defects` | 发明 | 编号不符、无引用语、多项引用、缺句号、主题词错用、不存在的图、段落重号、标记冲突、未填骨架空槽 | 11 条 |

所有案例都是合成材料，不得放入真实申请稿件（保密红线，`tools/check_no_workspace_data.py` 守卫）。

## 案例格式（`cases/<id>.yaml`）

```yaml
id: dm01-um-clean                 # 必须与文件名一致
application_type: utility_model   # invention | utility_model
title: 一种卡扣式储物盒
structured_claims: [{claim_no: 1, claim_type: independent, parent_claim_no: null}, ...]
figures: [{figure_id: FIG-1, parts: [{label: 壳体, mark: "1"}, ...]}]
claims: |            # 与 07_drafting/manuscript/claims.md 同格式
specification: |     # [0001] 段落号 + 独立成行的五部分标题
abstract: |
expected:            # 每个注入缺陷一条；干净稿为 []
  - {code: M-003, path: claims/2}
```

比对按 `(code, path)` 集合进行；同一位置同一代码的多条消息合并为一条。

## 运行

```bash
python tools/score_drafting.py --suite benchmarks/drafting/cases                 # 报告
python tools/score_drafting.py --suite benchmarks/drafting/cases --gate perfect  # CI 门
```

`--gate perfect`：全部注入缺陷检出且零误报。`tests/test_drafting_benchmark.py` 做受控破坏
（删期望 → 误报、伪造期望 → 漏检、干净稿注入缺陷 → 检出），防止评分器沦为橡皮图章。

## 扩充纪律

- 新增 lint 规则时，同时补一个注入该缺陷的案例，并保证两个干净稿仍为零发现；
- 不为通过门而修改期望：漏检或误报说明规则需要修正，修正后两侧干净稿必须仍然干净。
