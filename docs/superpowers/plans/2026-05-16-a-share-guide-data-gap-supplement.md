# A股接入指南数据缺口补充 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `A股数据源接入指南.md` 中已验证的腾讯行情 API、同花顺 AKShare 财务摘要和东方财富数据中心能力补充进 `a-share-market-researcher` 的数据源映射、comps 口径和文档说明。

**Architecture:** 采用最小改动的指令与文档方案，不在 `financial-services` 仓库复制抓取脚本，不新增 Python 依赖，不新增 MCP server。`a-share-data-sources` 继续作为唯一数据源目录，新增“指南可补字段”和“仍缺字段”分层；`a-share-comps-analysis` 使用这些字段填补行情、估值、财务摘要和三大报表缺口；cookbook README 与路线图明确当前 managed agent 默认只能读取文件，不能直接执行网络抓取。

**Tech Stack:** Markdown skills、YAML managed-agent manifests、现有 `scripts/sync-agent-skills.py`、现有 `scripts/check.py`；参考外部本地文件 `/Users/ding/workspace/mengzai/stock-analysis/model-builder/A股数据源接入指南.md`，但不把该外部路径写成运行时依赖。

---

## 文件结构

本计划只更新 `financial-services` 仓库内的 agent 指令、skill 和文档。外部
`stock-analysis/model-builder` 里的脚本保持不变，只作为实现口径参考。

- Modify: `plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md`
  - 职责：补充腾讯行情 API、同花顺 AKShare 财务摘要、东方财富数据中心三类免费来源，并把它们映射到字段级缺口。
- Modify: `plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md`
  - 职责：让 comps 表优先使用指南可补字段，并显式区分外部数据、计算值、模型假设和缺失来源。
- Modify: `plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md`
  - 职责：说明可读取用户提供的数据包和导出文件，但当前 managed agent 不默认执行网络请求。
- Modify: `managed-agent-cookbooks/a-share-market-researcher/README.md`
  - 职责：记录指南可补数据、运行时限制、数据包契约和仍缺数据。
- Modify: `docs/china-equity-trading-roadmap.md`
  - 职责：把腾讯行情、同花顺 AKShare、东方财富数据中心加入公开数据源方向。
- Sync: `python3 scripts/sync-agent-skills.py`
  - 职责：把 vertical source skills 同步到 `plugins/agent-plugins/a-share-market-researcher/skills/`。

## 已确认的补充范围

`A股数据源接入指南.md` 能补齐以下研究字段：

| 来源 | 可补字段 | 来源类型 | 口径要求 |
|---|---|---|---|
| 腾讯行情 API | 名称、最新价、昨收、今开、最高、最低、涨跌幅、成交量、成交额、换手率、动态 PE、流通市值、总市值 | `public_market_data` | 访问时间或行情时间戳，盘中快照 |
| 同花顺 AKShare 财务摘要 | 近 5 年营收、净利润、扣非净利润、营收增速、净利增速、EPS、BPS、经营现金流/股、毛利率、净利率、ROE、资产负债率 | `public_market_data` | 报告期，年报或报告期口径 |
| 东方财富数据中心 | 利润表、资产负债表、现金流量表字段，包括营业收入、成本、归母净利润、总资产、总负债、货币资金、应收账款、存货、经营现金流、资本开支、折旧摊销 | `public_market_data` | 报告期，合并报表，金额单位 |
| 计算字段 | 总股本、流通股本、营收 CAGR、利润 CAGR、EV、EV/Revenue、EV/EBITDA | `public_market_data` + `calculated` 口径 | 写明公式和输入来源 |

仍不能补齐以下研究字段：行业规模、行业增速、渗透率、公司业务真实暴露、
订单、产能、客户、技术路线、公告风险事件、资金流、两融、北向、5 日和
20 日历史涨跌幅、peer universe 自动生成。

### Task 1: 更新 A 股数据源目录

**Files:**
- Modify: `plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md`

- [ ] **Step 1: 验证当前数据源目录存在且还没有指南来源分层**

Run:

```bash
test -f plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md
! rg -n "腾讯行情 API|东方财富数据中心|指南可补字段|计算字段政策" plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md
```

Expected: 第一条命令以 `0` 退出；第二条命令以 `0` 退出，表示这些新术语当前不存在。

- [ ] **Step 2: 用补充后的完整内容重写数据源目录**

Run:

