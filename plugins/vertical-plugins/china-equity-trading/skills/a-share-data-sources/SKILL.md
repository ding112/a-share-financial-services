---
name: a-share-data-sources
description: 为 A 股研究字段映射免费或公开数据源，分类来源质量，并在缺少可靠来源时显式标记来源缺失。用于 A 股行业概览、竞争格局、可比公司、想法清单、事件检查和风险检查。
---

# A-share data sources

使用本 skill 判断每个 A 股研究字段可以由哪个免费或公开来源支持。本 skill
不增加付费终端、隐藏接口或供应商权限。如果字段不能从下列来源或用户提供
材料验证，标记为 `来源缺失`。

## 研究事实类型

先判断当前任务需要验证哪类事实，再选择来源。下游技能不得绕过本表自定义
证据标准。

| 事实类型 | 主要用途 | 关键风险 |
|---|---|---|
| 公司是否属于该主题 | `a-share-competitive-analysis`、`a-share-idea-generation` | 概念板块标签替代业务证据 |
| 业务暴露强弱 | `a-share-competitive-analysis`、`a-share-idea-generation` | 用新闻热度替代收入、订单、产品或客户证据 |
| 行业规模、增速、渗透率 | `a-share-sector-overview`、`a-share-competitive-analysis` | 用第三方预测冒充官方统计或披露事实 |
| 政策催化 | `a-share-sector-overview`、`a-share-idea-generation` | 用新闻转载替代原始政策文件 |
| 行情、成交额、换手率、市值 | `a-share-comps-analysis`、`a-share-idea-generation` | 没有行情时间戳仍按最新表现排序 |
| PE、PB、PS、EV multiples | `a-share-comps-analysis` | 口径混用、负利润公司仍使用 PE 排序 |
| 营收、利润、毛利率、ROE、现金流 | `a-share-comps-analysis`、`a-share-idea-generation` | 报告期不一致、摘要字段倒推三大报表 |
| 订单、产能、客户、技术路线 | `a-share-competitive-analysis`、`a-share-idea-generation` | 第三方研究线索替代公告或定期报告证据 |
| 解禁、减持、ST、问询、停复牌 | `a-share-idea-generation`、`a-share-risk-check` | 风险事实缺失后仍弱化风险描述 |
| 催化事件和失效条件 | `a-share-idea-generation` | 只有情绪或涨幅，没有可验证 why-now |

## 来源等级契约

按以下顺序选择每条事实的最高质量来源。来源等级决定事实能支撑的结论强度。

| 来源类型 | 等级 | 可支持的事实 | 不可支持的事实 |
|---|---:|---|---|
| `official_disclosure` | S1 | 主营业务、订单、产能、客户、财务事实、风险事件、公司行动 | 行业整体规模的无来源外推 |
| `official_statistics` | S2 | 行业规模、政策、监管、交易所市场数据、指数公开资料 | 单家公司业务暴露强弱 |
| `public_market_data` | S3 | 行情快照、估值、市值、公开财务摘要、指数或板块基础数据 | 法定披露事实、未经验证的主题暴露 |
| `company_public_material` | S4 | IR 记录、业绩说明会、官网、投资者材料中的管理层表述 | 未披露的订单、收入、客户份额 |
| `third_party` | S5 | 研究线索、新闻背景、待验证观点 | 核心业务暴露、核心 idea 入选依据 |
| `user_provided` | S5 | 用户明确提供的数据包、截图、CSV、JSON、Markdown 摘录 | 未标记来源的数据不能升级为 verified |
| `missing_source` | S6 | 保留字段和缺口说明 | 任何事实性结论 |

## 指南可补字段

`A股数据源接入指南.md` 验证了三类免费来源。它们可以补齐行情、估值、
财务摘要和三大报表缺口，但不能替代公告原文、行业统计或业务暴露证据。

| 数据源 | 可补字段 | 来源类型 | 口径要求 |
|---|---|---|---|
| 腾讯行情 API | 名称、最新价、昨收、今开、最高、最低、涨跌幅、成交量、成交额、换手率、动态 PE、流通市值、总市值 | `public_market_data` | 访问时间或行情时间戳，盘中快照 |
| 同花顺 AKShare 财务摘要 | 近 5 年营收、净利润、扣非净利润、营收增速、净利增速、EPS、BPS、经营现金流/股、毛利率、净利率、ROE、资产负债率 | `public_market_data` | 报告期，年报或报告期口径 |
| 东方财富数据中心 | 利润表、资产负债表、现金流量表字段，包括营业收入、营业成本、归母净利润、总资产、总负债、货币资金、应收账款、存货、经营现金流、资本开支、折旧摊销 | `public_market_data` | 报告期，合并报表，金额单位 |
| AkShare 行情快照 | 量比、振幅（来自 `stock_zh_a_spot_em`） | `public_market_data` | 实时快照，访问时间 |
| AkShare 事件类数据 | ST/退市、停复牌、限售解禁、股权质押 | `public_market_data` | 当日检查 |
| AkShare 板块行情 | 概念板块、行业板块实时行情、板块异动、资金流排名 | `public_market_data` | 当日快照 |
| AkShare 宏观数据 | GDP、CPI、PPI、PMI、固定资产投资、社会消费品零售总额 | `official_statistics` | 最新可用期 |
| AkShare 公司详情 | 主营构成、公司概况、股本结构 | `official_disclosure` / `public_market_data` | 巨潮来源优先 |
| AkShare 北向/融资融券 | 北向资金净流入、北向持股、融资融券余额 | `public_market_data` | 最新可用期 |
| AkShare 基金持仓 | 基金重仓股、ETF 行情 | `public_market_data` | 最新报告期 |
| 东方财富大宗交易 | 逐笔交易日、收盘价、成交价、成交量、成交额、折溢价、公开买卖方营业部 | `public_market_data` | 以研究截止日回溯；API 基础单位；不得推断资金意图或价格方向 |
| 东方财富股东户数 | 个股历史统计截止日、公告日、当期与上期户数、变化、户均持股及市值、总市值、总股本 | `public_market_data` | 使用 `RPT_HOLDERNUM_DET`；统计截止日和公告日双重可见性；API 基础单位；不得推断筹码或价格方向 |
| 深交所互动易、上证e互动 | 股票池内研究截止日前已回复的投资者问答 | `company_public_material` | 问题中的断言不构成事实；只有公司回复属于公司公开材料；公司回复需与公告或定期报告交叉验证 |

