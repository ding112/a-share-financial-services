# A-share Market Researcher — managed-agent template

## Overview

A-share sector or theme → industry overview → competitive landscape → peer
comps → ideas shortlist → Chinese research note. This cookbook uses the same
source as the
[`a-share-market-researcher`](../../plugins/agent-plugins/a-share-market-researcher)
Cowork plugin and runs it as a Managed Agent template.

## Deploy

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r ../../requirements.txt
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

The research workers are read-only for source data after the local data package
exists: they can read user-provided files and extracts, but only the dedicated
`data-prep` worker can execute the controlled local preparation script. When an
upstream workflow or the data-prep worker provides a data package generated from
Tencent, AkShare, Eastmoney, or similar public sources, classify it as
`public_market_data` and preserve the original source name, access time, report
period, and unit.

公开数据抓取器是 `scripts/fetch_a_share_public_data.py`。它可以从本地
`peer_universe.csv` 生成 `market_snapshot.csv`、`financial_summary.csv`、
`source_manifest.json` 和 `fetch_errors.csv`。一键入口是
`scripts/auto_prepare_a_share_research_pack.py`；当没有种子文件时，它使用
AkShare 公开概念或行业板块生成 `candidate_peer_universe.csv` 和
`peer_universe.csv`，再调用公开数据抓取器补行情和财务摘要。自动生成的概念
或板块成分只能作为 `待验证` 线索，不能作为已验证业务暴露。

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

Use `research-pack/` when an upstream workflow, analyst, or the dedicated
data-prep worker provides local files for a sector primer. After the package
exists, it is read-only input for the research workers; only `data-prep` runs
the controlled preparation script.

The recommended package contains these files:

| File | Required | Use |
|---|---|---|
| `source_manifest.json` | Yes | Declares each input file's source type, source name, data time, basis, verification status, and missing-data behavior. |
| `peer_universe.csv` | Yes | Defines the 8 to 15 candidate A-share companies, exchange, board, peer group, theme role, and exposure source reference. |
| `market_snapshot.csv` | No | Provides timestamped price, valuation, market-cap, and liquidity fields. |
| `financial_summary.csv` | No | Provides period-tagged revenue, profit, margin, ROE, leverage, and cash-flow fields. |
| `company_exposure.md` | No | Stores business exposure, order, capacity, customer, product, and technology-route evidence grouped by company code. |
| `events_and_risks.md` | No | Stores catalysts, regulatory events, reductions, unlocks, ST, suspension, and failure-condition evidence grouped by company code. |
| `candidate_peer_universe.csv` | No | Stores the full auto-generated candidate pool, public board source, selection metric, and verification status. |
| `auto_prepare_manifest.json` | No | Records theme, inputs, outputs, selected universe count, selection rule, and warnings for auditability. |

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

若要让 Claude Code 或 managed-agent data-prep worker 自动准备数据包，先在
仓库当前目录创建 `.venv` 并安装依赖：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

然后运行一键入口。若不提供 `--peer-universe`，脚本会通过 AkShare 公开概念
或行业板块生成候选池；离线测试可使用 fixture 数据源：

```bash
.venv/bin/python scripts/auto_prepare_a_share_research_pack.py \
  --theme 机器人产业链 \
  --output-dir out/robotics-reducer-research-pack \
  --as-of 2026-05-22
```

命令写出：

```text
out/robotics-reducer-research-pack/candidate_peer_universe.csv
out/robotics-reducer-research-pack/peer_universe.csv
out/robotics-reducer-research-pack/market_snapshot.csv
out/robotics-reducer-research-pack/financial_summary.csv
out/robotics-reducer-research-pack/source_manifest.json
out/robotics-reducer-research-pack/fetch_errors.csv
out/robotics-reducer-research-pack/auto_prepare_manifest.json
```

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
| `data-prep` | No | `Read`, `Grep`, `Glob`, `Bash` | None |
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
