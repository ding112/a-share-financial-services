# Quick Start（本地使用）

本页保留两条本地安装路径。Claude Code 路径提供完整的命名 agent 调用体验；
Codex 路径第一版只安装 agent plugin 中的 skills，不复制 Claude Code 的 slash
command 或命名 agent 调用语法。

## Claude Code 路径

Claude Code 使用 `.claude-plugin/marketplace.json`。安装后，可以用
`<agent>:<agent>(...)` 语法调用命名 agent。

### 1) 安装本地 marketplace

```bash
claude plugin marketplace add /Users/ding/workspace/mengzai/financial-services
```

### 2) 安装插件

```bash
claude plugin install a-share-screener@claude-for-financial-services
claude plugin install a-share-market-researcher@claude-for-financial-services
```

### 3) 使用命令

短线筛选（`a-share-screener`）：

```text
a-share-screener:a-share-screener(
  基于“机器人+减速器”生成A股短线研究清单，并保存到 ./out/机器人减速器短线研究清单.md
)
```

行业/主题研究（`a-share-market-researcher`）：

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。生成结果保存到 ./out/机器人产业链行业研究.md
)
```

### 4) 成功标志

看到类似 `Backgrounded agent` 或 agent 开始返回结果，即表示调用成功。

## Codex 路径

Codex 使用 `.agents/plugins/marketplace.json`。第一版登记
`plugins/agent-plugins/` 下的 agent 能力包，并额外登记 `equity-research`
skill package。Codex 暴露的是 skills，不是 Claude Code slash commands。

### 1) 安装本地 marketplace

```bash
codex plugin marketplace add /Users/ding/workspace/mengzai/financial-services
```

### 2) 安装 agent 能力包

当前 Codex CLI 只负责添加、升级或移除 marketplace。添加本地 marketplace 后，
在 Codex app 的插件界面安装 `financial-services` marketplace 中的
`a-share-screener`、`a-share-market-researcher` 或 `equity-research`。

### 3) 成功标志

安装完成后，开启新的 Codex 线程，让 Codex 重新加载插件和 skills。Codex 第一版
不提供 Claude Code 的 `a-share-market-researcher:a-share-market-researcher(...)`
或 `/equity-research:initiate` 调用语法；你可以直接描述研究任务，由已安装的
skills 参与响应。若要在 Claude Code 中使用 `/equity-research:initiate`，安装
Claude Code 的 `equity-research@claude-for-financial-services` 插件。

## 来源契约 smoke test

在本地调用 `a-share-market-researcher` 时，使用一个有明确来源要求的 prompt
检查来源契约是否生效：

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。
  要求：先列出本次研究用到的来源类型、来源名称、数据时间、报告期或口径、
  验证状态和缺失行为；如果只有概念标签或新闻线索，放入待验证名单，不要进入
  核心 idea shortlist。生成结果保存到 ./out/机器人产业链来源契约测试.md
)
```

成功标志：

- 输出包含 `来源类型`、`来源名称`、`数据时间`、`报告期或口径`、
  `验证状态` 和 `缺失行为`。
- 核心 idea 不使用单独的概念标签作为入选依据。
- 缺失行情、估值或业务暴露证据时，输出写 `来源缺失` 或 `待验证`。

## 数据包契约 smoke test

