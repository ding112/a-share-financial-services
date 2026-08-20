# AmazingData 授权终端 A 股研究接口目录

本文整理 AmazingData 授权终端 HTTP 服务（银河「星耀数智」）中适合补充
`a-share-market-researcher` 的接口。内容只记录可查询的数据类型、参数、业务
用途、来源等级和实测状态，不记录实现细节，也不要求下游实现接口调用。

来源基准：

- 服务形态：用户已在本机搭建 AmazingData HTTP 服务，把 55 个 MCP 工具暴露
  为 REST（`POST /api/{tool}`，JSON body，JSON response）。服务端持有单一
  登录会话，客户端无需凭证；只通过 `AD_HTTP_BASE` 访问，配置见
  `docs/amazingdata-http-access.md`。
- 实测结果：2026-08-20 全量 sweep（`.scratch/sweep_ad_all_result.json`，
  gitignored）55 工具中 OK=54、ERR=0、SKIP=1（仅 `mcp_logout` 主动跳过，
  且中途未登录态恢复后复验）。**全部业务接口实测可用**，残余 `EMPTY` 均为
  查询参数/报告期需复验，无 HTTP 500。
- 来源等级：AmazingData 定位 `licensed_terminal`（S2.5），置于
  `official_statistics`（S2）与 `public_market_data`（S3）之间。它可以升级
  行情、复权、估值、财务三表、事件风险、交易行为等 S3 字段，不能升级
  `official_disclosure`（公告、业务暴露、订单、客户、政策）。

## 使用规则

| 规则 | 要求 |
|---|---|
| licensed_terminal 升级 | 可升级行情、复权、估值、财务三表、事件风险、交易行为等 S3 字段；是比 `public_market_data` 更高的来源等级。 |
| official_disclosure 边界 | 不得替代公告原文、巨潮定期报告或交易所披露作为 `official_disclosure`。 |
| 交易行为证据边界 | 资金流、龙虎榜、大宗交易只说明交易行为，不说明基本面；不得升级为业务暴露证据。 |
| 代码格式 | 证券代码带市场后缀，例如 `000001.SZ`、`600519.SH`、`113066.SH`。 |
| 复权因子 | 前/后复权因子是 60/120 日收益率计算前提，需注明复权基准日或计算日期。 |
| 行情时间戳 | 快照或 K线无行情时间戳时不得用于最新表现排序（对齐 SKILL 降级规则）。 |
| 单会话限制 | 服务端持单一登录会话，同一账号并发登录会被停服；调用期间勿在别处登录。 |

## 快速选择

按下表把研究流程中的数据缺口映射到 AmazingData 数据能力。

| 研究问题 | 可查数据类型 | 优先接口 | 推荐落地文件 |
|---|---|---|---|
| 候选股票当前交易状态如何？ | 实时快照、成交额、换手率、盘中报价 | `mcp_snapshot` | `market_snapshot.csv` |
| 短期和中期走势如何？ | 日线 OHLCV、成交额、前复权收益率 | `mcp_kline`, `mcp_backward_factor` | `market_snapshot.csv` |
| 交易日历与假期如何？ | 交易日历（区间查询前置） | `mcp_calendar` | 全局交易日/假期判定 |
| 候选股票的基础信息是什么？ | 证券代码表、涨跌停价、上市日 | `mcp_code_list`, `mcp_code_info` | `peer_universe.csv` |
| 公司财务表现如何？ | 利润表、资产负债表、现金流量表 | `mcp_income`, `mcp_balance_sheet`, `mcp_cash_flow` | `financial_summary.csv`, `financial_statements.csv` |
| 有哪些事件和风险？ | 限售解禁、股权质押、历史停复牌 | `mcp_equity_restricted`, `mcp_equity_pledge_freeze`, `mcp_history_stock_status` | `events_and_risks.md` |
| 交易资金是否支持主题？ | 龙虎榜、大宗交易、融资融券 | `mcp_long_hu_bang`, `mcp_block_trading`, `mcp_margin_summary` | `market_context.csv`, `margin_trading.csv` |
| 指数与行业成分有哪些？ | 指数成分、申万行业成分、行业指数行情/权重 | `mcp_index_constituent`, `mcp_industry_index_constituent`, `mcp_industry_index_quote`, `_industry_index_weight` | `peer_universe.csv`, `market_context.csv` |
| 是否有可转债线索？ | 可转债清单、转股/赎回/回售/条款 | `mcp_kzz`, `mcp_convertible_bond_conversion`, `_redemption`, `_resale`, `_terms` | 可转债博弈测算 |