```bash
cat > plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md <<'MARKDOWN'
---
name: a-share-data-sources
description: 为 A 股研究字段映射免费或公开数据源，分类来源质量，并在缺少可靠来源时显式标记来源缺失。用于 A 股行业概览、竞争格局、可比公司、想法清单、事件检查和风险检查。
---

# A-share data sources

使用本 skill 判断每个 A 股研究字段可以由哪个免费或公开来源支持。本 skill
不增加付费终端、隐藏接口或供应商权限。如果字段不能从下列来源或用户提供
材料验证，标记为 `来源缺失`。

## 来源优先级

按以下顺序选择每条事实的最高质量来源：

1. **法定披露和官方文件**：巨潮资讯、上交所、深交所、北交所、公司公告、
   定期报告、临时公告、交易所问询和回复、监管规则、政策文件。
2. **官方统计和监管数据**：国家统计局、中国人民银行、证监会、交易所市场
   数据、交易所融资融券数据、中证指数公开资料。
3. **公开行情和结构化数据**：腾讯行情 API、AkShare 可访问的公开行情、
   同花顺 AKShare 财务摘要、东方财富数据中心、指数、行业和个股基础数据；
   东方财富和同花顺公开页面只作为可复核来源或底层公开源线索。
4. **公司和行业公开材料**：公司官网、投资者关系活动记录、业绩说明会、
   行业协会公开报告、部委或地方政府产业文件。
5. **第三方研究、新闻和用户上传材料**：只作为线索或用户提供来源。必须
   标明 `user_provided` 或 `third_party`，不得把概念标签当成业务暴露证据。

## 指南可补字段

`A股数据源接入指南.md` 验证了三类免费来源。它们可以补齐行情、估值、
财务摘要和三大报表缺口，但不能替代公告原文、行业统计或业务暴露证据。

| 数据源 | 可补字段 | 来源类型 | 口径要求 |
|---|---|---|---|
| 腾讯行情 API | 名称、最新价、昨收、今开、最高、最低、涨跌幅、成交量、成交额、换手率、动态 PE、流通市值、总市值 | `public_market_data` | 访问时间或行情时间戳，盘中快照 |
| 同花顺 AKShare 财务摘要 | 近 5 年营收、净利润、扣非净利润、营收增速、净利增速、EPS、BPS、经营现金流/股、毛利率、净利率、ROE、资产负债率 | `public_market_data` | 报告期，年报或报告期口径 |
| 东方财富数据中心 | 利润表、资产负债表、现金流量表字段，包括营业收入、营业成本、归母净利润、总资产、总负债、货币资金、应收账款、存货、经营现金流、资本开支、折旧摊销 | `public_market_data` | 报告期，合并报表，金额单位 |

## 字段映射

| 数据需求 | 首选免费/公开来源 | 可接受兜底 | 缺失数据行为 |
|---|---|---|---|
| 股票代码、简称、交易所 | AkShare 个股基础数据、交易所公司列表、腾讯行情 API 名称字段 | 用户提供股票池 | 标记 `来源缺失`，但保留用户给定代码 |
| 最新价、涨跌幅、成交额、换手率 | 腾讯行情 API、AkShare 公开行情接口 | 东方财富或同花顺公开页面截图/摘录 | 写 `来源缺失`，不要估算 |
| 昨收、今开、最高、最低、成交量 | 腾讯行情 API、AkShare 公开行情接口 | 用户提供行情导出 | 写 `来源缺失`，不要估算 |
| 量比 | AkShare 公开行情接口 | 用户提供行情导出 | 写 `来源缺失`，不要用成交量自行近似 |
| 近 5 日和近 20 日涨跌幅 | AkShare 历史行情自行计算，并注明计算日期 | 用户提供价格序列 | 写 `来源缺失`，不要用记忆补数 |
| 总市值、流通市值、动态 PE | 腾讯行情 API、AkShare 估值或个股指标 | 东方财富公开页交叉核验 | 写 `来源缺失`，注明缺少估值口径 |
| PB、PS | AkShare 估值或个股指标、东方财富公开页交叉核验 | 用户提供数据库导出 | 写 `来源缺失`，注明缺少估值口径 |
| 营收、净利润、扣非净利润、EPS、BPS、经营现金流/股 | 同花顺 AKShare 财务摘要、东方财富数据中心、巨潮资讯定期报告 | 用户提供财务表 | 写 `来源缺失`，不要用行业均值替代 |
| 营收增速、净利增速、毛利率、净利率、ROE、资产负债率 | 同花顺 AKShare 财务摘要、东方财富数据中心、巨潮资讯定期报告 | 用户提供财务表 | 写 `来源缺失`，不要用行业均值替代 |
| 利润表、资产负债表、现金流量表明细 | 东方财富数据中心、巨潮资讯定期报告 | 用户提供三表导出 | 写 `来源缺失`，不要用摘要字段倒推三表 |
| 总股本、流通股本 | 腾讯行情 API 的市值和价格计算；交易所或公告股本数据 | 用户提供股本表 | 若由市值和价格计算，口径写 `计算值: 市值 / 最新价` |
| EV、EV/Revenue、EV/EBITDA | 用户提供模型导出、公开行情与财务数据计算 | 用户提供数据库导出 | 缺少现金、债务或 EBITDA 时写 `来源缺失` |
| 主营业务和主题暴露 | 年报、半年报、投资者关系记录、交易所互动和公告 | 第三方研究或用户摘录 | 进入 `待验证`，不得进入核心证据 |
| 订单、产能、客户、技术路线 | 公司公告、定期报告、投资者关系记录 | 新闻或第三方研究线索 | 进入 `待验证`，注明需公告确认 |
| 行业规模、增速、渗透率 | 国家统计局、部委文件、行业协会公开报告、公司公告引用 | 用户提供行业报告 | 写 `来源缺失`，不要自行外推 |
| 政策催化 | 国务院、发改委、工信部、财政部、证监会、交易所公开文件 | 新闻转载 | 标记 `待验证`，注明原始政策缺口 |
| 解禁、减持、回购、停复牌、ST、监管问询 | 巨潮资讯、交易所公告 | AkShare 事件类数据、用户材料 | 写 `来源缺失`，不得弱化风险 |
| 融资融券、北向、资金流 | 交易所融资融券数据、AkShare 资金流数据 | 东方财富公开页面 | 写 `来源缺失`，不要写方向性判断 |
| 指数、行业、概念成分 | 中证指数公开资料、AkShare 指数和板块数据 | 东方财富和同花顺公开概念页 | 概念标签只作线索，不作暴露证据 |

## 计算字段政策

计算字段可以进入 comps 表，但必须写明公式、输入来源和计算时间。计算字段
不得冒充原始披露数据。

| 计算字段 | 允许公式 | 必须具备的输入 |
|---|---|---|
| 总股本 | 总市值 / 最新价 | 腾讯行情 API 或等价来源的总市值和最新价 |
| 流通股本 | 流通市值 / 最新价 | 腾讯行情 API 或等价来源的流通市值和最新价 |
| 营收 CAGR | 最近一期营收 / 最早一期营收 的年化增长 | 同一来源、同一口径的 2 个以上年度营收 |
| 利润 CAGR | 最近一期净利润 / 最早一期净利润 的年化增长 | 同一来源、同一口径的 2 个以上年度净利润 |
| EV | 总市值 + 有息债务 - 货币资金 | 市值、短期借款、长期借款、货币资金 |
| EV/Revenue | EV / 营业收入 | EV 和同报告期营业收入 |
| EV/EBITDA | EV / EBITDA | EV 和已披露或用户提供的 EBITDA |

## 引用契约

每个已引用字段必须在输出或来源说明里带这些标签：

- `来源类型`: `official_disclosure`、`official_statistics`、
  `public_market_data`、`company_public_material`、`third_party`、
  `user_provided` 或 `missing_source`。
- `来源名称`: 站点、文件、API wrapper 或用户文件名。
- `数据时间`: 发布日期、公告日期、访问日期或行情时间戳。
- `口径`: TTM、LYR、最新季度、收盘价、盘中快照、合并报表、母公司报表
  或计算方法。

## Workflow

1. 列出当前任务需要的字段。
2. 把每个字段映射到来源优先级里最高质量的可用来源。
3. 业务暴露和风险事实优先使用官方披露。
4. 价格、流动性和估值快照优先使用腾讯行情 API 或 AkShare 公开行情。
5. 财务摘要优先使用同花顺 AKShare 财务摘要、东方财富数据中心或定期报告。
6. 每个数字标注来源类型、来源名称、时间戳和口径。
7. 计算字段写明公式和输入来源。
8. 可靠来源不足的字段写入 `来源缺失` 或 `待验证`，不要删除对应行。
9. 在得出结论前，先总结关键来源缺口。

## Guardrails

- 除非用户明确提供导出或连接器，不要把 Wind、Choice、iFinD、Bloomberg、
  CapIQ 或 FactSet 写成可用来源。
- 不要把腾讯行情 API、同花顺 AKShare 或东方财富数据中心写成法定披露来源。
- 不要假设 AkShare 每个 endpoint 都稳定可用。如果接口失败或返回陈旧数据，
  标记字段为 `来源缺失`。
- 不要绕过登录、限流或把非稳定接口行为当成稳定能力。
- 没有行情时间戳时，不要按实时表现给公司排序。
- 不要把概念板块成员关系当成收入暴露证据。
- 不要把模型假设写成事实数据。Beta、无风险利率、ERP、WACC、永续增长率、
  预测增长率和预测利润率必须标记为模型假设。
MARKDOWN
```

