# AkShare A 股研究接口目录

本文整理 AkShare 中适合补充 `a-share-market-researcher` 的公开数据
接口。内容只记录可查询的数据类型、业务用途和使用边界，不记录实现细节。

来源基准：

- 仓库：`git@github.com:akfamily/akshare.git`
- 本次扫描提交：`f077137 Dev (#7276)`
- 扫描日期：`2026-05-23`
- 扫描文档：`docs/data/*/*.md`
- 接口规模：共 1006 个文档化接口，其中股票 372、指数 87、宏观 215、
  基金 90、债券 43、期货 54。

## 使用规则

先按研究问题选择数据能力，再选择接口。AkShare 是公开数据接口库，不等同于
法定披露或付费数据库；下游必须保留来源名、访问时间、报告期、口径和缺失
行为。

| 规则 | 要求 |
|---|---|
| 概念和行业标签 | 只能作为股票池和业务暴露线索，不得单独证明公司主题暴露。 |
| 行情、估值和资金流 | 作为 `public_market_data`，用于筛选、排序、快照和市场语境。 |
| 巨潮、交易所和定期报告 | 可作为 `official_disclosure` 或 `official_statistics`，优先级高于新闻和板块标签。 |
| 新闻、热度、研报和股评 | 只能作为 `third_party` 线索，不得支撑核心入选理由。 |
| 互动平台和 IR 问答 | 作为 `company_public_material`，需要和公告、年报或半年报交叉验证。 |
| 资金流、北向和龙虎榜 | 只能说明交易行为和市场关注，不说明基本面优劣。 |
| 宏观和商品数据 | 可补行业背景、成本和需求代理变量，但不能替代单家公司披露。 |

## 快速选择

按下表把研究流程中的数据缺口映射到 AkShare 数据能力。

| 研究问题 | 可查数据类型 | 优先接口 | 推荐落地文件 |
|---|---|---|---|
| 这个主题有哪些候选 A 股？ | 全 A 名单、概念板块、行业板块、指数成份 | `stock_info_a_code_name`, `stock_board_concept_name_em`, `stock_board_concept_cons_em`, `stock_board_industry_name_em`, `stock_board_industry_cons_em`, `index_stock_cons_csindex` | `candidate_peer_universe.csv`, `peer_universe.csv` |
| 候选股票当前交易状态如何？ | 实时价格、涨跌幅、成交额、换手率、市值、估值 | `stock_zh_a_spot_em`, `stock_bid_ask_em`, `stock_zh_a_st_em`, `stock_tfp_em` | `market_snapshot.csv` |
| 短期和中期走势如何？ | 日线、分时、分笔、前复权收益率 | `stock_zh_a_hist`, `stock_zh_a_hist_min_em`, `stock_intraday_em`, `stock_zh_a_tick_tx` | `market_snapshot.csv` |
| 主题板块是否在扩散？ | 概念/行业指数、板块实时行情、板块异动、板块资金流 | `stock_board_concept_spot_em`, `stock_board_concept_hist_em`, `stock_board_industry_spot_em`, `stock_board_industry_hist_em`, `stock_board_change_em`, `stock_sector_fund_flow_rank` | `market_context.csv` |
| 公司基本面和财务表现如何？ | 业绩报表、快报、预告、三表、关键指标 | `stock_yjbb_em`, `stock_yjkb_em`, `stock_yjyg_em`, `stock_financial_analysis_indicator_em`, `stock_financial_abstract`, `stock_zcfz_em`, `stock_lrb_em`, `stock_xjll_em` | `financial_summary.csv`, `financial_statements.csv` |
| 公司是否真实暴露于主题？ | 主营构成、主营介绍、公司概况、公告、调研 | `stock_zygc_em`, `stock_zyjs_ths`, `stock_profile_cninfo`, `stock_zh_a_disclosure_report_cninfo`, `stock_zh_a_disclosure_relation_cninfo`, `stock_individual_notice_report` | `company_exposure.md` |
| 有哪些事件和风险？ | ST、停复牌、解禁、回购、质押、担保、诉讼、董监高持股变动 | `stock_zh_a_st_em`, `stock_tfp_em`, `stock_restricted_release_summary_em`, `stock_repurchase_em`, `stock_gpzy_pledge_ratio_em`, `stock_cg_guarantee_cninfo`, `stock_cg_lawsuit_cninfo`, `stock_share_hold_change_sse`, `stock_share_hold_change_szse`, `stock_share_hold_change_bse` | `events_and_risks.md` |
| 交易资金是否支持主题？ | 个股资金流、行业资金流、概念资金流、北向持股、融资融券、龙虎榜 | `stock_individual_fund_flow`, `stock_individual_fund_flow_rank`, `stock_sector_fund_flow_hist`, `stock_concept_fund_flow_hist`, `stock_hsgt_hold_stock_em`, `stock_hsgt_individual_em`, `stock_margin_detail_sse`, `stock_margin_detail_szse`, `stock_lhb_detail_em` | `market_context.csv`, `events_and_risks.md` |
| 市场估值和指数背景如何？ | 指数行情、指数成份、指数权重、指数估值、市场 PE/PB | `stock_zh_index_spot_em`, `index_zh_a_hist`, `index_stock_cons_weight_csindex`, `stock_zh_index_value_csindex`, `stock_a_ttm_lyr`, `stock_a_all_pb`, `stock_index_pe_lg`, `stock_index_pb_lg` | `market_context.csv` |
| 宏观和行业代理指标如何？ | GDP、CPI、PPI、PMI、固定资产投资、社零、用电、货币供应、进出口 | `macro_china_gdp`, `macro_china_cpi`, `macro_china_ppi`, `macro_china_pmi`, `macro_china_gdzctz`, `macro_china_consumer_goods_retail`, `macro_china_society_electricity`, `macro_china_money_supply`, `macro_china_hgjck` | `macro_context.csv` |
| 上游成本或周期品是否影响主题？ | 期货行情、库存、仓单、现货与股票关系 | `futures_zh_spot`, `futures_hist_em`, `futures_inventory_em`, `futures_warehouse_receipt_dce`, `futures_warehouse_receipt_czce`, `futures_shfe_warehouse_receipt`, `futures_spot_stock` | `macro_context.csv`, `sector_context.md` |
| 机构持仓是否与主题重合？ | 基金重仓股、基金行业配置、基金持仓、ETF 行情 | `fund_report_stock_cninfo`, `fund_report_industry_allocation_cninfo`, `fund_portfolio_hold_em`, `fund_etf_spot_em` | `market_context.csv` |

