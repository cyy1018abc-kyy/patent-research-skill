# Patent Research Skill 4.3.0（撰写交付线：实用新型优先 + 正文一致性校验 + 正文骨架；kernel 0.11.0）

Requires **patentkit 0.11.0, assessment protocol 1**, Python 3.11+。内核 **0.10.0 → 0.11.0**
（需重装内核 wheel）。扩展 `patent_intel` 本轮**无变化**（0.3.0 延续）。

## 什么变了

本轮把重点从检索线转到**撰写交付线**，并优先打通**实用新型**场景
（方案：`docs/4.3-drafting-delivery-plan.md`，里程碑 M1 + M2 + M3）：

- **申请类型与权项类别**（内核契约，向后兼容，schema_version 仍 1.0）：
  `drafting_plan.application_type`（`invention` | `utility_model`，缺省=发明）、
  `drafting_plan.abstract_figure`（摘要附图 `FIG-n`）、`claim.claim_category`
  （`product` | `method` | `use`，从属权项未声明时继承所引权项）。
  `draft plan --type utility_model`：附图需求改为结构示意图，**不再生成方法流程图需求**；
  实施例要求写明形状、构造、位置与连接关系。`draft status` 显示申请类型。
- **G-D 审计码 D-020…D-025**：实用新型方法/用途类权项（含继承）error；实用新型独立
  权项未声明 `product` error；实用新型无附图需求、或附图全为流程图/状态机 error；
  原子措辞疑似方法/材料/软件特征 **warn**（由人判断）；从属权项类别与所引权项不一致
  error（全部类型）；摘要附图指向不存在的图 error（全部类型）。
- **人工绘制的结构附图**：新图型 `external_drawing`——`figures import` 导入 PNG 线条图并以
  SHA-256 钉住，`--parts` 登记全部附图标记；`figures review` 人工看图确认，**绑定文件哈希+
  标记清单**（改图或改标记即失效）。F-015（文件缺失/非 PNG/被改动）、F-016（未确认/过期）。
  `figures plan` 遇到结构/剖视/立体等视图需求**不再自动生成框图冒充**，只列入 `needs_import`。
- **交付门**：E-013（实用新型无附图）、E-014（实用新型未指定摘要附图或摘要附图不在交付件中；
  声明了申请类型的发明为 W-003 warn）、E-015（外部附图交付后被改动或失去确认）；外部附图按
  文件哈希冻结进 PatentDocumentModel，未确认的外部附图 `deliver build` 直接拒绝。
  DOCX 首行写「实用新型名称/发明名称」，并单列「摘要附图」。
- **零迁移承诺**：未声明 `application_type` 的旧计划重建出的文档模型**逐字节一致**
  （同一工作区新旧内核 model_fingerprint 相同，回归测试锁定），已签核交付不会因升级失效。
- **正文一致性校验 `draft lint`（M2，新模块 `manuscript_lint.py`）**：稿件正文 ↔ 结构化模型与形式要求，
  M-001…M-015——编号与结构一致、从属权项引用语↔`parent_claim_no`、段落号、说明书五部分标题、
  摘要 ≤300 字、名称 ≤25 字（warn）、含糊用语（warn）、先行基础启发式（warn）、附图标记括注（warn）
  与标记冲突（error）、主题词与申请类型（warn）、附图说明逐图覆盖（error）、权项引用附图（warn）、
  权项句号。error 阻塞交付：`deliver build` 拒绝构建，`deliver check` 报 **E-016**；启发式一律 warn。
- **正文骨架 `draft render`（M3，新模块 `manuscript_render.py`）**：由结构化模型生成权利要求书（编号、
  从属引用语取自 `parent_claim_no`、原子文本原样）、说明书（五部分标题按申请类型、连续段落号、每项权项
  一段技术方案、附图说明逐图取自附图规格、每图部件与附图标记清单）与摘要骨架；模型里没有的内容一律留
  `【待补：…】` 空槽——**不编造技术内容**；lint 新增 **M-016**（未填空槽 = error，交付拦截）。实用新型
  计划主题像方法时权项主题渲染为「产品名称」空槽。已有稿件不覆盖（需 `--force`）。同时写出支持映射建议
  `07_drafting/render/support_suggestion.json`（仍须 import + 人工复核）。内核测试锁定「骨架填空后 lint 零发现」。
- **撰写基准（M0 首批）**：`benchmarks/drafting/` 四个合成案例（实用新型/发明各一份干净稿 + 缺陷注入稿，
  共 24 个注入缺陷，覆盖 M-002…M-016）；`tools/score_drafting.py --gate perfect` 入 CI——
  全部检出且零误报；`tests/test_drafting_benchmark.py` 受控破坏防橡皮图章。
- **方法论**：新增 `drafting/references/20-utility-model.md`、`21-manuscript-lint.md`、`22-manuscript-render.md`（中英镜像）；
  SKILL.md 硬约束 13、D1/D7/D8 接线、触发短语；14/16/17 号文档补码表；evals +4 用例（49→53）；术语锚定 +3。
- 测试：内核 801 passed（0.10.0 时 753；新增 `test_utility_model.py` 25 例、`test_manuscript_lint.py` 12 例、`test_manuscript_render.py` 11 例）。

## 安装与迁移

安装器清单、manifest schema 2、双 zip 结构不变（全量包含四个技能）。已有用户：重装技能包
与 **0.11.0 内核 wheel**；扩展无需重装。规则表 V001–V038 不变，评估协议 1 不变；工作区无需迁移。

## 边界（与上一版一致）

- 本技能产出底稿与判定辅助，不构成法律意见；不预测授权；实用新型客体结论由代理师确认
  （D-020/D-021 基于声明的类别，D-023 只是措辞提醒）；
- 法规口径只引用能核对的出处（专利法第 2 条第 3 款、审查指南第一部分第二章），不臆造细则条号；
- CNIPA XML 官方格式仍未实现（`official_format_status` 维持 `not_attempted`）；
  `release_ready` 只是内部交付门，不得宣称「可直接提交」；
- CNIPA/OPS 在线来源维持 `partial`。