如果你已经准备了本地研究数据包，可以让 `a-share-market-researcher` 先解析
数据包，再开始写行业研究。推荐目录名是 `research-pack/`，必需文件是
`source_manifest.json` 和 `peer_universe.csv`。

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。
  使用 ./research-pack/机器人产业链/ 作为输入数据包。
  先解析 source_manifest.json 和 peer_universe.csv；如果存在
  market_snapshot.csv、financial_summary.csv、financial_statements.csv、company_exposure.md 或
  events_and_risks.md、investor_interactions.csv，也一并读取。请先列出数据包字段来源、数据时间、
  报告期或口径、验证状态和缺失行为，再生成结果到
  ./out/机器人产业链行业研究.md
)
```

成功标志：

- 输出先说明 `source_manifest.json` 和 `peer_universe.csv` 是否存在。
- 缺少可选文件时，对应字段写 `来源缺失`、`待验证` 或 `口径不可比`。
- 没有 `snapshot_time` 的行情或估值字段不用于排序。
- `financial_summary.csv` 只用于最新一期摘要；`financial_statements.csv` 才用于多报告期三表明细，不能相互倒推。
- `statement_scope=来源缺失` 时只做同公司同来源趋势观察；跨公司比较和统一口径派生计算写 `口径不可比` 或 `来源缺失`。

## 抓取财务报表明细

已有 `peer_universe.csv` 时，可以单独生成资产负债表、利润表和现金流量表的
多报告期标准长表。默认报告期窗口为 12 个，普通股票池使用 AkShare；离线验收
使用 fixture。该阶段是可选补充数据，不改变 `financial_summary.csv`；一键准备可用
`--financial-statement-source`、`--financial-statement-period-limit` 和
`--financial-statement-fixture-scenario` 复现来源、窗口和离线场景。

```bash
python3 scripts/fetch_a_share_financial_statements.py \
  --peer-universe fixtures/a-share-research-packs/robotics-reducer/peer_universe.csv \
  --output-dir out/机器人产业链/research-pack \
  --as-of 2026-08-16 \
  --period-limit 12 \
  --source fixture
```

命令写出或更新 `financial_statements.csv`、`source_manifest.json` 和
`fetch_errors.csv`。资产负债表是报告期末时点值，利润表和现金流量表是年初至
报告期末累计值；公告日或更新时间不可见、历史版本无法恢复、结构异常和北交所
不支持均按固定错误阶段记录。在线来源失败时一键准备只告警并继续；可用
`--skip-financial-statements` 跳过，配合 `--force` 会清理陈旧财务报表产物。

`financial_statements.csv` 中的 `verified` 只表示来源行已定位、解析和映射，不
代表法定完整财报或已确认合并口径。来源未声明范围时 `statement_scope` 为
`来源缺失`，不得用于跨公司统一口径比较。

## Comps artifact smoke test

准备好 `research-pack/` 后，可以只刷新 comps artifact：

```text
a-share-market-researcher:a-share-market-researcher(
  Refresh comps only: A股机器人产业链。
  使用 ./research-pack/机器人产业链/，输出 comps_main.csv、
  comps_source_notes.csv、comps_exceptions.csv、comps_statistics.csv、
  comps_data_gaps.csv 和 comps_summary.md 的 Markdown 预览。不要补数；
  缺少行情时间戳、报告期或来源时，写 来源缺失、待验证 或 口径不可比。
)
```

成功标志：

- 输出包含 `comps_main.csv`、`comps_source_notes.csv`、
  `comps_exceptions.csv`、`comps_statistics.csv`、`comps_data_gaps.csv`
  和 `comps_summary.md`。
- 每个数字字段能追溯到来源、时间和口径。
- 样本数小于 3 的指标不输出统计分布。

## Fixture 端到端 smoke test

仓库包含固定的 A 股研究数据包 fixtures。它们用于无网络验证输入契约和
comps artifact 交接，不代表实时行情或投资建议。

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。
  使用 ./fixtures/a-share-research-packs/robotics-reducer/。
  先列出数据包覆盖、缺失字段、异常值和待验证证据，再生成中文研究 note。
)
```

