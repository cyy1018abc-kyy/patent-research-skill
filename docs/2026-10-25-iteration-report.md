# 2026-10-25 升级迭代验收报告（skill 2.5.0 / kernel 0.3.0）

> 依据：`../升级迭代清单-2026-10-25.md`（P0×4 / P1×8 / P2×8，共 20 项）。
> 原计划的 2.5/2.6/2.7/2.8 四个版本节奏合并为**一次配对发布**（2.5.0 + 0.3.0），
> 以便一轮完整验证。每项的证据都可复现。

## 一、验证总览（全绿）

| 验证 | 结果 | 复现命令 |
|---|---|---|
| 内核全量测试（开发树） | **503 passed / 9 skipped / 0 failed** | `python -m pytest tests regression_tests`（于 `../patentkit/`） |
| 内核全量测试（CI 路径=补丁树） | **503 passed / 9 skipped** | `python -m pytest kernel-build/patentkit-0.1.2/{regression_tests,tests}` |
| 补丁可应用性（CI 等价） | ✅ 对纯净 0.1.2 解包 `git apply` 成功，含全部新模块 | 见 `release/patches/patentkit-0.1.2-to-0.3.0.patch` |
| 仓库发布验收（unittest） | **11 tests OK / 2 skipped（Linux-only）** | `python -m unittest discover -s tests -v` |
| evals / 术语 / 保密守卫 | ✅ 三项全过 | `python evals/validate_evals.py` 等 |
| 端到端冒烟（隔离 venv） | ✅ 发布 zip + 0.3.0 wheel → `self_test.py` **6/6**（含 docx） | 见 §三 |
| 语法检查（CI 等价） | ✅ compileall + `bash -n install.sh` | — |

## 二、逐项完成情况

### P0（质量工程）

| # | 事项 | 交付物 | 验证 |
|---|---|---|---|
| 1 | 触发评测集 | `evals/evals.json`（14 例：trigger×6 / boundary×4 / refusal×3 / format×1）+ `evals/validate_evals.py` + `evals/README.md`；CI 新步骤 | validate_evals 通过；**触发短语逐字锚定 SKILL.md description**；⚠️ 前缀与结果格式五项均有覆盖断言 |
| 2 | self_test 自检 | `patent-research-skill/scripts/self_test.py`（六项：Python/内核/封装/合成样例/正用例 validate 通过/反用例 门不全 PASS + docx 冒烟） | 隔离 venv 实测 6/6，exit 0 |
| 3 | 保密红线 | `.gitignore` 红线段（`/0?_*/`、`专利申请/`、`交付文本/`、`workspace.yml`、`*.docx/doc/pptx`）+ `tools/check_no_workspace_data.py`（CI 步骤） | 守卫通过；对工作区标记/数据目录/稿件文件三类均有拦截逻辑与误报处理说明 |
| 4 | 中文主版本 | `SKILL.md`（2.5.0，中文）+ `references/01–13 + glossary.md`（中文）+ 资产模板中文化 + `agents/openai.yaml` 双语；英文镜像入 `references.en/`（SKILL.en.md 已同步 2.5.0） | 术语一致性检查通过；发布包内 14 篇 references 全在；测试断言 `version: 2.5.0` |

### P1（能力延伸）

| # | 事项 | 交付物 | 验证 |
|---|---|---|---|
| 5 | DOCX 查新报告 | 内核 `export.py`（`patentkit export-docx`，可选 `[docx]` extra）+ `scripts/export_docx.py` | 测试断言门禁表/D 列/免责声明逐字来自工作区；隔离 venv 冒烟产物 smoke.docx |
| 6 | 数值 A/B/C 溯源 | 内核 `provenance.py`（scan/check）+ V031/V032 接入 validate | fail-closed 测试：无来源→error；B 级引用未知候选→error；C 级须显式声明 |
| 7 | 附图基线 | 内核 `figures.py`（check/draw：标记双向一致性 V033 warn + 确定性 SVG 框图）+ `references/08-figures.md` | 双向误配测试（图有正文无 / 正文有图无均报 warn）；SVG 无外链断言 |
| 8 | 交底/权要方法论 | `references/09-disclosure-drafting.md`（五段式+细则 20–23 映射+说不清清单）、`10-claim-drafting.md`（零披露原子/数值层从权/自检） | SKILL 该用/不该用表与 references 09 边界互引；evals R1/R2 锁定边界行为 |
| 9 | 检索数据源扩展 | `docs/data-sources.md`（BigQuery/OPS/pqai 评估 + MCP 维持冻结决策 + 新源五条验收标准） | 决策文档；MCP 工具数不变（冻结条款未被破坏） |
| 10 | 双语术语表 | `references/glossary.md`（中⇄英 60+ 条）+ `evals/check_terminology.py`（CI） | 校验通过：01–07 双侧配对完整、13 个核心锚定术语两侧均在用 |
| 11 | 证据账本强化 | 内核 `ledger.py`（账本视图）+ V034（结论引用账本外编号 → error） | 测试：引用 P-907（不存在）→ V034 error；合法引用 P-001 → 无 finding |
| 12 | OA 答复骨架 | `references/11-oa-response.md`（拆条表/三层反向论证/修改走 13 闭环/期限先看台账） | 与 ledger/deadlines/13 号文档互链；边界（不预测授权）入文 |

