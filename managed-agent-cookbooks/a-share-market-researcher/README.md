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

## Research note assembly output contract

When an upstream workflow has already produced `research-pack/`, phase 5 comps
artifact, and phase 6 research handoff directories, the phase 7 assembly step
creates these local files:

| File | Use |
|---|---|
| `<中文主题>行业研究.md` | Chinese research note draft for analyst review. |
| `<中文主题>路演大纲.md` | Slide outline for optional PPTX production. |
| `research_assembly_manifest.json` | Input and output manifest for auditability. |

The Markdown note is the default deliverable. A binary PPTX is produced only
when the user explicitly asks for slides; use the bundled `pptx-author` skill
for that file-producing step.

The optional comps workbook is generated from the phase 5 CSV artifacts. It is
for analyst review and formatting convenience only; the CSV files remain the
auditable source of truth.

## 端到端 fixture

使用 `robotics-reducer` fixture 复现本地只读 workflow。所有命令都只读取
本地文件，并把输出写到已忽略的 `out/` 目录；命令不会抓取腾讯、AkShare、
东方财富或其他网络来源。

先把本地 raw exports 整理成标准 `research-pack/`：

```bash
python3 scripts/prepare_a_share_research_pack.py \
  --input-dir fixtures/a-share-raw-exports/robotics-reducer \
  --output-dir out/robotics-reducer-research-pack \
  --theme 机器人产业链 \
  --as-of 2026-05-17
```

命令写出：

```text
out/robotics-reducer-research-pack/source_manifest.json
out/robotics-reducer-research-pack/peer_universe.csv
out/robotics-reducer-research-pack/market_snapshot.csv
out/robotics-reducer-research-pack/financial_summary.csv
out/robotics-reducer-research-pack/company_exposure.md
out/robotics-reducer-research-pack/events_and_risks.md
```

然后生成阶段 5 comps artifacts：

```bash
python3 scripts/generate_a_share_comps_artifacts.py \
  --research-pack out/robotics-reducer-research-pack \
  --output-dir out/robotics-reducer-comps \
  --theme 机器人产业链
```

命令写出：

```text
out/robotics-reducer-comps/comps_main.csv
out/robotics-reducer-comps/comps_source_notes.csv
out/robotics-reducer-comps/comps_exceptions.csv
out/robotics-reducer-comps/comps_statistics.csv
out/robotics-reducer-comps/comps_data_gaps.csv
out/robotics-reducer-comps/comps_summary.md
```

可选：从阶段 5 CSV artifacts 生成分析师复核用 workbook：

```bash
python3 scripts/generate_a_share_comps_workbook.py \
  --comps-dir out/robotics-reducer-comps \
  --output out/机器人产业链可比公司.xlsx \
  --theme 机器人产业链
```

然后生成阶段 6 research handoff：

```bash
python3 scripts/generate_a_share_research_handoff.py \
  --research-pack out/robotics-reducer-research-pack \
  --comps-dir out/robotics-reducer-comps \
  --output-dir out/robotics-reducer-handoff \
  --theme 机器人产业链
```

命令写出：

```text
out/robotics-reducer-handoff/competitive_handoff.csv
out/robotics-reducer-handoff/idea_inputs.csv
out/robotics-reducer-handoff/idea_risk_register.csv
out/robotics-reducer-handoff/research_handoff_summary.md
```

最后组装阶段 7 中文研究 note 和路演大纲：

```bash
python3 scripts/generate_a_share_research_note.py \
  --research-pack out/robotics-reducer-research-pack \
  --comps-dir out/robotics-reducer-comps \
  --handoff-dir out/robotics-reducer-handoff \
  --output-dir out/robotics-reducer-note \
  --theme 机器人产业链 \
  --angle 关注减速器国产替代和机器人量产弹性 \
  --as-of 2026-05-18
```

命令写出：

```text
out/robotics-reducer-note/机器人产业链行业研究.md
out/robotics-reducer-note/机器人产业链路演大纲.md
out/robotics-reducer-note/research_assembly_manifest.json
```

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
