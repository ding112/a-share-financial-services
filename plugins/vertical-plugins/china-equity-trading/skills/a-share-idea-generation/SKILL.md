---
name: a-share-idea-generation
description: Generate a three-to-five-name A-share ideas shortlist from sector overview, competitive landscape, and comps output, with thesis hooks and risks.
---

# A-share idea generation

Use this skill to create the ideas shortlist section of an A-share sector or
thematic primer. The shortlist expresses research relevance, not trade
instructions.

## Inputs

- Sector overview.
- Competitive landscape.
- Peer comps spread.
- Risk flags, event calendar, and analyst constraints when available.

## Workflow

1. Select three to five A-share names that best express the theme.
2. For each name, write a one-line thesis hook tied to business exposure,
   industry structure, valuation dispersion, quality, liquidity, or catalyst.
3. Include the strongest evidence and the most important caveat for each
   shortlisted name.
4. Exclude names with unverifiable exposure, severe risk flags, suspension,
   or missing core data from the main shortlist.
5. Place uncertain names in `待验证观察名单` instead of the main shortlist.

## Output format

Return Chinese Markdown with:

- `核心想法清单`, three to five names.
- `待验证观察名单`, only when useful.
- `主要风险与失效条件`.

Each core idea must include:

- `代码`
- `简称`
- `主题角色`
- `一句话逻辑`
- `关键证据`
- `主要风险`
- `失效条件`

## Guardrails

- Do not write buy, sell, add, reduce, target-price, or return language.
- Do not include a name in the core shortlist when the exposure source is
  missing.
- Do not hide risk flags to make a shortlist look stronger.
