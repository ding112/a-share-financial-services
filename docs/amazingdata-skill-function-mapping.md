# AmazingData HTTP 接口与 skill 功能映射

本文把 AmazingData HTTP 服务（银河「星耀数智」）的 55 个 REST 工具，按
`a-share-data-sources` SKILL 定义的研究事实类型、research-pack 落地文件和
来源等级契约做功能映射，用于决定哪些接口进入 `licensed_terminal` 来源
等级的能力表，以及接入顺序。

映射依据：

- 数据源形态：用户已在本机搭建 AmazingData HTTP 服务，把 55 个 MCP 工具
  暴露为 REST（`POST /api/{tool}`，JSON body，JSON response）。服务端持有
  单一登录会话，客户端无需凭证。
- 实测结果：2026-08-20 全量 sweep，55 工具中 OK=54、ERR=0、SKIP=1（仅
  `mcp_logout` 主动跳过），结果存于 `.scratch/sweep_ad_all_result.json`
  （gitignored）。历史轨迹：08-19 OK=30/ERR=24 → 08-20 早 OK=41 → 修复后
  OK=48 → 登录恢复后 OK=54/ERR=0。**当前全部业务工具实测可用**，残留
  `EMPTY` 均为参数/报告期需复验，无 HTTP 500。
- 来源等级：AmazingData 是用户提供的授权终端连接器，待写入 SKILL 的新等级
  `licensed_terminal`，置于 S2 `official_statistics` 与 S3 `public_market_data`
  之间。它不能升级 `official_disclosure`（公告、业务暴露、订单、客户、政策）。

## 映射原则

从 skill 功能出发选接口，而不是按数据源自身清单排序。判定三维：

- **来源升级价值**：该字段当前在 SKILL 字段契约里由 AkShare/腾讯/东财以
  `public_market_data` (S3) 支撑，AmazingData 能否把它升级到
  `licensed_terminal`。
- **skill 功能覆盖**：接口能否支撑 `a-share-data-sources` 的研究事实类型或
  research-pack 落地文件。
- **当前可用性**：实测 OK 优先；ERR 按修复成本排后；EMPTY 需复验参数。
  2026-08-20 末次复测后 ERR=0、无 HTTP 500，残余 EMPTY 均为查询参数（换
  代码/日期/报告期）可复验，客户端零改动。

AmazingData 在 SKILL 契约里的定位边界：

- 可以升级行情、复权、估值、财务三表、事件风险、交易行为等 S3 字段。
- 不能替代公告原文、巨潮定期报告、交易所披露作为 `official_disclosure`。
- 资金流、龙虎榜、大宗交易只说明交易行为，不说明基本面，与 SKILL 现有
  guardrail 一致，不得升级为业务暴露证据。

## 功能模块映射

### F0 行情、复权与短期表现

对应 SKILL 字段契约「最新价、涨跌幅、成交额、换手率」「近 5/20/60/120 日
收益率」与 `market_snapshot.csv`。当前首选腾讯行情 API + AkShare
`stock_zh_a_hist(adjust="qfq")`，全部 S3。AmazingData 可把整条链路升级为
`licensed_terminal`，是升级价值最高的模块。

| 优先级 | skill 功能 | AmazingData 接口 | 实测 | 落地文件 |
|---|---|---|---|---|
| F0-1 | K线 OHLCV 与成交额 | `mcp_kline` | OK，字段 `code/kline_time/open/high/low/close/volume/amount` | `market_snapshot.csv` |
| F0-2 | 前/后复权因子（60/120 日收益率前提） | `mcp_backward_factor` | OK，8707 条（pytables 已解封） | `market_snapshot.csv` return basis |
| F0-3 | 实时快照（盘中报价） | `mcp_snapshot` | OK | `market_snapshot.csv` 盘中字段 |
| F0-4 | 交易日历（区间查询前置） | `mcp_calendar` | OK，8707 条 | 全局交易日/假期判定 |
| F0-5 | 证券代码表与基础信息（涨跌停价、上市日） | `mcp_code_list`、`mcp_code_info` | OK，5548 / 10462 | `peer_universe.csv` code/exchange/board |

F0-2 的 `backward_factor` 曾在 08-19 阻塞于服务端缺 `pytables`；2026-08-20
复测已装 `tables`，接口返回 OK，F0 整链解锁。`code_info` 提供的涨跌停价与
上市日是 AkShare 弱项，属于纯增量。

