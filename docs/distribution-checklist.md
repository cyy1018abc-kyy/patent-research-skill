# 技能市场分发准备清单（对应升级清单 P2-20）

> 上架是**对外动作**（等于公开发布），需仓库所有者确认后执行；本清单把准备做满。

## 上架前准备（已完成 ✅ / 待办 ⬜）

- ✅ 可安装包：`patent-research-skill-v2.5.0.zip`（含安装器 + 合成样例 + manifest/SHA256）
- ✅ 配对内核：`patentkit-0.3.0` wheel/sdist（CI 从公开源+补丁重构，可审计）
- ✅ 英文 README（仓库根）+ 中文主版本技能文档（references.en/ 双语）
- ✅ 触发评测集 evals/（14 例，CI 锚定 description）
- ✅ 保密守卫（tools/check_no_workspace_data.py + .gitignore 红线）
- ⬜ 效果示例截图/走查：`docs/example-walkthrough.md` 需补一张真实终端输出的脱敏截图
  （标注 ⚠️ 数据为合成样例）
- ⬜ LICENSE/作者信息核对（Apache-2.0 已有；市场要求署名时补充）

## 目标市场与要求

| 市场 | 形态 | 要求 | 优先级 |
|---|---|---|---|
| GitHub Release（现状） | zip + wheel | 已满足 | 已上线 |
| skillhub.cn / ClawHub | 技能包（SKILL.md 目录） | 目录名 = name；README 中文 | 高（目标用户在国内） |
| agentskills.io / Tessl registry | git 仓库或包 | name/description 元数据；evals 可展示 | 中 |
| aiskill.market | 包 | 待查（英文 description） | 低 |

## 上架话术要点（诚实边界）

- 描述里写「检索/自检/证据链/交付物」，**不写**「保证授权」「替代代理师」；
- 卖点 = 证据分级（verified/attested/asserted）+ 五门验收 + fail-closed 纪律，
  这是与 12.2k star 的 patent-disclosure-skill 的**差异化**，不是功能数量；
- 免责声明随包走（SKILL 硬约束、README、export-docx 文档头三处都有）。