## AkShare 接口查询目录

当任务是评估 AkShare 还能补充哪些 A 股研究数据，或需要为 agent 选择可查
数据能力时，读取
`references/akshare-a-share-interface-catalog.md`。该目录按研究问题整理
AkShare 股票、指数、宏观、基金、债券和期货接口，只记录数据类型、业务
用途、来源等级和使用边界，不要求下游实现接口调用。

目录中的概念板块、行业板块、新闻、热度、研报、资金流、龙虎榜和北向数据
只能作为 `third_party`、`public_market_data` 或市场语境线索；不得把它们
升级为主营业务、订单、客户、产能或技术路线证据。巨潮、交易所、中证指数
和国家统计口径的数据可以作为更高等级来源，但仍必须保留访问时间、报告期、
公告标题、指数代码或统计口径。

## 公开数据抓取器

`scripts/fetch_a_share_public_data.py` 是本地公开数据抓取器。它负责
把股票池中的 A 股代码转换为 research-pack 可消费文件：

- `market_snapshot.csv`：行情、成交额、换手率、量比、振幅、市值、公开估值和
  AkShare 前复权短期表现快照（含 5/20/60/120 日收益率）。
- `financial_summary.csv`：公开财务摘要、报告期、盈利质量和资产负债字段。

该抓取器不覆盖行业规模、行业增速、渗透率、政策原文、公司公告、业务暴露、
订单、产能、客户、技术路线。短期表现只使用 AkShare `stock_zh_a_hist(..., adjust="qfq")`
前复权收盘价计算 5/20/60/120 日收益率，缺失时写 `来源缺失`，不得补数。

辅助抓取器：

| 脚本 | 输出文件 | 数据范围 |
|---|---|---|
| `fetch_a_share_events_risks.py` | `events_and_risks.md` | ST、停复牌、限售解禁、股权质押 |
| `fetch_a_share_market_context.py` | `market_context_fund_flow.csv`, `market_context_board_changes.csv`, `market_context_limit_up.csv` | 行业资金流、板块异动、涨停池 |
| `fetch_a_share_macro_context.py` | `macro_context.csv` | GDP、CPI、PPI、PMI |
| `fetch_a_share_company_details.py` | `company_details.csv` | 主营构成、公司概况、股本结构 |
| `fetch_a_share_northbound_margin.py` | `northbound_flow.csv`, `northbound_holdings.csv`, `margin_trading.csv` | 北向资金、融资融券 |
| `fetch_a_share_board_sector.py` | `board_sector_context.csv` | 概念板块和行业板块实时行情 |
| `fetch_a_share_fund_holdings.py` | `fund_heavy_stocks.csv`, `etf_list.csv` | 基金重仓股、ETF 行情 |
| `fetch_a_share_research_reports.py` | `research_reports.csv`, `research_reports/` | 股票池个股及显式东方财富行业代码对应的研报索引和限量 PDF 材料 |
| `fetch_a_share_investor_interactions.py` | `investor_interactions.csv` | 深市互动易与沪市上证e互动中研究截止日前已回复的问答 |

抓取器输出的 `source_manifest.json` 必须保留来源类型、来源名称、访问时间、
报告期或口径、验证状态和缺失行为。下游技能不得把公开行情或公开财务摘要
升级为法定披露事实。

默认财务源是 Eastmoney。只有显式传入 `--financial-source akshare` 时，
抓取器才使用 AkShare `stock_financial_abstract`；此时 AkShare 依赖缺失、
接口失败或字段无法解析必须让命令返回非 0，并在 `fetch_errors.csv` 中保留
失败原因。

`scripts/fetch_a_share_research_reports.py` 是独立研报索引与 PDF 抓取入口。它默认只按
`peer_universe.csv` 中的证券代码检索东方财富个股研报；只有使用者重复传入一个或
多个 `--industry-code` 时，才额外请求这些东方财富行业代码对应的行业研报。不提供
该参数时不发起行业请求，也不从主题名称、概念板块、股票池或自然语言推断行业代码。
默认截至 `as-of` 回溯 730 天，每个证券或显式行业最多保留 20 条；按发布日期降序、
稳定报告 ID 升序排序。索引身份由范围类型、对象标识和报告 ID 共同确定，同一报告 ID
对应的 PDF 内容跨范围复用。东方财富请求使用明确 User-Agent、30 秒超时、串行节流和
最多 3 次有限重试。

研报索引和材料目录统一标记为 `third_party`、`待验证`。默认按同一稳定排序
下载每个证券或显式行业最新 3 份 PDF；可通过 `--pdf-limit-per-security` 调整上限，或用
`--skip-pdf-download` 只保留索引。有效既有文件会直接复用；响应状态、最小
大小或 `%PDF-` 文件签名不合格时不会落盘。PDF 文件名包含稳定报告 ID 和清理、
截断后的标题，索引只写数据包内相对路径。检索成功但无记录时在
`fetch_errors.csv` 写 `research_report_index_no_data`；请求或解析失败时写
`research_report_index`；单份 PDF 失败时保留索引行、将 `local_pdf_path` 写为
`来源缺失` 并记录 `research_report_pdf`。单个证券或行业失败时保留其他对象的成功
结果；全部证券与显式行业索引请求失败时，独立入口写完空索引、来源清单和错误记录后
返回非零。端点和字段映射参考
Apache-2.0 项目 `a-stock-data` 与 AkShare 公开实现，本项目使用标准库按自身
契约重新实现，不把外部项目作为运行时依赖。

`scripts/fetch_a_share_investor_interactions.py` 是独立互动平台问答抓取入口。
它按 `peer_universe.csv` 路由：深市 A 股读取深交所互动易，沪市 A 股读取
上证e互动，北交所当前记录 `investor_interaction_unsupported`。默认按回答时间
截至 `as-of` 回溯 365 天，每证券最多保留 50 条已回复问答；问题时间和回答时间
都不得晚于研究截止日。记录按证券代码、回答时间降序和来源记录 ID 稳定排序，
并生成本地 `iq_` 稳定标识。