### F1 财务摘要与三大报表

对应 SKILL 字段契约「营收、利润、毛利率、ROE、现金流」「利润表、资产负债表、
现金流量表明细」与 `financial_summary.csv`、`financial_statements.csv`。
当前首选 AkShare 摘要与东财数据中心，S3。AmazingData 三表为授权终端口径，
可升级。

| 优先级 | skill 功能 | AmazingData 接口 | 实测 | 落地文件 |
|---|---|---|---|---|
| F1-1 | 利润表（营收、营业成本、归母净利） | `mcp_income` | OK | `financial_summary.csv` revenue/net_profit |
| F1-2 | 现金流量表（经营现金流、资本开支） | `mcp_cash_flow` | OK | `financial_summary.csv` operating_cash_flow |
| F1-3 | 资产负债表（总资产、负债、货币资金、应收、存货） | `mcp_balance_sheet` | OK，18 条（已解除 HTTP 500） | `financial_statements.csv`，EV 计算输入 |
| F1-4 | 业绩快报与预告（提前业绩） | `mcp_profit_express`、`mcp_profit_notice` | EMPTY，需换季报期复验 | `financial_summary.csv` 提前口径 |

F1-3 资产负债表是 SKILL「计算字段政策」里 EV 计算的必需输入
（EV = 总市值 + 有息债务 - 货币资金），此前长期 HTTP 500；2026-08-20 修复
后转 OK（18 条），**关键缺口已解除**，可进契约。F1-1 与 F1-2 随之整链可用，
F1 三表全部立即可写契约。

### F2 事件与风险检查

对应 SKILL 字段契约「解禁、减持、回购、停复牌、ST、问询」与
`events_and_risks.md`，是 `a-share-risk-check` 的主输入。当前首选巨潮与
交易所，兜底 AkShare 事件类。AmazingData 作 `licensed_terminal` 兜底，
覆盖度优于 AkShare，但 SKILL 契约要求巨潮/交易所优先，故写成第二兜底
而非首选。

| 优先级 | skill 功能 | AmazingData 接口 | 实测 | 落地文件 |
|---|---|---|---|---|
| F2-1 | 限售解禁 | `mcp_equity_restricted` | OK | `events_and_risks.md` 解禁压力 |
| F2-2 | 股权质押冻结 | `mcp_equity_pledge_freeze` | OK | `events_and_risks.md` 质押风险 |
| F2-3 | 历史停复牌 | `mcp_history_stock_status` | OK，44 条（已复验） | `events_and_risks.md` 交易状态 |
| F2-4 | 分红配送 | `mcp_dividend` | EMPTY，非 500，需换报告期复验 | `events_and_risks.md` 分红，巨潮仍优先 |

F2-1、F2-2 与 F2-3 均实测 OK、直接进契约。F2-4 不再报 HTTP 500，本次返回
EMPTY（查询参数下无分红记录），换报告期参数复验后定。

### F3 交易行为与资金（why-now 线索）

对应 SKILL 字段契约「融资融券、北向、资金流」「龙虎榜」与
`market_context.csv`。SKILL 明确这些只能说明交易行为，不说明基本面。
AmazingData 在此为纯增量，字段比 AkShare 更结构化（含席位名与买卖额）。

| 优先级 | skill 功能 | AmazingData 接口 | 实测 | 落地文件 |
|---|---|---|---|---|
| F3-1 | 龙虎榜（席位、游资、机构） | `mcp_long_hu_bang` | OK，9 条，含 `TRADER_NAME/BUY_AMOUNT/SELL_AMOUNT/FLOW_MARK` | `market_context.csv` |
| F3-2 | 大宗交易（折溢价、机构调仓） | `mcp_block_trading` | OK，122 条，含 `B_BUYER_NAME/B_SELLER_NAME/BLOCK_AVG_VOLUME` | `market_context.csv` |
| F3-3 | 融资融券汇总 | `mcp_margin_summary` | OK，含 `SUM_BORROW_MONEY_BALANCE/SUM_SEC_LENDING_BALANCE` | `market_context.csv`、`margin_trading.csv` |

