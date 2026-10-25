# Patent Research Skill 3.2.0（检索规划 + 改稿闭环 + 链全景）

Requires **patentkit 0.4.0, assessment protocol 1**（不变）, Python 3.11+.

## 什么变了（内核 minor 升级 + 文档同步）

- **检索覆盖规划**（内核 `patentkit queryplan`，references/02）：每轴「已登记 vs 已执行」
  子查询、G-S-02 verified 缓冲（口径同 05）、概念要素组覆盖缺口三件套；对未覆盖组给出
  确定性补查骨架，`--apply` 只追加进查询库（既有编号永不重排，注释逐字节保留）。
  status 的下一步提示在 G-S-02 未过时指向它。
- **改稿闭环内核化**（内核 `patentkit revise`，drafting references/13）：结构化局部补丁
  （每个 find 必须恰好命中一次，否则整包拒绝、零写入）+ 补丁/台账/登记表重绑定同一事务
  + 轮次后完整性检查（「改了没登记」= revise status exit 1 = validate V036）；同一问题
  3 轮显式报警升级。
- **证据链全景**（内核 `patentkit chain`）：日志→候选池→D 列→判定 runs→结论→账本→
  五门→改稿台账，一页纯本地静态 HTML（无外链无脚本）。
- 新增校验规则 V035（台账结构坏 = error）/ V036（改了没登记 = warn，strict 升级）；
  `validate` 规则范围 V001–V036。
- 参考文档 02/05（research）与 13（drafting）中英镜像同步。

## 升级

安装本包覆盖旧目录即可（`--force`）；**内核必须同步升到 0.4.0**（技能封装层会拒绝旧内核）；
工作区无需迁移（新能力均为可选启用：台账在第一次 `revise apply` 时创建）。

## Download and install

Download `patent-research-skill-v3.2.0.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.4.0-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.4.0).
Verify against `SHA256SUMS-skill-v3.2.0.txt`（覆盖两个 zip）。
