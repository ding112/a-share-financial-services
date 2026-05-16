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