问答固定标记为 `company_public_material`、`待验证`。问题由投资者提出，问题中
的断言不构成事实；只有公司回复属于公司公开材料，公司回复需与公告或定期报告
交叉验证，不得单独升级为主营业务、订单、客户、产能、经营质量或投资价值证据。
成功但无已回复问答时写 `investor_interaction_no_data`；请求、响应或解析失败时写
`investor_interaction`。单个证券失败时保留其他证券结果；全部受支持证券失败时，
独立入口写完稳定空表、来源清单和错误记录后返回非零。一键准备把该阶段视为可选
补充数据源，失败只告警并继续核心数据包。

## 自动 research-pack 准备

`scripts/auto_prepare_a_share_research_pack.py` 是 Claude Code 和 managed-agent
data-prep worker 使用的一键准备入口。它负责在 `research-pack/` 缺失时生成
本地可审计输入，不负责写 research note、comps artifact 或投资结论。

运行环境必须在仓库当前目录提供 `.venv/bin/python`，并通过根目录
`requirements.txt` 安装 AkShare。脚本不得自动运行 `pip install`，也不得
下载或执行未列出的脚本。

推荐调用：

```bash
.venv/bin/python scripts/auto_prepare_a_share_research_pack.py \
  --theme 机器人产业链 \
  --as-of 2026-05-22
```

当用户提供 `--peer-universe` 时，脚本以该股票池为准；当没有种子文件时，
脚本用 AkShare 公开概念或行业板块成分生成候选股票池。自动生成的主题
暴露只能标记为 `待验证` 或 `仅作线索`，不得把概念或板块成员关系升级为
业务暴露事实。

自动准备入口写出这些文件：

| 文件 | 用途 |
|---|---|
| `candidate_peer_universe.csv` | 保存公开板块或用户股票池的完整候选，含候选来源、匹配板块和筛选指标。 |
| `peer_universe.csv` | 保存进入 comps 的 8 到 15 只公司；自动生成时 `theme_role` 默认为 `待验证`。 |
| `market_snapshot.csv` | 由公开行情来源生成的行情、估值、市值、流动性、量比、振幅和短期表现快照（含 60/120 日收益率）。 |
| `financial_summary.csv` | 由 Eastmoney 或 AkShare 公开财务摘要生成的最新一期报告期财务字段。 |
| `events_and_risks.md` | 由 AkShare 事件类接口生成的 ST、停复牌、限售解禁和质押风险数据。 |
| `market_context_fund_flow.csv` | 行业资金流排名和主力净流入数据。 |
| `market_context_board_changes.csv` | 板块异动和领涨股数据。 |
| `market_context_limit_up.csv` | 涨停股票池和涨停原因。 |
| `macro_context.csv` | GDP、CPI、PPI、PMI 宏观指标。 |
| `company_details.csv` | 主营构成、公司概况和股本结构。 |
| `annual_reports.csv` | 最近 2 个年报年度的公告标题、公告日期、巨潮链接、PDF 链接和本地 PDF 路径。 |
| `annual_reports/` | 年报 PDF 原文目录，用于后续抽取主营业务、订单、产能、客户和技术路线证据。 |
| `research_reports.csv` | 股票池对应的东方财富个股研报索引；默认回溯 730 天，每证券最多 20 条。 |
| `research_reports/` | 限量研报 PDF 材料目录；默认每证券最新 3 份，可显式跳过下载。 |
| `block_trades.csv` | 股票池对应的东方财富逐笔大宗交易事实；默认回溯 365 天，每证券最多 50 笔。 |
| `shareholder_counts.csv` | 股票池对应的东方财富个股历史股东户数快照；默认按统计截止日回溯 730 天，每证券最多 8 个研究截止日前已公告快照。 |
| `investor_interactions.csv` | 股票池对应的深交所互动易与上证e互动已回复问答；默认按回答时间回溯 365 天，每证券最多 50 条。 |
| `northbound_flow.csv` | 北向资金净流入趋势。 |
| `northbound_holdings.csv` | 北向持股数量和比例。 |
| `margin_trading.csv` | 融资融券余额和买入额。 |
| `board_sector_context.csv` | 概念板块和行业板块实时行情。 |
| `fund_heavy_stocks.csv` | 基金重仓股与 peer 交叉数据。 |
| `etf_list.csv` | ETF 行情列表。 |
| `market_context_stock_fund_flow.csv` | 个股资金流排名和主力净流入数据。 |
| `index_valuation.csv` | 指数估值历史（PE、PB、股息率）。 |
| `market_pe_pb.csv` | A 股整体 PE/PB。 |
| `index_spot.csv` | 主要指数实时行情。 |
| `source_manifest.json` | 声明每个文件的来源类型、来源名称、时间、口径、验证状态和缺失行为。 |
| `fetch_errors.csv` | 记录行情、财务、研报索引、PDF、大宗交易、股东户数和互动问答的无数据或抓取失败；字段失败时下游必须写 `来源缺失`。 |
| `auto_prepare_manifest.json` | 记录主题、输入、输出、候选数量、筛选规则、市场行为事实参数和是否少于 8 只。 |

默认筛选规则是按成交额降序、再按总市值降序、再按来源顺序，过滤名称包含
ST、`*ST` 或退市风险的公司，最多保留 15 只。少于 8 只时可以继续流程，
但必须在输出中提示分析师复核股票池。

市场行为事实阶段默认执行，可以用 `--skip-market-activity` 整体跳过；阶段同时
输出大宗交易和股东户数事实。普通股票池默认使用东方财富，fixture 股票池默认使用离线
fixture。来源完全失败时一键准备只告警并继续核心数据包，独立入口仍保留非零
退出码和稳定空产物。

互动平台问答阶段同样默认执行，可以用 `--skip-investor-interactions` 跳过。
普通股票池按交易所读取深交所互动易或上证e互动，fixture 股票池默认使用离线
fixture；来源完全失败时只告警并继续核心数据包。跳过阶段时必须同时移除旧的
`investor_interactions.csv`、来源清单条目和对应错误记录。

