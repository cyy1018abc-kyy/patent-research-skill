# 来源与判断分离：实施与验证记录

日期：2026-10-23。范围：仅实施已确认的第一点，不调整检索数量阈值、时间窗或数据库访问策略。

## 交付结构

- 当前仓库：Skill 2.4.0 开发版，分支 `feat/source-assessment-separation`。
- 相邻 `../patentkit/`：从公开 patentkit 0.1.2 源码包派生的内核 0.2.0，本地实施，不将内核复制进技能仓库。
- 相邻 `../deliverables/`：wheel、sdist、技能源码 ZIP、两份补丁与 SHA256SUMS。
- 相邻 `../_verification/`：隔离安装环境、合成工作区、安装验证 JSON 与构建日志。
- 公开复现入口：`release/patches/` 包含内核完整补丁与复现说明；CI 从核验过哈希的公开源码包应用补丁并运行 31 项新回归。

内核原始源码包 SHA-256：`5ab1ff6e6387c1b6f30e8e084b0da88d93bf71426e9cb901158562d9b52aae14`，已与公开 Release 校验文件核对。

## 已落实的规则

| 要求 | 实现落点 |
|---|---|
| 来源等级保持独立 | 保留 evidence_level，assessment 导入不修改来源字段 |
| AI 可参与 G-S-02 | assessment.eligible_axis：双维评分、原文引用与理由、当前指纹、对应技术轴 |
| G-S-03 必须人工确认 | assessment.confirm_batch / confirmation_valid，按明确 ID 与当前指纹逐篇记录 |
| 实质变更失效、元数据修正保持 | 指纹绑定判断字段、引用位置与定位内容；忽略作者等无关字段及单纯时间戳变化 |
| 人工判断优先 | 冲突 AI 结果进入 assessment_proposals，原评分与排除决定保持 |
| 保留历史 | review_history 保存旧判断、原确认及当时引用内容 |
| 旧数据不补造确认 | migrate-assessments 默认 dry-run；缺失身份标为 unknown，保留旧字段 |
| 新旧入口一致 | gates、validate、review、API、status/progress、报告共同使用内核协议；旧 CSV 不产生确认 |
| 不让旧内核假装执行新规则 | 技能包装层要求 assessment protocol 1；不兼容时退出 3，--json 保持单个 JSON |

## 验证结果

环境：Windows、Python 3.12.14、pytest 9.1.1。仅使用合成数据。

1. 内核新行为回归 **31 项通过**：支持充分的 AI 判定、人工确认、实质变更、元数据稳定、人工优先、引用真实性、字段结构、重复/过期/跨目标批次拒绝、写入失败回滚、保守迁移及旧 CSV 边界。
2. 新回归加可运行的上游初始化、CLI 帮助和路径测试：**89 项通过，3 项未执行**。三项依赖公开源码包遗漏的 repo fixture，未伪造上游夹具或将它们记为通过。其余依赖原 conftest、私有项目快照或发布构建器的上游测试未纳入此次可运行集合。
3. 技能包装层契约：**4 项通过**，包括旧内核拒绝、支持协议接受、未知协议拒绝，以及文档/示例语义。
4. 构建得到 patentkit 0.2.0 wheel 和 sdist；wheel 在独立虚拟环境离线安装成功，确认模块从 site-packages 导入，并重跑 **31 项回归通过**。
5. 隔离安装合成案例：N1 可计数数量为 `0 → 1 → 1 → 1 → 0`；G-S-03 数量为 `0 → 0 → 1 → 1 → 0`，依次对应旧记录、AI 判定、人工确认、作者信息修正、支撑段落变化。来源等级始终 verified。此处是行为测试，不是实际专利检索结果，也不表示五项门槛全部 PASS。
6. 实际技能 status/gates/validate 包装脚本均输出单个可解析 JSON；样例数量未达到门槛时 gates 返回 1，status 与校验返回 0。合成工作区完成支持性检查与比较记录后 validate --strict 为 0 error / 0 warn。
7. Python 编译检查、技能仓库 git diff --check 通过。
8. 两份补丁已分别对公开 main 基线、核验后的 0.1.2 源码执行 git apply --check，均通过；wheel 中包含新模块和扩展后的工作区 schema。

## 复现命令

在任务工作区中执行：

```powershell
.\.venv\Scripts\python.exe -m pytest patentkit/regression_tests -o addopts= -q --tb=line -p no:cacheprovider
.\.venv\Scripts\python.exe -m unittest discover -s patent-research-skill/tests -v
```

构建：进入 `patentkit/` 后，执行 `..\.venv\Scripts\python.exe -m build --no-isolation --outdir ../deliverables`。本机沙箱对构建目录及生成文件的访问有限制，构建与隔离安装通过工作区内的受控提权执行；未修改系统 Python 或用户安装的技能。

## 仍需明确的边界

- 本记录描述本地实施与验证；分支及 PR 状态以 GitHub 为准。未发布正式 Release，未迁移真实专利工作区。
- 引用匹配及指纹一致性不能证明模型的语义判断正确；命令中的人工身份是操作记录，不是自然人身份认证。
- 批量写入对正常 IO 失败执行回滚；多文件操作不承诺突然断电时的数据库级事务性，应保留原始材料与备份。
- 现有构建配置会产生许可证格式和模板包发现的弃用/配置提示；本轮未重构发行流程，已实际检查 wheel 安装和模板初始化。
- 来源等级沿用原内核实现；本轮没有扩大为来源采集真实性、数据库适配或法律判定准确性的全面审计。