```text
a-share-market-researcher:a-share-market-researcher(
  Refresh comps only: A股CPO光模块。
  使用 ./fixtures/a-share-research-packs/cpo-optical-module/。
  对缺少 snapshot_time 的行情字段写 来源缺失，不得按最新表现排序。
)
```

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股低空经济, angle: 政策催化与订单兑现。
  使用 ./fixtures/a-share-research-packs/low-altitude-economy/。
  因为缺少 market_snapshot.csv 和 financial_summary.csv，估值、流动性和
  质量字段必须降级为 来源缺失 或 口径不可比。
)
```

## 抓取公开行情和财务摘要

如果你已经有 `peer_universe.csv`，可以先抓取公开行情和财务摘要。这个命令会
联网访问公开数据源，并把结果写成 research-pack 可消费的本地文件。该命令负责
行情快照和财务摘要；三大报表明细由下方独立入口生成，不从摘要倒推。

```bash
python3 scripts/fetch_a_share_public_data.py \
  --peer-universe fixtures/a-share-research-packs/robotics-reducer/peer_universe.csv \
  --output-dir out/机器人产业链/research-pack \
  --as-of "2026-05-21 15:00:00"
```

命令会写出以下文件：

- `market_snapshot.csv`
- `financial_summary.csv`
- `source_manifest.json`
- `fetch_errors.csv`

离线验证可以使用 fixture source：

```bash
python3 scripts/fetch_a_share_public_data.py \
  --peer-universe fixtures/a-share-research-packs/robotics-reducer/peer_universe.csv \
  --output-dir out/机器人产业链/research-pack \
  --as-of "2026-05-21 15:00:00" \
  --market-source fixture \
  --financial-source fixture
```

## 抓取交易所互动平台问答

已有 `peer_universe.csv` 时，可以把深市“互动易”和沪市“上证e互动”的已回复
问答加入同一个 research-pack。默认按回答时间截至 `as-of` 回溯 365 天，每证券
最多保留 50 条；北交所当前会在 `fetch_errors.csv` 中标记为不支持。

```bash
python3 scripts/fetch_a_share_investor_interactions.py \
  --peer-universe fixtures/a-share-research-packs/robotics-reducer/peer_universe.csv \
  --output-dir out/机器人产业链/research-pack \
  --as-of 2026-08-13
```

命令写出或更新：

- `investor_interactions.csv`
- `source_manifest.json`
- `fetch_errors.csv`

离线检查使用固定 fixture，不访问交易所：

```bash
python3 scripts/fetch_a_share_investor_interactions.py \
  --peer-universe fixtures/a-share-research-packs/robotics-reducer/peer_universe.csv \
  --output-dir out/机器人产业链/research-pack \
  --as-of 2026-08-13 \
  --source fixture
```

问答统一标记为 `company_public_material`、`待验证`。问题中的断言不构成事实；
公司回复也不能替代法定信息披露，必须回到公告或定期报告交叉验证。一键准备默认不执行
该阶段；需要时使用 `--include-investor-interactions` 显式启用。

## 本地公开数据预处理

如果你已经在本地导出腾讯行情、AkShare 财务摘要或其他 CSV，可以先把这些
文件整理成标准 `research-pack/`。这个脚本只读取本地文件，不访问网络。

```bash
python3 scripts/prepare_a_share_research_pack.py \
  --input-dir fixtures/a-share-raw-exports/robotics-reducer \
  --output-dir out/机器人产业链/research-pack \
  --theme 机器人产业链 \
  --as-of 2026-05-17
```

生成后，用 `a-share-market-researcher` 读取输出目录：

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。
  使用 ./out/机器人产业链/research-pack/ 作为 research-pack 输入。
  先列出 source_manifest.json 中的来源、数据时间、报告期或口径和缺失行为。
)
```

## 生成 A 股 comps artifact

准备好本地 `research-pack/` 后，可以用阶段 5 生成器直接产出 comps artifact
文件集。这个脚本只读取本地文件，不访问网络，也不会为缺失字段补数。

```bash
python3 scripts/generate_a_share_comps_artifacts.py \
  --research-pack fixtures/a-share-research-packs/robotics-reducer \
  --theme 机器人产业链
```