## 字段来源契约

每个字段必须有首选来源、可接受兜底和缺失行为。缺失行为是输出契约的一部分，
不得删除字段来隐藏数据缺口。

| 数据需求 | 首选免费/公开来源 | 可接受兜底 | 缺失数据行为 |
|---|---|---|---|
| 股票代码、简称、交易所 | AkShare 个股基础数据、交易所公司列表、腾讯行情 API 名称字段 | 用户提供股票池 | 标记 `来源缺失`，但保留用户给定代码 |
| 最新价、涨跌幅、成交额、换手率 | 腾讯行情 API、AkShare 公开行情接口 | 东方财富或同花顺公开页面截图/摘录 | 写 `来源缺失`，不要估算 |
| 昨收、今开、最高、最低、成交量 | 腾讯行情 API、AkShare 公开行情接口 | 用户提供行情导出 | 写 `来源缺失`，不要估算 |
| 量比 | AkShare 公开行情接口 | 用户提供行情导出 | 写 `来源缺失`，不要用成交量自行近似 |
| 近 5 日和近 20 日涨跌幅 | AkShare `stock_zh_a_hist(..., adjust="qfq")` 前复权收盘价自行计算，并注明计算日期 | 用户提供价格序列 | 写 `来源缺失`，不要用记忆补数，也不要写成未来收益判断 |
| 近 60 日和近 120 日涨跌幅 | AkShare `stock_zh_a_hist(..., adjust="qfq")` 前复权收盘价自行计算，并注明计算日期 | 用户提供价格序列 | 写 `来源缺失`，不要用记忆补数，也不要写成未来收益判断 |
| 总市值、流通市值、动态 PE | 腾讯行情 API、AkShare 估值或个股指标 | 东方财富公开页交叉核验 | 写 `来源缺失`，注明缺少估值口径 |
| PB、PS | AkShare `stock_value_em` 的 `市销率`、AkShare 估值或个股指标、东方财富公开页交叉核验 | 用户提供数据库导出 | 写 `来源缺失`，注明缺少估值口径 |
| 营收、净利润、扣非净利润、EPS、BPS、经营现金流/股 | AkShare `stock_financial_abstract` 最新一期摘要、东方财富数据中心、巨潮资讯定期报告 | 用户提供财务表 | 写 `来源缺失`，不要用行业均值替代 |
| 营收增速、净利增速、毛利率、净利率、ROE、资产负债率 | AkShare `stock_financial_abstract` 最新一期摘要、东方财富数据中心、巨潮资讯定期报告 | 用户提供财务表 | 写 `来源缺失`，不要用行业均值替代 |
| 利润表、资产负债表、现金流量表明细 | 东方财富数据中心、巨潮资讯定期报告 | 用户提供三表导出 | 写 `来源缺失`，不要用摘要字段倒推三表 |
| 个股研报索引、评级和原始盈利预测 | 东方财富 `reportapi` | 用户提供研报索引 | 固定标记 `third_party`、`待验证`，不得写入财务摘要、业务暴露、估值排序或 idea shortlist |
| 投资者互动问答 | 深交所互动易、上证e互动 | 公司公告、定期报告或用户提供问答摘录 | 固定标记 `company_public_material`、`待验证`；问题断言不构成事实，公司回复需公告核验 |
| 总股本、流通股本 | 腾讯行情 API 的市值和价格计算；交易所或公告股本数据 | 用户提供股本表 | 若由市值和价格计算，口径写 `计算值: 市值 / 最新价` |
| EV、EV/Revenue、EV/EBITDA | 用户提供模型导出、公开行情与财务数据计算 | 用户提供数据库导出 | 缺少现金、债务或 EBITDA 时写 `来源缺失` |
| 主营业务和主题暴露 | 年报、半年报、投资者关系记录、交易所互动和公告 | 第三方研究或用户摘录 | 进入 `待验证`，不得进入核心证据 |
| 订单、产能、客户、技术路线 | 公司公告、定期报告、投资者关系记录 | 新闻或第三方研究线索 | 进入 `待验证`，注明需公告确认 |
| 行业规模、增速、渗透率 | 国家统计局、部委文件、行业协会公开报告、公司公告引用 | 用户提供行业报告 | 写 `来源缺失`，不要自行外推 |
| 政策催化 | 国务院、发改委、工信部、财政部、证监会、交易所公开文件 | 新闻转载 | 标记 `待验证`，注明原始政策缺口 |
| 解禁、减持、回购、停复牌、ST、监管问询 | 巨潮资讯、交易所公告 | AkShare 事件类数据、用户材料 | 写 `来源缺失`，不得弱化风险 |
| 融资融券、北向、资金流 | 交易所融资融券数据、AkShare 资金流数据 | 东方财富公开页面 | 写 `来源缺失`，不要写方向性判断 |
| 指数、行业、概念成分 | 中证指数公开资料、AkShare 指数和板块数据 | 东方财富和同花顺公开概念页 | 概念标签只作线索，不作暴露证据 |
| 量比、振幅 | AkShare `stock_zh_a_spot_em` 全市场实时快照 | 用户提供行情导出 | 写 `来源缺失`，不得自行计算 |
| 60 日、120 日收益率 | AkShare `stock_zh_a_hist` 前复权收盘价自行计算 | 用户提供价格序列 | 写 `来源缺失`，不得写成未来收益判断 |
| 板块异动、领涨股 | AkShare `stock_board_change_em` | 东方财富公开页面 | 用于 why-now 线索，不证明业务暴露 |
| 涨停股票池 | AkShare `stock_zt_pool_em` | 东方财富公开页面 | 不用于基本面结论 |
| 宏观指标 GDP/CPI/PPI/PMI | AkShare 宏观接口 (`macro_china_gdp`, `macro_china_cpi`, `macro_china_ppi`, `macro_china_pmi`) | 国家统计局公开数据 | 用于行业背景，不得外推到单家公司 |
| 主营构成 | AkShare `stock_zygc_em` | 年报、半年报 | 东方财富来源需公告核验 |
| 公司概况 | AkShare `stock_profile_cninfo` | 巨潮资讯 | 巨潮优先 |
| 股本结构 | AkShare `stock_zh_a_gbjg_em` | 交易所或公告 | 巨潮优先 |
| 北向资金和持股 | AkShare `stock_hsgt_fund_flow_summary_em`, `stock_hsgt_hold_stock_em` | 交易所公开数据 | 只说明外资流向，不作为基本面证据 |
| 融资融券余额 | AkShare `stock_margin_sse` | 交易所公开数据 | 用作交易风险参考 |
| 概念/行业板块实时行情 | AkShare `stock_board_concept_spot_em`, `stock_board_industry_spot_em` | 东方财富公开数据 | 不证明业务暴露 |
| 基金重仓股 | AkShare `fund_report_stock_cninfo` | 巨潮基金报告 | 用于观察机构持仓和拥挤度 |
| ETF 行情 | AkShare `fund_etf_spot_em` | 东方财富公开数据 | 用于市场交易工具参考 |
| ST/退市 | AkShare `stock_zh_a_st_em` | 东方财富公开数据 | 进入风险检查 |
| 停复牌 | AkShare `stock_tfp_em` | 东方财富公开数据 | 进入风险检查 |
| 限售解禁 | AkShare `stock_restricted_release_summary_em` | 东方财富公开数据 | 进入风险检查 |
| 股权质押 | AkShare `stock_gpzy_pledge_ratio_em` | 东方财富公开数据 | 进入风险检查 |

