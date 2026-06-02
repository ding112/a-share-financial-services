# Claude for Financial Services

## 快速使用

从 GitHub 检出仓库后，安装 A 股 Market Researcher：

```bash
git clone https://github.com/ding112/a-share-financial-services.git
cd a-share-financial-services
git checkout main
claude plugin marketplace add .
claude plugin install a-share-market-researcher@claude-for-financial-services
```

安装后直接调用 A 股 Market Researcher：

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。
  生成结果保存到 ./out/机器人产业链/note/。
)
```

默认研究笔记输出为 `./out/机器人产业链/note/机器人产业链行业研究.md`，
路演大纲输出为 `./out/机器人产业链/note/机器人产业链路演大纲.md`。

面向股票研究、A 股交易研究和投行建模工作流的参考 agents、skills 和数据
连接器集合。

本仓库的核心内容可以用两种方式交付：作为 Claude Cowork 插件安装，或通过
Claude Managed Agents API 部署到你自己的工作流引擎里。两种方式共用同一份
系统提示词和技能文件。

> [!IMPORTANT]
> 本仓库内容不构成投资、法律、税务或会计建议。Agents 只用于起草分析师工作
> 成果，例如模型、备忘录、研究笔记和演示材料；所有输出都需要合格专业人员
> 复核。Agents 不提供投资建议，不执行交易，不绑定风险，不入账，也不批准客户
> 准入。你需要自行验证输出，并遵守适用于你所在机构的法律法规。

仓库内容包括：

- **[Agents](#agents)**：端到端工作流 agents，例如 Pitch Agent、Market
  Researcher、A-share Screener。每个 agent 都同时提供 Cowork 插件和
  [Claude Managed Agent 模板](./managed-agent-cookbooks)。
- **[Vertical plugins](#vertical-plugins)**：按业务领域组织的 skills、slash
  commands 和数据连接器。如果只需要 `/comps`、`/dcf`、`/earnings` 等能力，
  可以单独安装这些插件。

## Agents

每个 agent 都对应一个完整工作流。Agent 插件是自包含的，会打包它需要的
skills，因此安装 agent 后即可使用。

| 功能 | Agent | 作用 |
|---|---|---|
| 覆盖与顾问 | **[Pitch Agent](./plugins/agent-plugins/pitch-agent)** | 从可比公司、交易先例和 LBO 到品牌化 pitch deck |
| 研究与建模 | **[Market Researcher](./plugins/agent-plugins/market-researcher)** | 生成行业或主题研究、竞争格局、可比公司和 idea shortlist |
| | **[A-share Market Researcher](./plugins/agent-plugins/a-share-market-researcher)** | 生成 A 股行业或主题概览、竞争格局、可比公司和中文研究笔记 |
| | **[A-share Screener](./plugins/agent-plugins/a-share-screener)** | 基于题材、事件、量化和风险检查生成 A 股短线研究清单 |
| | **[Earnings Reviewer](./plugins/agent-plugins/earnings-reviewer)** | 从财报电话会和公告到模型更新与研究笔记草稿 |
| | **[Model Builder](./plugins/agent-plugins/model-builder)** | 生成 DCF、LBO、三表模型和可比公司分析 Excel |

Managed Agent 部署模板位于
[managed-agent-cookbooks/](./managed-agent-cookbooks)，包含 `agent.yaml`、
叶子 subagents、steering examples 和安全说明。

## 仓库结构

```text
plugins/
  agent-plugins/               # 命名 agents，每个 agent 一个自包含插件
  vertical-plugins/            # 按业务领域组织的 skills、commands 和 MCP 配置
  partner-built/               # 合作伙伴插件，例如 LSEG 和 S&P Global
managed-agent-cookbooks/       # Claude Managed Agent 模板，每个 agent 一个目录
claude-for-msft-365-install/   # Microsoft 365 add-in 管理员安装工具
scripts/                       # 部署、校验、编排和同步脚本
```

## 快速开始

### Claude Code

本地使用 `a-share-market-researcher` 的安装和调用方式见
[docs/quick-start.md](./docs/quick-start.md)。

`a-share-market-researcher` 的自动 `research-pack` 准备流程需要本地 Python
虚拟环境和 AkShare。先在仓库根目录创建 `.venv` 并安装依赖：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

当 `a-share-market-researcher` 在 Claude Code 中缺少 `research-pack/` 时，
它只会通过 `.venv/bin/python scripts/auto_prepare_a_share_research_pack.py`
运行受控本地脚本；不会自动安装依赖，也不会运行未列出的抓取脚本。

```bash
# 添加本地 marketplace
claude plugin marketplace add .

