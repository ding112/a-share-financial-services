# dsh 内嵌改造蓝图

本文记录把本仓库从一个 Claude Code / Codex 插件 marketplace 仓库改造为
「内嵌 DeepSeek Harness（dsh）的独立应用」的方案。目标形态已经确认：打包一
个 `fsi` profile，`dsh --profile fsi` 启动自带 GUI 的金融服务应用；六个 FSI
agent 各成为一个 dsh agent preset，在会话开始时由用户选择。

> **Note:** 这是设计蓝图，不是已完成的改造。文中标注「待实测」的位置需要在
> 落地时用 dsh 的 `cordis_inspect` 等运行时接口核对签名后再实现。

## 背景与目标

本仓库的核心资产是运行时无关的 Markdown、YAML 与 Python：

- `plugins/agent-plugins/<slug>/agents/<slug>.md`：六个 agent 的 system prompt，
  带 `name` / `description` / `tools` frontmatter。
- `plugins/vertical-plugins/<v>/skills/*/SKILL.md`：可复用 skills。
- `plugins/vertical-plugins/<v>/commands/*.md`：slash commands。
- `plugins/vertical-plugins/<v>/.mcp.json`：金融数据 MCP 配置。
- `managed-agent-cookbooks/<slug>/`：无界面部署模板（agent.yaml 与
  subagents/*.yaml 叶子 worker）。
- `scripts/*.py`：AkShare 数据抓取、校验与产出脚本。

改造的原则是「一处源、三个 wrapper」：`vertical-plugins` 与 `agents/*.md` 保持
为唯一源，现有 Claude Code、Codex 两个 wrapper 继续可用，dsh 作为第三个
wrapper 以薄适配层接入。

### 已验证的兼容性

- dsh 的 skill 就是 `<name>/SKILL.md` + kebab-case `name` / `description`
  frontmatter，与本仓库 skills 格式一致，可被 `dsh-skill-filesystem` 直接扫描。
- dsh 的 MCP 客户端（`@deepseek-ai/dsh-mcp-client`）支持 `streamable-http`
  传输，和 `.mcp.json` 中的 HTTP 服务器逐条对应；模型侧工具名形如
  `mcp__<server>__<tool>`，与 Claude Code / Codex 相同形状。
- dsh 的 agent preset 由 `agent.cordis.yml`（组合）与 `preset.yml`（元数据）
  组成，发现自用户根 `~/.dsh/.agent-presets/` 与部署配置根
  `config/agent-presets/`。

### 需要适配的部分

slash commands 是唯一需要少量运行时胶水的资产：dsh 的 commands 是程序式注册
（`ctx.commands.register`），不是 markdown 文件。需要在 `fsi-app` bundle 里写
一个薄插件，把 `commands/*.md` 的正文在运行时注入当前 agent。

## 目标架构

```
dsh 进程（fsi profile）
├─ HOST 平面（dsh-base + dsh-web-app）            / 不改动
│    agent-default-model（opencode-go），llm，session，agent-loop，
│    sandbox，approval，permission，model route，
│    skill / commands 注册表，MCP 客户端              / 都是宿主单例
│
├─ fsi-app bundle（新增）                          / 薄适配层
│    cordis.patch.yml  skill-filesystem.customSkillDirs 指向 FSI skills，
│                        insert 11 个金融 MCP rows，branding 与本地化
│    lib/index.js       注册 FSI slash commands（ctx.commands.register）
│
└─ 6 个 agent presets（拷贝到用户根）
     每个 = persona（读 agents/<slug>.md） + 工具集 + skill 根 + MCP 子集
     +（可选）delegation group（对应 cookbook 的 leaf workers）

工作区 = 本仓库本身；./out/<主题>/ 产出布局不变；scripts/*.py 仍由 bash 工具运行
```

分层职责：

- HOST 平面：模型路由、会话、sandbox、审批、注册表。预设只贡献会话级工具、
  persona 与 prompt 段落，不持有跨会话服务。
- `fsi-app` bundle：一个 npm 包，导出 `./cordis.patch.yml`（声明式行）与
  `lib/index.js`（运行时胶水），向 profile 注入 FSI 能力。
- agent presets：决定单个会话的工具集、persona、skill 根与 MCP 子集，实现
  「每个 agent 一套护栏」。

## 新增目录结构

```
dsh/
├─ fsi-app/                          # 适配 bundle（一个 npm 包）
│   ├─ package.json                  # exports ./cordis.patch.yml
│   ├─ cordis.patch.yml              # skill 根 + MCP rows + branding
│   └─ lib/index.js                  # 注册 FSI slash commands
├─ presets/                          # 六个 FSI agent 预设源文件
│   └─ a-share-market-researcher/
│       ├─ agent.cordis.yml
│       └─ preset.yml
├─ profile.install.sh                # 建 fsi profile 并装 bundle
└─ presets.install.sh                # 拷贝预设到 ~/.dsh/.agent-presets/
scripts/
├─ install_dsh.py                    # 上述二者的幂等安装器（可选替代）
└─ sync_dsh_skills.py                # 多 skill 根下的同名去重校验
docs/dsh-embedding.md                # 本文档
```

现有 `plugins/`、`managed-agent-cookbooks/`、`scripts/*.py`、`AGENTS.md`、
`CLAUDE.md` 一律不动。

## 落地步骤

### 1. 创建 fsi profile

先初始化 `~/.dsh/profiles/fsi/` 并安装 bundle 依赖。`dsh plugin` 首次使用时
会自动创建 profile 目录：

```bash
dsh plugin --profile fsi add \
  @deepseek-ai/dsh-base \
  @deepseek-ai/dsh-web-app \
  @linxin666/dsh-web-ui-all \
  ./dsh/fsi-app        # 本仓库本地包（pnpm 支持 path 依赖）
```

确认 `~/.dsh/profiles/fsi/package.json` 中 `dsh.profile.bundles` 的顺序为
`dsh-base` → `dsh-web-app` → `dsh-web-ui-all` → `fsi-app`。越靠后越优先，
`fsi-app` 的 override 最后生效。

启动时的工作目录即仓库根目录，`{{cwd}}` 与 skill 路径都基于它。

### 2. 构建 fsi-app 适配 bundle

#### skill 根

在 `dsh/fsi-app/cordis.patch.yml` 中覆盖 `skill-filesystem` 行，把
`customSkillDirs` 指向各 vertical 与 agent 的 skills 目录：

```yaml
- id: skill-filesystem
  config:
    providerName: fsi-skills
    includeDefaultRoots: true            # 保留 .dsh/skills 与用户根，通用 skills 仍可用
    customSkillDirs:
      # vertical-plugins 是唯一源；agent skills 仅用于未能进入 vertical 的特例
      - !!js process.cwd() + '/plugins/vertical-plugins/equity-research/skills'
      - !!js process.cwd() + '/plugins/vertical-plugins/financial-analysis/skills'
      - !!js process.cwd() + '/plugins/vertical-plugins/china-equity-trading/skills'
      - !!js process.cwd() + '/plugins/vertical-plugins/investment-banking/skills'
      - !!js process.cwd() + '/plugins/agent-plugins/a-share-market-researcher/skills'
      - !!js process.cwd() + '/plugins/agent-plugins/a-share-screener/skills'
```

#### 金融数据 MCP

逐个插入 `@deepseek-ai/dsh-mcp-client` row，配置来自
`plugins/vertical-plugins/<v>/.mcp.json`：

```yaml
- insert:
    - id: mcp-daloopa
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: daloopa
        transport: streamable-http
        url: https://mcp.daloopa.com/server/mcp
    - id: mcp-factset
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: factset
        transport: streamable-http
        url: https://mcp.factset.com/mcp
    # ...morningstar / sp-global / moodys / mtnewswire / aiera / lseg
    # ...pitchbook / chronograph / egnyte
```

`failOnStartupError` 保持默认 `false`，单家 MCP 不可用不影响其余。带鉴权的
服务器把 token 放进 `headers`（用 `!!js` 表达式读环境变量），对应 cookbook 中
`${CAPIQ_MCP_URL}` 等环境变量继续沿用。

#### 品牌与本地化

覆盖 web 层的默认 persona 与语言：

```yaml
- id: system-prompt
  config:
    persona: >-
      你是金融服务研究助手，运行于 DeepSeek Harness。当前工作目录 {{cwd}}。
      所有输出遵守 AGENTS.md 与所在 agent 的护栏。
- id: locale
  config: { preference: zh }
```

皮肤通过 `~/.dsh/cordis.patch.yml` 的 `ui-skin-*` 开关选择。

#### slash commands 桥

在 `dsh/fsi-app/lib/index.js` 里写一个 Cordis 插件，把
`plugins/vertical-plugins/<v>/commands/*.md` 的正文注册成 dsh commands：

```js
// dsh/fsi-app/lib/index.js —— 结构示意，实际签名以运行时实测为准
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'

const FSI_COMMANDS = [
  { name: 'sector',       file: 'plugins/vertical-plugins/equity-research/commands/sector.md' },
  { name: 'thesis',       file: 'plugins/vertical-plugins/equity-research/commands/thesis.md' },
  { name: 'earnings',     file: 'plugins/vertical-plugins/equity-research/commands/earnings.md' },
  { name: 'morning-note', file: 'plugins/vertical-plugins/equity-research/commands/morning-note.md' },
]

export function apply(ctx) {
  const commands = ctx.get('commands')
  if (!commands) return                        // 无 UI 适配器时静默跳过
  const root = process.cwd()
  for (const item of FSI_COMMANDS) {
    commands.register({
      name: item.name,
      description: `FSI 斜杠命令 /${item.name}（源自 ${item.file}）`,
      async execute(agent, line) {
        const raw = await readFile(join(root, item.file), 'utf8')
        const body = raw.replace(/^---[\s\S]*?---\s*/, '')   // 剥离 Claude frontmatter
        // 把命令正文与用户输入作为一条指令提交给当前 agent
        agent.submit({ role: 'user', text: `${body}\n\n${line ?? ''}` })
        return { kind: 'success', text: `/${item.name} 已注入` }
      },
    })
  }
}
```

> **Warning:** `agent.submit` 仅为示意。落地前必须用 `cordis_inspect` 查询当前
> `commands` 注册表与 agent 接口的真实签名，不要按这里的写法臆测 API。

### 3. 把 FSI agents 映射为 dsh presets

从 `standard` 预设拷贝并修剪，一个 agent 一份。以
`a-share-market-researcher` 为模板：

`dsh/presets/a-share-market-researcher/preset.yml`：

```yaml
name: A股行业研究
description: 生成 A 股行业 / 主题研究笔记——概览、竞争格局、可比公司表、想法清单与中文 note
```

`dsh/presets/a-share-market-researcher/agent.cordis.yml`（裁剪后的组合）：

```yaml
# ── identity：persona 文本取自已存在的 agents/<slug>.md 正文（去掉 frontmatter） ──
- id: persona
  name: '@deepseek-ai/dsh-persona'
  config:
    text: >-
      你是 A-share Market Researcher……（正文来自
      plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md）
