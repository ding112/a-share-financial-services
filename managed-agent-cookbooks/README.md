# Managed-agent 模板

每个保留的 agent 都同时提供两种交付方式：作为 Cowork 插件安装，或作为
Claude Managed Agent 模板部署到你自己的工作流引擎里。这个目录中的模板会
引用对应 agent plugin 中的系统提示词和 skills，因此同一份源文件可以同时服务
两种运行方式。

运行 `../scripts/deploy-managed-agent.sh <slug>` 可以上传 skills、创建叶子
workers，并把解析后的配置提交到 `POST /v1/agents`。每个模板都包含
`steering-examples.json` 和对应 README，用于说明 steering event、安全层级和
交接方式。

| Agent | Vertical plugin | Cowork tile | CMA steering event | Leaf workers |
|---|---|---|---|---|
| [`pitch-agent`](./pitch-agent/) | investment-banking | 从可比公司、交易先例和 LBO 到品牌化 pitch deck | `Build pitch book: <target> / <acquirer>, thesis: <text>` | researcher · modeler · **deck-writer** |
| [`market-researcher`](./market-researcher/) | equity-research | 行业或主题研究、竞争格局、可比公司和 idea shortlist | `Primer: <sector or theme>, angle: <text>` | sector-reader · comps-spreader · **note-writer** |
| [`a-share-market-researcher`](./a-share-market-researcher/) | china-equity-trading | A 股行业或主题概览、竞争格局、可比公司和中文研究笔记 | `Primer: A股<行业或主题>, angle: <text>` | sector-reader · comps-spreader · **note-writer** |
| [`a-share-screener`](./a-share-screener/) | china-equity-trading | A 股题材、事件、量化和风险筛选并产出研究清单 | `Screen A股<主题>, style: <短线\|波段>` | market-context-reader · pool-builder · **research-list-writer** |
| [`earnings-reviewer`](./earnings-reviewer/) | equity-research | 从财报电话会和公告到模型更新与研究笔记草稿 | `Process earnings: <ticker> <period>` | transcript-reader · model-updater · **note-writer** |
| [`model-builder`](./model-builder/) | financial-analysis | 生成 DCF、LBO、三表模型和可比公司分析文件 | `Build <dcf\|lbo\|3-stmt> for <ticker>, assumptions: {...}` | data-puller · **builder** · auditor |

**加粗** 的 leaf worker 是唯一拥有 `Write` 权限的 worker。

## Manifest 与 API

`agent.yaml` 使用真实的 `POST /v1/agents` 字段名，并支持部署脚本解析的几个
便捷写法。

| Manifest 写法 | 部署时解析为 |
|---|---|
| `system: {file: ../../plugins/agent-plugins/<slug>/agents/<slug>.md, append: "..."}` | `system: "<inlined contents + append>"` |
| `system: {text: "..."}` | `system: "<text>"` |
| `skills: [{from_plugin: ../../plugins/agent-plugins/<slug>}]` | 上传该插件 `skills/*` 下所有 skills，并引用生成的 skill IDs |
| `skills: [{path: ../../...}]` | 上传指定 skill 路径，并引用生成的 skill ID |
| `callable_agents: [{manifest: ./subagents/x.yaml}]` | 先创建 subagent，再在 orchestrator 中引用它的 agent ID |

> **预览能力：** `callable_agents` 目前只支持一层 delegation。Orchestrator 可以
> 调用 workers，但 workers 不能继续调用其他 subagents。

## 跨 agent 交接

命名 agents 不会彼此直接调用。当一个 agent 需要另一个 agent 继续处理时，它会
在输出中生成 `handoff_request`。参考实现
[`../scripts/orchestrate.py`](../scripts/orchestrate.py) 会把 handoff 转成新的
steering event，并路由到允许的目标 agent。

参考脚本使用目标 agent allowlist 和 payload schema 校验来降低风险。生产环境中，
建议通过专用 tool call 或 typed SSE event 传递 handoff，而不是依赖模型输出文本。
