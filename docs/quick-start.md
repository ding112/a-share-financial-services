# Quick start：本地使用 `a-share-screener`

本文说明如何在本地 Claude Code 中安装和调用 `a-share-screener`。本地调用
使用 Claude Code 插件机制，不需要运行 `scripts/deploy-managed-agent.sh`。

## A-share Market Researcher

Use `a-share-market-researcher` when you want an A-share version of the
`market-researcher` workflow: industry overview, competitive landscape, peer
comps, ideas shortlist, and a Chinese research note.

Install it from the local marketplace:

```bash
claude plugin marketplace add /Users/ding/workspace/mengzai/financial-services
claude plugin install a-share-market-researcher@claude-for-financial-services
```

Call the named agent directly:

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口
)
```

Use `a-share-screener` instead when the request is a short-term research list,
topic screen, event calendar, quant screen, or risk filter.

## 使用场景

`a-share-screener` 是一个 named agent，用于把 A 股题材、事件、量化初筛和
风险检查串成一条短线研究工作流。它默认输出中文研究清单，并要求标记来源、
风险提示、观察条件和失效条件。

它不是一个 skill，因此不要这样调用：

```text
Skill(a-share-screener)
```

上面的调用会报错：

```text
Error: Unknown skill: a-share-screener
```

## 安装本地 marketplace

在仓库根目录执行以下命令，把当前仓库注册为 Claude Code 本地 marketplace：

```bash
claude plugin marketplace add /Users/ding/workspace/mengzai/financial-services
```

安装 `a-share-screener` named agent：

```bash
claude plugin install a-share-screener@claude-for-financial-services
```

如果只需要 A 股相关基础技能，而不需要完整 named agent，可以安装垂直技能包：

```bash
claude plugin install china-equity-trading@claude-for-financial-services
```

## 调用 named agent

安装完成后，重启或开启一个新的 Claude Code 会话。你可以直接用自然语言要求
Claude Code 使用 `a-share-screener`：

```text
用 a-share-screener 帮我根据“机器人 + 减速器”主题生成 A 股短线研究清单，输出到 ./out/。
```

也可以显式指定 agent：

```text
调用 a-share-screener:a-share-screener，基于“机器人 + 减速器”主题生成 A 股短线研究清单。
```

Claude Code 可能显示类似输出：

```text
a-share-screener:a-share-screener(A股短线研究清单生成)
Backgrounded agent
```

这表示 named agent 已经在后台运行。可以在 Claude Code 的后台 agent 管理界面
展开查看进度或继续交互。

## named agent 和 skills 的区别

`a-share-screener` 是 agent 插件，负责组织完整工作流。插件内部包含以下
skills，Claude Code 会在相关任务中自动使用它们：

- `a-share-daily-brief`
- `a-share-topic-screen`
- `a-share-event-calendar`
- `a-share-quant-screen`
- `a-share-risk-check`

如果要手动调用 skill，必须使用上面的 skill 名称，而不是
`a-share-screener`。

## 本地调用和 Managed Agent 的区别

本地 Claude Code 调用使用 `claude plugin install` 安装插件，并在本地会话中
运行 agent 或 skills。

`scripts/deploy-managed-agent.sh a-share-screener` 是远端部署流程。它会读取
`managed-agent-cookbooks/a-share-screener/agent.yaml`，上传 skills，创建
subagents，并把 orchestrator 发布到 Anthropic Managed Agents API。这个流程
面向 API 或 workflow engine，不是 Claude Code 本地交互的必要步骤。

本地日常使用优先选择 Claude Code 插件方式；只有要把 agent 接入远端编排、
定时任务或自建工作流时，才使用 managed-agent 部署。