## 股票池和主题识别

这些接口适合生成候选股票池、确认股票基础信息、补充板块或指数来源。
除交易所、中证和巨潮来源外，概念/行业板块只能作为线索。

| 数据类型 | 接口 | 业务用途 | 来源等级 |
|---|---|---|---|
| 全 A 股票代码和简称 | `stock_info_a_code_name`, `stock_info_sh_name_code`, `stock_info_sz_name_code`, `stock_info_bj_name_code` | 标准化股票池，补齐交易所和简称。 | `public_market_data` |
| 东方财富概念板块列表和成份 | `stock_board_concept_name_em`, `stock_board_concept_cons_em` | 从主题词生成候选池，记录概念来源。 | `third_party` 线索 |
| 东方财富行业板块列表和成份 | `stock_board_industry_name_em`, `stock_board_industry_cons_em` | 生成行业候选池和 peer 分组。 | `third_party` 线索 |
| 同花顺概念指数和简介 | `stock_board_concept_index_ths`, `stock_board_concept_info_ths` | 补充概念描述和历史表现。 | `third_party` 线索 |
| 同花顺行业指数和一览 | `stock_board_industry_summary_ths`, `stock_board_industry_index_ths` | 观察行业热度和行业内分组。 | `third_party` 线索 |
| 中证指数成份和权重 | `index_stock_cons_csindex`, `index_stock_cons_weight_csindex` | 识别指数成份、权重和基准组合。 | `official_statistics` |
| 巨潮行业分类和变更 | `stock_industry_category_cninfo`, `stock_industry_change_cninfo` | 验证公司官方行业归属变化。 | `official_disclosure` |
| 申万行业分类历史 | `stock_industry_clf_hist_sw` | 识别申万行业归属和历史迁移。 | `third_party` |

## 行情、估值和流动性

这些接口适合补充 `market_snapshot.csv`。行情字段必须带访问时间或行情
时间戳；没有时间戳时不能用于排序。