## 研究数据包契约

当用户或上游流程提供本地数据包时，优先按本节解析。数据包只表示 agent
可以读取的输入格式；它不是实时数据接入，也不代表这些数据已经通过法定
披露验证。

推荐目录名为 `research-pack/`。如果用户使用其他目录名，文件名和字段契约
仍按本节执行。

| 文件 | 必需性 | 主要用途 | 缺失行为 |
|---|---|---|---|
| `source_manifest.json` | 必需 | 声明每个数据文件的来源、时间、口径和验证状态 | 整个数据包只能作为 `user_provided` 线索，不得升级为 `verified` |
| `peer_universe.csv` | 必需 | 定义 8 到 15 只候选公司、交易所、主题暴露和 peer 分组 | 不能执行 comps 或 idea shortlist，只能要求补股票池 |
| `market_snapshot.csv` | 可选 | 提供行情、估值、市值、流动性、量比、振幅和前复权短期表现快照（含 60/120 日收益率） | 行情、估值、流动性和短期表现字段写 `来源缺失`，不得按最新表现排序 |
| `financial_summary.csv` | 可选 | 提供报告期财务摘要、盈利质量和资产负债字段 | 财务和质量字段写 `来源缺失` 或 `口径不可比` |
| `company_exposure.md` | 可选 | 保存公司业务暴露、订单、产能、客户和产品证据摘录 | 主题暴露只能进入 `待验证`，不得作为核心 idea 入选依据 |
| `events_and_risks.md` | 可选 | 保存催化、监管、减持、解禁、ST、停复牌和失效条件 | 风险字段写 `来源缺失`，不得弱化风险语言 |
| `market_context_fund_flow.csv` | 可选 | 行业资金流排名、主力净流入、大单资金流向 | 只用于市场语境，不作为基本面证据 |
| `market_context_board_changes.csv` | 可选 | 板块异动、涨跌幅、领涨股 | 用于 why-now 线索，不证明业务暴露 |
| `market_context_limit_up.csv` | 可选 | 涨停股票池、涨停原因 | 不用于基本面结论 |
| `macro_context.csv` | 可选 | GDP、CPI、PPI、PMI 宏观指标 | 用于行业背景，不得外推到单家公司 |
| `company_details.csv` | 可选 | 主营构成、公司概况、股本结构 | 巨潮来源可作 `official_disclosure`，需报告期标注 |
| `annual_reports.csv` | 可选 | 最近 2 个年报年度的法定披露索引和本地 PDF 路径 | 缺失时公司业务暴露、订单、产能、客户和技术路线保持 `待验证` |
| `research_reports.csv` | 可选 | 股票池对应的第三方个股研报索引、评级和原始盈利预测字段 | 只作后续核查线索，不进入财务摘要、业务暴露、估值排序或 idea shortlist |
| `research_reports/` | 可选 | 限量研报 PDF 材料目录 | 下载成功只表示材料已定位，不能据此升级验证状态 |
| `block_trades.csv` | 可选 | 股票池内逐笔大宗交易市场行为事实 | 缺失时不推断未发生交易；折溢价和营业部不得解释为吸筹、利益输送或价格方向 |
| `shareholder_counts.csv` | 可选 | 股票池内个股历史股东户数快照 | 缺失时不推断股东户数未变化；不得解释为筹码集中、主力吸筹、买卖方向、股东结构评分或价格因果 |
| `investor_interactions.csv` | 可选 | 股票池内深交所互动易与上证e互动已回复问答 | 缺失时不推断公司未回复；问题断言不得作为事实，公司回复保持 `待验证` 并回到公告或定期报告核验 |
| `northbound_flow.csv` | 可选 | 北向资金净流入趋势 | 只说明外资流向，不作为基本面证据 |
| `northbound_holdings.csv` | 可选 | 北向持股数量和比例 | 只用于市场语境，不说明基本面优劣 |
| `margin_trading.csv` | 可选 | 融资融券余额和买入额 | 用作交易风险参考 |
| `board_sector_context.csv` | 可选 | 概念板块和行业板块实时行情 | 不证明业务暴露 |
| `fund_heavy_stocks.csv` | 可选 | 基金重仓股与 peer 交叉 | 用于观察机构持仓和拥挤度 |
| `etf_list.csv` | 可选 | ETF 行情列表 | 用于市场交易工具参考 |
| `market_context_stock_fund_flow.csv` | 可选 | 个股资金流排名和主力净流入 | 只用于市场语境，不作为基本面证据 |
| `index_valuation.csv` | 可选 | 指数估值历史（PE、PB、股息率） | 来源等级 `official_statistics` |
| `market_pe_pb.csv` | 可选 | A 股整体 PE/PB | 用于市场估值语境 |
| `index_spot.csv` | 可选 | 主要指数实时行情 | 用于大盘背景 |

