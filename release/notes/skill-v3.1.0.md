# Patent Research Skill 3.1.0（发布工程自动化 + 镜像收尾）

Requires **patentkit 0.3.0, assessment protocol 1**（不变）, Python 3.11+.

## 什么变了（纯工程与文档收尾，无内核/规则变更）

- **发布工程自动化**：新增 `tools/bump_version.py`——把 skill↔kernel↔发布脚本的
  十余处硬编码配对点固化为显式清单（定向替换 → 一致性校验 → 全仓旧版本号残留
  扫描），`--check` 模式已入 CI，配对点漂移在推送时即被拦截；新增
  `tools/build_kernel_patch.py`——内核补丁重建四步（镜像开发树→diff→修双重前缀
  →验证可应用）固化为一条命令，内置两层机器验证：CI 同款 `git apply
  --directory`（钉死 autocrlf=false 的最严格口径）+ 与现有补丁产物树逐字节等价
  对比。本次已用它重建 0.1.2→0.3.0 补丁并验证等价（已发布补丁不变）；
- **research 08 附图英文镜像补齐**：`references.en/08-figures.md`，术语与共享
  glossary 一致；`evals/check_terminology.py` 的 research 配对扩到 01–08——
  至此两技能 references 全部双语；
- **分发收尾**：新增脱敏效果截图 `docs/assets/self-test-terminal.png`
  （`tools/render_terminal_shot.py` 真实运行 self_test 渲染，脚注标注合成样例）
  与市场上架文案底稿 `docs/marketplace-listing.md`；分发清单两项 ⬜ 转 ✅。

## 升级

安装本包覆盖旧目录即可（`--force`）；内核无需升级（0.3.0 不变）；工作区无需迁移。

## Download and install

Download `patent-research-skill-v3.1.0.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.3.0-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.3.0).
Verify against `SHA256SUMS-skill-v3.1.0.txt`（覆盖两个 zip）。