# 安装 A 股 Market Researcher
claude plugin install a-share-market-researcher@claude-for-financial-services
```

安装后，`a-share-market-researcher` 可以在会话中直接调用；相关 skills 会在
A 股研究任务中自动触发。

### Claude Managed Agents

```bash
export ANTHROPIC_API_KEY=sk-ant-...
scripts/deploy-managed-agent.sh a-share-screener
```

`managed-agent-cookbooks/` 下的每个模板都引用对应插件里的同一份系统提示词和
skills。部署脚本会解析文件引用、上传 skills、创建叶子 subagents，并把
orchestrator 提交到 `/v1/agents`。参考编排循环见
[scripts/orchestrate.py](./scripts/orchestrate.py)。

> **预览能力：** subagent delegation（`callable_agents`）仍是预览能力。安全
> 和交接说明见各 agent 的 README。

## 工作方式

| 项目 | 含义 | 位置 |
|---|---|---|
| Agents | 自包含工作流插件，包含系统提示词和所需 skills | `plugins/agent-plugins/<slug>/` |
| Skills | 可自动触发的领域方法、约定和步骤 | `plugins/vertical-plugins/<vertical>/skills/` 和 `plugins/agent-plugins/<slug>/skills/` |
| Commands | 显式调用的 slash actions，例如 `/comps`、`/earnings`、`/screen` | `plugins/vertical-plugins/<vertical>/commands/` |
| Connectors | 连接外部数据源或内部系统的 MCP 配置 | `plugins/vertical-plugins/financial-analysis/.mcp.json` |
| Managed-agent wrappers | Headless 部署用的 `agent.yaml`、subagents 和 steering examples | `managed-agent-cookbooks/<slug>/` |

仓库内容都是文件化的 Markdown、JSON 和 YAML，不需要构建步骤。

## Vertical plugins

建议从 **financial-analysis** 开始；它包含共享建模 skills 和数据连接器。然后
按工作流增加其他 vertical plugins。

| 插件 | 作用 |
|---|---|
| **[financial-analysis](./plugins/vertical-plugins/financial-analysis)** | Comps、DCF、LBO、三表模型、deck QC 和 Excel audit |
| **[investment-banking](./plugins/vertical-plugins/investment-banking)** | CIM、teaser、process letter、buyer list、merger model 和 deal tracker |
| **[equity-research](./plugins/vertical-plugins/equity-research)** | 财报点评、首次覆盖、模型更新、投资 thesis 和催化日历 |
| **[china-equity-trading](./plugins/vertical-plugins/china-equity-trading)** | A 股题材筛选、事件日历、盘前盘后摘要和风险检查 |
| **[lseg](./plugins/partner-built/lseg)** | LSEG 数据上的债券 RV、swap curves、FX carry、options vol 和 macro-rates |
| **[sp-global](./plugins/partner-built/spglobal)** | 基于 S&P Capital IQ 的 tear sheets、earnings previews 和 funding digests |

## MCP 集成

连接器集中在 **financial-analysis** 核心插件中，并可被其他插件复用。

| Provider | URL |
|---|---|
| [Daloopa](https://www.daloopa.com/) | `https://mcp.daloopa.com/server/mcp` |
| [Morningstar](https://www.morningstar.com/) | `https://mcp.morningstar.com/mcp` |
| [S&P Global](https://www.spglobal.com/) | `https://kfinance.kensho.com/integrations/mcp` |
| [FactSet](https://www.factset.com/) | `https://mcp.factset.com/mcp` |
| [Moody's](https://www.moodys.com/) | `https://api.moodys.com/genai-ready-data/m1/mcp` |
| [MT Newswires](https://www.mtnewswires.com/) | `https://vast-mcp.blueskyapi.com/mtnewswires` |
| [Aiera](https://www.aiera.com/) | `https://mcp-pub.aiera.com` |
| [LSEG](https://www.lseg.com/) | `https://api.analytics.lseg.com/lfa/mcp` |
| [PitchBook](https://pitchbook.com/) | `https://premium.mcp.pitchbook.com/mcp` |
| [Chronograph](https://www.chronograph.pe/) | `https://ai.chronograph.pe/mcp` |
| [Egnyte](https://www.egnyte.com/) | `https://mcp-server.egnyte.com/mcp` |

> MCP 访问可能需要对应数据供应商的订阅或 API key。

## Claude for Microsoft 365 安装工具

如果你的机构通过 Microsoft 365 add-in 在 Excel、PowerPoint、Word 和 Outlook
里使用 Claude，[claude-for-msft-365-install/](./claude-for-msft-365-install)
提供管理员安装工具。它用于对接你自己的云环境，例如 Vertex AI、Bedrock 或
内部 LLM gateway，而不是直接使用 Anthropic API。

安装方式：

```bash
claude plugin install claude-for-msft-365-install@claude-for-financial-services
/claude-for-msft-365-install:setup
```

这个安装工具和本仓库的 agents、vertical plugins 是分开的。它负责把 add-in
部署到租户中；部署后，实际运行的是本仓库里的 agents 和 skills。

## 定制方式

- **替换连接器**：把 `.mcp.json` 指向你的数据供应商或内部系统。
- **增加机构语境**：把术语、流程和格式标准写入 skill 文件。
- **带入模板**：用 `/ppt-template` 让 Claude 学习你的 PowerPoint 模板。
- **调整 agent 范围**：编辑 `agents/<slug>.md`，让 agent 匹配团队流程。
- **新增工作流**：复制现有结构，为新工作流创建 agent 和 cookbook。

## Skill 与 command 参考

<details>
<summary><b>financial-analysis</b>：核心建模、Excel 和 deck QC</summary>

| Skill | Command | 描述 |
|---|---|---|
| comps-analysis | `/comps` | 使用交易倍数做可比公司分析 |
| dcf-model | `/dcf` | 带 WACC 和敏感性分析的 DCF 估值 |
| lbo-model | `/lbo` | LBO 模型 |
| 3-statement-model | `/3-statement-model` | 填充三表模型模板 |
| audit-xls | `/debug-model` | Excel 模型审计、公式追踪、硬编码检查和平衡校验 |
| clean-data-xls | — | 清洗和标准化 Excel 表格数据 |
| deck-refresh | — | 刷新 deck 中的图表和表格链接 |
| competitive-analysis | `/competitive-analysis` | 竞争格局和市场定位分析 |
| ib-check-deck | — | 检查演示材料的一致性和错误 |
| pptx-author | — | 在 Managed Agent 模式下生成 `.pptx` |
| xlsx-author | — | 在 Managed Agent 模式下生成 `.xlsx` |
| ppt-template-creator | `/ppt-template` | 创建可复用的 PPT 模板 skill |
| skill-creator | — | 创建新 skill 的指南 |

</details>

<details>
<summary><b>investment-banking</b>：交易材料和执行</summary>

| Skill | Command | 描述 |
|---|---|---|
| strip-profile | `/one-pager` | 生成 pitch book 使用的一页公司简介 |
| pitch-deck | — | 用源数据填充 pitch deck 模板 |
| datapack-builder | — | 从 CIM 和公告构建数据包 |
| cim-builder | `/cim` | 起草 Confidential Information Memorandum |
| teaser | `/teaser` | 生成匿名一页 teaser |
| buyer-list | `/buyer-list` | 生成战略和财务买方名单 |
| merger-model | `/merger-model` | 并购 accretion/dilution 分析 |
| process-letter | `/process-letter` | 起草竞标说明和流程信 |
| deal-tracker | `/deal-tracker` | 跟踪交易里程碑和行动项 |

</details>

<details>
<summary><b>equity-research</b>：覆盖和发布</summary>

| Skill | Command | 描述 |
|---|---|---|
| earnings-analysis | `/earnings` | 财报后季度更新报告 |
| earnings-preview | `/earnings-preview` | 财报前情景分析和关键指标 |
| initiating-coverage | `/initiate` | 机构级首次覆盖报告 |
| model-update | `/model-update` | 用新数据更新财务模型 |
| morning-note | `/morning-note` | 晨会笔记和交易想法 |
| sector-overview | `/sector` | 行业格局和主题报告 |
| thesis-tracker | `/thesis` | 维护和更新投资 thesis |
| catalyst-calendar | `/catalysts` | 跟踪覆盖池催化事件 |
| idea-generation | `/screen` | 股票筛选和 idea sourcing |

</details>

## 贡献

本仓库主要由 Markdown、YAML 和 JSON 文件组成。新增内容时遵循以下流程：

- 新 skill：添加到 `plugins/vertical-plugins/<vertical>/skills/`，然后运行
  `python3 scripts/sync-agent-skills.py` 同步到使用它的 agent bundle。
- 新 agent：添加 `plugins/agent-plugins/<slug>/`，包含
  `agents/<slug>.md` 和 `skills/`，并创建对应的
  `managed-agent-cookbooks/<slug>/`。
- 提交前运行 `python3 scripts/check.py`。它会检查 manifests、跨文件引用和
  agent bundle skill 是否与 vertical source 保持一致。

## License

[Apache License 2.0](./LICENSE)