| 数据类型 | 接口 | 业务用途 | 备注 |
|---|---|---|---|
| 全 A 实时行情 | `stock_zh_a_spot_em` | 获取价格、涨跌幅、成交额、市值、换手、PE、PB 等快照。 | 当前抓取器可优先扩展该接口。 |
| 分市场实时行情 | `stock_sh_a_spot_em`, `stock_sz_a_spot_em`, `stock_bj_a_spot_em`, `stock_cy_a_spot_em`, `stock_kc_a_spot_em` | 按板块或交易所限制股票池。 | 用于板块范围过滤。 |
| 个股盘口报价 | `stock_bid_ask_em` | 补充买卖盘、委比、盘口流动性。 | 仅作为交易流动性信息。 |
| 个股日线行情 | `stock_zh_a_hist`, `stock_zh_a_daily`, `stock_zh_a_hist_tx` | 计算 5 日、20 日、60 日、120 日收益率和波动。 | 优先用 `stock_zh_a_hist` 的前复权口径。 |
| 分时和分笔 | `stock_zh_a_hist_min_em`, `stock_intraday_em`, `stock_intraday_sina`, `stock_zh_a_tick_tx` | 观察日内成交、冲击成本和异动。 | 只用于短线语境。 |
| 风险警示和退市 | `stock_zh_a_st_em`, `stock_zh_a_stop_em`, `stock_info_sh_delist`, `stock_info_sz_delist` | 排除 ST、退市和风险警示标的。 | 进入风险检查。 |
| A+H 比价 | `stock_zh_ah_spot_em`, `stock_zh_ah_daily`, `stock_zh_ah_name` | 对同时有 H 股的公司补充估值折溢价背景。 | 延迟行情，不能当实时交易数据。 |
| 板块行情 | `stock_board_concept_spot_em`, `stock_board_industry_spot_em` | 判断主题板块当日强弱。 | 只说明市场表现。 |
| 板块历史行情 | `stock_board_concept_hist_em`, `stock_board_industry_hist_em` | 计算题材相对强弱和阶段涨幅。 | 不证明业务暴露。 |
| 板块异动 | `stock_board_change_em`, `stock_changes_em` | 识别当日板块或盘口异常。 | 用于 why-now 线索。 |
| 涨跌停池 | `stock_zt_pool_em`, `stock_zt_pool_previous_em`, `stock_zt_pool_strong_em`, `stock_zt_pool_zbgc_em`, `stock_zt_pool_dtgc_em` | 识别涨停、炸板、跌停和短线强弱。 | 不用于基本面结论。 |

## 财务、估值和主营业务

这些接口适合补充 `financial_summary.csv`、`financial_statements.csv` 和
`company_exposure.md`。财务字段必须记录报告期、单位和报表口径。

| 数据类型 | 接口 | 业务用途 | 来源等级 |
|---|---|---|---|
| 业绩报表、快报、预告 | `stock_yjbb_em`, `stock_yjkb_em`, `stock_yjyg_em` | 快速比较收入、利润、预告区间和业绩变化。 | `public_market_data` |
| 披露预约 | `stock_yysj_em`, `stock_report_disclosure`, `news_report_time_baidu` | 建立财报日历和催化时间表。 | 巨潮为 `official_disclosure` |
| 关键财务指标 | `stock_financial_abstract`, `stock_financial_abstract_new_ths`, `stock_financial_analysis_indicator_em`, `stock_financial_analysis_indicator` | 补充 ROE、毛利率、净利率、资产负债率、每股指标。 | `public_market_data` |
| 三大报表摘要 | `stock_zcfz_em`, `stock_lrb_em`, `stock_xjll_em` | 按公司抓资产负债表、利润表和现金流量表字段。 | `public_market_data` |
| 东财按报告期三表 | `stock_balance_sheet_by_report_em`, `stock_profit_sheet_by_report_em`, `stock_cash_flow_sheet_by_report_em` | 对比多个报告期的三表趋势。 | `public_market_data` |
| 新浪三表 | `stock_financial_report_sina` | 作为三表数据交叉核验来源。 | `public_market_data` |
| 主营构成 | `stock_zygc_em` | 识别分产品、分地区或分行业收入结构。 | `public_market_data`，需公告核验 |
| 主营介绍 | `stock_zyjs_ths` | 提取公司业务介绍、产品和经营范围线索。 | `third_party` 或 `company_public_material` 线索 |
| 公司概况 | `stock_profile_cninfo`, `stock_individual_info_em`, `stock_individual_basic_info_xq` | 补公司简介、上市信息、行业、注册地和基础资料。 | 巨潮优先 |
| 股本结构 | `stock_zh_a_gbjg_em`, `stock_share_change_cninfo`, `stock_hold_change_cninfo` | 补总股本、流通股本和股本变动。 | 巨潮优先 |
| 估值序列 | `stock_value_em`, `stock_zh_valuation_baidu`, `stock_a_ttm_lyr`, `stock_a_all_pb` | 补 PE、PB、PS 和市场估值分位线索。 | `public_market_data` |

