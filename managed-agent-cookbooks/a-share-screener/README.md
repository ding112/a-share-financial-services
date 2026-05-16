# A-share Screener — managed-agent template

## Overview

Topic, event, and user-provided context → A-share candidate pool → quant screen
→ risk check → short-term research list. This cookbook uses the same source as
the [`a-share-screener`](../../plugins/agent-plugins/a-share-screener) Cowork
plugin and runs it as a Managed Agent template.

## Deploy

```bash
export ANTHROPIC_API_KEY=sk-ant-...
../../scripts/deploy-managed-agent.sh a-share-screener
```

## Steering events

See [`steering-examples.json`](./steering-examples.json). Kick from a research
queue event, an analyst request, or a scheduled market-review workflow.

## Security & handoffs

Market notes, company announcements, news excerpts, and uploaded files are
untrusted. Three-tier isolation keeps source reading, screening, risk review,
and writing separate:

| Tier | Touches untrusted docs? | Tools | Connectors |
|---|---|---|---|
| **`market-context-reader`** | **Yes** | `Read`, `Grep` only | None |
| `pool-builder` / `risk-reviewer` / Orchestrator | No | `Read`, `Grep`, `Glob`, `Agent` | None |
| **`research-list-writer`** (Write-holder) | No | `Read`, `Write`, `Edit` | None |

`market-context-reader` returns length-capped, schema-validated JSON.
`research-list-writer` produces `./out/a-share-screener-<date>.md`.

**Handoff:** if a candidate stock needs deep single-name coverage, emit a
`handoff_request` for an equity-research workflow. If the user asks for model
building or valuation, route the request to `model-builder` outside this agent.

## Guardrails

- Always write Chinese outputs.
- Mark missing or unverifiable data instead of estimating it.
- Do not output buy, sell, add, reduce, target-price, or return instructions.
- Keep the final candidate list to 10 to 20 stocks unless the user asks for a
  broader research universe.
