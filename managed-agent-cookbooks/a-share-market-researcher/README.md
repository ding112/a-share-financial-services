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
`note-writer` produces `./out/a-share-primer-<theme>.md` and optional slides
only when requested.

**Handoff:** use `a-share-screener` when the user asks for short-term topic,
event, quant, or risk screening lists. Use an equity-research workflow when a
shortlisted company needs deep single-name coverage.

## Guardrails

- Always write Chinese outputs.
- Mark missing or unverifiable data instead of estimating it.
- Do not output buy, sell, add, reduce, target-price, or return instructions.
- Stop for analyst review after the comps spread and after the note draft.