- id: agent-instructions
  name: '@deepseek-ai/dsh-agent-instructions'   # 自动加载 AGENTS.md / CLAUDE.md

# ── shell / fs（对应 frontmatter 的 tools: Read, Write, Edit, Bash） ──────────
- id: tool-bash                  # Bash：运行 scripts/*.py 与 validate 脚本
  name: '@deepseek-ai/dsh-tool-bash'
- id: tool-fs                    # Read / Write
  name: '@deepseek-ai/dsh-tool-fs'
- id: tool-fs-search             # Grep / Glob
  name: '@deepseek-ai/dsh-tool-fs-search'
- id: tool-str-replace-editor    # Edit：写 note 所需
  name: '@deepseek-ai/dsh-tool-str-replace-editor'
- id: tool-jobs
  name: '@deepseek-ai/dsh-tool-jobs'

# ── skills：只挂本 agent 用到的 skill 根 ────────────────────────────────────
- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  config:
    providerName: fsi-a-share
    includeDefaultRoots: false
    customSkillDirs:
      - !!js process.cwd() + '/plugins/agent-plugins/a-share-market-researcher/skills'
- id: tool-skill
  name: '@deepseek-ai/dsh-tool-skill'

# ── compaction（推荐保留，与 standard 一致） ────────────────────────────────
- id: compaction
  name: cordis:group
  group: true
  isolate: { compaction: true, toolResultPruner: true }
  config:
    - { id: compaction-basic,       name: '@deepseek-ai/dsh-compaction-basic' }
    - { id: command-compact,        name: '@deepseek-ai/dsh-command-compact' }
    - { id: tool-result-pruner,     name: '@deepseek-ai/dsh-compaction-tool-result-pruner',
        config: { thresholdChars: 8192, headChars: 4096, tailChars: 1024 } }

