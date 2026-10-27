# Patent Research Skill 3.7.0（改稿↔结论联动 V038 + 基准扩到 9 场景 + 支持性引用结构化）

Requires **patentkit 0.8.0, assessment protocol 1**, Python 3.11+.

## 什么变了

- **改稿闭环 ↔ conclusions 联动（内核 0.8.0，V038）**：稿件被补丁改动 ⇒
  `05_novelty_conclusions/*.md` 全部自动标 stale（内核生成的五门跟踪表除外）；
  `revise status` 列出 stale 清单并 exit 1；`revise close` 在处理完之前拒绝；
  处理 = `revise reconfirm --by <人名>`（人工重确认，绑定文件 sha256）或
  `revise reconfirm --waive --reason <理由> --by <人名>`（豁免入台账轮次）；
  validate 把「未处理 stale / 重确认后又改动 / 豁免未入台账」报为 V038 error。
  状态存于内核管理的 `05_novelty_conclusions/conclusions_state.yml`，旧工作区零迁移。
  参见 drafting 13 号参考文档（中英）。
- **撰写侧支持性引用结构化（内核 0.8.0，D-019）**：`support_mapping` 行新增可选
  `citations`（source=工作区相对路径 + locator=`L<n>[-L<m>]` 行区间或 `[NNNN]` 段落号）；
  写了就必须可解析——路径越界/不存在、locator 越界、段落号不存在都是 draft 审计
  error。旧 support_mapping 无需迁移。参见 drafting 15 号参考文档（中英）。
- **合成案例基准扩到 9 场景（评审 P1-1 的 8–12 区间）**：新增 bm04 票据 OCR（引用准确性）、
  bm05 智能阀门（特征遗漏）、bm06 无人机编队灯光（误判率，5 文献）、bm07 冰箱保鲜
  （特征遗漏）、bm08 3D 打印监测（引用准确性）、bm09 智能门锁（误判率，4 文献）。
  累计 9 案例 / 37 特征 / 417 判断点 / 142 条引文（评分器口径），金解门 `--gate perfect` 全绿；
  语料、真值、脚手架与参考解全部入库，参赛方法见 `benchmarks/README.md`。
- **发布工程**：`build_kernel_patch` 修复空新增文件的补丁头（无 `---/+++` 可消歧时
  git apply 报 "header lacks filename information"——新文件/删除文件的合成路径头
  现归一为对称形式）。

## 升级

1. 安装 `patentkit-0.8.0-py3-none-any.whl`（技能封装层会拒绝旧内核）；
2. 覆盖安装技能包（`--force`）；旧工作区数据与评估协议零迁移；
3. 正在改稿闭环中的工作区：下一轮 `revise apply` 起结论会自动进入 stale 状态，
   按 `revise status` 提示重确认或豁免即可。
