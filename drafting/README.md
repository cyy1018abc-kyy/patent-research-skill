# patent-drafting 技能（撰写底稿）

> **这是什么**：把检索成果（姊妹技能 patent-research 的证据链）转化为**底稿**——
> 交底书、权利要求/说明书骨架、OA 答复稿、改稿闭环。产出永远是「底稿 + gap 清单」，
> 不替代专利代理师，不预测授权。
>
> **前置**：`patentkit >= 0.10.0`（`pip install patentkit`）；检索侧工作用 patent-research 技能。

## 快速上手

1. 确认检索侧就绪：`python -m patentkit gates`（G-S-01～03 达标，verified 列）；
2. 打开 `SKILL.md` 按执行顺序走（A 交底线 / B OA 线 / C 政策线）；
3. 命令直接用 `python -m patentkit <子命令>`——本技能无脚本封装，规则都在内核。

## 包结构

```
patent-drafting/
├── SKILL.md            主入口：何时触发 / 分线执行顺序 / 硬约束 / 结果格式
├── references/         00 前置纪律摘要 + 09 交底 + 10 权要 + 11 OA + 12 政策 + 13 改稿闭环 + glossary
└── README.md           本文件
```

安装/升级/卸载：与 patent-research 同一发布包（`install.ps1` / `install.sh` 会同时安装两个技能）；
也可单独安装 `patent-drafting-skill-v<版本>.zip`。详见仓库根 README。