### `source_manifest.json`

`source_manifest.json` 必须是合法 JSON，并包含顶层 `files` 数组。数组中
每一项描述一个输入文件。

每一项必须包含这些字段：

| 字段 | 含义 |
|---|---|
| `file` | 数据包内的相对文件路径 |
| `source_type` | `来源等级契约` 中定义的来源类型 |
| `source_name` | 站点、API wrapper、导出名称、公告名称或用户文件名 |
| `data_time` | 访问时间、行情时间戳、公告日期或报告日期 |
| `period_or_basis` | 报告期、TTM、LYR、快照、公式或来源口径 |
| `verification_status` | `verified`、`user_provided`、`待验证` 或 `来源缺失` |
| `missing_behavior` | 文件或字段缺失时，下游技能必须如何降级 |

当一个文件内包含不同字段组的来源口径时，可以增加可选字段
`field_group`。例如 `return_5d`、`return_20d` 和 `return_basis` 写在
`market_snapshot.csv` 中，manifest 条目必须保留
`file: "market_snapshot.csv"`，并用 `field_group: "price_performance"`
区分短期表现来源；不得把 `price_performance` 写成不存在的文件路径。

### `peer_universe.csv`

`peer_universe.csv` 是阶段 1 的必需股票池文件。没有这个文件时，agent 不得
自行扩展公司名单来完成 comps 或 idea shortlist。

必需列：

| 字段 | 含义 |
|---|---|
| `code` | A 股证券代码，例如 `300750.SZ` 或 `600519.SH` |
| `name` | 中文证券简称 |
| `exchange` | `SH`、`SZ` 或 `BJ` |
| `board` | 主板、科创板、创业板、北交所或用户自定义板块 |
| `peer_group` | comps 和竞争格局使用的可比分组 |
| `theme_role` | 上游、中游、下游、平台、客户、替代品或其他主题角色 |
| `exposure_summary` | 一句话业务暴露摘要 |
| `exposure_source_ref` | 指向 `company_exposure.md` 或 source manifest 条目的引用 |

### `market_snapshot.csv`

`market_snapshot.csv` 是可选文件。存在时，只能作为带时间戳的行情、估值、
市值、流动性和短期表现快照；没有 `snapshot_time` 的行情字段不得用于排序。
`return_5d` 和 `return_20d` 只能作为历史短期表现展示口径，不进入估值、
流动性或质量统计。

推荐列：

| 字段 | 含义 |
|---|---|
| `code` | 与 `peer_universe.csv` 匹配的证券代码 |
| `price` | 最新价或收盘价 |
| `pct_change` | 快照周期涨跌幅 |
| `amount` | 成交额 |
| `turnover_rate` | 换手率 |
| `volume_ratio` | 量比，来自 AkShare `stock_zh_a_spot_em` |
| `amplitude` | 振幅，来自 AkShare `stock_zh_a_spot_em` |
| `market_cap` | 总市值 |
| `float_market_cap` | 流通市值 |
| `pe_ttm` | TTM 口径 PE |
| `pb` | PB |
| `ps_ttm` | TTM 口径 PS，来自 AkShare `stock_value_em` 的 `市销率` |
| `return_5d` | AkShare 前复权收盘价计算的 5 个交易日收益率，单位为百分比 |
| `return_20d` | AkShare 前复权收盘价计算的 20 个交易日收益率，单位为百分比 |
| `return_60d` | AkShare 前复权收盘价计算的 60 个交易日收益率，单位为百分比 |
| `return_120d` | AkShare 前复权收盘价计算的 120 个交易日收益率，单位为百分比 |
| `return_basis` | 短期表现来源和计算口径，例如 `AkShare 前复权收盘价，截至 <日期>` |
| `snapshot_time` | 行情时间戳或访问时间 |
| `basis` | 快照、收盘、前复权、未复权或用户提供口径 |

### `financial_summary.csv`

`financial_summary.csv` 是可选文件。存在时，财务字段必须带报告期和口径；
报告期不一致时，保留字段但标记 `口径不可比`。当 `--financial-source`
使用 `akshare` 时，只能从 `stock_financial_abstract` 输出每家公司最新一期
一行摘要；默认财务源仍为 Eastmoney。

推荐列：

| 字段 | 含义 |
|---|---|
| `code` | 与 `peer_universe.csv` 匹配的证券代码 |
| `period` | 报告期 |
| `revenue` | 营业收入 |
| `revenue_growth` | 营收增速 |
| `net_profit` | 归母净利润 |
| `deducted_net_profit` | 扣非归母净利润 |
| `gross_margin` | 毛利率 |
| `net_margin` | 净利率 |
| `roe` | ROE |
| `asset_liability_ratio` | 资产负债率 |
| `operating_cash_flow` | 经营现金流 |
| `basis` | 合并、母公司、年度、季度或用户提供口径 |

### `annual_reports.csv`

`annual_reports.csv` 是可选文件。存在时，它只证明本地数据包包含年报原文和
公告索引；下游必须从 PDF 原文或经引用的摘录中抽取具体事实，不能仅凭
`annual_reports.csv` 把业务暴露升级为已验证。

推荐列：

| 字段 | 含义 |
|---|---|
| `code` | 与 `peer_universe.csv` 匹配的证券代码 |
| `name` | 证券简称 |
| `report_year` | 年报年度 |
| `announcement_title` | 巨潮公告标题 |
| `announcement_date` | 公告日期 |
| `disclosure_url` | 巨潮公告详情页链接 |
| `pdf_url` | 巨潮 PDF 原文链接 |
| `local_pdf_path` | research-pack 内的本地 PDF 相对路径 |
| `source_type` | 固定为 `official_disclosure` |
| `source_name` | 固定为 `巨潮资讯` |
| `verification_status` | 固定为 `verified`，仅表示公告来源已定位 |
| `basis` | 年度报告原文 PDF |

### `research_reports.csv`

