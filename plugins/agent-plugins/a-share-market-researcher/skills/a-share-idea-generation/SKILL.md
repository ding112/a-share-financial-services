---
name: a-share-idea-generation
description: Generate a three-to-five-name A-share research ideas shortlist from sector overview, competitive landscape, and comps output, with screen criteria, thesis hooks, catalysts, risks, and next research questions.
---

# A-share idea generation

Use this skill to create the ideas shortlist section of an A-share sector or
thematic primer. The shortlist expresses research relevance and next diligence
priority, not trade instructions.

## Inputs

Use these inputs before selecting any company:

- Sector overview from `a-share-sector-overview`.
- Competitive landscape from `a-share-competitive-analysis`.
- Peer comps spread from `a-share-comps-analysis`.
- Source contract output from `a-share-data-sources`, especially evidence
  status for theme exposure, valuation or quality data, why-now catalysts,
  risks, and failure conditions.
- Risk flags, event calendar, analyst constraints, and user-provided
  exclusions when available.
- Any explicit universe boundary, such as A-share only, STAR Market, ChiNext,
  Northbound-heavy names, state-owned enterprises, private companies, or a
  user-provided stock pool.

## Search criteria

Start by restating the search criteria in Chinese. If the user did not provide
a criterion, infer the least restrictive version and mark it as
`用户未限定`.

Required criteria:

- `研究方向`: use one of `核心受益`, `观察候选`, or `风险排除`.
- `市值范围`: large cap, mid cap, small cap, micro cap, or `用户未限定`.
- `板块范围`: main board, STAR Market, ChiNext, Beijing Stock Exchange, or
  `用户未限定`.
- `行业或主题`: the sector, policy theme, technology chain, or demand cycle.
- `风格约束`: value, growth, quality, special situation, event-driven,
  high-dividend, turnaround, or `用户未限定`.
- `排除项`: ST, suspended, newly listed without sufficient disclosure,
  unverifiable exposure, severe regulatory risk, missing core data, or
  user-provided exclusions.

## A-share screening framework

Screen candidates with transparent criteria. A screen surfaces research
candidates; it does not prove an investment conclusion.

For each candidate, assess these dimensions:

| 维度 | 入选证据 | 降级或排除条件 |
|---|---|---|
| 主题暴露 | 年报、半年报、公告、投资者关系记录、订单、产能、客户、产品线或分部收入能证明业务相关 | 只有概念标签、新闻转载或第三方研究，且没有公司披露支持 |
| why-now | 政策落地、产业周期变化、订单拐点、价格变化、产能投放、库存周期、国产替代、出海或资本开支变化 | 催化只来自市场情绪，或没有可验证时间线 |
| 估值或质量 | `a-share-comps-analysis` 提供 PE、PB、PS、EV/Revenue、EV/EBITDA、ROE、毛利率、净利率、现金流或负债率中的可比字段 | 核心估值和质量字段均为 `来源缺失` |
| 流动性 | 成交额、换手率、流通市值或用户提供的交易约束支持可研究性 | 停牌、流动性严重不足，或行情字段没有数据时间 |
| 催化 | 财报、业绩预告、政策窗口、订单披露、产能节点、行业会议、产品发布或监管事件 | 催化无法落到公司或行业层面的可验证事件 |
| 风险 | 竞争、价格、毛利率、客户集中度、政策、监管、减持、解禁、财务质量和治理风险已明确列出 | 风险无法识别，或已有严重风险但没有反证 |
| 失效条件 | 明确写出什么事实会推翻 thesis | 只有正面逻辑，没有可检验的反面条件 |

Use style-specific screens only when the required data is available:

- `价值`: 相对 peer 的 PE、PB、PS、EV/Revenue、股息率或 FCF yield 有
  清晰折价，并解释折价可能合理或不合理的原因。
- `成长`: 收入增速、利润增速、订单、产能、渗透率、价格或份额变化能支持
  增长判断。
- `质量`: ROE、毛利率、净利率、现金流、资产负债率、客户结构或治理质量
  优于 peer 或更稳定。
- `事件驱动`: 财报、政策、订单、并购重组、回购、股权激励、解禁、减持、
  ST 风险或监管问询有明确日期和来源。
- `风险排除`: ST、停牌、重大监管问询、核心数据缺失、概念暴露不可验证、
  财务异常或流动性不足的公司进入 `风险排除名单`，不得进入核心清单。

## Thematic sweep

For thematic ideas, map the theme before choosing names:

1. Define the thesis in one sentence, including demand driver, supply
   constraint, policy driver, or technology change.
2. Map the value chain and separate direct beneficiaries, indirect
   beneficiaries, suppliers, customers, and substitutes.
3. Separate pure-play exposure from diversified exposure.
4. Identify what is already widely recognized by the market and what might be
   under-appreciated.
5. Look for second-order beneficiaries, such as upstream materials,
   equipment, testing, software, distribution, localization, or maintenance.
6. Mark which links need further verification from official disclosure.

## Idea presentation

For every core idea, present a compact Chinese research card.

Use this structure:

```markdown
### <简称>（<代码>）— <研究方向> — <一句话逻辑>

| 字段 | 内容 |
|---|---|
| 主题角色 | <公司在产业链或主题中的角色> |
| 关键证据 | <最强证据、来源类型、来源名称、数据时间、口径> |
| 估值或质量依据 | <来自 comps 的估值、质量、流动性或数据缺口> |
| 催化与为什么是现在 | <可验证催化、时间线和来源> |
| 主要风险 | <最重要的 2 到 4 个风险> |
| 失效条件 | <哪些事实会推翻这条研究逻辑> |
| 下一步研究问题 | <最值得继续验证的 2 到 3 个问题> |
```

Write the `一句话逻辑` as a research thesis hook. Do not use trade language.

## Research priority rules

Prioritize names for follow-up research with explicit reasoning. Do not rank
by price movement unless the source includes a data time.

Use this priority order:

1. `高优先级`: verified theme exposure, clear why-now, usable valuation or
   quality data, identifiable catalyst, and explicit failure conditions.
2. `中优先级`: verified theme exposure and clear why-now, but valuation,
   quality, liquidity, or catalyst evidence has gaps.
3. `观察候选`: plausible exposure with incomplete official evidence or
   incomplete comps data.
4. `风险排除`: severe risk flags, unverifiable exposure, suspension, ST,
   missing core data, or user-provided exclusion.

When two companies look similar, prefer the one with stronger official
disclosure, clearer business exposure, cleaner comps data, and more specific
failure conditions.

## Workflow

1. Restate the search criteria and universe boundary.
2. Remove companies that match the `风险排除` criteria.
3. Group remaining candidates by value-chain role and exposure quality.
4. Apply the A-share screening framework to each candidate.
5. Use the thematic sweep to identify direct, indirect, and second-order
   beneficiaries.
6. Select three to five `高优先级` or `中优先级` names for `核心想法清单`.
7. Put plausible but weakly sourced names in `待验证观察名单`.
8. Put severe risk or unverifiable names in `风险排除名单`.
9. Write the idea presentation card for each core idea.
10. Summarize the next diligence questions for the analyst.

## Output format

Return Chinese Markdown with these sections:

- `搜索条件与范围`.
- `筛选方法`.
- `核心想法清单`, three to five names.
- `待验证观察名单`, only when useful.
- `风险排除名单`, when exclusions were identified.
- `横向比较表`.
- `主要风险与失效条件`.
- `下一步研究问题`.

Each core idea must include:

- `代码`
- `简称`
- `研究方向`
- `主题角色`
- `一句话逻辑`
- `关键证据`
- `估值或质量依据`
- `催化与为什么是现在`
- `主要风险`
- `失效条件`
- `下一步研究问题`

The `横向比较表` must include these columns:

| 代码 | 简称 | 研究优先级 | 主题暴露 | why-now | 估值或质量依据 | 流动性 | 催化 | 主要风险 | 数据缺口 |
|---|---|---|---|---|---|---|---|---|---|

## Guardrails

- Apply the `a-share-data-sources` minimum evidence gate for
  `a-share-idea-generation`.
- 不输出买入、卖出、加仓、减仓、目标价或收益承诺。
- 概念标签不能单独作为核心入选依据。
- 没有数据时间的行情或估值字段不能用于优先级排序。
- 风险排除项不得进入核心想法清单。
- Do not include a company in the main shortlist unless it has theme exposure,
  valuation or quality evidence, why-now, risks, and failure conditions.
- If exposure is supported only by concept tags, news, or third-party research,
  place the company in `待验证观察名单`.
- Do not rank companies by latest price move, turnover, or volume unless the
  source includes a data time.
- Do not include a name in the core shortlist when the exposure source is
  missing.
- Do not hide risk flags to make a shortlist look stronger.
- Separate facts, research inference, and market sentiment.
- When a field is missing, keep the field and write `来源缺失` instead of
  estimating.