## 公告、调研和业务暴露证据

这些接口优先用于 `company_exposure.md`。当接口来源是公告、巨潮或交易所时，
可作为核心事实来源；当来源是新闻、研报或网页聚合时，只能作为线索。

| 数据类型 | 接口 | 业务用途 | 使用边界 |
|---|---|---|---|
| 沪深京公告 | `stock_zh_a_disclosure_report_cninfo`, `stock_notice_report`, `stock_individual_notice_report` | 查定期报告、重大合同、投资项目、回购、减持、问询回复等。 | 原公告优先。 |
| 调研和关系活动 | `stock_zh_a_disclosure_relation_cninfo`, `stock_jgdy_tj_em`, `stock_jgdy_detail_em` | 查机构调研、业绩说明会和投资者关系记录。 | 管理层表述需公告或年报交叉验证。 |
| 互动平台 | `stock_irm_cninfo`, `stock_irm_ans_cninfo`, `stock_sns_sseinfo` | 查互动易、上证 e 互动的问题和回复。 | 只能作为 `company_public_material`。 |
| 科创板公告 | `stock_zh_kcb_report_em` | 补充科创板公告和报告线索。 | 仍需引用公告时间和标题。 |
| 个股新闻 | `stock_news_em` | 查事件线索和舆情背景。 | `third_party`，不得作为核心证据。 |
| 个股研报和盈利预测 | `stock_research_report_em`, `stock_profit_forecast_em`, `stock_profit_forecast_ths`, `stock_rank_forecast_cninfo` | 查卖方覆盖、盈利预期和评级变化。 | 只能作为市场预期和线索。 |

## 事件、风险和公司行动

这些接口适合补充 `events_and_risks.md`，也可用于 idea shortlist 的排除项。

| 数据类型 | 接口 | 业务用途 | 来源等级 |
|---|---|---|---|
| 停复牌 | `stock_tfp_em`, `news_trade_notify_suspend_baidu` | 识别无法交易或临时停复牌风险。 | `public_market_data` |
| ST 和退市风险 | `stock_zh_a_st_em`, `stock_zh_a_stop_em`, `stock_staq_net_stop` | 过滤风险警示和退市标的。 | `public_market_data` |
| 限售解禁 | `stock_restricted_release_summary_em`, `stock_restricted_release_detail_em`, `stock_restricted_release_queue_em`, `stock_restricted_release_stockholder_em` | 识别解禁规模、时间和股东。 | `public_market_data` |
| 回购 | `stock_repurchase_em` | 识别公司回购计划和进展。 | 需公告核验。 |
| 分红配送 | `stock_fhps_em`, `stock_fhps_detail_em`, `stock_dividend_cninfo`, `stock_history_dividend` | 补现金分红、送转、除权除息。 | 巨潮优先。 |
| 配股和增发 | `stock_allotment_cninfo`, `stock_pg_em`, `stock_qbzf_em` | 识别再融资和股本摊薄。 | 巨潮优先。 |
| 质押 | `stock_gpzy_pledge_ratio_em`, `stock_gpzy_pledge_ratio_detail_em`, `stock_gpzy_individual_pledge_ratio_detail_em`, `stock_cg_equity_mortgage_cninfo` | 识别股权质押比例和重要股东质押。 | 巨潮优先。 |
| 担保和诉讼 | `stock_cg_guarantee_cninfo`, `stock_cg_lawsuit_cninfo` | 补充公司治理和潜在负债风险。 | `official_disclosure` |
| 董监高及股东变动 | `stock_share_hold_change_sse`, `stock_share_hold_change_szse`, `stock_share_hold_change_bse`, `stock_ggcg_em`, `stock_shareholder_change_ths` | 识别减持、增持和管理层持股变化。 | 交易所优先。 |
| 股东户数历史快照 | 东方财富 `RPT_HOLDERNUM_DET`（当前抓取）；`stock_hold_num_cninfo`（后续季度交叉验证候选） | 补统计截止日、公告日、户数变化、户均持股与总股本等可审计事实。 | 当前必须使用东方财富个股历史详情完整分页和双日期可见性，不得用全市场最新报表 `RPT_HOLDERNUMLATEST` 代替历史序列；户均持股映射 `AVG_HOLD_NUM`。巨潮季度数据仅作为后续官方交叉验证候选。不得据此判断筹码集中、吸筹或价格方向。 |
| 商誉 | `stock_sy_profile_em`, `stock_sy_yq_em`, `stock_sy_jz_em`, `stock_sy_em`, `stock_sy_hy_em` | 检查商誉规模和减值风险。 | `public_market_data` |

