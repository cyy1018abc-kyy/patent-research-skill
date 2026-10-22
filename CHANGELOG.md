# 变更记录（CHANGELOG）

## 2026-10-22 · 技能包 2.3.0

- 新增 Windows 一键安装器 `install-oneclick.cmd`（检查 Python → 装内核 wheel → 装技能），
  支持 `--quiet`；新增一页纸《安装说明-给同事.md》。
- 构建期校验发布包必须包含以上文件；新增回归测试。
- 内核 `patentkit` 保持 0.1.1。

## 2026-10-22 · 技能包 2.2.0

- 新增 `agents/openai.yaml`：桌面端 Skills 显示中文名「专利调研」+ 简介，`@` 选中后带默认提问。
- 构建期校验（缺/格式错构建失败）+ 回归测试。
- 版本 2.1.0 → 2.2.0。

## 2026-10-22 · 技能包 2.1.0 / 内核 0.1.1

- 技能包拆分出 `scripts/` 执行层（status/validate/gates/report/check）；
  新增独立安装包（install 脚本 + manifest + 脱敏示例工作区）；
  新增跨客户端测试资产（Claude Code / Codex CLI）。
- 内核修复 G-S-01 提示文案带出历史目标 ID；版本口径统一。
