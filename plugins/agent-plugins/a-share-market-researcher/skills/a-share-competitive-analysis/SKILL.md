---
name: a-share-competitive-analysis
description: Map the A-share competitive landscape for a sector or theme, including listed players, positioning, basis of competition, and recent moves.
---

# A-share competitive analysis

Use this skill to build the competitive landscape section of an A-share
sector or thematic primer. Focus on how listed companies compete and where
their exposure differs.

## Inputs

- A-share sector or theme.
- Candidate universe from `a-share-sector-overview` or analyst input.
- Source plan from `a-share-data-sources`, including source type, source name,
  data time, report period or basis, verification status, and missing-data
  behavior for each fact.
- Business-exposure evidence that meets the `a-share-data-sources` minimum
  evidence gate for `a-share-competitive-analysis`.
- Company announcements, filings, investor relations material, and reliable
  third-party research excerpts.

## Workflow

1. Group companies by value-chain role, business model, and exposure purity.
2. Compare scale, product mix, customer base, capacity, technology route,
   channel position, and margin drivers when the data is available.
3. Flag recent moves such as capacity expansion, large orders, policy
   qualification, mergers, buybacks, capital raises, or strategic cooperation.
4. Identify where the market narrative may overstate a company's exposure.
5. Classify each exposure claim as `official_disclosure`,
   `company_public_material`, `third_party`, `user_provided`, or
   `missing_source`.
6. Mark missing source support as `待验证` and keep weakly supported names
   outside the core peer set.

## Output format

Return Chinese Markdown with these sections:

- `核心玩家分组`
- `竞争维度`
- `近期变化`
- `暴露度强弱`
- `待验证事项`

## Guardrails

- Apply the `a-share-data-sources` source hierarchy before using any claim.
- Do not treat concept-board membership, news heat, or third-party research as
  sufficient evidence for core business exposure.
- Put companies with only weak exposure evidence into `待验证名单`, not the
  core competitive landscape.
- For each competition dimension, cite the supporting source type and source
  name.
- Do not rank companies by real-time performance unless verified market data
  is provided.
- Do not provide direct trading instructions.