```bash
python3 scripts/generate_a_share_comps_workbook.py \
  --comps-dir out/机器人产业链/comps \
  --theme 机器人产业链
```

成功输出：

```text
wrote comps workbook: out/机器人产业链/workbook/机器人产业链可比公司.xlsx
```

命令会写出以下文件：

- `comps_main.csv`
- `comps_source_notes.csv`
- `comps_exceptions.csv`
- `comps_statistics.csv`
- `comps_data_gaps.csv`
- `comps_summary.md`

成功标志：

- `comps_main.csv` 保留公司、主题角色、市值、估值和财务字段。
- 缺失值保留为 `来源缺失`，不使用估算值填充。
- 亏损公司会从 PE 统计中排除，而不是强行进入估值分位数。
- `comps_summary.md` 包含可用数据、不可排序字段、异常项、统计分布和
  idea generation 交接说明。

## 生成 A 股 research handoff

阶段 6 handoff 把 `research-pack/`、阶段 5 comps artifact、暴露证据和
事件风险汇成 competitive-analysis 与 idea-generation 可以直接消费的结构化
输入。

```bash
python3 scripts/generate_a_share_research_handoff.py \
  --research-pack fixtures/a-share-research-packs/robotics-reducer \
  --comps-dir out/机器人产业链/comps \
  --theme 机器人产业链
```

命令会写出以下文件：

- `competitive_handoff.csv`
- `idea_inputs.csv`
- `idea_risk_register.csv`
- `research_handoff_summary.md`

`competitive_handoff.csv` 用于竞争格局横向比较和 comps handoff。
`idea_inputs.csv` 与 `idea_risk_register.csv` 用于 idea generation 的
入选、降级和风险排除。`data_quality_flag` 非 `可用` 的公司不得直接用于
估值或质量排序。

## 生成阶段 7 研究 note assembly

阶段 5 comps artifact 和阶段 6 research handoff 都生成后，可以运行阶段 7
组装器生成中文研究 note、slide outline 和 manifest。

```bash
python3 scripts/generate_a_share_research_note.py \
  --research-pack fixtures/a-share-research-packs/robotics-reducer \
  --comps-dir out/机器人产业链/comps \
  --handoff-dir out/机器人产业链/handoff \
  --theme 机器人产业链 \
  --angle 关注减速器国产替代和机器人量产弹性 \
  --as-of 2026-05-18
```

成功输出：

```text
wrote research note assembly: out/机器人产业链/note
```

命令会写出以下文件：

```text
out/机器人产业链/note/机器人产业链行业研究.md
out/机器人产业链/note/机器人产业链路演大纲.md
out/机器人产业链/note/research_assembly_manifest.json
```

## 生成 A 股 dashboard

当同一主题目录下已经有 `research-pack/`、`comps/`、`handoff/` 和 `note/`
产物时，可以生成一个离线可打开的静态 HTML 看板。Dashboard 只读取本地文件，
不会联网，也不会修改原始研究产物。

```bash
python3 scripts/generate_a_share_dashboard.py \
  --theme 机器人产业链 \
  --research-pack out/机器人产业链/research-pack \
  --comps-dir out/机器人产业链/comps \
  --handoff-dir out/机器人产业链/handoff \
  --note-dir out/机器人产业链/note
```

成功输出：

```text
wrote A-share dashboard: out/机器人产业链/dashboard/index.html
```

看板包含以下区块：

- 总览：主题、股票数量、数据质量和生成时间。
- 股票池：代码、简称、主题角色、研究优先级、风险摘要和失效条件。
- Comps：市值、PE、PB、PS、短期表现、收入、净利和 ROE。
- 图表区：`PE TTM vs ROE` 和 `市值 vs 20 日表现` 两个基础散点图。
- 风险与来源：风险登记、数据缺口、异常项、source manifest 和 note 链接。

Dashboard 是研究复核工具，不输出买入、卖出、目标价或收益承诺。