## 资金流、交易行为和市场热度

这些接口只能说明市场关注和交易行为。输出中必须避免把资金流、龙虎榜或热度
写成基本面改善。

| 数据类型 | 接口 | 业务用途 | 使用边界 |
|---|---|---|---|
| 个股资金流 | `stock_fund_flow_individual`, `stock_individual_fund_flow`, `stock_individual_fund_flow_rank` | 观察个股短期资金净流入和排名。 | 只用于市场语境。 |
| 行业和概念资金流 | `stock_fund_flow_industry`, `stock_fund_flow_concept`, `stock_sector_fund_flow_rank`, `stock_sector_fund_flow_summary`, `stock_sector_fund_flow_hist`, `stock_concept_fund_flow_hist` | 判断题材扩散和资金集中度。 | 不证明主题暴露。 |
| 主力和大单 | `stock_main_fund_flow`, `stock_fund_flow_big_deal` | 观察主力净流入和大单交易。 | 只能作为交易线索。 |
| 大宗交易逐笔事实 | `stock_dzjy_mrmx` / 东方财富 `RPT_DATA_BLOCKTRADE` | 补成交价、成交量、成交额、折溢价和公开买卖方营业部。 | AkShare 当前实现固定首个 5000 行且不翻页，长窗口可能截断；当前接入按股票池直接完整分页。不得推断吸筹、利益输送或价格方向。 |
| 北向资金和持股 | `stock_hsgt_fund_flow_summary_em`, `stock_hsgt_hist_em`, `stock_hsgt_hold_stock_em`, `stock_hsgt_individual_em`, `stock_hsgt_individual_detail_em`, `stock_hsgt_board_rank_em` | 补外资流向、持股和板块排行。 | 北向不是基本面证据。 |
| 融资融券 | `stock_margin_sse`, `stock_margin_detail_sse`, `stock_margin_szse`, `stock_margin_detail_szse`, `stock_margin_account_info`, `stock_margin_ratio_pa` | 补杠杆交易、融资买入和融券卖出。 | 用作交易风险。 |
| 龙虎榜 | `stock_lhb_detail_em`, `stock_lhb_stock_statistic_em`, `stock_lhb_jgmmtj_em`, `stock_lhb_jgstatistic_em`, `stock_lhb_detail_daily_sina` | 识别营业部和机构席位交易。 | 不用于基本面判断。 |
| 热度和搜索 | `stock_hot_rank_em`, `stock_hot_rank_latest_em`, `stock_hot_rank_detail_em`, `stock_hot_search_baidu`, `stock_hot_keyword_em`, `stock_comment_em` | 观察舆情、关注度和情绪。 | `third_party` 线索。 |

## 指数、市场估值和基准

这些接口适合补充 `market_context.csv`，用于行业研究报告的市场背景和估值
参照。

| 数据类型 | 接口 | 业务用途 | 来源等级 |
|---|---|---|---|
| A 股指数实时和历史行情 | `stock_zh_index_spot_em`, `stock_zh_index_spot_sina`, `index_zh_a_hist`, `stock_zh_index_daily_em` | 补基准指数表现和大盘背景。 | `public_market_data` |
| 中证指数成份和权重 | `index_stock_cons_csindex`, `index_stock_cons_weight_csindex` | 构建指数基准、权重和成份股池。 | `official_statistics` |
| 中证指数估值 | `stock_zh_index_value_csindex` | 补指数 PE、PB、股息率等估值。 | `official_statistics` |
| 国证指数 | `index_all_cni`, `index_hist_cni`, `index_detail_cni`, `index_detail_hist_cni`, `index_detail_hist_adjust_cni` | 补国证指数、样本和调样。 | `official_statistics` |
| 申万指数 | `sw_index_first_info`, `index_hist_sw` | 补申万行业指数行情。 | `third_party` |
| 市场估值 | `stock_a_ttm_lyr`, `stock_a_all_pb`, `stock_market_pe_lg`, `stock_market_pb_lg`, `stock_index_pe_lg`, `stock_index_pb_lg` | 补 A 股整体或指数估值分位语境。 | `public_market_data` |
| 市场统计 | `stock_sse_summary`, `stock_szse_summary`, `stock_sse_deal_daily`, `stock_szse_sector_summary`, `macro_china_stock_market_cap` | 补市场总貌、成交、市值和融资语境。 | 交易所优先。 |