# ── delegation（仅在有 cookbook subagents 的 agent 上加） ────────────────────
# - id: delegation
#   name: cordis:group
#   group: true
#   isolate: { workflowEngine: true }
#   config:
#     - { id: tool-subagent, name: '@deepseek-ai/dsh-tool-subagent',
#         config: { provider: spawn, toolName: subagent, backgroundMode: continuable } }
#     - { id: workflow-worker-thread, name: '@deepseek-ai/dsh-workflow-worker-thread',
#         config: { provider: spawn } }
#     - { id: tool-workflow, name: '@deepseek-ai/dsh-tool-workflow' }
```

工具闸门与 cookbook 对齐：只读叶子 worker（例如 `auditor`、`sector-reader`）
对应的预设去掉 `tool-str-replace-editor`；带 `mcp_toolset` 的 agent（
`model-builder` → capiq / daloopa，`market-researcher` → capiq / factset）在
预设里追加对应的 `mcp-*` rows。

> **Note:** 发布服务（publish 一个 service）的行必须放进带 `isolate` realm 的
> group。预设里若注册了会 publish service 的行，第二条会话挂载同名 preset 会
> 冲突，挂载校验会直接拒绝。拿不准某一行是否 publish service 时，用
> `cordis_inspect what:"services"` 看它的归属 fiber。

### 4. 接入 skills 并去重

`dsh-skill-filesystem` 直接扫描 `<name>/SKILL.md`，因此 FSI skills 无需改写。

唯一风险是跨根同名 skill 冲突。`scripts/sync_dsh_skills.py` 负责：遍历所有
`customSkillDirs`，报告重复的 `name`，只保留 `vertical-plugins` 为权威源；
确有必要的 a-share 特例 skill 统一加前缀。此检查纳入 `scripts/check.py`。

### 5. 接入 MCP

见步骤 2 的 MCP 段。Codex marketplace 第一版对 vertical skill 包的限定不适用
于 dsh 侧：可放开全部 MCP，由各预设按需启用或禁用。

### 6. 接入 subagent 与 workflow

`managed-agent-cookbooks/<slug>/subagents/*.yaml` 的叶子 worker 映射为该
agent 预设 `delegation` group 里的 `tool-subagent` / `tool-workflow`
（spawn provider）。编排逻辑仍由 agent system prompt 驱动。
`a-share-screener` 有四个叶子 worker，用 `tool-workflow` 一次性 fan-out 最自然。

### 7. 复用工作区、脚本与护栏

- `./out/<中文主题>/` 产出布局与 `scripts/validate_a_share_output_layout.py`
  原样保留，由 bash 工具调用。
- `.venv` 与 `requirements.txt` 的准备流程不变，`tool-bash` 统一使用
  `.venv/bin/python`。
- `AGENTS.md` / `CLAUDE.md` 由 `dsh-agent-instructions` 自动注入，护栏天然生效。

### 8. 编写安装与校验脚本

`dsh/profile.install.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail
dsh plugin --profile fsi add @deepseek-ai/dsh-base @deepseek-ai/dsh-web-app \
  @linxin666/dsh-web-ui-all ./dsh/fsi-app
# 校正 bundles 顺序（示例用 node 改写 package.json，落地时以实际结构为准）
node -e "const h=require('os').homedir();const p=require(h+'/.dsh/profiles/fsi/package.json');\
p.dsh.profile.bundles=['@deepseek-ai/dsh-base','@deepseek-ai/dsh-web-app',\
'@linxin666/dsh-web-ui-all','./dsh/fsi-app'];\
require('fs').writeFileSync(h+'/.dsh/profiles/fsi/package.json',JSON.stringify(p,null,2))"
dsh --profile fsi --dump-config | head -40   # 校验合成树
```

`dsh/install-presets.sh`（通用 preset 安装器，仓库内实现的脚本；蓝图曾设想为
`presets.install.sh`，落地名以此为准）：

```bash
bash dsh/install-presets.sh            # 安装全部 6 个 FSI agent preset
bash dsh/install-presets.sh <slug>     # 只安装某一个
```

脚本会校验凭据（`DEEPSEEK_API_KEY` 或 `~/.dsh/.credentials.yaml`）→ 把
`dsh/presets/<slug>/` 拷到 `~/.dsh/.agent-presets/<slug>/` → 用 `dsh/persona.py`
把 `plugins/agent-plugins/<slug>/agents/<slug>.md` 去 frontmatter 后的正文注入
`agent.cordis.yml` 的 `__PERSONA_TEXT__` 占位符。`install-mvp.sh` 是它的向后兼容
包装（等价于只装 a-share）。

`scripts/check.py` 已增加 `check_dsh_presets()`：校验 `dsh/presets/<slug>/` 与
`plugins/agent-plugins/<slug>/` 一一对应、`agent.cordis.yml` 保留
`__PERSONA_TEXT__` 占位符、`customSkillDirs` 指向的 bundled skills 根存在、
`preset.yml` 可解析——防止 preset 与 persona 源漂移。

## 启动与验证

按顺序执行：

```bash
# 1. 安装 Python 依赖（一次性）
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

# 2. 建 profile 并安装预设
bash dsh/profile.install.sh && bash dsh/install-presets.sh

# 3. 启动 GUI
dsh --profile fsi
# 预设选择器应出现六个 FSI agent，例如「A股行业研究」「A股短线筛选」
```

验证清单：

- 预设选择器列全六个 FSI agent。
- skill 目录包含 `a-share-data-sources` 等 FSI skills。
- `/sector` 等 slash commands 可触发。
- MCP 工具出现在模型工具表中，形如 `mcp__daloopa__*`，且能连通。
- 用 `fixtures/` 下的 A 股数据包跑通 README 中的 case，产物写入
  `./out/机器人产业链/note/`。
- `python3 scripts/check.py` 全绿，包含新增的 dsh 同步检查。

## 范围、风险与边界

- **不动唯一源**：`plugins/vertical-plugins/` 的 skills、
  `agents/<slug>.md`、`scripts/*.py`、`AGENTS.md` 全部保留，Claude Code 与
  Codex 两个 wrapper 继续可用。
- **新增代码量小**：`fsi-app/cordis.patch.yml`（声明式，主体）、
  `fsi-app/lib/index.js`（slash 命令桥，几十行）、六个预设（从 standard 拷贝
  修剪）、两个安装脚本。没有对 FSI 知识资产的重写。
- **MCP 凭证**：带鉴权的服务器配 `headers`，token 从环境变量读取。
- **命令 API 待实测**：`agent.submit` 是示意，落地时用 `cordis_inspect` 核对
  `commands` 注册表与 agent 的真实签名。
- **模型路由是 HOST 平面**：沿用 `~/.dsh/settings.yaml` 的
  `agent-default-model`。某个 agent 要固定模型时，在 host 层分 agent 配置或
  会话内选择，不要塞进预设。
- **预设分发方式**：预设发现自 `~/.dsh/.agent-presets/`（用户根）与部署
  `config/agent-presets/`。「预设随 profile bundle 分发」未在已读文档中证实，
  因此采用「仓库存源 + 安装脚本拷贝到用户根」的确认可用方式。

## 下一步

- 把本蓝图拆成实施任务，落盘到 `.scratch/` 的 issue 跟踪。
- 首先搭建 `dsh/fsi-app` 骨架与 `fsi` profile，用 `--dump-config` 做第一次合成
  校验。
- 然后用 `cordis_inspect` 核对 commands / agent 签名，再写 slash 命令桥。
- 最后复制标准预设生成六个 FSI 预设，跑通 README 的 A 股 case 作为端到端验收。