## F0 行情、复权与短期表现

对应 SKILL 字段契约「最新价、涨跌幅、成交额、换手率」「近 5/20/60/120 日
收益率」与 `market_snapshot.csv`。当前首选腾讯行情 API + AkShare
`stock_zh_a_hist(adjust="qfq")`，全部 `public_market_data`（S3）；AmazingData
可将整条链路升级为 `licensed_terminal`（S2.5），是升级价值最高的模块。
F0 的 6 个接口在 2026-08-20 全量 sweep 中全部实测 OK。

| 数据类型 | 接口 | 参数（实测） | 业务用途 | 来源等级 | 实测 |
|---|---|---|---|---|---|
| K线 OHLCV 与成交额 | `mcp_kline` | `code_list`, `begin_date`, `end_date`, `period=day`, `limit`；列 `code/kline_time/open/high/low/close/volume/amount` | 计算 5/20/60/120 日收益率、观察阶段走势。 | `licensed_terminal` | OK |
| 前/后复权因子 | `mcp_backward_factor` | `code_list`；返回按代码分键，count 8707 | 前复权收益率计算前提（60/120 日收益率 basis）。 | `licensed_terminal` | OK |
| 实时快照（盘中报价） | `mcp_snapshot` | `code_list`；返回 `code_count`，按日期分键 | 最新价、涨跌幅、成交额、换手率等盘中字段。 | `licensed_terminal` | OK |
| 交易日历 | `mcp_calendar` | `market=SH`；返回 `success/market/query_date/count/calendar`，count 8708 | 区间查询前置、全局交易日/假期判定。 | `licensed_terminal` | OK |
| 证券代码表 | `mcp_code_list` | `security_type=EXTRA_STOCK_A`；返回 `security_type/count/code_list`，count 5548 | 股票池 code/exchange，标准化证券代码。 | `licensed_terminal` | OK |
| 证券基础信息 | `mcp_code_info` | `security_type=EXTRA_STOCK_A`；返回 count 10457，列 `symbol/security_status/pre_close/high_limited/low_limited/price_tick/list_day` | 涨跌停价（`high_limited/low_limited`）、上市日（`list_day`）——AkShare 弱项，纯增量。 | `licensed_terminal` | OK |

落地说明：

- `mcp_kline` 与 `mcp_backward_factor` 组合可替代 AkShare 前复权口径计算
  `return_5d/20d/60d/120d`；复权因子需注明复权基准日。
- `mcp_code_info` 的涨跌停价与上市日是 AkShare 弱项，属纯增量字段，写入
  `peer_universe.csv` 的 code/exchange/board 与基础信息列。
- `mcp_calendar` 是区间查询前置；缺失时不得假定任意日为交易日。
- 快照与 K线字段必须带行情时间戳，无时间戳不得用于排序。

## 财务摘要与三大报表（F1）

对应 SKILL 字段契约「营收、利润、毛利率、ROE、现金流」「利润表、资产负债表、
现金流量表明细」与 `financial_summary.csv`、`financial_statements.csv`。
AmazingData 三表为授权终端口径（S2.5），可升级东财/巨潮的 S3 兜底。实测
全部 OK。

| 数据类型 | 接口 | 业务用途 | 来源等级 | 实测 |
|---|---|---|---|---|
| 利润表 | `mcp_income` | 营收、营业成本、归母净利等。 | `licensed_terminal` | OK |
| 现金流量表 | `mcp_cash_flow` | 经营现金流、资本开支等。 | `licensed_terminal` | OK |
| 资产负债表 | `mcp_balance_sheet` | 总资产、负债、货币资金、应收、存货；EV 计算必需（EV = 市值 + 有息债务 - 货币资金）。已解除历史 HTTP 500。 | `licensed_terminal` | OK，18 条 |

## 事件与风险检查（F2）