## 宏观、产业和商品代理变量

这些接口适合补充 `macro_context.csv` 或 `sector_context.md`。它们用于解释
需求、成本、库存和周期背景，不用于证明单家公司订单或收入。

| 数据类型 | 接口 | 业务用途 |
|---|---|---|
| 宏观增长和价格 | `macro_china_gdp`, `macro_china_gdp_yearly`, `macro_china_cpi`, `macro_china_cpi_yearly`, `macro_china_ppi`, `macro_china_ppi_yearly` | 补经济、通胀和工业品价格背景。 |
| 景气指标 | `macro_china_pmi`, `macro_china_pmi_yearly`, `macro_china_cx_pmi_yearly`, `macro_china_non_man_pmi`, `macro_china_enterprise_boom_index` | 解释制造业和服务业景气度。 |
| 投资、消费和贸易 | `macro_china_gdzctz`, `macro_china_consumer_goods_retail`, `macro_china_hgjck`, `macro_china_exports_yoy`, `macro_china_imports_yoy`, `macro_china_trade_balance` | 补终端需求和外需背景。 |
| 金融条件 | `macro_china_money_supply`, `macro_china_new_financial_credit`, `macro_china_lpr`, `macro_china_reserve_requirement_ratio`, `macro_china_shibor_all` | 补流动性和融资条件。 |
| 行业代理指标 | `macro_china_society_electricity`, `macro_china_mobile_number`, `macro_china_energy_index`, `macro_china_commodity_price_index`, `macro_china_construction_index`, `macro_china_lpi_index` | 为电力、消费电子、能源、建材、物流等主题提供代理变量。 |
| 期货行情 | `futures_zh_spot`, `futures_zh_realtime`, `futures_hist_em`, `futures_zh_daily_sina` | 补原材料、能源和农产品价格。 |
| 库存和仓单 | `futures_inventory_em`, `futures_inventory_99`, `futures_warehouse_receipt_dce`, `futures_warehouse_receipt_czce`, `futures_shfe_warehouse_receipt`, `futures_gfex_warehouse_receipt` | 判断供需边际和库存压力。 |
| 现货与股票 | `futures_spot_stock`, `futures_spot_sys`, `spot_goods` | 连接商品现货价格和相关股票线索。 |
| 可转债 | `bond_zh_hs_cov_spot`, `bond_zh_hs_cov_daily`, `bond_zh_hs_cov_min`, `bond_cov_comparison`, `bond_cb_jsl` | 补可转债行情、转股溢价率和股债联动。 |

## 基金、ETF 和机构持仓

这些接口适合补充机构持仓和 ETF 语境。它们说明资金配置和市场偏好，不直接
证明企业基本面。

| 数据类型 | 接口 | 业务用途 |
|---|---|---|
| 基金重仓股 | `fund_report_stock_cninfo`, `stock_report_fund_hold`, `stock_report_fund_hold_detail` | 观察公募基金持仓和主题拥挤度。 |
| 基金行业配置 | `fund_report_industry_allocation_cninfo`, `fund_portfolio_industry_allocation_em` | 判断机构对行业的配置方向。 |
| 基金资产配置 | `fund_report_asset_allocation_cninfo`, `fund_portfolio_hold_em` | 补组合资产和持仓结构。 |
| ETF 行情和列表 | `fund_etf_spot_em`, `fund_etf_hist_em`, `fund_etf_category_sina`, `fund_etf_fund_info_em` | 补主题 ETF、行业 ETF 和市场交易工具。 |
| 基金持仓资产 | `fund_individual_detail_hold_xq`, `fund_portfolio_hold_em`, `fund_portfolio_bond_hold_em` | 识别基金持仓资产和主题篮子。 |
| 基金排行和规模 | `fund_open_fund_rank_em`, `fund_exchange_rank_em`, `fund_aum_em`, `fund_scale_open_sina` | 观察资金规模和产品热度。 |

