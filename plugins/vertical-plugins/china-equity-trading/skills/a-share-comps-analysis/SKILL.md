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
- Source contract output from `a-share-data-sources`, including source type,
  source name, data time, report period or basis, verification status, and
  missing-data behavior for every market, valuation, financial, and computed
  field.
- Available market data, historical prices, financial metrics, source
  timestamps, and user-provided data exports.
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
- `总市值`
- `流通市值`
- `动态PE`
- `PB`
- `PS`
- `营收`
- `净利润`
- `扣非净利润`
- `营收增速`
- `净利增速`
- `毛利率`
- `净利率`
- `ROE`
- `资产负债率`
- `经营现金流`
- `资本开支`
- `货币资金`
- `有息债务`
- `EV/Revenue`
- `EV/EBITDA`
- `数据时间戳`
- `来源类型`
- `来源`
- `口径`
- `异常值标记`

## Guide-backed source mapping

Use `a-share-data-sources` before filling the table. The `A股数据源接入指南.md`
source set can fill these groups when the data is provided by a pre-run script,
export file, or analyst-supplied extract.

| 字段组 | 推荐来源 | 来源类型 | 口径 |
|---|---|---|---|
| 行情快照 | 腾讯行情 API、AkShare 公开行情 | `public_market_data` | 盘中快照或访问时间 |
| 市值和动态 PE | 腾讯行情 API、AkShare 估值字段 | `public_market_data` | 与行情快照同一时间 |
| 财务摘要 | 同花顺 AKShare 财务摘要 | `public_market_data` | 报告期，年报或报告期口径 |
| 三大报表 | 东方财富数据中心、定期报告 | `public_market_data` 或 `official_disclosure` | 报告期，合并报表，金额单位 |
| 股本 | 交易所或公告股本数据；或总市值 / 最新价计算 | `official_disclosure` 或 `public_market_data` | 披露股本或计算值 |
| EV 倍数 | 市值、现金、债务、收入、EBITDA 计算 | `public_market_data` | 写明公式和输入来源 |
| 业务暴露 | 年报、半年报、公告、投资者关系记录 | `official_disclosure` 或 `company_public_material` | 披露日期和分部口径 |

## Computed-field policy

Computed fields can appear in the spread only when the inputs are present. Put
`计算值` in the `口径` column and include the formula in the source note.

| 计算字段 | Formula note |
|---|---|
| `总股本` | `总市值 / 最新价` |
| `流通股本` | `流通市值 / 最新价` |
| `营收CAGR` | `最近一期营收 / 最早一期营收` 的年化增长 |
| `利润CAGR` | `最近一期净利润 / 最早一期净利润` 的年化增长 |
| `EV` | `总市值 + 有息债务 - 货币资金` |
| `EV/Revenue` | `EV / 营业收入` |
| `EV/EBITDA` | `EV / EBITDA` |

## Workflow

1. Apply `a-share-data-sources` before selecting or ranking any metric.
2. Normalize stock codes and exchanges before comparing peers.
3. Normalize units for market cap, turnover, revenue, profit, cash, debt, and
   cash-flow fields.
4. Keep valuation definitions consistent across the peer set.
5. Mark suspended, ST, newly listed, loss-making, negative EBITDA, or outlier
   names.
6. If real-time fields are unavailable, keep the row and write `来源缺失` in
   the affected cells.
7. If a computed field lacks any input, keep the field and write `来源缺失`.
8. Summarize what the spread implies for exposure, quality, liquidity, and
   valuation dispersion.

## Output format

Return Chinese Markdown with:

- A peer comps table.
- A short `估值与流动性观察` section.
- A short `异常值与数据缺口` section.
- A short `字段来源说明` section listing source type, source name, timestamp,
  and口径 for each field group.

## Guardrails

- Do not estimate missing price, turnover, valuation, or growth data.
- Do not treat model assumptions as historical facts.
- Do not use opaque scoring models.
- Do not provide buy, sell, target-price, or return instructions.
