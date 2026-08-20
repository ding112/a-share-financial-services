# Claude for Financial Services

这是一个面向金融服务工作流的 Claude Code 插件、Codex agent 能力包和
Managed Agent 模板仓库。它把金融分析、A 股研究、投行材料、模型构建和
合作伙伴数据能力整理成可安装的插件，并为部分工作流提供无界面部署模板。

第一次接触这个项目时，只需要先理解两件事：

- `plugins/agent-plugins/` 放端到端工作流 agent，例如 A 股行业研究。
- `plugins/vertical-plugins/` 放可复用的领域 skills、commands 和 MCP 配置。

> [!IMPORTANT]
> 本仓库内容不构成投资、法律、税务或会计建议。Agents 只用于起草分析师工作
> 成果，所有输出都需要合格专业人员复核。Agents 不提供投资建议，不执行交易，
> 不绑定风险，不入账，也不批准客户准入。

## 术语

本仓库同时服务多个运行时。以下术语用于区分安装入口、能力来源和部署模板。

| 术语 | 含义 |
|---|---|
| Claude Code plugin | Claude Code / Cowork 读取的插件包，由 `.claude-plugin/plugin.json` 和 `.claude-plugin/marketplace.json` 注册。 |
| Codex plugin | Codex 读取的本地插件包，由 `.codex-plugin/plugin.json` 和 `.agents/plugins/marketplace.json` 注册。第一版暴露 agent plugin 中的 skills，并额外暴露 `equity-research` skill package。 |
| Agent plugin | `plugins/agent-plugins/<slug>/` 下的端到端工作流入口，包含 agent system prompt 和同步后的 skills。 |
| Vertical plugin | `plugins/vertical-plugins/<vertical>/` 下的领域能力源，包含原始 skills、Claude Code commands 和可选 MCP 配置。 |
| Managed Agent template | `managed-agent-cookbooks/<slug>/` 下的无界面部署模板，复用 agent plugin 的 system prompt 和 skills。 |

## 先跑一个 case

最快的上手方式是安装 `a-share-market-researcher`，用仓库里的 fixture 数据包
生成一份 A 股主题研究笔记。这个 case 不需要先抓实时行情。

```bash
git clone https://github.com/ding112/a-share-financial-services.git
cd a-share-financial-services
claude plugin marketplace add ./
claude plugin install a-share-market-researcher@claude-for-financial-services
```

安装后，在 Claude Code 会话里调用 agent：

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。
  使用 ./fixtures/a-share-research-packs/robotics-reducer/ 作为输入数据包。
  先列出数据包覆盖、缺失字段、异常值和待验证证据，再生成中文研究 note。
  生成结果保存到 ./out/机器人产业链/note/。
)
```

成功后，你会看到研究笔记写入：

```text
./out/机器人产业链/note/机器人产业链行业研究.md
./out/机器人产业链/note/机器人产业链路演大纲.md
```

### 抓取公开数据跑研究

如果你希望用公开数据源准备 `research-pack/`，不需要手动运行数据准备脚本。
先创建本地 Python 环境并安装依赖：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

然后在 Claude Code 会话里直接调用 agent。Agent 内置的
`a-share-data-sources` skill 会在缺少 `research-pack/` 时自动准备数据包：

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。
  如果本地还没有 research-pack，请自动准备公开数据 research-pack；
  先列出 source_manifest.json 中的来源、数据时间、报告期或口径和缺失行为，
  再生成中文研究 note。
  生成结果保存到 ./out/机器人产业链/note/。
)
```

这个流程会联网访问公开数据源。成功后，你会看到以下文件：

```text
./out/机器人产业链/research-pack/source_manifest.json
./out/机器人产业链/research-pack/peer_universe.csv
./out/机器人产业链/note/机器人产业链行业研究.md
./out/机器人产业链/note/机器人产业链路演大纲.md
```

如果公开数据源暂时不可用，先检查
`./out/机器人产业链/research-pack/fetch_errors.csv`。

更完整的本地测试、fixture 冒烟测试和公开数据准备流程见
[`docs/quick-start.md`](./docs/quick-start.md)。