Expected: 命令以 `0` 退出，文件被完整重写。

- [ ] **Step 3: 验证指南来源和仍缺字段已写入**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md')
text = p.read_text()
required = [
    '腾讯行情 API',
    '同花顺 AKShare 财务摘要',
    '东方财富数据中心',
    '计算字段政策',
    'EV/Revenue',
    '不要把模型假设写成事实数据',
]
missing = [item for item in required if item not in text]
assert not missing, missing
print('a-share-data-sources guide supplement: ok')
PY
```

Expected:

```text
a-share-data-sources guide supplement: ok
```

- [ ] **Step 4: 提交数据源目录更新**

Run:

```bash
git add plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md
git commit -m "feat: map A-share guide data sources"
```

Expected: commit 成功，且只包含 `a-share-data-sources/SKILL.md`。

### Task 2: 更新 comps skill 的字段口径

**Files:**
- Modify: `plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md`

- [ ] **Step 1: 验证当前 comps skill 存在**

Run:

```bash
test -f plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md
rg -n "Free-source mapping|Required fields|来源缺失" plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md
```

Expected: 两条命令都以 `0` 退出，并能看到当前字段和来源规则。

- [ ] **Step 2: 用补充后的完整内容重写 comps skill**

Run:

```bash
cat > plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md <<'MARKDOWN'
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
- Source plan from `a-share-data-sources`, including the mapped free or public
  source for each required field.
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

