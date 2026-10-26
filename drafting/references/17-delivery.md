# 17 · 交付管线（P4）：冻结快照 → 申请文件包 → 交付清单 → 人工签核

> 本文件定义 P4 完整交付：由**同一冻结快照**生成权利要求书/说明书/摘要/附图审阅稿（DOCX，
> 可选 PDF 预览），产出可核验的**交付清单（delivery manifest）**，并由人工**签核**。
> 纪律：产物只能来自冻结模型；任何输入变化都会使旧交付**失效**，必须重建、重新签核。
> `release_ready` 是**内部交付门**，不等于官方受理合规，更不等于"可直接提交"。

## 1. 交付输入（人/AI 提供）

| 输入 | 位置 | 说明 |
|---|---|---|
| 权利要求正文 | `07_drafting/manuscript/claims.md` | 每项权项一行，形如 `1. ...`；编号必须与结构化权项一致 |
| 说明书正文 | `07_drafting/manuscript/specification.md` | 段落以 `[0001]` 起头；支持映射引用的段落必须存在 |
| 摘要 | `07_drafting/manuscript/abstract.md` | 非空 |
| 结构化模型 | `07_drafting/{drafting_plan,claim_atoms,claims_structured,support_mapping,support_review}.json/yml` | P2 |
| 附图规格 | `07_drafting/figures/*.figure.yml` | P3；交付时自动渲染 SVG/PNG |
| 研究门禁快照 | `gates` 计算结果 | 冻结进模型；变化则清单失效 |

稿件正文仍在工作区受控目录，**不进入公开仓库**（保密红线）。

## 2. 命令

```powershell
# 1) 前提：当前写作门必须是 review_draft（P2/P3 全部门禁通过）
python -m patentkit draft status --root .\workspace

# 2) 生成冻结模型 + DOCX 审阅稿（默认 dry-run；--pdf 需本地转换器）
python -m patentkit deliver build --root .\workspace            # dry-run
python -m patentkit deliver build --root .\workspace --apply
python -m patentkit deliver build --root .\workspace --apply --pdf

# 3) 校验：产物哈希、模型是否过期、权项/段落/附图一致性、门禁快照、签核
python -m patentkit deliver check --root .\workspace

# 4) 人工签核（绑定当前清单指纹；清单内容再变则签核自动失效）
python -m patentkit deliver sign --root .\workspace --by inventor --apply

# 5) 内部交付门
python -m patentkit draft gate --to release_ready --by inventor --apply
python -m patentkit deliver status --root .\workspace
```

## 3. 工作区文件

| 文件 | 内容 |
|---|---|
| `11_delivery/patent_document_model.json` | **PatentDocumentModel**：目标/候选、权项、段落、摘要、附图（含 SVG/PNG 哈希）、输入哈希、门禁快照、`model_fingerprint` |
| `11_delivery/artifacts/patent-application.docx` | 审阅稿：权利要求书 / 说明书 / 说明书摘要 / 附图（有 Pillow 时嵌入 PNG） |
| `11_delivery/artifacts/patent-application.pdf` | 可选 PDF 预览；**无转换器时明确不生成**，不伪造 |
| `11_delivery/delivery_manifest.json` | 交付清单：快照、drafting_plan 哈希、门禁状态、artifact_list（路径/格式/SHA-256/生成器/官方状态）、签核（含绑定指纹）、`official_format_status` |
| `11_delivery/validation_report.json` | 本次构建的校验结果、PDF/CNIPA 状态、告警 |
| `11_delivery/cnipa_format_notes.md` | CNIPA XML 研究记录：状态 `not_attempted`（**不是合规声明**） |

## 4. 校验码（`deliver check`）

| 代码 | 级别 | 含义 |
|---|---|---|
| E-001 | error | 尚无交付清单（先 build） |
| E-002 | error | 冻结快照过期：候选/计划/原子/权项/支持映射/稿件/模型指纹任一变化 |
| E-003 | error | 产物缺失或哈希与清单不符 |
| E-004 | error | 稿件权项编号与冻结模型不一致 / 稿件解析失败 |
| E-005 | error | 说明书段落集合与冻结模型不一致 / 支持映射引用段落缺失 |
| E-006 | error | 正文引用了冻结模型中不存在的图 |
| E-007 | error | 研究门禁与冻结快照不一致 |
| E-008 | error | `draft audit` 存在 error（含附图 D-018） |
| E-009 | error | 未签核，或签核指纹与当前清单不匹配 |
| E-010 | error | 清单/模型 schema 违规或 JSON 损坏 |
| E-011 | error | 缺少独权（权项1）或摘要为空 |
| E-012 | error | 清单声称官方工具已验证但没有任何已验证产物（禁止虚假合规声明） |
| W-001 | warn | 交付中没有附图 |
| W-002 | warn | 请求了 PDF 但未生成（无本地转换器） |

## 5. 签核与失效语义

1. **签核绑定清单指纹**：`review_signoff.manifest_fingerprint` = 去掉签核字段后的清单指纹。
   签核后清单任何实质变化（产物、哈希、门禁、快照）都会让签核失效（E-009）。
2. **任何输入变化**（候选/计划/原子/权项/支持映射/稿件/图规格/门禁）→ `deliver check` 报 E-002，
   `draft status` 从 `release_ready` 自动回落到 `concept`（stale）。
3. 改稿流程：改正文/模型 → 重新过 `review_draft` 门 → 重新 `deliver build` → `deliver check` →
   人工重新签核 → 再 `draft gate --to release_ready`。禁止只重签旧清单。
4. `release_ready` 仅表示**内部交付检查通过且有签核**；官方提交格式（CNIPA XML）未验证前，
   不得宣称合规、不得宣称可直接提交。

## 6. 官方格式（CNIPA XML）现状

- 本版本**不实现** CNIPA XML：先按方案 §5.4 完成官方规范调研与官方工具验证，再升级
  `official_format_status`（`not_attempted` → `generated_unverified` → `verified_by_official_tool`）。
- `export_cnipa_xml()` 目前**故意 fail-closed**；清单 `official_format_status` 保持
  `not_attempted`；`deliver check` 的 E-012 防止虚假升级。
- DOCX/PDF 只是内部审阅稿，不是官方电子申请文件。

## 7. 验收自检（交付前）

- [ ] `deliver check` 零 error（E-009 在签核后消失）；
- [ ] 交付清单产物哈希与磁盘文件一致；
- [ ] 权项编号/段落号/图号在模型、稿件、附图三处一致；
- [ ] 研究门禁快照与当前 gates 一致；
- [ ] 人工逐页审阅 DOCX（含附图清晰度、编号、分页），并完成签核；
- [ ] 稿件正文未进入公开仓库；未使用真实专利数据做测试。
