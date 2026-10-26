# Patent Research Skill 3.5.0 — P0–P4 upgrade (three skills, structured drafting, figures, delivery)

Requires **patentkit 0.7.0, assessment protocol 1**, Python 3.11+.

## 什么变了

本版把 P0–P4 升级方案（`docs/patent-skill-upgrade-implementation-plan.md`）作为一条本地开发线
集成进发布链。G-S-01～05、证据三级、assessment protocol 1、V001–V037 与
`revise`/`provenance`/`attest`/`ledger` 语义**保持不变**；新增能力均为叠加，内核版本升到 0.7.0。

- **P0 · 版本化契约与非破坏性迁移**：`patentkit/contracts.py`（12 类数据契约、canonical JSON
  指纹、path confinement）；`patentkit/workspace_upgrade.py`（`upgrade check/apply` 只新增
  `10_discovery/`、`11_delivery/` 等目录，不改旧数据；旧工作区原样可用）。
- **P1 · patent-discovery 第三技能**：材料登记（`intake`：SHA-256 + locator + 解析缓存）、
  技术事实库/专利候选（`discovery`：G-I-001…025 控制层）、人工确认绑定内容指纹（改内容旧确认
  自动失效）、研究交接（`discovery handoff`，G-I 未过则 fail-closed）；公开技能载荷新增
  `discovery/`（中英双语 references 00–03 + glossary），全量包与安装器支持三技能。
- **P2 · 结构化撰写**：`draft` 管线（DraftingPlan → ClaimAtom → Claim → SupportMapping，
  G-D 审计 D-001…D-017；原子确认绑定内容指纹，D-017 拦截「自称已确认」）；
  `concept → review_draft` 双状态写作门（要求 G-S-01/02/03 PASS、审计零 error、原子/支持映射
  人工确认、候选指纹当前；模型包裹指纹失效自动回落）；`draft impact` 改稿影响传播。
- **P3 · 专业附图**：`figures plan/render/validate`（系统框图/方法流程图；确定性黑白 SVG，
  同规格字节一致 + 黄金快照回归；可选 300-DPI PNG；F-001…F-014 图文一致性检查，复用 V033
  标记核对；渲染器不得创造/删除部件）。
- **P4 · 完整交付**：`deliver build/check/sign/status`（冻结 PatentDocumentModel → DOCX 审阅稿
  + 可选 PDF 预览 → delivery manifest（SHA-256 交叉校验）→ 人工签核绑定清单指纹）；
  `draft gate --to release_ready`；**CNIPA XML 未实现**：`official_format_status=not_attempted`，
  E-012 拦截虚假合规声明；DOCX/PDF 仅为内部审阅稿，不得宣称「可直接提交」。

**技能侧同步**：drafting 新增 14–17 号参考文档（结构化撰写、权项原子/支持映射、专业附图、
交付管线，中英镜像）+ SKILL 硬约束 9–12；evals 扩到 33 例 / 3 技能（含 review_draft 门禁、
文本生图、提交声明拒绝用例）；术语表新增 12 组锚定术语；发布工程支持三技能与 0.7.0 内核配对。

**升级步骤（已有用户）**：

1. 安装 `patentkit-0.7.0-py3-none-any.whl`（技能封装层会拒绝旧内核）；
2. 覆盖安装技能包（`--force`）；三技能会同时安装 patent-research / patent-drafting /
   patent-discovery；
3. 旧工作区先跑 `python -m patentkit upgrade check`（只读），再 `upgrade apply` 增加
   `10_discovery/`、`11_delivery/` 目录；G-S 结论与旧数据不变；
4. 旧工作区无需 `migrate` 即可继续检索；要使用 discovery/draft/deliver 时按
   `upgrade apply` 的清单补齐新目录。

**发布范围**：本地发布集成产物，**未推送远端、未创建 GitHub Release**。发布前需人工复核
`release/notes/`、版本配对与安装验收记录。