1. Normalize stock codes and exchanges before comparing peers.
2. Normalize units for market cap, turnover, revenue, profit, cash, debt, and
   cash-flow fields.
3. Keep valuation definitions consistent across the peer set.
4. Mark suspended, ST, newly listed, loss-making, negative EBITDA, or outlier
   names.
5. If real-time fields are unavailable, keep the row and write `来源缺失` in
   the affected cells.
6. If a computed field lacks any input, keep the field and write `来源缺失`.
7. Summarize what the spread implies for exposure, quality, liquidity, and
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
MARKDOWN
```

Expected: 命令以 `0` 退出，文件被完整重写。

- [ ] **Step 3: 验证 comps 字段组和计算字段政策已写入**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md')
text = p.read_text()
required = [
    'Guide-backed source mapping',
    '腾讯行情 API',
    '同花顺 AKShare 财务摘要',
    '东方财富数据中心',
    'Computed-field policy',
    '字段来源说明',
]
missing = [item for item in required if item not in text]
assert not missing, missing
print('a-share-comps-analysis guide supplement: ok')
PY
```

Expected:

```text
a-share-comps-analysis guide supplement: ok
```

- [ ] **Step 4: 提交 comps skill 更新**

Run:

```bash
git add plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md
git commit -m "feat: refine A-share comps guide sources"
```

Expected: commit 成功，且只包含 `a-share-comps-analysis/SKILL.md`。

### Task 3: 更新 agent prompt 的运行边界

**Files:**
- Modify: `plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md`

- [ ] **Step 1: 验证 agent prompt 存在且当前没有数据包边界说明**

Run:

```bash
test -f plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md
! rg -n "数据包|腾讯行情 API|不默认执行网络请求" plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md
```

Expected: 第一条命令以 `0` 退出；第二条命令以 `0` 退出，表示这些说明还没有写入。