`research_reports.csv` 是可选的第三方研报索引。它只用于发现后续需要核查的
材料，不得把评级、盈利预测或观点写入 `financial_summary.csv`，也不得单独
证明业务暴露、订单、客户、经营质量或驱动 idea shortlist。即使来源失败，
文件也必须保留稳定表头，`research_reports/` 目录必须存在。

固定列：

| 字段 | 含义 |
|---|---|
| `report_id` | 东方财富稳定研报 ID；与范围类型、对象标识共同构成索引身份，并用于复用 PDF |
| `scope_type` | `stock`（个股）或 `industry`（显式行业） |
| `security_code` | 个股研报为与 `peer_universe.csv` 匹配的标准 A 股证券代码；行业研报留空 |
| `security_name` | 个股研报的证券简称；行业研报留空 |
| `industry_code` | 个股研报为源记录中的行业代码；行业研报为使用者显式提供的东方财富行业代码 |
| `industry_name` | 源记录中的个股或行业名称，缺失时留空 |
| `title` | 研报标题 |
| `institution` | 发布机构简称 |
| `publish_date` | 发布日期 |
| `report_type` | 源记录中的报告类型 |
| `rating` | 源记录中的评级 |
| `profit_forecast_raw` | 按固定字段保留的原始盈利预测 JSON，不并入财务摘要 |
| `detail_url` | 由源记录 `encodeUrl` 定位的东方财富详情链接；源字段缺失时写 `来源缺失` |
| `pdf_url` | 东方财富原始 PDF 定位链接 |
| `local_pdf_path` | 下载成功时为数据包内 `research_reports/` 相对路径；跳过或失败时为 `来源缺失` |
| `source_type` | 固定为 `third_party` |
| `source_name` | 固定为 `东方财富研报` |
| `verification_status` | 固定为 `待验证` |
| `basis` | `as-of`、回溯天数、每证券或显式行业上限和使用边界 |

### `block_trades.csv`

`block_trades.csv` 是可选的大宗交易市场行为事实表。它只记录研究截止日前
已经发生的逐笔交易，不包含交易后的涨跌表现、买卖方向评分或营业部属性推断。
即使来源无数据或失败，独立抓取入口也必须保留稳定表头；字段缺失表示未知，
不得写成零或据此推断没有发生交易。

固定列：

| 字段 | 含义 |
|---|---|
| `block_trade_id` | 根据交易事实和确定性重复序号生成的稳定本地标识；不是来源官方编号 |
| `security_code` | 与 `peer_universe.csv` 匹配的标准 A 股证券代码 |
| `security_name` | 证券简称；来源缺失时写 `来源缺失` |
| `trade_date` | 交易日期，不得晚于研究截止日 |
| `close_price_cny` | 当日收盘价，人民币元；来源缺失时写 `来源缺失` |
| `deal_price_cny` | 大宗交易成交价，人民币元 |
| `deal_volume_shares` | 成交量，股；使用 API 基础单位，不按网页万股展示重复缩放 |
| `deal_amount_cny` | 成交额，人民币元；使用 API 基础单位，不按网页万元展示重复缩放 |
| `premium_discount_pct` | 相对收盘价的折溢价百分比；来源冲突或不可计算时写 `来源缺失` |
| `premium_discount_pct_basis` | `source`、`calculated` 或 `来源缺失` |
| `buyer_name` | 公开买方营业部名称；缺失时写 `来源缺失` |
| `seller_name` | 公开卖方营业部名称；缺失时写 `来源缺失` |
| `source_type` | 固定为 `public_market_data` |
| `source_name` | 固定为 `东方财富大宗交易` |
| `verification_status` | 固定为 `待验证` |
| `basis` | `as-of`、回溯天数、每证券上限和市场行为事实边界 |

### `shareholder_counts.csv`

`shareholder_counts.csv` 是可选的股东户数历史快照表。当前抓取使用东方财富
`RPT_HOLDERNUM_DET` 个股历史详情，按统计截止日回溯，并要求公告日存在且不晚于
研究截止日。巨潮季度股东户数数据只作为后续官方交叉验证候选，不能以宽泛的
“巨潮优先”替代当前历史快照语义。文件不包含区间股价涨跌或任何筹码、资金意图
和价格因果结论。

固定列：

| 字段 | 含义 |
|---|---|
| `shareholder_snapshot_id` | 由证券代码、统计截止日和公告日生成的 `sh_` 稳定本地标识 |
| `security_code` | 与股票池匹配的标准 A 股证券代码 |
| `security_name` | 证券简称；缺失时写 `来源缺失` |
| `statistical_end_date` | 统计截止日，位于回溯窗口且不晚于研究截止日 |
| `announcement_date` | 公告日，必须存在且不晚于研究截止日 |
| `holder_count` | 本次股东户数，户 |
| `previous_holder_count` | 上次股东户数，户；缺失时写 `来源缺失` |
| `holder_count_change` | 户数变化；来源冲突或不可计算时写 `来源缺失` |
| `holder_count_change_basis` | `source`、`calculated` 或 `来源缺失` |
| `holder_count_change_pct` | 户数变化率，百分比；来源冲突或不可计算时写 `来源缺失` |
| `holder_count_change_pct_basis` | `source`、`calculated` 或 `来源缺失` |
| `average_holding_shares` | 户均持股，股；映射 `AVG_HOLD_NUM`，不按网页单位重复缩放 |
| `average_holding_market_value_cny` | 户均持股市值，人民币元，API 基础单位 |
| `total_market_cap_cny` | 总市值，人民币元，API 基础单位 |
| `total_shares` | 总股本，股，API 基础单位 |
| `source_type` | 固定为 `public_market_data` |
| `source_name` | 固定为 `东方财富股东户数` |
| `verification_status` | 固定为 `待验证` |
| `basis` | `as-of`、双日期可见性、回溯天数、每证券上限和禁止推断边界 |

### `investor_interactions.csv`

`investor_interactions.csv` 是可选的交易所互动平台已回复问答表。深市 A 股来自
深交所互动易，沪市 A 股来自上证e互动；北交所当前不支持。文件只纳入问题时间
和回答时间都不晚于研究截止日、且回答时间位于回溯窗口内的完整问答。问题是
投资者输入，问题中的断言不构成事实；只有公司回复属于公司公开材料，公司回复
需与公告或定期报告交叉验证。