## 可补充到 research-pack 的建议字段

在不改变现有契约的前提下，可以新增可选文件或字段。缺失时仍按 `来源缺失`
处理。

| 文件 | 建议字段 | 支持接口 | 业务用途 |
|---|---|---|---|
| `candidate_peer_universe.csv` | `candidate_source`, `candidate_board`, `candidate_score`, `verification_status` | `stock_board_concept_cons_em`, `stock_board_industry_cons_em`, `index_stock_cons_csindex` | 保留候选来源和线索属性。 |
| `market_snapshot.csv` | `volume_ratio`, `amplitude`, `turnover_rate`, `pe_ttm`, `pb`, `market_cap`, `float_market_cap`, `return_60d`, `return_120d` | `stock_zh_a_spot_em`, `stock_zh_a_hist` | 补交易、估值和阶段表现。 |
| `financial_summary.csv` | `report_type`, `report_date`, `yoy_revenue`, `yoy_net_profit`, `roe`, `gross_margin`, `net_margin`, `debt_ratio`, `ocf` | `stock_yjbb_em`, `stock_financial_analysis_indicator_em`, `stock_financial_abstract` | 补财务质量和可比口径。 |
| `financial_statements.csv` | `statement_type`, `period`, `line_item`, `value`, `unit` | `stock_zcfz_em`, `stock_lrb_em`, `stock_xjll_em`, `stock_balance_sheet_by_report_em`, `stock_profit_sheet_by_report_em`, `stock_cash_flow_sheet_by_report_em` | 支持 EV、现金流和资产负债分析。 |
| `company_exposure.md` | 主营构成、产品、客户、公告标题、调研摘录、互动平台摘录 | `stock_zygc_em`, `stock_zyjs_ths`, `stock_profile_cninfo`, `stock_zh_a_disclosure_report_cninfo`, `stock_zh_a_disclosure_relation_cninfo`, `stock_irm_ans_cninfo` | 形成主题暴露证据链。 |
| `events_and_risks.md` | ST、停复牌、解禁、减持、质押、回购、担保、诉讼、商誉、问询 | `stock_zh_a_st_em`, `stock_tfp_em`, `stock_restricted_release_summary_em`, `stock_gpzy_pledge_ratio_em`, `stock_repurchase_em`, `stock_cg_guarantee_cninfo`, `stock_cg_lawsuit_cninfo`, `stock_sy_em` | 建立风险排除和催化检查。 |
| `market_context.csv` | 指数表现、板块表现、资金流、北向、融资融券、龙虎榜 | `index_zh_a_hist`, `stock_board_concept_hist_em`, `stock_sector_fund_flow_hist`, `stock_hsgt_hist_em`, `stock_margin_detail_sse`, `stock_lhb_detail_em` | 为研究 note 提供市场语境。 |
| `macro_context.csv` | PMI、PPI、社零、固定资产投资、商品价格、库存、用电 | `macro_china_pmi`, `macro_china_ppi`, `macro_china_consumer_goods_retail`, `macro_china_gdzctz`, `futures_hist_em`, `futures_inventory_em`, `macro_china_society_electricity` | 为行业景气和成本分析提供代理变量。 |

## 不建议作为核心证据的数据

以下数据可以保留在研究线索或市场语境里，但不得作为主题暴露、订单、收入、
客户或技术路线的核心证据。

| 数据类型 | 接口示例 | 原因 |
|---|---|---|
| 概念板块标签 | `stock_board_concept_cons_em`, `stock_board_concept_info_ths` | 标签可滞后或泛化，不能证明收入暴露。 |
| 新闻和内容聚合 | `stock_news_em`, `stock_news_main_cx` | 新闻可能转载、滞后或缺少原始披露。 |
| 个股热度和搜索 | `stock_hot_rank_em`, `stock_hot_search_baidu`, `stock_hot_keyword_em` | 热度代表关注，不代表业务事实。 |
| 千股千评和投票 | `stock_comment_em`, `stock_zh_vote_baidu` | 主观评价不能支撑研究结论。 |
| 龙虎榜和资金流 | `stock_lhb_detail_em`, `stock_main_fund_flow`, `stock_individual_fund_flow` | 交易行为不能替代基本面证据。 |
| 卖方研报和预测 | `stock_research_report_em`, `stock_profit_forecast_em`, `stock_profit_forecast_ths` | 可作市场预期，不可替代公告或财报。 |