## 仓库里有什么

仓库的核心目录如下：

```text
plugins/
  agent-plugins/             # 命名 agents，每个 agent 一个自包含插件
  vertical-plugins/          # 按业务领域组织的 skills、commands 和 MCP 配置
  partner-built/             # 合作伙伴插件，例如 LSEG 和 S&P Global
managed-agent-cookbooks/     # Claude Managed Agent 模板
claude-for-msft-365-install/ # Microsoft 365 add-in 管理员安装工具
fixtures/                    # 本地 smoke test 用的固定输入数据
scripts/                     # 校验、同步、部署和 A 股数据准备脚本
docs/                        # 更细的本地使用说明
```

主要入口：

| 你想做什么 | 从哪里开始 |
|---|---|
| 跑 A 股行业研究 case | `a-share-market-researcher` 和 `docs/quick-start.md` |
| 看有哪些端到端 agents | `plugins/agent-plugins/` |
| 看可复用 skills 和 commands | `plugins/vertical-plugins/` |
| 部署 Managed Agent | `managed-agent-cookbooks/` |
| 安装 Microsoft 365 add-in 管理工具 | `claude-for-msft-365-install/README.md` |

## 常用 agents

这些 agent 是完整工作流入口，安装后可以直接在 Claude Code 中调用：

| Agent | 作用 |
|---|---|
| `a-share-market-researcher` | 生成 A 股行业或主题研究笔记 |
| `a-share-screener` | 生成 A 股短线研究清单 |
| `market-researcher` | 生成行业或主题研究、竞争格局和 idea shortlist |
| `earnings-reviewer` | 从财报电话会和公告生成模型更新与研究笔记草稿 |
| `model-builder` | 生成 DCF、LBO、三表模型和可比公司分析 Excel |
| `pitch-agent` | 从可比公司、交易先例和 LBO 到 pitch deck |

完整插件清单由 [`.claude-plugin/marketplace.json`](./.claude-plugin/marketplace.json)
注册。Codex 第一版注册 `plugins/agent-plugins/` 下的 agent 能力包，并额外注册
`equity-research` skill package；清单见
[`.agents/plugins/marketplace.json`](./.agents/plugins/marketplace.json)。

## 开发和校验

仓库内容主要是 Markdown、JSON 和 YAML，不需要构建步骤。改动前先确认应该改
源文件，而不是改同步后的副本。

- 修改 skill：优先编辑 `plugins/vertical-plugins/<vertical>/skills/`。
- 同步 agent bundle：运行 `python3 scripts/sync-agent-skills.py`。
- 修改 Codex manifest：优先改 `plugins/agent-plugins/<slug>/.codex-plugin/plugin.json`。
  `equity-research` 是第一版唯一允许进入 Codex marketplace 的 vertical skill
  package，用于暴露 `initiating-coverage` 等 skills；不要把其它 vertical plugin
  加入 Codex marketplace。
- 提交前校验：运行 `python3 scripts/check.py`。

`scripts/check.py` 会检查 manifests、跨文件引用、Managed Agent 模板、Codex
marketplace，以及 agent bundle skill 是否与 vertical source 保持一致。

### 用 DeepSeek Harness（DSH）跑 FSI agent

仓库把 6 个 FSI agent 各定义成 DSH preset，可在不受 Claude Code 宿主约束的情况下
用 DeepSeek 模型跑研究/建模/投行材料：

```bash
cd <本仓库根>
bash dsh/install-presets.sh       # 安装全部 6 个 preset 到 ~/.dsh/.agent-presets/
dsh --profile web                  # 在仓库根启动，preset 选择器选对应 agent
```

详见 [`dsh/README.md`](./dsh/README.md)。persona 由安装脚本从
`plugins/agent-plugins/<slug>/agents/<slug>.md` 生成（单一事实源），技能指向各
agent 的 bundled skills，`scripts/check.py` 会守卫 preset 与 persona 源不漂移。

## 许可证

本项目使用 [Apache License 2.0](./LICENSE)。
