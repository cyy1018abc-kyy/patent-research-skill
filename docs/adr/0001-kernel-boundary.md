# ADR 0001 — 内核边界：patentkit 保留唯一法理权威，扩展只读

- 状态：**已接受**（2026-10-28，WP-0 冻结）
- 背景：蓝图 §0/§2/§15；风险登记表把「扩展绕开人工审核」列为极高风险。
- 决策人：仓库维护者（Jackey yang / cyy1018abc-kyy）。

## 背景

4.0 增加检索策略、多源采集、文档解析与权项建议能力。若这些能力各自维护一套
证据等级或确认流程，会重现历史上「口径分裂」（A4 类）问题，并把 `verified`
稀释成可被工具自动授予的标签。

## 决策

1. **patentkit 是唯一的证据等级、门禁、判断与签核权威。** 扩展不引入第二套
   G-S/V 规则，不写 `03_candidates/`，不触碰 `evidence_level`。
2. **扩展对内核工作区只读。** 读取走内核公共 API（`patentkit.model.load_logs`
   / `load_candidates`、`patentkit.paths` 语义）；需要驱动内核命令时只能以
   子进程方式调用 `kernel_allowlist.READONLY_VERBS` 白名单动词，并拒绝
   `FORBIDDEN_FLAGS` 全部写入型旗标（`--apply`/`--run`/`--force`/`--fill` 等）。
3. **扩展全部状态进独立 sidecar**（ADR 0002），对内核不可见、可随时删除。
4. **人工确认语义不变。** `reconfirm`/`waive` 仍走 V038；扩展产出的修改建议
   `requires_human_review` 恒为 true，进底稿必须复走内核 `draft`/`revise` 门禁。
5. **raw 工件纪律不变。** 扩展采集的原始响应要成为内核 `verified` 候选，唯一
   路径是落 `02_search_logs/raw/` + `.log.json` 后经内核 `ingest`——这是内核
   契约，不是扩展可以模拟的形态。

## 机器校验

- `extensions/patent_intel/src/patent_intel/kernel_allowlist.py` 是边界的唯一声明点。
- `tests/test_kernel_boundary.py`（仓库级）断言：
  a. 扩展源码没有任何对内核工作区路径的写操作（静态扫描 + `kernel_bridge.py` 零
     写文件调用）；
  b. 桥接拒绝白名单之外的一切内核动词；
  c. `FORBIDDEN_FLAGS` 中的旗标出现在任何桥接调用参数里即抛错。
- 违反本 ADR 的 PR 在 CI 阻断，不依赖评审者记忆。

## 后果

- 正面：内核可独立演进；扩展可整体卸载；审计路径单一。
- 代价：扩展的部分能力（如直接写候选提速）被放弃；采集器必须经内核 ingest
  契约落盘，多一道格式转换。
- 未来重议条件：内核官方提供受限写入 API 且保留人工确认链时，才考虑把
  「批准后的查询入库」自动化；白名单扩充须逐动词补只读证明测试。

## 版本策略补充（2026-10-30，Phase V / V4-3）

扩展 `patent_intel` **不进 skill↔kernel 版本配对**：配对（bump_version.py 的
SKILL/KERNEL_PAIRING_FILES + publish 双 tag）覆盖的是「方法论 ↔ 内核协议」耦合；
扩展是可选增量组件，`patentkit >= 0.8.0` 的下限约束由其自身 wheel 元数据表达。
扩展升版只动 `extensions/patent_intel/pyproject.toml` 与发行脚本资产名（gate 于
release_doctor 扩展检查），不触发内核补丁链。