固定列：

| 字段 | 含义 |
|---|---|
| `interaction_id` | 由证券代码、平台和来源记录 ID 生成的 `iq_` 稳定本地标识 |
| `security_code` | 与股票池匹配的标准沪深 A 股证券代码 |
| `security_name` | 证券简称；来源缺失时写 `来源缺失` |
| `platform` | `深交所互动易` 或 `上证e互动` |
| `source_record_id` | 平台公开响应中的问题或 feed 记录 ID |
| `question` | 投资者问题原文；其中的断言不得作为已验证事实 |
| `answer` | 上市公司回复原文 |
| `question_time` | 问题公开时间，不得晚于研究截止日 |
| `answer_time` | 公司回答公开时间，位于回溯窗口且不得晚于研究截止日 |
| `question_source` | 平台公开的提问客户端来源，例如 APP、网站或 Android |
| `answerer` | 平台公开的公司回答者名称；缺失时写公司简称或 `来源缺失` |
| `source_url` | 可定位该问题或公司 feed 记录的公开页面链接 |
| `source_type` | 固定为 `company_public_material` |
| `source_name` | `深交所互动易` 或 `上证e互动` |
| `verification_status` | 固定为 `待验证` |
| `basis` | `as-of`、回溯天数、每证券上限、问题与回复各自证据边界及公告核验要求 |

### Markdown evidence files

`company_exposure.md` 和 `events_and_risks.md` 是可选证据文件。它们必须按
公司代码分组，并为每条证据保留来源类型、来源名称、数据时间、报告期或
口径和验证状态。

使用这个形状：

```text
## 300750.SZ 宁德时代

- 事实: <业务暴露、订单、产能、客户、产品、催化或风险>
  来源类型: <source_type>
  来源名称: <source_name>
  数据时间: <data_time>
  报告期或口径: <period_or_basis>
  验证状态: <verification_status>
```

## 引用元数据 schema

每个已引用字段必须在输出或来源说明里带这些标签。下游技能可以用表格、
脚注或字段来源说明呈现，但不得省略这些信息。

| 字段 | 含义 | 示例 |
|---|---|---|
| `字段名` | 被引用的数据字段或事实名称 | `动态PE` |
| `事实或数值` | 原始事实、数值或计算结果 | `35.2x` |
| `来源类型` | 本契约定义的来源类型 | `public_market_data` |
| `来源名称` | 站点、文件、API wrapper 或用户文件名 | `腾讯行情 API` |
| `数据时间` | 发布日期、公告日期、访问日期或行情时间戳 | `2026-05-17 14:30` |
| `报告期或口径` | TTM、LYR、最新季度、收盘价、盘中快照、合并报表、母公司报表或计算方法 | `盘中快照` |
| `验证状态` | `verified`、`user_provided`、`待验证` 或 `来源缺失` | `verified` |
| `缺失行为` | 缺失时如何降级 | `不得用于排序` |

## 降级规则

当来源不足、来源冲突或数据陈旧时，按以下规则降级，而不是补数或删除字段。

| 情况 | 行为 |
|---|---|
| 缺业务暴露证据 | 公司不得进入核心 idea，只能列入 `待验证名单` |
| 只有概念板块标签 | 概念标签不能单独作为核心入选依据 |
| 缺行情或估值时间戳 | 字段保留为 `来源缺失`，不得用于最新表现排序 |
| 行情时间戳过旧 | 标记 `陈旧数据`，不得写成实时或最新 |
| 缺行业规模或增速来源 | 不外推；输出 `来源缺失` 或定性描述 |
| 只有新闻或第三方研究支持 | 标记 `third_party`，只能作为线索 |
| 来源冲突 | 法定披露优先，并保留冲突说明 |
| 财务报告期不一致 | 保留字段，但标记口径不可比 |
| 计算字段缺输入 | 写 `来源缺失`，不得用行业均值替代 |

## 下游技能最低证据门槛

这些门槛定义三个下游技能可以输出什么结论。

### `a-share-competitive-analysis`

- 核心公司必须有至少一个主营业务或主题暴露来源。
- 业务暴露优先使用 `official_disclosure` 或 `company_public_material`。
- 只有概念标签、新闻热度或第三方研究线索的公司只能进入 `待验证名单`。
- 竞争维度必须说明对应证据来源，例如成本、技术、产能、客户、渠道、
  资质、政策位置或产品结构。

### `a-share-comps-analysis`

- 行情和估值字段必须带数据时间。
- 财务字段必须带报告期或口径。
- 计算字段必须写公式、输入字段、输入来源和计算时间。
- 缺字段时保留公司和字段，写 `来源缺失`。
- 负利润、负 EBITDA、ST、停牌、新股、异常高低估值必须进入异常值说明。

### `a-share-idea-generation`

- idea 入选必须同时具备主题暴露、估值或质量证据、why-now、风险和失效条件。
- 没有业务暴露证据的公司不得进入主 shortlist。
- 没有行情时间戳的公司不得因最新涨跌幅、成交额或换手率入选。
- 只有新闻、研报或概念标签的结论必须标记 `待验证`。
- 输出不得包含买入、卖出、加仓、减仓、目标价或收益承诺。

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

## Workflow

1. 列出当前任务需要的字段和事实类型。
2. 把每个字段映射到来源等级里最高质量的可用来源。
3. 业务暴露和风险事实优先使用法定披露。
4. 价格、流动性和估值快照优先使用腾讯行情 API 或 AkShare 公开行情。
5. 财务摘要优先使用同花顺 AKShare 财务摘要、东方财富数据中心或定期报告。
6. 每个数字标注来源类型、来源名称、数据时间、报告期或口径、验证状态。
7. 计算字段写明公式、输入来源和计算时间。
8. 可靠来源不足的字段写入 `来源缺失` 或 `待验证`，不要删除对应行。
9. 在得出结论前，先总结关键来源缺口。
10. 把下游技能最低证据门槛用于最终输出检查。

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