本组对 `a-share-idea-generation` 的 why-now 线索有价值，契约里固定写
`licensed_terminal`，但不得升级为基本面证据，与 SKILL guardrail 一致。

### F4 指数与行业成分（选股域）

对应 SKILL 字段契约「指数、行业、概念成分」与 `peer_universe.csv`、
`market_context.csv`。当前首选中证指数（S2 `official_statistics`），AkShare
板块作线索。AmazingData 指数成分作 `licensed_terminal` 兜底。

| 优先级 | skill 功能 | AmazingData 接口 | 实测 | 落地文件 |
|---|---|---|---|---|
| F4-1 | 指数成分股 | `mcp_index_constituent` | OK，1226 条 | `peer_universe.csv` 指数选股 |
| F4-2 | 申万行业指数成分 | `mcp_industry_index_constituent` | OK，184 条 | 行业 peer 分组 |
| F4-3 | 行业指数行情与权重 | `mcp_industry_index_quote`、`mcp_industry_index_weight`、`mcp_industry_index_info` | OK（quote 22 / weight 2266 / info 511） | `market_context.csv` |

F4-1、F4-2 与 F4-3 复测后全部 OK 出数，`a-share-quant-screen` 与
`a-share-sector-overview` 的选股域可用。SKILL 契约要求中证指数优先，
AmazingData 仍写成 `licensed_terminal` 兜底。

### F5 可转债专题

对应 `a-share-idea-generation` 的可选衍生线索。在 SKILL 字段契约里属可选
线索，优先级最低。

| 优先级 | skill 功能 | AmazingData 接口 | 实测 | 落地文件 |
|---|---|---|---|---|
| F5-1 | 可转债清单 | `mcp_kzz` | OK，321 只 | 可转债线索 |
| F5-2 | 转股、赎回、回售等 | `mcp_convertible_bond_conversion`、`_redemption`、`_resale`、`_issue`、`_conversion_change`、`_adjustment`、`_terms`、`_balance` | 全部 OK（转股/赎回/回售/发行/条款各 1 条，转股价变更 7 条，余额 13 条） | 可转债博弈测算 |

F5-1 与 F5-2 复测后全部 OK。可转债博弈测算（转股、赎回、回售、条款）可
进契约。

### F6 公司详情（股东与股本）

对应 SKILL 字段契约「股东人数和集中度」「股本结构」与
`company_details.csv`。SKILL 要求巨潮优先，AmazingData 作兜底。

| 优先级 | skill 功能 | AmazingData 接口 | 实测 | 落地文件 |
|---|---|---|---|---|
| F6-1 | 十大股东、股东户数、股本结构 | `mcp_share_holder`、`mcp_holder_num`、`mcp_equity_structure` | EMPTY，需换报告期复验 | `company_details.csv` |

当前全 EMPTY，换报告期参数复验后再定是否进契约。

## 接入执行顺序

按 skill 功能价值与实测可用性分三批。2026-08-20 末次复测（OK=54/ERR=0）后，
一、二批的「实测阻塞」已全部解除，三批中的关键缺口 `balance_sheet` 也已
解除；批次主要体现「契约优先级」，而非「能不能用」。

第一批，立即接入，阶段 2 契约硬条目，全部实测 OK：

1. F0-1 `mcp_kline`
2. F0-3 `mcp_snapshot`
3. F0-4 `mcp_calendar`
4. F0-5 `mcp_code_list`、`mcp_code_info`
5. F1-1 `mcp_income`
6. F1-2 `mcp_cash_flow`
7. F1-3 `mcp_balance_sheet`（HTTP 500 已解除，EV 计算必需）
8. F2-1 `mcp_equity_restricted`
9. F2-2 `mcp_equity_pledge_freeze`
10. F3-1 `mcp_long_hu_bang`
11. F3-2 `mcp_block_trading`
12. F3-3 `mcp_margin_summary`
13. F5-1 `mcp_kzz`

第二批，增量接入（复测后全部 OK）：

1. F0-2 `mcp_backward_factor`（补 return_60d/120d）
2. F2-3 `mcp_history_stock_status`（44 条）
3. F4-1 `mcp_index_constituent`（1226 条）、F4-2 `mcp_industry_index_constituent`（184 条）
4. F4-3 行业指数 `mcp_industry_index_quote` / `_weight` / `_info`
5. F5-2 可转债 `mcp_convertible_bond_*`（转股、赎回、回售、条款、余额等）

