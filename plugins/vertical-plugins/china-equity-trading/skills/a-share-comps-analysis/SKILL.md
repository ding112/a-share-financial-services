---
name: a-share-comps-analysis
description: Build an A-share peer comps spread using transparent market, valuation, liquidity, and quality fields, with missing real-time data clearly marked.
---

# A-share comps analysis

Use this skill to create the peer comps section of an A-share primer. The
spread must use simple, auditable fields and must not fabricate real-time
market data.

## Inputs

- Peer set from `a-share-competitive-analysis`.
- Available market data, historical prices, financial metrics, and source
  timestamps.
- Analyst-provided universe or exclusions.

## Required fields

For each company, include these fields when sourced:

- `代码`
- `简称`
- `交易所`
- `行业/主题角色`
- `核心暴露证据`
- `最新价`
- `涨跌幅`
- `成交额`
- `换手率`
- `量比`
- `近5日涨跌幅`
- `近20日涨跌幅`
- `市值`
- `PE`
- `PB`
- `PS`
- `营收增速`
- `净利增速`
- `毛利率`
- `ROE`
- `数据时间戳`
- `来源`
- `异常值标记`

## Workflow

1. Normalize units for market cap, turnover, and financial values.
2. Keep valuation definitions consistent across the peer set.
3. Mark suspended, ST, newly listed, loss-making, or outlier names.
4. If real-time fields are unavailable, keep the row and write `来源缺失`
   in the affected cells.
5. Summarize what the spread implies for exposure, quality, liquidity, and
   valuation dispersion.

## Output format

Return Chinese Markdown with:

- A peer comps table.
- A short `估值与流动性观察` section.
- A short `异常值与数据缺口` section.

## Guardrails

- Do not estimate missing price, turnover, valuation, or growth data.
- Do not use opaque scoring models.
- Do not provide buy, sell, target-price, or return instructions.
