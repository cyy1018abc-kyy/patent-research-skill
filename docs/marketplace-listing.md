# 技能市场上架文案底稿（4.0.0）

> 给 `docs/distribution-checklist.md` 的"实际提交上架"用：文案可直接复制，
> 话术边界照 `distribution-checklist.md` 的"上架话术要点"执行——只写检索/自检/
> 证据链/交付物，**不写**"保证授权""替代代理师"。

## skillhub.cn / ClawHub（中文，优先）

**技能名**：patent-research-skill（专利调研与撰写技能组）

**一句话简介**（≤60 字）：

> 专利查新调研 + 交底/权要撰写底稿：证据三级分级、五道验收门、结论必须命中
> 证据账本，全程留痕可复现。

**详细描述**：

面向中国专利实践（CNIPA 口径）的四技能包，装一个包得到四个技能：

- **patent-research**：查新调研。候选池 → 三层判定（单篇新颖性/组合创造性/
  技术效果）→ G-S 五道验收门 × 严格 verified 口径 → 查新报告 docx / 对比地图
  HTML，数字零手工转写；
- **patent-drafting**：撰写底稿。交底书五段式、独权/从权撰写规则、OA 答复
  逐条拆解，数值声明强制 A/B/C 溯源（V031/V032 fail-closed）；
- **patent-discovery**：研发材料到专利候选点。来源登记 → 技术事实抽取 →
  候选生成排序 → 发明人确认（内容指纹绑定）→ 检索交接草案；
- **patent-audit**：检索证据链审计（4.0 新增）。覆盖率台账（要素×数据源×分类号）
  → 对抗验证每个「要素↔对比文件」映射 → 逐字引文独立复核 → 三态结论
  （confirmed / needs_validation / rejected）+ 中立报告；方法论改编自
  Cloudflare security-audit-skill（MIT），审计基线 bm01/bm02 可回归评分。

与其他专利技能的差异在**防伪**，不在功能数量：

1. 证据三级分级（verified / attested / asserted），来源与判断分离；
2. 门禁 FAIL 时的处置是"检索不足，去补检索"，不提供放宽阈值的选项；
3. AI 参与的判定有显式协议（G-S-02 可 AI 评分，G-S-03 强制人工确认，冲突降级）；
4. 结论只能引用证据账本内的编号（V034），编造引用在交付前被拦截；
5. 校验规则只活在 patentkit 内核（单一规则权威源），技能层没有第二套口径。

要求 Python 3.11+ 与配套内核 patentkit 0.10.0（Release 页提供 wheel 与 SHA256）。
安装后跑 `python research/scripts/self_test.py` 六项自检（见下方截图）。

**标签**：专利 / 查新 / prior-art / CNIPA / novelty search / 证据链

**效果截图**：`docs/assets/self-test-terminal.png`（⚠️ 图内数据为合成样例）

## agentskills.io / Tessl（英文短文案）

**Name**: patent-research-skill

**Description**:

> Patent novelty-search, drafting, discovery and audit skill suite for Chinese
> patent practice. Evidence is graded (verified / attested / asserted), acceptance
> gates refuse to pass on thin evidence (fail-closed), conclusions may only cite
> the evidence ledger, and every number carries A/B/C provenance. The audit skill
> (v4.0) adds a coverage ledger, adversarial mapping validation and independent
> verbatim-quote review with three-verdict findings. Ships with installers, a
> synthetic sample workspace, a six-point self-test, and a reproducible kernel
> (CI rebuilds patentkit from public source + a committed patch).

**Tags**: patent, prior-art, novelty-search, fail-closed, evidence-chain, CNIPA, audit

## 提交时随附核对

- [ ] zip 与 SHA256SUMS 取自最新 Release 资产（CI 构建产物，不手工重打包）
- [ ] 描述里不出现"保证授权 / 法律意见 / 替代代理师"
- [ ] 截图脚注保留"合成样例数据"标注
- [ ] 目录名 = 技能 name（skillhub/ClawHub 要求）
- [ ] 免责声明三处随包走：SKILL 硬约束、README、export-docx 文档头
