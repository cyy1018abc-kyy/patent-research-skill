# 06 撰写与润色规范

## 稿件在库外（硬性要求）

**稿件正文不进仓库。** 仓库里只放：

- 路径 + `sha256`（`07_drafting/manuscript_registry.yml`）
- 修订台账（`07_drafting/revision_ledger.md`）
- 特征原子表与支持映射表（结构化分析产物）

**为什么**：稿件是最易泄漏的资产，而仓库必须保持可分发（「核心与数据分离」，
见 [04](04-evidence-level-system.md)）。

## 每次改稿的固定动作

```powershell
# 1. 改完稿件后重新绑定 sha256
python -m patentkit attest --apply

# 2. 在 07_drafting/revision_ledger.md 加一行（版本 / 日期 / 改了什么）

# 3. 校验登记表结构
python -m patentkit validate --strict
```

> 忘了 `attest --apply` 时，`attest --check` 会报 sha256 漂移（exit 1）—— 这是好事：
> 说明「登记表指向的文件」和「实际文件」不一致，审阅者可能正看着旧版。
> 多轮改稿的完整纪律（补丁→变更日志→重过门，禁止顺手改无关内容）见
> [13-改稿闭环](13-revision-loop.md)。

## 数值声明必须溯源（A/B/C）

权利要求里的每个数值范围都是法律边界。**未经溯源的数值 = 建立在空气上的权利要求。**
内核 0.3.0 起（V031/V032）：

```powershell
# 1. 扫描稿件生成溯源登记骨架
python -m patentkit provenance scan --manuscript 07_drafting/claims.md --out 07_drafting/numerical_provenance.yml

# 2. 人工为每条数值声明填 sources：
#    A=自产材料（ref 指向工作区文件+locator）
#    B=文献/对比文件（ref 填候选 ID，如 P-012）
#    C=实施例示例（必须 note 显式声明，不得伪装实测）

# 3. 校验（validate 同步生效）
python -m patentkit provenance check
```

三级缺陷与严重度（权项 vs 说明书支持性，由 `claims/numerical_consistency_check.md` 产出）：

| 缺陷 | 示例 | 严重度 |
|---|---|---|
| **超范围**（权项宽于说明书） | 权项 `R_c ∈ 2~6`，说明书 `3.0~5.0` | **最危险**；答复救不回 |
| 端点未披露 | 权项 `0.33~0.45`，说明书只给 0.36 | 中 |
| 完全无支持 | 权项 `λ ∈ 1.05~1.35`，说明书无任何值 | 中 |

**修法二选一**：把权项收窄到已披露范围（安全）；或申请日前补说明书
（只能补概括性说明与典型值，不得新增技术方案）。

> ⚠️ 能不能补由**发明人**判断——取决于该范围是否已有仿真/实验支持。

## 权利要求的三项自检

1. **数值范围须有说明书支持**（见上，最容易漏）。
2. **每条权项映射到说明书段落**：维护 `07_drafting/specification/support_mapping_table.md`，
   给每个原子标注支持段落。标不出来的原子要么补实施例，要么删。
3. **无孤立项**：从属权项必须挂在某独立权项下，附加特征不得与被引权项矛盾。
   撰写方法详见 [10-权利要求撰写](10-claim-drafting.md)。

## 有益效果必须可追溯

`G-D-01` 硬性要求：**每条有益效果必须对应 `04_comparative_analysis` 中某个 D 列的差异。**
对不上号的效果，要么没对比过，要么本身站不住。

| 可接受 | 不可接受 |
|---|---|
| 「分级排放使氧排放损失 1.86→0.44 mol/600s（-77%）」 | 「提高了效率」 |
| 「负载阶跃下供氧响应 0.19→0.05 s（3.8 倍）」 | 「响应更快」 |

## 公式渲染

| 错 | 对 | 原因 |
|---|---|---|
| `n_{in}^{hat}` | `\hat{n}_{in}` | 上标里的文字会按字面渲染成 "hat" |
| 裸 `%` | `%%`（部分工具的参数解析） | 被当成格式占位符 |

改公式后**逐条预览**，不要只看源码。

## 交稿前清单

```powershell
python -m patentkit check          # validate --strict + gates
python -m patentkit attest --check
python -m patentkit provenance check
python -m patentkit figures check
```

- [ ] 五门全 PASS（`verified` 列）
- [ ] `validate` 0 error / 0 warn
- [ ] `attest --check` 通过（无 sha256 漂移）
- [ ] 每个权项数值有说明书支持，且数值溯源登记（A/B/C）全覆盖
- [ ] 每条有益效果映射到具体 D 列
- [ ] 附图标记与正文双向一致（V033 无告警或已人工复核）
- [ ] 修订台账有新行