对应 SKILL 字段契约「解禁、减持、回购、停复牌、ST、问询」与
`events_and_risks.md`。SKILL 契约要求巨潮/交易所优先，AmazingData 作
`licensed_terminal` 兜底（覆盖度优于 AkShare）。

| 数据类型 | 接口 | 业务用途 | 来源等级 | 实测 |
|---|---|---|---|---|
| 限售解禁 | `mcp_equity_restricted` | 解禁规模、时间、股东。 | `licensed_terminal` | OK |
| 股权质押冻结 | `mcp_equity_pledge_freeze` | 质押比例与冻结风险。 | `licensed_terminal` | OK |
| 历史停复牌 | `mcp_history_stock_status` | 交易状态、停复牌区间。 | `licensed_terminal` | OK，44 条 |

## 交易行为与资金（F3，why-now 线索）

对应 SKILL 字段契约「融资融券、北向、资金流」「龙虎榜」与
`market_context.csv`。只说明交易行为，不说明基本面；不得升级为业务暴露
证据。

| 数据类型 | 接口 | 业务用途 | 来源等级 | 实测 |
|---|---|---|---|---|
| 龙虎榜 | `mcp_long_hu_bang` | 席位、游资、机构，含 `TRADER_NAME/BUY_AMOUNT/SELL_AMOUNT/FLOW_MARK`。 | `licensed_terminal` | OK，9 条 |
| 大宗交易 | `mcp_block_trading` | 折溢价、机构调仓，含 `B_BUYER_NAME/B_SELLER_NAME/BLOCK_AVG_VOLUME`。 | `licensed_terminal` | OK，122 条 |
| 融资融券汇总 | `mcp_margin_summary` | 融资余额、融券余额，含 `SUM_BORROW_MONEY_BALANCE/SUM_SEC_LENDING_BALANCE`。 | `licensed_terminal` | OK |

## 指数与行业成分（F4，选股域）

对应 SKILL 字段契约「指数、行业、概念成分」与 `peer_universe.csv`、
`market_context.csv`。SKILL 要求中证指数（S2 `official_statistics`）优先，
AmazingData 作选股域兜底。

| 数据类型 | 接口 | 业务用途 | 来源等级 | 实测 |
|---|---|---|---|---|
| 指数成分股 | `mcp_index_constituent` | `000300.SH` 等指数成分选股。 | `licensed_terminal` | OK，1226 条 |
| 申万行业指数成分 | `mcp_industry_index_constituent` | `801010.SI` 等申万行业 peer 分组。 | `licensed_terminal` | OK，184 条 |
| 行业指数行情/权重/信息 | `mcp_industry_index_quote`, `mcp_industry_index_weight`, `mcp_industry_index_info` | 行业指数行情、权重与分类信息。 | `licensed_terminal` | OK |

## 可转债专题（F5）

对应 `a-share-idea-generation` 的可选衍生线索，优先级最低。

| 数据类型 | 接口 | 业务用途 | 来源等级 | 实测 |
|---|---|---|---|---|
| 可转债清单 | `mcp_kzz` | 全市场可转债列表。 | `licensed_terminal` | OK，321 只 |
| 转股/赎回/回售/条款 | `mcp_convertible_bond_conversion`, `_redemption`, `_resale`, `_issue`, `_conversion_change`, `_adjustment`, `_terms`, `_balance` | 可转债博弈测算数据。 | `licensed_terminal` | OK |

## 公司详情（F6）与待复验接口

F6 股东与股本（`mcp_share_holder`、`mcp_holder_num`、`mcp_equity_structure`）
及业绩快报/预告（`mcp_profit_express`、`mcp_profit_notice`）、分红
（`mcp_dividend`）在实测中返回 `EMPTY`（业务成功、0 条），属查询参数/报告期
需复验，非接口故障；换报告期或代码后可定是否进契约。各接口实测状态以最新
sweep 结果（`.scratch/sweep_ad_all_result.json`）为准。

## 不建议作为核心证据的数据

与 SKILL guardrail 一致：AmazingData 的资金流、龙虎榜、大宗交易（F3）只能
说明交易行为和市场关注，不得作为主题暴露、订单、收入、客户或技术路线的
核心证据；AmazingData 行情与财务数据不得冒充法定披露事实。