- [ ] **Step 2: 在 Guardrails 中插入运行边界说明**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md')
text = p.read_text()
anchor = '- 外部可调度的是 agent type；`a-share-data-sources` 只在本 Agent 内部作为 skill 使用，不是独立 agent type。\n'
insert = anchor + '- 可以读取用户提供的数据包、CSV、JSON、Markdown 摘录或预先运行的数据抓取结果；当前 managed-agent 配置不默认执行网络请求或 Python 抓取脚本。\n- 若用户提供的数据包来自腾讯行情 API、同花顺 AKShare 财务摘要或东方财富数据中心，按 `public_market_data` 标记，并保留来源名称、访问时间、报告期和口径。\n'
assert anchor in text
text = text.replace(anchor, insert, 1)
p.write_text(text)
PY
```

Expected: 命令以 `0` 退出，Guardrails 新增两条说明。

- [ ] **Step 3: 验证运行边界说明已写入**

Run:

```bash
rg -n "数据包|腾讯行情 API|不默认执行网络请求|public_market_data" plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md
```

Expected output includes:

```text
plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md:33:- 可以读取用户提供的数据包、CSV、JSON、Markdown 摘录或预先运行的数据抓取结果；当前 managed-agent 配置不默认执行网络请求或 Python 抓取脚本。
plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md:34:- 若用户提供的数据包来自腾讯行情 API、同花顺 AKShare 财务摘要或东方财富数据中心，按 `public_market_data` 标记，并保留来源名称、访问时间、报告期和口径。
```

- [ ] **Step 4: 提交 agent prompt 更新**

Run:

```bash
git add plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md
git commit -m "chore: clarify A-share data package boundary"
```

Expected: commit 成功，且只包含 agent prompt 更新。

### Task 4: 更新 cookbook README 和路线图

**Files:**
- Modify: `managed-agent-cookbooks/a-share-market-researcher/README.md`
- Modify: `docs/china-equity-trading-roadmap.md`

- [ ] **Step 1: 验证文档存在**

Run:

```bash
test -f managed-agent-cookbooks/a-share-market-researcher/README.md
test -f docs/china-equity-trading-roadmap.md
```

Expected: 两条命令都以 `0` 退出。

- [ ] **Step 2: 在 cookbook README 的 Free data-source policy 后追加指南补充段落**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('managed-agent-cookbooks/a-share-market-researcher/README.md')
text = p.read_text()
anchor = 'Use these source classes in outputs and internal handoffs:\n'
insert = '''The current managed-agent template is read-only for source data: it can read
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

'''
assert anchor in text
text = text.replace(anchor, insert + anchor, 1)
p.write_text(text)
PY
```

Expected: 命令以 `0` 退出，README 新增指南可补缺口表。

- [ ] **Step 3: 更新路线图的数据源方向段落**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('docs/china-equity-trading-roadmap.md')
text = p.read_text()
old = '''- 公开行情和结构化数据：AkShare 可访问的公开行情、历史行情、估值、资金流、
  指数、行业和个股基础数据。
'''
new = '''- 公开行情和结构化数据：腾讯行情 API、AkShare 可访问的公开行情、历史行情、
  估值、资金流、指数、行业和个股基础数据。
- 指南验证的财务数据：同花顺 AKShare 财务摘要可补近 5 年营收、利润、
  增速、利润率和 ROE；东方财富数据中心可补利润表、资产负债表和现金流量表。
'''
assert old in text
text = text.replace(old, new, 1)
p.write_text(text)
PY
```

Expected: 命令以 `0` 退出，路线图补充腾讯、同花顺和东方财富数据方向。

- [ ] **Step 4: 验证文档补充内容**

Run:

```bash
rg -n "Tencent quote API|Tonghuashun via AkShare|Eastmoney data center|腾讯行情 API|东方财富数据中心" managed-agent-cookbooks/a-share-market-researcher/README.md docs/china-equity-trading-roadmap.md
```

Expected output includes README 中的英文表格行，以及路线图中的中文数据源说明。

- [ ] **Step 5: 提交文档更新**

Run:

```bash
git add managed-agent-cookbooks/a-share-market-researcher/README.md docs/china-equity-trading-roadmap.md
git commit -m "docs: document A-share guide-backed data gaps"
```

Expected: commit 成功，且只包含 README 和路线图更新。

### Task 5: 同步 bundled skills

**Files:**
- Modify generated copy: `plugins/agent-plugins/a-share-market-researcher/skills/a-share-data-sources/SKILL.md`
- Modify generated copy: `plugins/agent-plugins/a-share-market-researcher/skills/a-share-comps-analysis/SKILL.md`

- [ ] **Step 1: 运行 skill 同步脚本**

Run:

```bash
python3 scripts/sync-agent-skills.py
```

Expected: 命令以 `0` 退出。若脚本输出同步文件列表，列表包含 `a-share-data-sources` 和 `a-share-comps-analysis`。

- [ ] **Step 2: 验证 bundled copies 与 vertical sources 一致**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import filecmp
pairs = [
    (
        Path('plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md'),
        Path('plugins/agent-plugins/a-share-market-researcher/skills/a-share-data-sources/SKILL.md'),
    ),
    (
        Path('plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md'),
        Path('plugins/agent-plugins/a-share-market-researcher/skills/a-share-comps-analysis/SKILL.md'),
    ),
]
for src, dst in pairs:
    assert src.exists(), src
    assert dst.exists(), dst
    assert filecmp.cmp(src, dst, shallow=False), (src, dst)
print('a-share bundled skills synced: ok')
PY
```

