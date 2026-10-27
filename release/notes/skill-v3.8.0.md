# Patent Research Skill 3.8.0（内核写盘点显式 LF 统一）

Requires **patentkit 0.9.0, assessment protocol 1**, Python 3.11+.

## 什么变了

- **内核 0.9.0：文本写盘点全部显式 LF**。此前 31 处 `write_text` 未传 `newline`，
  Windows 文本模式默认把 `\n` 翻译成 `\r\n`，同一工作区/基准案例在 Windows 与
  Linux/CI 上逐字节不同（3.7.0 轮实测 115 个文件漂移；基准生成器当时只能用
  `_force_lf()` 在末端兜底）。本轮从内核源头统一：init 模板拷贝、评估/回填/普查
  JSON、review 工作表（CSV+JSON）、fetch 原始工件与日志、五门跟踪表、报告/映射/
  溯源/图面、交付与改稿等 31 处写入点全部补 `newline="\n"`，产物在所有平台
  逐字节一致，sha256 绑定与跨平台金样不再受行尾漂移威胁。
- **两条不变量回归测试锁住纪律**：`test_init_writes_lf_only`（init 模板拷贝路径）与
  `test_pipeline_writes_lf_only`（金样管线上被内核触碰的每个字节），内核测试
  761 项全绿（747 过 / 14 跳）。二进制写盘点（mkstemp+fdopen `wb` 原子写、
  `shutil.copy2` 证据原件）保持原样，不受影响。
- **行为说明**：review 工作表 CSV（utf-8-sig）在 Windows 上从 CRLF 变为 LF——与
  Linux/CI 既有口径一致（Excel 365 打开正常）；磁盘上已存在的 CRLF 文件**不会**
  被批量改写，仅在该文件下一次被内核重写时归一为 LF。
- **发布工程**：`release/patches/README.md` 的两处散文内核版本号
  （"current kernel is"、"declares version"）固化为 `bump_version.py --check`
  常驻校验——0.8.0 轮漏改（停在 0.7.0）由本轮补齐，此后 CI 拦截。

## 升级

1. 安装 `patentkit-0.9.0-py3-none-any.whl`（技能封装层会拒绝旧内核）；
2. 覆盖安装技能包（`--force`）；旧工作区数据与评估协议零迁移；
3. 已有工作区无需任何操作；从 0.9.0 起内核新写入的文件在所有平台都是 LF。