### P2（大版本方向）

| # | 事项 | 交付物 | 性质 |
|---|---|---|---|
| 13 | 多技能矩阵拆分 | `docs/skill-matrix-plan.md`（三方案对比、推荐 C、六项配套、**三个待拍板决策点**） | 设计文档（按清单约定留待立项） |
| 14 | 专利地图 | 内核 `map.py`（离线自包含 HTML：门禁表/每轴三列覆盖条/D 列） | **已实现**；测试断言无 `<script`/无外链 |
| 15 | 政策雷达 | `references/12-policy-radar.md` + `docs/policy-log.md`（登记格式+「待改未改=未处理」纪律） | 人工核查清单（不联网，保密边界内） |
| 16 | 多轮改稿闭环 | `references/13-revision-loop.md`（补丁→日志→attest→重过门→失效重确认；三硬规则+轮数上限） | 与内核 attest/fingerprint 机制（2.4.0 已有）显式整合 |
| 17 | 期限台账 | 内核 `deadlines.py`（PRESETS：申请费 2 月/实审 3 年/OA 4+2 月/年费周年；list/check/init） | **已实现**；测试：月份钳制、逾期/临期/缺 base_date 拒算（fail-closed）、done 剔除 |
| 18 | 1+N 布局 | 内核 `layout.py`（跨目标候选/角色/等级/空轴/通过门总览 + 主件建议；verified=0 时**拒绝排名**） | **已实现**（只读） |
| 19 | 软著/侵权联动 | `docs/scope-decisions.md`（两项均**默认不做**的理由 + 解冻条件 + evals R2 锁定） | 决策记录（按清单「不建议做」执行） |
| 20 | 生态分发 | `docs/distribution-checklist.md`（四市场要求/已备项/待办=脱敏截图；诚实边界话术）+ `docs/example-walkthrough.md`（合成数据真实输出的走查） | 准备完成；上架动作本身待所有者确认 |

## 三、端到端冒烟记录（2026-10-25，Windows / Python 3.12.14）

```
隔离 venv：pip install patentkit-0.3.0-py3-none-any.whl python-docx
发布包：patent-research-skill-v2.5.0.zip（解压后）
> python pkg/patent-research/scripts/self_test.py
  [OK] python 3.12.14 / [OK] patentkit 0.3.0 (protocol 1)
  [OK] sample_workspace / [OK] validate_clean_sample: 0 error 0 warn
  [OK] gates_empty_sample_not_pass（反用例） / [OK] export_docx_smoke
  结果：6/6 通过，exit 0
```

## 四、本轮修正的既有问题（顺带，均已入 CHANGELOG/补丁）

1. **sdist 内核测试套件不可运行**：`tests/conftest.py` 未随包分发，12 个测试文件全部
   无法收集。已重建 conftest（fixture API 从用例反推），并把与 0.2.0 评估协议语义
   过时的 17 处断言同步到现行口径（is_reviewed=G-S 判定合格性、G-S-03 人工确认等），
   私有仓库布局依赖的 9 个测试改为模块级跳过——CI 现在跑**全量** 503 项而不只是
   31 项回归。
2. **模板 glossary 字段名错位**：模板用 `title_zh`，registry 读 `name_zh`，
   `init` 出来的轴名在 Terminology 里恒为空。已在补丁中把模板统一为 `name_zh/name_en`。
   （位于 patch 的 templates 变更内。）
3. CI 里 wheel glob/SHA256SUMS 曾残留 0.2.0 引用（升级时静默漏改），已随本次全量
   版本配对扫描清除；`grep 0.2.0|2.4.0` 全仓复核通过（历史文档除外）。

## 五、遗留与建议（不阻塞验收）

1. **发布**：所有产物在 `dist/`（zip+wheel+sdist+SHA256SUMS）。推送 main 后 CI 会
   重新构建并发布配对 Release（本地未做 git commit/push，按仓库纪律留给所有者）。
2. references 08–13 + glossary 的英文镜像暂缺（references.en/README 已声明），
   翻译后加入 check_terminology 的锚定表即可。
3. P2-13 的三个决策点（拆分方案/时间窗/OA 是否并入 drafting）待拍板。
4. 分发清单唯一待办：走查文档配一张脱敏终端截图。