Expected:

```text
a-share bundled skills synced: ok
```

- [ ] **Step 3: 提交同步结果**

Run:

```bash
git add plugins/agent-plugins/a-share-market-researcher/skills/a-share-data-sources/SKILL.md plugins/agent-plugins/a-share-market-researcher/skills/a-share-comps-analysis/SKILL.md
git commit -m "chore: sync A-share guide-backed skills"
```

Expected: commit 成功，且只包含 bundled skill copies。

### Task 6: 全量校验

**Files:**
- Verify: `plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md`
- Verify: `plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md`
- Verify: `plugins/agent-plugins/a-share-market-researcher/skills/a-share-data-sources/SKILL.md`
- Verify: `plugins/agent-plugins/a-share-market-researcher/skills/a-share-comps-analysis/SKILL.md`
- Verify: `plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md`
- Verify: `managed-agent-cookbooks/a-share-market-researcher/README.md`
- Verify: `docs/china-equity-trading-roadmap.md`

- [ ] **Step 1: 运行仓库检查脚本**

Run:

```bash
python3 scripts/check.py
```

Expected:

```text
OK — 96 file(s) checked, 0 issues.
```

If the file count changes because another tracked file is added before execution, the important expected condition is `0 issues`.

- [ ] **Step 2: 运行聚焦引用检查**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
checks = {
    'plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md': [
        '腾讯行情 API',
        '同花顺 AKShare 财务摘要',
        '东方财富数据中心',
        '计算字段政策',
        'missing_source',
    ],
    'plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md': [
        'Guide-backed source mapping',
        '字段来源说明',
        'EV/Revenue',
        'EV/EBITDA',
    ],
    'plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md': [
        '不默认执行网络请求',
        '腾讯行情 API',
        'public_market_data',
    ],
    'managed-agent-cookbooks/a-share-market-researcher/README.md': [
        'Tencent quote API',
        'Tonghuashun via AkShare financial abstract',
        'Eastmoney data center',
        'missing_source',
    ],
    'docs/china-equity-trading-roadmap.md': [
        '腾讯行情 API',
        '同花顺 AKShare 财务摘要',
        '东方财富数据中心',
    ],
}
for filename, needles in checks.items():
    text = Path(filename).read_text()
    missing = [needle for needle in needles if needle not in text]
    assert not missing, (filename, missing)
print('a-share guide supplement references: ok')
PY
```

Expected:

```text
a-share guide supplement references: ok
```

- [ ] **Step 3: 检查最终 git 状态只包含预期变更或为空**

Run:

```bash
git status --short
```

Expected: 如果每个任务都已提交，输出只允许保留执行前已有的未跟踪 `.claude/` 和 `docs/superpowers/`。不应出现未暂存的 tracked file。

## Self-review

**Spec coverage:** 本计划覆盖用户要求的“从 A 股数据源接入指南补充数据缺口”。Task 1 把指南来源映射到字段；Task 2 把字段用于 comps；Task 3 明确 agent 运行边界；Task 4 写入 cookbook 和路线图；Task 5 同步 agent bundled skills；Task 6 做全量校验。

**Placeholder scan:** 本计划不包含禁用占位表达或未展开的代码步骤。

**Type consistency:** 来源类型统一使用 `public_market_data`、`official_disclosure`、`official_statistics`、`company_public_material`、`third_party`、`user_provided`、`missing_source`。计算字段在文档中统一使用 `计算值` 口径，不新增 schema enum。