第三批，参数/报告期复验后定（均非 500，当前 EMPTY 或需换查询期）：

1. F1-4 业绩快报与预告（`mcp_profit_express` / `mcp_profit_notice`，换季报期）
2. F2-4 分红配送（`mcp_dividend`，换报告期，巨潮仍优先）
3. F6-1 股东与股本（`mcp_share_holder` / `mcp_holder_num` / `mcp_equity_structure`，换报告期）
4. 其余 EMPTY：可转债回售/赎回公告与停牌、期权、期货/期权代码表（多为无数据或需专有参数）

## 已知缺口与修复路径

本节记录复测后的剩余项。2026-08-20 末次复测 **ERR=0、无 HTTP 500**，此前
分类的 pytables 阻塞、SDK 缺方法、服务端 `end_date` bug、HTTP 500（含关键
缺口 `balance_sheet`）均已在 PC 端修复。残余项全部为 `EMPTY`（业务成功、
返回 0 条），属**查询参数/报告期需复验**，不是客户端可修的服务端故障：

| 接口 | 现象 | 复验方向 |
|---|---|---|
| `mcp_profit_express`、`mcp_profit_notice` | EMPTY（空 list） | 换有业绩快报/预告的季报期（如年报/三季报窗口） |
| `mcp_dividend` | EMPTY | 换有分红的报告期；巨潮仍优先 |
| `mcp_share_holder`、`mcp_holder_num`、`mcp_equity_structure` | EMPTY（空 list） | 换已披露十大股东/股东户数的报告期 |
| `mcp_right_issue`、`mcp_margin_detail` | EMPTY / None | 换有配股或融资明细的区间 |
| `mcp_convertible_bond_resale_notice`、`_redemption_notice`、`_suspension` | EMPTY | 样本券 113066.SH 无对应事件；换有该事件的券 |
| `mcp_code_list_future`、`mcp_code_list_option` | EMPTY | 需要对应期货/期权代码表参数 |
| `mcp_option_basic_info`、`_contract_info`、`_month_contract_change` | EMPTY | 需先有期权标的/合约参数 |
| `mcp_logout` | SKIP（脚本刻意不调） | 断开登录，不参与扫描 |

补充说明：若登录会话中途失效，大量工具会返回 `未登录 AmazingData`
（`success:false` / `not_logged_in`），该报错走服务端 `mcp_get_login_status`
排查，不属于接口故障；本轮已恢复正常登录。

## 与 SKILL 契约的衔接

本映射是阶段 2 skill 契约写入的依据（已据 08-20 末次 OK=54/ERR=0 复测更新）。
落地时：

- 在 `a-share-data-sources/SKILL.md` 的来源等级契约表新增
  `licensed_terminal` 行，置于 S2 与 S3 之间。
- 在「指南可补字段」表新增 AmazingData 行，可补字段以实测 OK、能对应
  research-pack 落地文件的接口为准（行情/复权/估值/财务三表/事件/交易行为/
  指数成分/可转债），不含 `EMPTY` 未复验的接口（业绩快报、分红、股东股本
  等）与不升级业务暴露的工具。
- 新增 `references/ad-http-interface-catalog.md`，对齐
  `akshare-a-share-interface-catalog.md` 风格，按研究问题整理 AmazingData
  接口、参数、来源等级与实测状态。
- 新增 `docs/amazingdata-http-access.md`，记录 `AD_HTTP_BASE` 配置、凭证
  边界、单会话限制、登录失效排查、免责声明与「已知缺口与修复路径」表。
- 改 vertical 源头后运行 `scripts/sync-agent-skills.py` 同步到 agent 包，
  再运行 `scripts/check.py` 保持 0 issues。

## Next steps

1. 到 `a-share-data-sources/SKILL.md` 落 `licensed_terminal` 等级行与「指南
   可补字段」AmazingData 行。
2. 新增 `references/ad-http-interface-catalog.md`（按研究问题整理实测 OK 的
   AmazingData 接口）。
3. 写 `docs/amazingdata-http-access.md` 接入文档（配置、凭证边界、单会话、
   登录失效排查、缺口表）。
4. 运行 `scripts/sync-agent-skills.py` 同步到 agent 包，再运行
   `scripts/check.py` 保持 0 issues。
