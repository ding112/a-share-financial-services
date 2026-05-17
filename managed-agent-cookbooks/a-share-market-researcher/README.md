# A-share Market Researcher — managed-agent template

## Overview

A-share sector or theme → industry overview → competitive landscape → peer
comps → ideas shortlist → Chinese research note. This cookbook uses the same
source as the
[`a-share-market-researcher`](../../plugins/agent-plugins/a-share-market-researcher)
Cowork plugin and runs it as a Managed Agent template.

## Deploy

```bash
export ANTHROPIC_API_KEY=sk-ant-...
../../scripts/deploy-managed-agent.sh a-share-market-researcher
```

## Steering events

See [`steering-examples.json`](./steering-examples.json). Kick from an A-share
research queue event, an analyst request, or a scheduled sector-primer refresh.

## Free data-source policy

This agent does not configure Wind, Choice, iFinD, CapIQ, FactSet, Bloomberg, or
other paid vendor connectors. It uses `a-share-data-sources` to map each field
to free or public sources before drafting the note.

`a-share-data-sources` 是随包分发的 skill，不是可直接调度的 agent type。
外部入口使用 `a-share-market-researcher:a-share-market-researcher`；不要使用 `a-share-market-researcher:a-share-data-sources`。

The current managed-agent template is read-only for source data: it can read
user-provided files and extracts, but it does not execute the Tencent, AkShare,
or Eastmoney network calls by default. When an upstream workflow provides a data
package generated from those sources, classify it as `public_market_data` and
preserve the original source name, access time, report period, and unit.

Guide-backed free sources can fill these gaps:

| Source | Filled data gap | Source class |
|---|---|---|
| Tencent quote API | Latest price, open, previous close, high, low, volume, amount, turnover, dynamic PE, total market cap, and float market cap. | `public_market_data` |
| Tonghuashun via AkShare financial abstract | Five-year revenue, profit, non-recurring profit, growth rates, EPS, BPS, operating cash flow per share, gross margin, net margin, ROE, and liability ratio. | `public_market_data` |
| Eastmoney data center | Income statement, balance sheet, and cash-flow statement fields. | `public_market_data` |
| Calculated fields | Shares, CAGR, EV, EV/Revenue, and EV/EBITDA when every input is sourced. | `public_market_data` with formula in the basis note |

The same guide does not fill industry size, industry growth, penetration,
orders, capacity, customers, technology route, risk-event announcements, capital
flow, margin financing, northbound holdings, or historical 5-day and 20-day
returns. Keep those fields as `missing_source` unless another reliable source is
provided.

## Research-pack input contract

Use `research-pack/` when an upstream workflow or analyst provides local files
for a sector primer. The package is read-only input for the agent. It does not
make the managed-agent template run Tencent, AkShare, Eastmoney, or any other
network collection by default.

The recommended package contains these files:

| File | Required | Use |
|---|---|---|
| `source_manifest.json` | Yes | Declares each input file's source type, source name, data time, basis, verification status, and missing-data behavior. |
| `peer_universe.csv` | Yes | Defines the 8 to 15 candidate A-share companies, exchange, board, peer group, theme role, and exposure source reference. |
| `market_snapshot.csv` | No | Provides timestamped price, valuation, market-cap, and liquidity fields. |
| `financial_summary.csv` | No | Provides period-tagged revenue, profit, margin, ROE, leverage, and cash-flow fields. |
| `company_exposure.md` | No | Stores business exposure, order, capacity, customer, product, and technology-route evidence grouped by company code. |
| `events_and_risks.md` | No | Stores catalysts, regulatory events, reductions, unlocks, ST, suspension, and failure-condition evidence grouped by company code. |

If `source_manifest.json` is missing, treat the package as `user_provided`
leads only. If `peer_universe.csv` is missing, stop before comps and idea
shortlist work and ask for a stock pool. Optional files can be absent, but the
corresponding market, financial, exposure, event, or risk fields must remain
`missing_source`, `来源缺失`, `待验证`, or `口径不可比`.

Use these source classes in outputs and internal handoffs:

| Source class | Use for |
|---|---|
| `official_disclosure` | Company filings, exchange announcements, periodic reports, inquiry letters, and replies. |
| `official_statistics` | National Bureau of Statistics, People's Bank of China, CSRC, exchange market data, and public index materials. |
| `public_market_data` | AkShare-backed public market data, public行情 pages, index data, valuation snapshots, and liquidity fields. |
| `company_public_material` | Investor relations records, earnings briefings, company websites, and public presentation material. |
| `third_party` | Industry reports, sell-side excerpts, news, and public concept-board labels used as leads. |
| `user_provided` | Files, exports, screenshots, or notes supplied by the analyst. |
| `missing_source` | Fields that cannot be verified from the available free or user-provided sources. |

## Security & handoffs

Third-party reports, issuer materials, announcements, news excerpts, and
uploaded files are untrusted. Three-tier isolation keeps source reading,
comps spreading, and writing separate:

| Tier | Touches untrusted docs? | Tools | Connectors |
|---|---|---|---|
| **`sector-reader`** | **Yes** | `Read`, `Grep` only | None |
| `comps-spreader` / Orchestrator | No | `Read`, `Grep`, `Glob`, `Agent` | None |
| **`note-writer`** (Write-holder) | No | `Read`, `Write`, `Edit` | None |

`sector-reader` returns length-capped, schema-validated JSON.
`note-writer` produces a Chinese-named Markdown file under `./out/`, such as
`./out/机器人产业链行业研究.md`, and optional Chinese-named slides only when
requested.

**Handoff:** use `a-share-screener` when the user asks for short-term topic,
event, quant, or risk screening lists. Use an equity-research workflow when a
shortlisted company needs deep single-name coverage.

## Guardrails

- Always write Chinese outputs.
- Mark missing or unverifiable data instead of estimating it.
- Do not output buy, sell, add, reduce, target-price, or return instructions.
- Stop for analyst review after the comps spread and after the note draft.
